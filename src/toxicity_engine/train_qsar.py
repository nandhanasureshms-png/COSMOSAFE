
from pathlib import Path
import json
import sys

import joblib
import numpy as np
import pandas as pd

from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)

# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_processing.tox21_loader import (
    RAW_DATA_PATH,
    TOX21_ENDPOINTS,
)

OUTPUT_DIR = BASE_DIR / "models" / "toxicity"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINT = "NR-AR"
RANDOM_SEED = 42
TEST_SIZE = 0.20
FINGERPRINT_BITS = 2048

# --------------------------------------------------
# MOLECULAR FINGERPRINTS
# --------------------------------------------------

fingerprint_generator = rdFingerprintGenerator.GetMorganGenerator(
    radius=2,
    fpSize=FINGERPRINT_BITS,
)


def smiles_to_fingerprint(smiles):
    """Convert valid SMILES into a Morgan fingerprint."""
    if not isinstance(smiles, str) or not smiles.strip():
        return None

    try:
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None:
            return None

        fingerprint = fingerprint_generator.GetFingerprint(molecule)
        array = np.zeros((FINGERPRINT_BITS,), dtype=np.uint8)
        DataStructs.ConvertToNumpyArray(fingerprint, array)
        return array

    except Exception:
        return None


# --------------------------------------------------
# LOAD AND PREPARE DATA
# --------------------------------------------------

def prepare_data():
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Tox21 dataset not found: {RAW_DATA_PATH}"
        )

    print("Loading Tox21 dataset...")
    df = pd.read_csv(RAW_DATA_PATH)

    required = {"smiles", ENDPOINT}
    missing_columns = required - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Required columns missing: {sorted(missing_columns)}"
        )

    # Keep only records with known binary labels.
    labels = pd.to_numeric(df[ENDPOINT], errors="coerce")
    valid_label = labels.isin([0, 1]) & df["smiles"].notna()

    df = df.loc[valid_label, ["smiles"]].copy()
    y = labels.loc[valid_label].astype(int)

    print(f"Records with known labels: {len(df)}")
    print(f"Negative labels: {(y == 0).sum()}")
    print(f"Positive labels: {(y == 1).sum()}")

    print("Generating molecular fingerprints...")
    features = []
    kept_indices = []

    for index, smiles in df["smiles"].items():
        fingerprint = smiles_to_fingerprint(smiles)
        if fingerprint is not None:
            features.append(fingerprint)
            kept_indices.append(index)

    if not features:
        raise ValueError("No valid molecular fingerprints were generated.")

    X = np.vstack(features)
    y = y.loc[kept_indices].to_numpy()

    if len(np.unique(y)) != 2:
        raise ValueError("Training requires both positive and negative labels.")

    print(f"Usable structures: {len(y)}")
    print(f"Fingerprint shape: {X.shape}")

    return X, y


# --------------------------------------------------
# TRAIN AND EVALUATE
# --------------------------------------------------

def main():
    if ENDPOINT not in TOX21_ENDPOINTS:
        raise ValueError(f"Unknown Tox21 endpoint: {ENDPOINT}")

    X, y = prepare_data()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    print("\nTraining Random Forest classifier...")
    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    print("\n" + "=" * 65)
    print(f"QSAR RESULTS — {ENDPOINT}")
    print("=" * 65)

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["Negative", "Positive"],
            zero_division=0,
        )
    )

    print("Confusion matrix [negative, positive]:")
    print(confusion_matrix(y_test, predictions, labels=[0, 1]))

    roc_auc = roc_auc_score(y_test, probabilities)
    pr_auc = average_precision_score(y_test, probabilities)

    print(f"\nROC-AUC: {roc_auc:.4f}")
    print(f"PR-AUC (average precision): {pr_auc:.4f}")
    print(f"Positive test prevalence baseline: {y_test.mean():.4f}")

    # Save model and metadata.
    model_path = OUTPUT_DIR / f"{ENDPOINT}_random_forest.joblib"
    metadata_path = OUTPUT_DIR / f"{ENDPOINT}_metadata.json"

    joblib.dump(
        {
            "model": model,
            "endpoint": ENDPOINT,
            "fingerprint_bits": FINGERPRINT_BITS,
            "fingerprint_radius": 2,
            "decision_threshold": 0.5,
            "random_seed": RANDOM_SEED,
        },
        model_path,
    )

    metadata = {
        "endpoint": ENDPOINT,
        "model_type": "RandomForestClassifier",
        "fingerprint": "Morgan",
        "fingerprint_radius": 2,
        "fingerprint_bits": FINGERPRINT_BITS,
        "random_seed": RANDOM_SEED,
        "test_size": TEST_SIZE,
        "roc_auc": float(roc_auc),
        "average_precision": float(pr_auc),
        "positive_test_prevalence": float(y_test.mean()),
        "training_records": int(len(y_train)),
        "test_records": int(len(y_test)),
        "note": (
            "Initial random split; duplicate and scaffold leakage checks "
            "are still required before relying on generalization estimates."
        ),
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\nModel saved to: {model_path}")
    print(f"Metadata saved to: {metadata_path}")
    print("\nInitial QSAR training run complete.")


if __name__ == "__main__":
    main()
