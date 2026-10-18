
from pathlib import Path

import joblib
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "toxicity" / "NR-AR_random_forest.joblib"
REFERENCE_PATH = BASE_DIR / "models" / "toxicity" / "NR-AR_similarity_reference.npz"


_MODEL_CACHE = None
_REFERENCE_CACHE = None


def _load_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Trained model not found: {MODEL_PATH}")

    saved_data = joblib.load(MODEL_PATH)

    if not isinstance(saved_data, dict) or "model" not in saved_data:
        raise ValueError("Saved model file has an unexpected format.")

    _MODEL_CACHE = (
        saved_data["model"],
        int(saved_data["fingerprint_bits"]),
        int(saved_data["fingerprint_radius"]),
        float(saved_data["decision_threshold"]),
    )
    return _MODEL_CACHE


def _load_reference(expected_bits):
    global _REFERENCE_CACHE
    if _REFERENCE_CACHE is not None and _REFERENCE_CACHE.shape[1] == expected_bits:
        return _REFERENCE_CACHE

    if not REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Similarity reference not found: {REFERENCE_PATH}. "
            "Run build_similarity_reference.py first."
        )

    with np.load(REFERENCE_PATH, allow_pickle=False) as data:
        fingerprints = data["fingerprints"]

    if fingerprints.ndim != 2 or fingerprints.shape[1] != expected_bits:
        raise ValueError("Reference fingerprint dimensions do not match the model.")

    _REFERENCE_CACHE = fingerprints
    return _REFERENCE_CACHE


def _maximum_similarity(fingerprint, reference_fingerprints):
    """Return the highest Tanimoto similarity to a reference fingerprint."""
    if reference_fingerprints is None or len(reference_fingerprints) == 0:
        return None

    query_bits = np.zeros(len(fingerprint), dtype=np.float32)
    DataStructs.ConvertToNumpyArray(fingerprint, query_bits)
    query_sum = float(np.sum(query_bits))

    if query_sum == 0.0:
        return 0.0

    ref_float = reference_fingerprints.astype(np.float32)
    ref_sums = np.sum(ref_float, axis=1)

    intersection = np.dot(ref_float, query_bits)
    denominator = query_sum + ref_sums - intersection

    valid = denominator > 0
    if not np.any(valid):
        return 0.0

    similarities = intersection[valid] / denominator[valid]
    return float(np.max(similarities))


def predict_nr_ar(smiles):
    if not isinstance(smiles, str) or not smiles.strip():
        return {
            "success": False,
            "error": "A non-empty SMILES string is required.",
        }

    molecule = Chem.MolFromSmiles(smiles.strip())

    if molecule is None:
        return {
            "success": False,
            "error": "The supplied SMILES is invalid or unsupported.",
        }

    canonical_smiles = Chem.MolToSmiles(molecule, canonical=True)

    model, fingerprint_bits, fingerprint_radius, threshold = _load_model()

    if model.n_features_in_ != fingerprint_bits:
        return {
            "success": False,
            "error": "Fingerprint size does not match the trained model.",
        }

    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=fingerprint_radius,
        fpSize=fingerprint_bits,
    )
    fingerprint = generator.GetFingerprint(molecule)
    fingerprint_array = np.zeros(fingerprint_bits, dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fingerprint, fingerprint_array)

    reference_fingerprints = _load_reference(fingerprint_bits)
    max_similarity = _maximum_similarity(
        fingerprint, reference_fingerprints
    )

    probabilities = model.predict_proba([fingerprint_array])[0]
    classes = list(model.classes_)
    positive_index = classes.index(1)
    activity_probability = float(probabilities[positive_index])
    predicted_activity = int(activity_probability >= threshold)

    # This is a provisional screening flag, not a validated applicability domain.
    similarity_warning_threshold = 0.30
    if max_similarity is None:
        applicability = "unknown"
        applicability_message = "No reference structures were available."
    elif max_similarity < similarity_warning_threshold:
        applicability = "low_similarity"
        applicability_message = (
            "The input has low maximum fingerprint similarity to the "
            "reference dataset. Treat this prediction cautiously."
        )
    else:
        applicability = "reference_similar"
        applicability_message = (
            "A structurally similar reference was found. This does not "
            "establish prediction reliability."
        )

    return {
        "success": True,
        "endpoint": "NR-AR",
        "canonical_smiles": canonical_smiles,
        "predicted_activity": predicted_activity,
        "activity_probability": round(activity_probability, 6),
        "decision_threshold": threshold,
        "maximum_reference_similarity": round(max_similarity, 6)
        if max_similarity is not None else None,
        "applicability": applicability,
        "applicability_message": applicability_message,
        "model_type": type(model).__name__,
        "interpretation": (
            "Estimated probability of activity in the NR-AR assay; "
            "not a general cosmetic safety determination."
        ),
        "limitations": [
            "Only the NR-AR endpoint is supported by this predictor.",
            "The probability is not a probability of harm to a person.",
            "Maximum fingerprint similarity is not a calibrated confidence score.",
            "The provisional similarity threshold has not been validated.",
        ],
    }


if __name__ == "__main__":
    import pprint

    test_chemicals = {
        "Ethanol": "CCO",
        "Glycerol": "C(C(CO)O)O",
        "Acetic acid": "CC(=O)O",
        "Caffeine": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        "Invalid input": "not-a-valid-smiles",
    }

    for name, smiles in test_chemicals.items():
        print(f"\n--- {name} ---")
        try:
            pprint.pp(predict_nr_ar(smiles))
        except (FileNotFoundError, ValueError) as error:
            print(f"Prediction could not be completed: {error}")
