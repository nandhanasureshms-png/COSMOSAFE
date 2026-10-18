from pathlib import Path
import pandas as pd


# ============================================================
# PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = (
    BASE_DIR
    / "data"
    / "raw"
    / "tox21.csv.gz"
)


# ============================================================
# LOAD DATASET
# ============================================================

def load_tox21_dataset():

    print("\nLoading Tox21 dataset...")

    if not RAW_DATA_PATH.exists():

        raise FileNotFoundError(
            f"Dataset not found at:\n{RAW_DATA_PATH}"
        )

    df = pd.read_csv(RAW_DATA_PATH)

    print("Dataset loaded successfully!")

    return df


# ============================================================
# INSPECT DATASET
# ============================================================

def inspect_dataset(df):

    print("\n" + "=" * 60)
    print("TOX21 DATASET INSPECTION")
    print("=" * 60)

    print("\nDATASET SHAPE")
    print(f"Rows: {df.shape[0]}")
    print(f"Columns: {df.shape[1]}")

    print("\nCOLUMN NAMES")

    for column in df.columns:
        print(f" - {column}")

    print("\nFIRST 5 ROWS")
    print(df.head())

    print("\nMISSING VALUES")

    print(df.isnull().sum())

    print("\nDUPLICATE ROWS")
    print(df.duplicated().sum())


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        df = load_tox21_dataset()

        inspect_dataset(df)

        print("\n" + "=" * 60)
        print("INSPECTION COMPLETE")
        print("=" * 60)

    except Exception as e:

        print("\nERROR:")
        print(e)


if __name__ == "__main__":
    main()