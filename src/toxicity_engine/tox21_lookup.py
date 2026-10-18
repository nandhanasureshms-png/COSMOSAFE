
from pathlib import Path
import sys

import pandas as pd

# ------------------------------------------------------------
# PROJECT PATHS
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_processing.tox21_loader import TOX21_ENDPOINTS
from toxicity_engine.chemical_standardizer import canonicalize_smiles

PROCESSED_DATA_PATH = (
    BASE_DIR / "data" / "processed" / "tox21_processed.csv"
)


# ------------------------------------------------------------
# LOAD AND PREPARE TOX21 DATASET
# ------------------------------------------------------------

def load_tox21_for_lookup():
    """
    Load Tox21 and prepare canonical SMILES for exact matching.

    Invalid dataset structures are retained in the loaded
    DataFrame for inspection, but excluded from valid matches.
    """

    if not PROCESSED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Processed Tox21 dataset not found: "
            f"{PROCESSED_DATA_PATH}"
        )

    print("Loading processed Tox21 dataset...")

    df = pd.read_csv(PROCESSED_DATA_PATH)

    required_columns = {"mol_id", "smiles", *TOX21_ENDPOINTS}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "Tox21 dataset is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    df = df.copy()

    print(f"Rows loaded: {len(df)}")

    print("Canonicalizing chemical structures...")

    df["canonical_smiles"] = df["smiles"].apply(
        canonicalize_smiles
    )

    invalid_count = int(df["canonical_smiles"].isna().sum())

    if invalid_count:
        print(
            f"Warning: {invalid_count} invalid structures "
            "cannot be used for exact structure matching."
        )

    print("Tox21 lookup data prepared.")

    return df


# ------------------------------------------------------------
# CREATE REUSABLE LOOKUP INDEX
# ------------------------------------------------------------

def build_tox21_index(tox21_df):
    """
    Build an index from canonical SMILES to matching records.

    Build this once and reuse it for multiple chemical searches.
    """

    required_columns = {"canonical_smiles", "mol_id", "smiles"}
    missing_columns = required_columns - set(tox21_df.columns)

    if missing_columns:
        raise ValueError(
            "Lookup DataFrame is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    index = {}

    valid_rows = tox21_df.dropna(
        subset=["canonical_smiles"]
    )

    for _, row in valid_rows.iterrows():
        key = row["canonical_smiles"]
        index.setdefault(key, []).append(row)

    return index


# ------------------------------------------------------------
# LOOK UP A CHEMICAL
# ------------------------------------------------------------

def lookup_tox21_chemical(input_smiles, tox21_df=None, tox21_index=None):
    """
    Look up a valid chemical structure in Tox21.

    Supply either tox21_df or tox21_index.
    Results contain experimental assay labels, not a
    general declaration that an ingredient is safe or unsafe.
    """

    canonical_input = canonicalize_smiles(input_smiles)

    if canonical_input is None:
        return {
            "status": "invalid_smiles",
            "message": "The input is not a valid supported SMILES structure.",
            "tox21_data": None,
        }

    if tox21_index is None:
        if tox21_df is None:
            return {
                "status": "error",
                "message": "A Tox21 DataFrame or lookup index is required.",
                "tox21_data": None,
            }

        tox21_index = build_tox21_index(tox21_df)

    matches = tox21_index.get(canonical_input, [])

    if not matches:
        return {
            "status": "not_found",
            "message": "No exact canonical SMILES match was found in Tox21.",
            "tox21_data": None,
        }

    records = []

    for row in matches:
        endpoint_results = {}

        for endpoint in TOX21_ENDPOINTS:
            value = row.get(endpoint)

            if pd.isna(value):
                endpoint_results[endpoint] = None
            else:
                numeric_value = float(value)

                if numeric_value not in (0.0, 1.0):
                    endpoint_results[endpoint] = None
                else:
                    endpoint_results[endpoint] = int(numeric_value)

        records.append({
            "mol_id": str(row["mol_id"]),
            "original_smiles": row["smiles"],
            "canonical_smiles": row["canonical_smiles"],
            "toxicity_endpoints": endpoint_results,
        })

    return {
        "status": "found",
        "message": (
            f"Found {len(records)} matching Tox21 record(s). "
            "Review individual assay values and missing results."
        ),
        "tox21_data": records,
    }


# ------------------------------------------------------------
# BACKWARDS-COMPATIBLE SEARCH FUNCTION
# ------------------------------------------------------------

def search_tox21(input_smiles, tox21_df=None, tox21_index=None):
    """Search Tox21 using either a DataFrame or a reusable index."""

    return lookup_tox21_chemical(
        input_smiles,
        tox21_df=tox21_df,
        tox21_index=tox21_index,
    )


# ------------------------------------------------------------
# DISPLAY RESULTS
# ------------------------------------------------------------

def print_tox21_result(result):
    print("\n" + "=" * 65)
    print("TOX21 EXPERIMENTAL EVIDENCE RESULT")
    print("=" * 65)

    print("Status:", result["status"])
    print("Message:", result["message"])

    for number, record in enumerate(
        result.get("tox21_data") or [], start=1
    ):
        print(f"\nMATCH {number}")
        print("Mol ID:", record["mol_id"])
        print("SMILES:", record["canonical_smiles"])
        print("\nTOXICITY ASSAY ENDPOINTS:")

        for endpoint, value in record["toxicity_endpoints"].items():
            if value is None:
                label = "Missing / unavailable"
            elif value == 1:
                label = "Positive assay result"
            else:
                label = "Negative assay result"

            print(f"  {endpoint}: {value} ({label})")


# ------------------------------------------------------------
# BASIC MANUAL TEST
# ------------------------------------------------------------

if __name__ == "__main__":
    tox21_df = load_tox21_for_lookup()
    tox21_index = build_tox21_index(tox21_df)

    # Ethanol: example structure, CCO
    result = search_tox21(
        "CCO",
        tox21_index=tox21_index,
    )

    print_tox21_result(result)
