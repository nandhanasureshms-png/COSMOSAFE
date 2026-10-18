from pathlib import Path
import pandas as pd

from tox21_loader import (
    get_tox21_dataset,
    TOX21_ENDPOINTS
)


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DATA_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "tox21_processed.csv"
)


# ============================================================
# CLEAN SMILES
# ============================================================

def clean_smiles(df):
    """
    Perform basic SMILES cleaning.

    Important:
    We do NOT chemically modify or canonicalize SMILES here.
    Chemical structure standardization will happen later.
    """

    df = df.copy()

    original_count = len(df)

    # Remove leading/trailing whitespace
    df["smiles"] = df["smiles"].astype(str).str.strip()

    # Remove invalid empty values
    df = df[
        df["smiles"].notna()
    ]

    df = df[
        df["smiles"] != ""
    ]

    df = df[
        df["smiles"] != "nan"
    ]

    removed_count = original_count - len(df)

    print(
        f"Invalid/empty SMILES rows removed: "
        f"{removed_count}"
    )

    return df


# ============================================================
# VALIDATE TOXICITY ENDPOINT VALUES
# ============================================================

def validate_endpoint_values(df):
    """
    Check that Tox21 labels are:

    0 = inactive
    1 = active
    NaN = missing experimental result
    """

    df = df.copy()

    for endpoint in TOX21_ENDPOINTS:

        # Convert values safely to numeric
        df[endpoint] = pd.to_numeric(
            df[endpoint],
            errors="coerce"
        )

        unique_values = (
            df[endpoint]
            .dropna()
            .unique()
        )

        invalid_values = [

            value
            for value in unique_values
            if value not in [0, 1]
        ]

        if invalid_values:

            print(
                f"WARNING: Unexpected values in "
                f"{endpoint}: {invalid_values}"
            )

    print("Endpoint value validation complete.")

    return df


# ============================================================
# REMOVE EXACT DUPLICATES
# ============================================================

def remove_exact_duplicates(df):
    """
    Remove only completely identical rows.

    We do NOT remove duplicate SMILES automatically because
    duplicate compounds may require scientific analysis later.
    """

    df = df.copy()

    before = len(df)

    df = df.drop_duplicates()

    after = len(df)

    removed = before - after

    print(
        f"Exact duplicate rows removed: {removed}"
    )

    return df


# ============================================================
# PREPROCESS DATASET
# ============================================================

def preprocess_tox21():

    print("\n" + "=" * 60)
    print("TOX21 PREPROCESSING")
    print("=" * 60)

    # Load validated dataset
    df = get_tox21_dataset()

    print(
        f"\nOriginal dataset shape: {df.shape}"
    )

    # Step 1: Clean SMILES
    print("\nStep 1: Cleaning SMILES...")
    df = clean_smiles(df)

    # Step 2: Validate endpoint values
    print("\nStep 2: Validating endpoint values...")
    df = validate_endpoint_values(df)

    # Step 3: Remove exact duplicates
    print("\nStep 3: Removing exact duplicates...")
    df = remove_exact_duplicates(df)

    print(
        f"\nProcessed dataset shape: {df.shape}"
    )

    return df


# ============================================================
# SAVE PROCESSED DATASET
# ============================================================

def save_processed_dataset(df):

    # Create folder if needed
    PROCESSED_DATA_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Save processed dataset
    df.to_csv(
        PROCESSED_DATA_PATH,
        index=False
    )

    print(
        "\nProcessed dataset saved successfully:"
    )

    print(PROCESSED_DATA_PATH)


# ============================================================
# MAIN
# ============================================================

def main():

    df = preprocess_tox21()

    save_processed_dataset(df)

    print("\n" + "=" * 60)
    print("PREPROCESSING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()