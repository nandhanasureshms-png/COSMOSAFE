
import argparse
from pathlib import Path

from ocr.text_extractor import extract_text_from_image
from ocr.ingredient_extractor import extract_ingredient_candidates


def process_label(image_path: str) -> dict:
    """Read a label image and extract ingredient candidates."""
    ocr_result = extract_text_from_image(image_path)

    if ocr_result["status"] != "success":
        return {
            "status": "error",
            "ocr_text": "",
            "ingredients": [],
            "message": ocr_result["message"],
        }

    ingredient_result = extract_ingredient_candidates(
        ocr_result["text"]
    )

    return {
        "status": ingredient_result["status"],
        "ocr_text": ocr_result["text"],
        "ingredients": ingredient_result["ingredients"],
        "message": ingredient_result["message"],
    }



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract ingredients from a cosmetic label image."
    )
    parser.add_argument(
        "image_path",
        help="Path to the cosmetic label image (JPG or PNG).",
    )
    args = parser.parse_args()

    result = process_label(args.image_path)

    print("Status:", result["status"])
    print("\nIngredient candidates:")

    for ingredient in result["ingredients"]:
        print("-", ingredient)

    print("\nReview required before screening.")
    print("Message:", result["message"])
