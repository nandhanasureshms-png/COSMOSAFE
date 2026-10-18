from rdkit import Chem


# ============================================================
# CANONICALIZE SMILES
# ============================================================

def canonicalize_smiles(smiles):
    """
    Convert a SMILES string into RDKit canonical SMILES.

    Returns:
        Canonical SMILES string
        or None if the SMILES is invalid.
    """

    if smiles is None:
        return None

    smiles = str(smiles).strip()

    if not smiles:
        return None

    try:

        molecule = Chem.MolFromSmiles(smiles)

        if molecule is None:
            return None

        canonical_smiles = Chem.MolToSmiles(
            molecule,
            canonical=True
        )

        return canonical_smiles

    except Exception:

        return None


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_smiles = [

        "CCO",

        "C(CO)O",

        "invalid_smiles"
    ]

    print("\nSMILES CANONICALIZATION TEST")
    print("=" * 50)

    for smiles in test_smiles:

        canonical = canonicalize_smiles(smiles)

        print(f"\nOriginal: {smiles}")
        print(f"Canonical: {canonical}")