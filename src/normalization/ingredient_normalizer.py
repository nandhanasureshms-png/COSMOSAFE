import re


# ============================================================
# INGREDIENT NORMALIZATION
# ============================================================

def normalize_ingredient_name(ingredient):
    """
    Normalize a cosmetic ingredient name.

    Example:
        "  NIACINAMIDE " -> "niacinamide"
        "Sodium   Hyaluronate" -> "sodium hyaluronate"
    """

    # Check invalid input
    if ingredient is None:
        return None

    # Convert to string
    ingredient = str(ingredient)

    # Replace non-breaking spaces and normalize unicode hyphens
    ingredient = ingredient.replace("\u00a0", " ")
    ingredient = re.sub(r"[\u2010-\u2015]", "-", ingredient)

    # Convert to lowercase
    ingredient = ingredient.lower()

    # Replace multiple spaces with one space
    ingredient = re.sub(
        r"\s+",
        " ",
        ingredient
    )

    # Remove unnecessary surrounding punctuation and whitespace
    ingredient = ingredient.strip(" \t\r\n.,;:")

    # Return None if empty
    if not ingredient:
        return None

    return ingredient


# ============================================================
# NORMALIZE MULTIPLE INGREDIENTS
# ============================================================

def normalize_ingredient_list(ingredients):
    """
    Normalize a list of ingredient names, preserving the original length and position.
    Returns None for invalid/blank entries instead of dropping them.
    """
    if ingredients is None:
        return []

    return [normalize_ingredient_name(item) for item in ingredients]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_ingredients = [

        "  NIACINAMIDE ",
        "Sodium   Hyaluronate",
        "GLYCERIN",
        " Vitamin C ",
        None,
        ""
    ]

    print("\nINGREDIENT NORMALIZATION TEST")
    print("=" * 50)

    normalized = normalize_ingredient_list(
        test_ingredients
    )

    for ingredient in normalized:

        print(ingredient)