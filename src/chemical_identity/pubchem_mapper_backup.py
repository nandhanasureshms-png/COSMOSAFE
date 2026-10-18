
import requests
from urllib.parse import quote


# ============================================================
# PUBCHEM CONFIGURATION
# ============================================================

PUBCHEM_BASE_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
)

REQUEST_TIMEOUT = 15


# ============================================================
# COMPLEX INGREDIENT KEYWORDS
# ============================================================

COMPLEX_INGREDIENT_KEYWORDS = [
    "fragrance",
    "parfum",
    "perfume",
    "essential oil",
    "aloe vera extract",
    "extract",
    "mineral oil",
    "flavor",
    "aroma",
]


# ============================================================
# CHECK FOR COMPLEX INGREDIENTS
# ============================================================

def is_complex_ingredient(ingredient_name):
    """Identify ingredients that may represent mixtures."""

    ingredient_name = ingredient_name.strip().lower()

    return any(
        keyword in ingredient_name
        for keyword in COMPLEX_INGREDIENT_KEYWORDS
    )


# ============================================================
# CREATE STANDARD RESPONSE
# ============================================================

def create_mapping_result(
    ingredient_name,
    status,
    message=None,
    chemical_data=None,
):
    """Create a consistent chemical mapping response."""

    result = {
        "ingredient_name": ingredient_name,
        "status": status,
        "message": message,
        "pubchem_cid": None,
        "connectivity_smiles": None,
        "molecular_formula": None,
        "molecular_weight": None,
        "iupac_name": None,
    }

    if chemical_data:
        result.update(chemical_data)

    return result


# ============================================================
# PUBCHEM LOOKUP
# ============================================================

def query_pubchem(ingredient_name):
    """Request chemical properties from PubChem."""

    encoded_name = quote(str(ingredient_name), safe="")

    properties = (
        "MolecularFormula,"
        "MolecularWeight,"
        "IUPACName,"
        "ConnectivitySMILES"
    )

    url = (
        f"{PUBCHEM_BASE_URL}"
        f"/name/{encoded_name}"
        f"/property/{properties}/JSON"
    )

    return requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )


# ============================================================
# MAIN CHEMICAL MAPPING FUNCTION
# ============================================================

def map_ingredient_to_chemical(ingredient_name):
    """
    Map a chemical ingredient to PubChem.

    Possible statuses:
    mapped, complex_mixture, not_found,
    api_error, invalid_input.
    """

    # STEP 1: VALIDATE INPUT

    if ingredient_name is None:
        return create_mapping_result(
            None,
            "invalid_input",
            "Ingredient name is missing.",
        )

    ingredient_name = str(ingredient_name).strip()

    if not ingredient_name:
        return create_mapping_result(
            ingredient_name,
            "invalid_input",
            "Ingredient name is empty.",
        )

    # STEP 2: CHECK FOR COMPLEX INGREDIENTS

    if is_complex_ingredient(ingredient_name):
        return create_mapping_result(
            ingredient_name,
            "complex_mixture",
            (
                "This ingredient may represent a mixture, extract, "
                "oil, fragrance, or complex material. A single "
                "chemical identity cannot be assumed."
            ),
        )

    # STEP 3: QUERY PUBCHEM

    try:
        response = query_pubchem(ingredient_name)

        if response.status_code == 404:
            return create_mapping_result(
                ingredient_name,
                "not_found",
                "No matching compound was found in PubChem.",
            )

        response.raise_for_status()

        data = response.json()

        properties_list = (
            data.get("PropertyTable", {}).get("Properties", [])
        )

        if not properties_list:
            return create_mapping_result(
                ingredient_name,
                "not_found",
                "PubChem returned no compound properties.",
            )

        properties = properties_list[0]

        chemical_data = {
            "pubchem_cid": properties.get("CID"),
            "connectivity_smiles": properties.get(
                "ConnectivitySMILES"
            ),
            "molecular_formula": properties.get(
                "MolecularFormula"
            ),
            "molecular_weight": properties.get(
                "MolecularWeight"
            ),
            "iupac_name": properties.get("IUPACName"),
        }

        # STEP 4: VERIFY CHEMICAL IDENTITY DATA

        if not chemical_data["pubchem_cid"]:
            return create_mapping_result(
                ingredient_name,
                "not_found",
                "PubChem did not return a valid compound ID.",
            )

        if not chemical_data["connectivity_smiles"]:
            return create_mapping_result(
                ingredient_name,
                "not_found",
                (
                    "A compound was returned, but no usable "
                    "ConnectivitySMILES structure was available."
                ),
                chemical_data,
            )

        # STEP 5: RETURN SUCCESS

        return create_mapping_result(
            ingredient_name,
            "mapped",
            "Chemical successfully mapped using PubChem.",
            chemical_data,
        )

    except requests.exceptions.Timeout:
        return create_mapping_result(
            ingredient_name,
            "api_error",
            "PubChem request timed out.",
        )

    except requests.exceptions.RequestException as error:
        return create_mapping_result(
            ingredient_name,
            "api_error",
            f"PubChem request failed: {error}",
        )

    except (KeyError, IndexError, ValueError, TypeError) as error:
        return create_mapping_result(
            ingredient_name,
            "api_error",
            f"Unexpected PubChem response: {error}",
        )


# ============================================================
# DISPLAY RESULT
# ============================================================

def print_mapping_result(result):
    """Display a chemical mapping result."""

    print("\n" + "=" * 60)
    print("CHEMICAL MAPPING RESULT")
    print("=" * 60)

    print(f"Ingredient: {result.get('ingredient_name')}")
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message')}")

    if result.get("status") == "mapped":
        print("\nCHEMICAL IDENTITY")

        print(f"PubChem CID: {result.get('pubchem_cid')}")
        print(f"SMILES: {result.get('connectivity_smiles')}")
        print(f"Formula: {result.get('molecular_formula')}")
        print(f"Molecular Weight: {result.get('molecular_weight')}")
        print(f"IUPAC Name: {result.get('iupac_name')}")


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_ingredients = [
        "niacinamide",
        "glycerin",
        "caffeine",
        "fragrance",
        "aloe vera extract",
        "random_fake_chemical",
    ]

    for ingredient in test_ingredients:
        result = map_ingredient_to_chemical(ingredient)
        print_mapping_result(result)

