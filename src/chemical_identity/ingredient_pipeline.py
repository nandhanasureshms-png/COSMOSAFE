import sys
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone

SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from normalization.ingredient_normalizer import normalize_ingredient_name
from chemical_identity.pubchem_mapper import map_ingredient_to_chemical
from toxicity_engine.qsar_predictor import predict_nr_ar

try:
    from rdkit import Chem
except ImportError:
    Chem = None


def process_ingredient(
    raw_ingredient,
    approved_mapping=None,
    identity_review=None
):
    """
    Map an ingredient and optionally run NR-AR QSAR.

    Human-reviewed mappings require identity_review evidence.
    Automated mappings are eligible only when the mapper explicitly marks
    them as mapped and identity_verified. RDKit structure checks still apply.

    A successful prediction is not a general safety determination.
    """

    normalized = normalize_ingredient_name(raw_ingredient)

    if not normalized:
        return {
            "raw_ingredient": raw_ingredient,
            "normalized_ingredient": None,
            "mapping_result": {
                "ingredient_name": raw_ingredient,
                "normalized_name": None,
                "status": "invalid_input",
                "message": "Ingredient could not be normalized.",
                "identity_verified": False,
                "needs_manual_review": False,
                "candidate_pubchem_cids": [],
            },
            "toxicity_result": {
                "status": "not_run",
                "message": "Invalid ingredient input.",
                "screening_eligible": False,
            }
        }

    if approved_mapping is not None:
        mapping = deepcopy(approved_mapping)
    else:
        mapping = map_ingredient_to_chemical(raw_ingredient)

    toxicity = {
        "status": "not_run",
        "message": "A validated chemical identity is required.",
        "screening_eligible": False,
    }

    has_structure = bool(
        mapping.get("pubchem_cid")
        and mapping.get("connectivity_smiles")
    )

    # Explicit human review path.
    human_reviewed = (
        approved_mapping is not None
        and isinstance(identity_review, dict)
        and bool(identity_review.get("reviewed_at"))
        and bool(identity_review.get("evidence_note"))
        and has_structure
    )

    # Automated path: the mapper must explicitly flag a curated match.
    # This flag is trustworthy only if the curated mapping table has
    # been independently checked against reliable chemical references.
    automated_match = (
        mapping.get("status") in ("mapped", "verified")
        and mapping.get("identity_verified") is True
        and mapping.get("needs_manual_review") is False
        and has_structure
    )

    eligible = human_reviewed or automated_match

    if not eligible:
        toxicity["message"] = (
            "Prediction not run: identity is unverified, ambiguous, "
            "or lacks sufficient mapping evidence."
        )
        toxicity["screening_eligible"] = False

    elif Chem is None:
        toxicity["message"] = (
            "Prediction not run: RDKit is unavailable. "
            "Install RDKit in the active virtual environment."
        )
        toxicity["screening_eligible"] = False

    else:
        smiles = mapping["connectivity_smiles"]

        try:
            mol = Chem.MolFromSmiles(smiles)
        except Exception:
            mol = None

        if mol is None:
            toxicity["message"] = (
                "The SMILES could not be parsed by RDKit."
            )
            toxicity["structure_error"] = "invalid_smiles"
            toxicity["screening_eligible"] = False

        elif len(Chem.GetMolFrags(mol)) != 1:
            toxicity["message"] = (
                "Multiple molecular components detected; additional "
                "identity review is required."
            )
            toxicity["structure_error"] = "multi_component"
            toxicity["screening_eligible"] = False

        else:
            mapping["structure_validation"] = {
                "rdkit_parse_success": True,
                "single_component": True
            }

            if human_reviewed:
                mapping["identity_review"] = {
                    "reviewed_at": identity_review["reviewed_at"],
                    "reviewer": identity_review.get(
                        "reviewer", "local_user"
                    ),
                    "evidence_note": identity_review["evidence_note"],
                    "pubchem_cid": mapping["pubchem_cid"],
                    "connectivity_smiles": smiles
                }

            try:
                prediction = predict_nr_ar(smiles)

                if prediction.get("success"):
                    toxicity = {
                        "status": "completed",
                        "message": (
                            "NR-AR assay activity prediction completed. "
                            "This does not establish overall ingredient "
                            "or product safety."
                        ),
                        "screening_eligible": True,
                        "prediction": prediction
                    }
                else:
                    toxicity = {
                        "status": "prediction_failed",
                        "message": prediction.get(
                            "error", "QSAR prediction failed."
                        ),
                        "screening_eligible": True,
                        "prediction": prediction
                    }

            except Exception as error:
                toxicity = {
                    "status": "prediction_failed",
                    "message": str(error),
                    "screening_eligible": True,
                }

    return {
        "raw_ingredient": raw_ingredient,
        "normalized_ingredient": normalized,
        "mapping_result": mapping,
        "toxicity_result": toxicity
    }


def print_pipeline_result(result):
    print("\n" + "=" * 60)
    print("COSMOSAFE INGREDIENT PIPELINE RESULT")
    print("=" * 60)

    print("Raw ingredient:", result.get("raw_ingredient"))
    print("Normalized:", result.get("normalized_ingredient"))

    mapping = result.get("mapping_result", {})

    print("\nCHEMICAL MAPPING")
    print("Status:", mapping.get("status"))
    print("Message:", mapping.get("message"))
    print("PubChem CID:", mapping.get("pubchem_cid"))
    print("Formula:", mapping.get("molecular_formula"))
    print("Identity verified:", mapping.get("identity_verified"))

    toxicity = result.get("toxicity_result", {})

    print("\nNR-AR SCREENING")
    print("Status:", toxicity.get("status"))
    print("Message:", toxicity.get("message"))

    prediction = toxicity.get("prediction")

    if prediction:
        print(
            "Predicted activity:",
            prediction.get("predicted_activity")
        )
        print(
            "Activity probability:",
            prediction.get("activity_probability")
        )
        print(
            "Maximum reference similarity:",
            prediction.get("maximum_reference_similarity")
        )
        print("Applicability:", prediction.get("applicability"))
        print("Interpretation:", prediction.get("interpretation"))

        for item in prediction.get("limitations", []):
            print("-", item)


if __name__ == "__main__":
    ingredients = [
        "Aqua",
        "Octocrylene",
        "Niacinamide",
        "Glycerin",
        "Fragrance",
        "Aloe Vera Extract",
        "random_fake_chemical"
    ]

    for ingredient in ingredients:
        result = process_ingredient(ingredient)
        print_pipeline_result(result)