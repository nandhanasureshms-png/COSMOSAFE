
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_processing.tox21_loader import RAW_DATA_PATH

ENDPOINT = "NR-AR"
OUTPUT_DIR = BASE_DIR / "models" / "toxicity"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / f"{ENDPOINT}_similarity_reference.npz"
BITS = 2048
RADIUS = 2

generator = rdFingerprintGenerator.GetMorganGenerator(
    radius=RADIUS,
    fpSize=BITS,
)


def main():
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {RAW_DATA_PATH}")

    df = pd.read_csv(RAW_DATA_PATH)

    labels = pd.to_numeric(df[ENDPOINT], errors="coerce")
    valid = labels.isin([0, 1]) & df["smiles"].notna()
    smiles_values = df.loc[valid, "smiles"].astype(str)

    fingerprints = []
    canonical_smiles_values = []
    seen = set()
    invalid_count = 0

    for smiles in smiles_values:
        molecule = Chem.MolFromSmiles(smiles)

        if molecule is None:
            invalid_count += 1
            continue

        canonical = Chem.MolToSmiles(molecule, canonical=True)

        if canonical in seen:
            continue

        seen.add(canonical)

        fingerprint = generator.GetFingerprint(molecule)
        array = np.zeros(BITS, dtype=np.uint8)
        DataStructs.ConvertToNumpyArray(fingerprint, array)

        fingerprints.append(array)
        canonical_smiles_values.append(canonical)

    if not fingerprints:
        raise ValueError("No valid reference fingerprints were generated.")

    np.savez_compressed(
        OUTPUT_PATH,
        fingerprints=np.asarray(fingerprints, dtype=np.uint8),
        canonical_smiles=np.asarray(canonical_smiles_values, dtype=str),
    )

    summary = {
        "endpoint": ENDPOINT,
        "fingerprint": "Morgan",
        "fingerprint_radius": RADIUS,
        "fingerprint_bits": BITS,
        "unique_reference_structures": len(fingerprints),
        "invalid_structures_skipped": invalid_count,
        "source": str(RAW_DATA_PATH),
    }

    print(json.dumps(summary, indent=2))
    print(f"\nSimilarity reference saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
