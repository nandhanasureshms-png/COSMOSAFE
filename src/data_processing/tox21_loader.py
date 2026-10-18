from pathlib import Path
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = (
    BASE_DIR
    / "data"
    / "raw"
    / "tox21.csv.gz"
)


# ============================================================
# TOX21 ENDPOINTS
# ============================================================

TOX21_ENDPOINTS = [

    # Nuclear receptor pathways
    "NR-AR",
    "NR-AR-LBD",
    "NR-AhR",
    "NR-Aromatase",
    "NR-ER",
    "NR-ER-LBD",
    "NR-PPAR-gamma",

    # Stress response pathways
    "SR-ARE",
    "SR-ATAD5",
    "SR-HSE",
    "SR-MMP",
    "SR-p53"
]


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "mol_id",
    "smiles"
] + TOX21_ENDPOINTS


# ============================================================
# LOAD RAW DATASET
# ============================================================

def load_raw_tox21():
    """
    Load the raw Tox21 dataset from disk.
    """

    if not RAW_DATA_PATH.exists():

        raise FileNotFoundError(
            f"\nTox21 dataset not found.\n"
            f"Expected location:\n{RAW_DATA_PATH}"
        )

    print("\nLoading raw Tox21 dataset...")

    df = pd.read_csv(RAW_DATA_PATH)

    print("Dataset loaded successfully.")

    return df


# ============================================================
# VALIDATE DATASET
# ============================================================

def validate_tox21_dataset(df):
    """
    Validate that the dataset contains all required
    columns for CosmoSafe toxicity processing.
    """

    print("\nValidating Tox21 dataset...")

    missing_columns = [

        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "\nDataset validation failed."
            "\nMissing required columns:\n"
            + "\n".join(
                f"- {column}"
                for column in missing_columns
            )
        )

    # Check dataset is not empty
    if df.empty:

        raise ValueError(
            "Dataset validation failed: dataset is empty."
        )

    # Check SMILES availability
    missing_smiles = df["smiles"].isna().sum()

    if missing_smiles > 0:

        print(
            f"Warning: {missing_smiles} missing SMILES values."
        )

    print("Dataset validation successful.")

    print(f"Total compounds: {len(df)}")
    print(f"Total endpoints: {len(TOX21_ENDPOINTS)}")

    return True


# ============================================================
# LOAD + VALIDATE
# ============================================================

def get_tox21_dataset():
    """
    Main function used by CosmoSafe modules.

    Loads and validates the Tox21 dataset.
    """

    df = load_raw_tox21()

    validate_tox21_dataset(df)

    return df


# ============================================================
# TEST LOADER
# ============================================================

if __name__ == "__main__":

    df = get_tox21_dataset()

    print("\n" + "=" * 60)
    print("TOX21 LOADER TEST SUCCESSFUL")
    print("=" * 60)

    print(f"\nDataset Shape: {df.shape}")

    print("\nTox21 Endpoints:")

    for endpoint in TOX21_ENDPOINTS:

        print(f" - {endpoint}")