
from pathlib import Path
import sys

import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold

BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_processing.tox21_loader import RAW_DATA_PATH
from toxicity_engine.chemical_standardizer import canonicalize_smiles


def get_scaffold(smiles):
    """Return the Bemis-Murcko scaffold for a valid molecule."""
    molecule = Chem.MolFromSmiles(smiles)

    if molecule is None:
        return None

    scaffold = MurckoScaffold.GetScaffoldForMol(molecule)

    # Acyclic molecules can have an empty scaffold.
    return Chem.MolToSmiles(scaffold, canonical=True)


def main():
    print("Loading Tox21 dataset...")
    df = pd.read_csv(RAW_DATA_PATH)

    # Inspect NR-AR records with known labels.
    df["NR-AR"] = pd.to_numeric(df["NR-AR"], errors="coerce")
    df = df[df["NR-AR"].isin([0, 1]) & df["smiles"].notna()].copy()

    print(f"Records with known NR-AR labels: {len(df)}")
    print("\nStandardizing structures...")

    df["canonical_smiles"] = df["smiles"].apply(canonicalize_smiles)
    df = df.dropna(subset=["canonical_smiles"]).copy()

    print(f"Valid structures: {len(df)}")

    duplicate_rows = int(df["canonical_smiles"].duplicated().sum())
    unique_structures = int(df["canonical_smiles"].nunique())

    print("\n" + "=" * 60)
    print("CHEMICAL OVERLAP REPORT")
    print("=" * 60)
    print(f"Unique canonical structures: {unique_structures}")
    print(f"Repeated structure rows: {duplicate_rows}")

    print("\nGenerating chemical scaffolds...")
    df["scaffold"] = df["canonical_smiles"].apply(get_scaffold)

    valid_scaffolds = df["scaffold"].notna()
    scaffold_count = int(df.loc[valid_scaffolds, "scaffold"].nunique())
    acyclic_count = int((df["scaffold"] == "").sum())

    print(f"Unique non-missing scaffolds: {scaffold_count}")
    print(f"Records with empty (often acyclic) scaffolds: {acyclic_count}")

    print("\nScaffold analysis complete.")
    print("No model files or dataset files were modified.")


if __name__ == "__main__":
    main()
