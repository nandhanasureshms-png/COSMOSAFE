
import sys
import json
import argparse
from pathlib import Path

# Ensure the src directory is available for imports.
SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from normalization.ingredient_normalizer import normalize_ingredient_name
from ocr.label_pipeline import process_label
from chemical_identity.pubchem_mapper import map_ingredient_to_chemical
from chemical_identity.ingredient_pipeline import (
    process_ingredient,
    print_pipeline_result,
)
from chemical_identity.identity_reviewer import (
    generate_identity_review_registry,
    save_identity_review_registry,
)
from integration.structured_report import build_structured_report


def screen_reviewed_ingredients(
    ingredients: list[str],
) -> list[dict]:
    """
    Process the corrected ingredient list without repeated prompts.

    Preserves every original ingredient entry and its original position.
    Blank, invalid, or duplicated entries are retained and recorded.
    Uncertain or missing mappings are recorded and skipped for QSAR.
    Only mappings that pass the existing configured eligibility
    checks are passed to the ingredient pipeline.

    Note: configured identity flags are not independent scientific
    validation. Validate curated mappings against reliable sources.
    """
    results = []

    for idx, ingredient in enumerate(ingredients):
        if ingredient is None:
            raw_name = ""
        else:
            raw_name = str(ingredient).strip()

        print(f"\nProcessing ingredient {idx + 1}/{len(ingredients)}: '{raw_name}'")

        if not raw_name:
            # Preserve blank/empty entry at its original position
            result = process_ingredient(raw_name)
            results.append(result)
            continue

        try:
            mapping = map_ingredient_to_chemical(raw_name)
        except Exception as exc:
            print(f"Mapping failed for {raw_name}: {exc}")
            mapping = {
                "ingredient_name": raw_name,
                "normalized_name": normalize_ingredient_name(raw_name),
                "status": "api_error",
                "message": f"Mapping exception: {exc}",
                "identity_verified": False,
                "needs_manual_review": True,
                "candidate_pubchem_cids": [],
            }

        automated_match = (
            mapping.get("status") in ("mapped", "verified")
            and mapping.get("identity_verified") is True
            and mapping.get("needs_manual_review") is False
            and bool(mapping.get("pubchem_cid"))
            and bool(mapping.get("connectivity_smiles"))
        )

        if not automated_match:
            print(
                "Identity uncertain or unavailable; "
                "QSAR will not run."
            )
            print("Mapping status:", mapping.get("status"))

            result = process_ingredient(
                raw_name,
                approved_mapping=mapping,
            )
            results.append(result)
            continue

        print("Configured curated mapping found.")
        print("PubChem CID:", mapping.get("pubchem_cid"))
        print(
            "Note: verify curated identity records independently "
            "before treating them as scientifically confirmed."
        )

        try:
            result = process_ingredient(
                raw_name,
                approved_mapping=mapping,
            )
            results.append(result)

        except Exception as exc:
            print(f"Ingredient processing failed for {raw_name}: {exc}")

            results.append({
                "raw_ingredient": raw_name,
                "normalized_ingredient": (
                    mapping.get("normalized_name")
                    or normalize_ingredient_name(raw_name)
                ),
                "mapping_result": mapping,
                "toxicity_result": {
                    "status": "prediction_failed",
                    "message": (
                        "Ingredient processing failed. "
                        f"Details: {exc}"
                    ),
                    "screening_eligible": True,
                },
            })

    return results


def parse_reviewed_list(text: str) -> list[str]:
    """Clean and validate the user-corrected ingredient list without dropping duplicates."""
    ingredients = []

    for line in text.splitlines():
        name = line.strip().strip(",;").strip()

        if not name:
            continue

        # Do not drop duplicate entries; preserve every user entry
        ingredients.append(name)

    if len(ingredients) < 2:
        print("Please provide at least two ingredients.")
        return []

    if len(ingredients) > 100:
        print("Too many ingredients. Please check the list.")
        return []

    return ingredients


def save_structured_report(report: dict, output_path: Path = None) -> Path:
    """Save the structured toxicity report as JSON."""
    if output_path is None:
        project_root = Path(__file__).resolve().parents[2]
        output_path = project_root / "data" / "toxicity_report.json"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    return output_path


