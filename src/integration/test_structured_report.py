
import json

from chemical_identity.ingredient_pipeline import process_ingredient
from integration.structured_report import build_structured_report


test_ingredients = [
    "Niacinamide",
    "Glycerin",
    "Fragrance",
    "DefinitelyNotARealChemical123",
]

ingredient_results = []

for ingredient in test_ingredients:
    print(f"Processing: {ingredient}")

    try:
        result = process_ingredient(ingredient)
        ingredient_results.append(result)
    except Exception as error:
        print(f"Could not process {ingredient}: {error}")

report = build_structured_report(ingredient_results)

print("\n========== STRUCTURED REPORT ==========\n")
print(json.dumps(report, indent=2, ensure_ascii=False))

with open("data/toxicity_report_test.json", "w", encoding="utf-8") as file:
    json.dump(report, file, indent=2, ensure_ascii=False)

print("\nReport saved to data/toxicity_report_test.json")
