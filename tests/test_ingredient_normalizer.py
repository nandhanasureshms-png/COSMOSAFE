import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from normalization.ingredient_normalizer import (
    normalize_ingredient_name,
    normalize_ingredient_list,
)


class TestIngredientNormalizer(unittest.TestCase):
    def test_normalize_basic(self):
        self.assertEqual(normalize_ingredient_name("  NIACINAMIDE "), "niacinamide")
        self.assertEqual(normalize_ingredient_name("Sodium   Hyaluronate"), "sodium hyaluronate")
        self.assertEqual(normalize_ingredient_name("GLYCERIN"), "glycerin")

    def test_normalize_unicode_and_spaces(self):
        # Non-breaking space
        self.assertEqual(normalize_ingredient_name("Aqua\u00a0Glycerin"), "aqua glycerin")
        # En-dash / em-dash / hyphens
        self.assertEqual(normalize_ingredient_name("c12\u201315 alkyl benzoate"), "c12-15 alkyl benzoate")
        self.assertEqual(normalize_ingredient_name("peg\u2010100 stearate"), "peg-100 stearate")

    def test_normalize_empty_and_punctuation(self):
        self.assertIsNone(normalize_ingredient_name(None))
        self.assertIsNone(normalize_ingredient_name(""))
        self.assertIsNone(normalize_ingredient_name("   "))
        self.assertIsNone(normalize_ingredient_name("...,;;;"))
        self.assertEqual(normalize_ingredient_name("Aqua,"), "aqua")
        self.assertEqual(normalize_ingredient_name(".Glycerin;"), "glycerin")

    def test_normalize_list_preserves_length_and_order(self):
        inputs = ["Aqua", "  ", None, "Niacinamide", "Glycerin"]
        result = normalize_ingredient_list(inputs)
        self.assertEqual(len(result), 5)
        self.assertEqual(result, ["aqua", None, None, "niacinamide", "glycerin"])

    def test_normalize_list_empty(self):
        self.assertEqual(normalize_ingredient_list([]), [])
        self.assertEqual(normalize_ingredient_list(None), [])


if __name__ == "__main__":
    unittest.main()