def main() -> None:
    """Run OCR, confirm ingredients, screen, and save the report."""
    parser = argparse.ArgumentParser(description="CosmoSafe Reviewed Label Pipeline")
    parser.add_argument("--image", type=str, default=None, help="Path to cosmetic label image")
    parser.add_argument("--batch", action="store_true", help="Run batch processing non-interactively using OCR ingredients")
    parser.add_argument("--output", type=str, default=None, help="Path to output structured report JSON")
    parser.add_argument("--review-output", type=str, default=None, help="Path to output identity review registry JSON")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    report_path = Path(args.output) if args.output else project_root / "data" / "toxicity_report.json"
    review_path = Path(args.review_output) if args.review_output else project_root / "reports" / "toxicity" / "ingredient_identity_review.json"

    # Batch non-interactive mode
    if args.batch and args.image:
        image_path = args.image.strip().strip('"').strip("'")
        print(f"Running CosmoSafe in batch mode for image: {image_path}")

        label_result = process_label(image_path)
        print("\n=== OCR RESULT ===")
        print("Status:", label_result.get("status"))
        print("Message:", label_result.get("message"))

        if label_result.get("status") == "error":
            print(f"Could not process image: {label_result.get('message')}")
            return

        candidates = label_result.get("ingredients", [])
        print(f"Extracted {len(candidates)} raw OCR ingredients from label.")

        print("\n=== CHEMICAL MAPPING AND QSAR SCREENING ===")
        results = screen_reviewed_ingredients(candidates)

        report = build_structured_report(results)
        save_structured_report(report, report_path)

        registry = generate_identity_review_registry(report["results"])
        save_identity_review_registry(registry, review_path)

        print("\n=== STRUCTURED REPORT SUMMARY ===")
        print(json.dumps(report.get("summary", {}), indent=2))
        print("Pipeline status:", report.get("pipeline_status", "unknown"))
        print("Report saved to:", report_path)
        print("Identity review registry saved to:", review_path)
        return

    # Interactive mode
    if args.image:
        image_path = args.image.strip().strip('"').strip("'")
    else:
        image_path = input(
            "Enter the cosmetic label image path: "
        ).strip().strip('"').strip("'")

    if not image_path:
        print("No image path provided. Screening cancelled.")
        return

    label_result = process_label(image_path)

    print("\n=== OCR RESULT ===")
    print("Status:", label_result.get("status"))
    print("Message:", label_result.get("message"))

    if label_result.get("status") == "error":
        print("Could not process this image.")
        return

    print("\n=== ORIGINAL OCR TEXT ===")
    print(label_result.get("ocr_text", ""))

    candidates = label_result.get("ingredients", [])
    initial_text = "\n".join(str(item) for item in candidates)

    print("\n=== CURRENT INGREDIENT LIST ===")
    print(initial_text or "(empty)")

    print("\nCorrect the ingredient list.")
    print("Enter one ingredient per line.")
    print("Press Enter on an empty line when finished.")
    print("If OCR is wrong, enter the complete corrected list.")

    entered_lines = []

    while True:
        try:
            line = input()
        except EOFError:
            break

        if not line.strip():
            break

        entered_lines.append(line)

    edited_text = "\n".join(entered_lines)

    source_text = (
        edited_text if edited_text.strip() else initial_text
    )

    reviewed_ingredients = parse_reviewed_list(source_text)

    if not reviewed_ingredients:
        print("No valid ingredient list. Screening cancelled.")
        return

    print("\n=== FINAL INGREDIENT LIST ===")

    for index, ingredient in enumerate(
        reviewed_ingredients, start=1
    ):
        print(f"{index}. {ingredient}")

    confirmation = input(
        "\nType YES to confirm this complete ingredient list: "
    ).strip().upper()

    if confirmation != "YES":
        print("Confirmation not received. Screening cancelled.")
        return

    print("\n=== CHEMICAL MAPPING AND QSAR SCREENING ===")

    results = screen_reviewed_ingredients(reviewed_ingredients)

    print("\n=== INGREDIENT RESULTS ===")

    for result in results:
        print_pipeline_result(result)

    report = build_structured_report(results)
    save_structured_report(report, report_path)

    registry = generate_identity_review_registry(report["results"])
    save_identity_review_registry(registry, review_path)

    print("\n=== STRUCTURED REPORT SUMMARY ===")
    print(json.dumps(report.get("summary", {}), indent=2))
    print("Pipeline status:", report.get("pipeline_status", "unknown"))
    print("Report saved to:", report_path)
    print("Identity review registry saved to:", review_path)


if __name__ == "__main__":
    main()
