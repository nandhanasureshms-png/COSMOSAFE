
import re


def extract_ingredient_candidates(ocr_text: str) -> dict:
    """
    Extract candidate ingredients from OCR text.
    OCR results must be reviewed before toxicity screening.
    """
    if not ocr_text or not ocr_text.strip():
        return {
            "status": "needs_review",
            "ingredients": [],
            "message": "No OCR text was provided.",
        }

    match = re.search(
        r"\b(?:ingredients?|gredients?|ngredients?)\b\s*:?\s*(.*)",
        ocr_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return {
            "status": "needs_review",
            "ingredients": [],
            "message": "Ingredient heading not found in OCR text.",
        }

    section = match.group(1)

    # Stop at common headings following the ingredient list.
    section = re.split(
        r"\b(directions for use|how to use|warning|caution|storage)\s*:?",
        section,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    # Replace line breaks with spaces.
    section = re.sub(r"[\r\n]+", " ", section)

    ingredients = [
        item.strip(" \t.,;:|\"'()")
        for item in section.split(",")
    ]

    ingredients = [
        item for item in ingredients
        if item and len(item) <= 100
    ]

    return {
        "status": "needs_review",
        "ingredients": ingredients,
        "message": (
            "Candidates extracted. Verify names and list completeness "
            "before chemical mapping or toxicity screening."
        ),
    }


if __name__ == "__main__":
    test_cases = [
        (
            "Standard heading",
            "INGREDIENTS: Aqua, Glycerin, Niacinamide",
        ),
        (
            "Heading without colon",
            "Ingredients Aqua, Glycerin, Niacinamide",
        ),
        (
            "Missing heading",
            "Aqua, Glycerin, Niacinamide",
        ),
        (
            "Ingredient list followed by warning",
            "Ingredients: Aqua, Glycerin, Niacinamide. Warning: "
            "Avoid contact with eyes.",
        ),
    ]

    for name, sample in test_cases:
        result = extract_ingredient_candidates(sample)
        print(f"\nTest: {name}")
        print("Status:", result["status"])
        print("Candidates:", result["ingredients"])
        print("Message:", result["message"])
