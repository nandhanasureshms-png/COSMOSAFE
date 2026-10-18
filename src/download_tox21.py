from pathlib import Path
import requests

# Project root
BASE_DIR = Path(__file__).resolve().parents[1]

# Where the dataset will be saved
OUTPUT_PATH = BASE_DIR / "data" / "raw" / "tox21.csv.gz"

# Official DeepChem dataset URL
URL = "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/tox21.csv.gz"


def download_file():
    print("Downloading Tox21 dataset...")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(URL, stream=True)
    response.raise_for_status()

    with open(OUTPUT_PATH, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    print("Download complete!")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.2f} KB")


if __name__ == "__main__":
    download_file()