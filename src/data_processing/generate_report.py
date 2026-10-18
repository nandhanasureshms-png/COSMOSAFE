from pathlib import Path
import json
import pandas as pd

from tox21_loader import TOX21_ENDPOINTS


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

REPORT_PATH = (
    BASE_DIR
    / "outputs"
    / "tox21_data_report.json"
)


# ============================================================
# LOAD PROCESSED DATASET
# ============================================================

def load_processed_dataset():

    if not PROCESSED_DATA_PATH.exists():

        raise FileNotFoundError(
            f"Processed dataset not found:\n"
            f"{PROCESSED_DATA_PATH}"
        )

    print("Loading processed Tox21 dataset...")

    df = pd.read_csv(PROCESSED_DATA_PATH)

    print("Processed dataset loaded successfully.")

    return df


# ============================================================
# GENERATE REPORT
# ============================================================

def generate_dataset_report(df):

    report = {

        "dataset_name": "Tox21",

        "total_records": int(len(df)),

        "total_columns": int(len(df.columns)),

        "total_endpoints": len(TOX21_ENDPOINTS),

        "endpoints": {},

        "missing_values": {},

        "duplicate_information": {

            "exact_duplicate_rows": int(
                df.duplicated().sum()
            ),

            "duplicate_smiles": int(
                df["smiles"].duplicated().sum()
            )
        }
    }


    # --------------------------------------------------------
    # ENDPOINT STATISTICS
    # --------------------------------------------------------

    for endpoint in TOX21_ENDPOINTS:

        active_count = int(
            (df[endpoint] == 1).sum()
        )

        inactive_count = int(
            (df[endpoint] == 0).sum()
        )

        missing_count = int(
            df[endpoint].isna().sum()
        )

        report["endpoints"][endpoint] = {

            "active": active_count,

            "inactive": inactive_count,

            "missing": missing_count
        }


    # --------------------------------------------------------
    # MISSING VALUES
    # --------------------------------------------------------

    for column in df.columns:

        report["missing_values"][column] = int(
            df[column].isna().sum()
        )


    return report


# ============================================================
# SAVE REPORT
# ============================================================

def save_report(report):

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4
        )

    print("\nReport saved successfully:")
    print(REPORT_PATH)


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "=" * 60)
    print("GENERATING TOX21 DATA REPORT")
    print("=" * 60)

    df = load_processed_dataset()

    report = generate_dataset_report(df)

    save_report(report)

    print("\n" + "=" * 60)
    print("REPORT GENERATION COMPLETE")
    print("=" * 60)

    print(f"\nTotal Records: {report['total_records']}")
    print(f"Total Endpoints: {report['total_endpoints']}")


if __name__ == "__main__":
    main()