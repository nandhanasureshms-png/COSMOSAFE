
from pathlib import Path

import joblib
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = (
    BASE_DIR
    / "models"
    / "toxicity"
    / "NR-AR_random_forest.joblib"
)

FINGERPRINT_BITS = 2048
FINGERPRINT_RADIUS = 2

generator = rdFingerprintGenerator.GetMorganGenerator(
    radius=FINGERPRINT_RADIUS,
    fpSize=FINGERPRINT_BITS,
)


def predict_nr_ar(smiles):
    molecule = Chem.MolFromSmiles(smiles)

    if molecule is None:
        raise ValueError("Invalid SMILES structure.")

    fingerprint = generator.GetFingerprint(molecule)
    array = np.zeros(FINGERPRINT_BITS, dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fingerprint, array)

    saved = joblib.load(MODEL_PATH)
    model = saved["model"]

    probability = float(
        model.predict_proba(array.reshape(1, -1))[0, 1]
    )

    print("Endpoint: NR-AR")
    print("Input SMILES:", smiles)
    print(f"Predicted assay-activity probability: {probability:.4f}")
    print("This is a model prediction, not a safety determination.")


if __name__ == "__main__":
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Saved model not found: {MODEL_PATH}")

    predict_nr_ar("CCO")

