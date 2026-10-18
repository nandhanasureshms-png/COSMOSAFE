
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps


# Location of the installed Tesseract OCR engine.
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_text_from_image(image_path: str) -> dict:
    """
    Extract text from a cosmetic label image.

    Returns the extracted text and processing status.
    """
    path = Path(image_path)

    if not path.is_file():
        return {
            "status": "error",
            "text": "",
            "message": f"Image file not found: {path}",
        }

    try:
        
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")

            # Enlarge small text to help OCR.
            image = image.resize(
                (image.width * 2, image.height * 2),
                Image.Resampling.LANCZOS,
            )

            # Improve contrast and sharpen the text.
            image = ImageOps.grayscale(image)
            image = ImageOps.autocontrast(image)
            image = image.filter(ImageFilter.SHARPEN)

            extracted_text = pytesseract.image_to_string(
                image,
                config="--oem 3 --psm 6",
            )

        return {
            "status": "success",
            "text": extracted_text.strip(),
            "message": "Text extraction completed.",
        }

    except Exception as exc:
        return {
            "status": "error",
            "text": "",
            "message": str(exc),
        }



if __name__ == "__main__":
    image_path = "data/test_label.jpg"

    result = extract_text_from_image(image_path)

    print("Status:", result["status"])
    print("Extracted text:")
    print(result["text"])
    print("Message:", result["message"])
