
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)
from sklearn.model_selection import GroupShuffleSplit

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_PATH = BASE_DIR / "data" / "raw" / "tox21.csv.gz"
OUTPUT_DIR = BASE_DIR / "reports" / "toxicity"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINT = "NR-AR"
RANDOM_SEED = 42


def canonicalize_and_scaffold(smiles):
    """Return a canonical SMILES and its non-empty scaffold group."""
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return None, None

        canonical = Chem.MolToSmiles(mol, canonical=True)
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        scaffold_smiles = Chem.MolToSmiles(
            scaffold, canonical=True
        )

        # Do not group all acyclic molecules together.
        # Give each acyclic structure its own group.
        if not scaffold_smiles:
            scaffold_smiles = "ACYCLIC:" + canonical

        return canonical, scaffold_smiles
    except Exception:
        return None, None


def make_fingerprint(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    return AllChem.GetMorganFingerprintAsBitVect(
        mol, radius=2, nBits=2048
    )


def main():
    print("Loading dataset...")
    df = pd.read_csv(RAW_PATH)

    df[ENDPOINT] = pd.to_numeric(
        df[ENDPOINT], errors="coerce"
    )
    df = df[
        df[ENDPOINT].isin([0, 1]) & df["smiles"].notna()
    ].copy()

    print(f"Known {ENDPOINT} labels: {len(df)}")
    print("Standardizing structures and assigning groups...")

    results = df["smiles"].apply(canonicalize_and_scaffold)
    df["canonical_smiles"] = results.apply(lambda x: x[0])
    df["scaffold_group"] = results.apply(lambda x: x[1])
    df = df.dropna(
        subset=["canonical_smiles", "scaffold_group"]
    ).copy()

    # If multiple records have the same exact structure,
    # do not let conflicting duplicate structures leak across groups.
    df = df.drop_duplicates(
        subset=["canonical_smiles"], keep="first"
    ).copy()

    df["fingerprint"] = df["canonical_smiles"].apply(
        make_fingerprint
    )
    df = df[df["fingerprint"].notna()].copy()

    print(f"Usable unique structures: {len(df)}")
    print(f"Scaffold/acyclic groups: {df['scaffold_group'].nunique()}")
    print(f"Positive labels: {(df[ENDPOINT] == 1).sum()}")
    print(f"Negative labels: {(df[ENDPOINT] == 0).sum()}")

    X = np.zeros((len(df), 2048), dtype=np.uint8)
    for i, fp in enumerate(df["fingerprint"]):
        DataStructs.ConvertToNumpyArray(fp, X[i])

    y = df[ENDPOINT].astype(int).to_numpy()
    groups = df["scaffold_group"].to_numpy()

    # Split by group so the same group cannot occur in both sets.
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=0.20, random_state=RANDOM_SEED
    )
    train_idx, test_idx = next(
        splitter.split(X, y, groups=groups)
    )

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    train_groups = set(groups[train_idx])
    test_groups = set(groups[test_idx])

    overlap = train_groups.intersection(test_groups)

    print("\nGroup-split verification:")
    print(f"Training records: {len(train_idx)}")
    print(f"Testing records: {len(test_idx)}")
    print(f"Overlapping groups: {len(overlap)}")

    if overlap:
        raise RuntimeError("Group leakage detected!")

    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        raise RuntimeError(
            "One split contains only one label class. "
            "A reliable classification evaluation is not possible "
            "with this split; adjust the split strategy."
        )

    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )

    print("\nTraining scaffold-split model...")
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]

    report = classification_report(
        y_test,
        predictions,
        labels=[0, 1],
        target_names=["Negative", "Positive"],
        zero_division=0,
        output_dict=True,
    )

    roc_auc = roc_auc_score(y_test, probabilities)
    pr_auc = average_precision_score(y_test, probabilities)
    matrix = confusion_matrix(
        y_test, predictions, labels=[0, 1]
    )

    print("\nScaffold-split classification report:")
    print(classification_report(
        y_test,
        predictions,
        labels=[0, 1],
        target_names=["Negative", "Positive"],
        zero_division=0,
    ))
    print("Confusion matrix:")
    print(matrix)
    print(f"ROC-AUC: {roc_auc:.4f}")
    print(f"PR-AUC (average precision): {pr_auc:.4f}")
    print(
        "Positive test prevalence baseline: "
        f"{y_test.mean():.4f}"
    )

    results = {
        "endpoint": ENDPOINT,
        "split_method": "GroupShuffleSplit by scaffold",
        "acyclic_grouping": "each unique canonical acyclic structure is its own group",
        "random_seed": RANDOM_SEED,
        "train_records": int(len(train_idx)),
        "test_records": int(len(test_idx)),
        "overlapping_groups": len(overlap),
        "train_positive_count": int(y_train.sum()),
        "test_positive_count": int(y_test.sum()),
        "roc_auc": float(roc_auc),
        "average_precision": float(pr_auc),
        "test_positive_prevalence": float(y_test.mean()),
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "note": (
            "Assay-specific activity prediction, not a general "
            "cosmetic safety determination. One group split is "
            "a preliminary evaluation."
        ),
    }

    output_path = OUTPUT_DIR / "NR-AR_scaffold_evaluation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nEvaluation report saved to: {output_path}")
    print("Existing trained model files were not changed.")


if __name__ == "__main__":
    main()
