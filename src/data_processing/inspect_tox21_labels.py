
from pathlib import Path
import sys
import pandas as pd

# Make the src folder importable
BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_processing.tox21_loader import (
    get_tox21_dataset,
    TOX21_ENDPOINTS,
)
from toxicity_engine.chemical_standardizer import canonicalize_smiles


def inspect_tox21_labels():
    df = get_tox21_dataset()

    print("\n" + "=" * 70)
    print("TOX21 LABEL QUALITY REPORT")
    print("=" * 70)

    for endpoint in TOX21_ENDPOINTS:
        labels = pd.to_numeric(df[endpoint], errors="coerce")

        positive = int((labels == 1).sum())
        negative = int((labels == 0).sum())
        missing = int(labels.isna().sum())
        other = int((labels.notna() & ~labels.isin([0, 1])).sum())

        print(f"\nEndpoint: {endpoint}")
        print(f"  Positive (1): {positive}")
        print(f"  Negative (0): {negative}")
        print(f"  Missing:      {missing}")
        print(f"  Other values: {other}")

    print("\n" + "-" * 70)
    print("CHEMICAL STRUCTURE CHECK")
    print("-" * 70)

    valid_smiles = df["smiles"].dropna().astype(str).str.strip()
    canonical = valid_smiles.apply(canonicalize_smiles)

    print(f"Rows in dataset: {len(df)}")
    print(f"Missing SMILES: {int(df['smiles'].isna().sum())}")
    print(f"Valid standardized structures: {int(canonical.notna().sum())}")
    print(f"Invalid structures: {int(canonical.isna().sum())}")
    print(
        "Rows with repeated canonical structures:",
        int(canonical[canonical.notna()].duplicated().sum()),
    )

    print("\nInspection complete. No dataset files were modified.")


if __name__ == "__main__":
    inspect_tox21_labels()
