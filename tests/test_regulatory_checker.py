import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from regulatory.regulatory_checker import check_ingredient_regulation


class TestRegulatoryChecker(unittest.TestCase):
    def test_prohibited_substance(self):
        # Hydroquinone CID 785 is explicitly prohibited in general cosmetics under IS 4707 Part 1
        res = check_ingredient_regulation(
            pubchem_cid=785,
            ingredient_name="Hydroquinone",
            jurisdiction="india",
        )
        self.assertEqual(res["compliance_status"], "explicitly_prohibited")
        self.assertFalse(res["is_compliant"])
        self.assertTrue(res["requires_action"])
        self.assertIn("IS 4707", res["legal_basis"])

    def test_restricted_substance_compliant_concentration(self):
        # Phenoxyethanol CID 31236 limit is 1.0%; test with 0.8%
        res = check_ingredient_regulation(
            pubchem_cid=31236,
            ingredient_name="Phenoxyethanol",
            concentration_pct=0.8,
            jurisdiction="india",
        )
        self.assertEqual(res["compliance_status"], "restricted_with_conditions")
        self.assertTrue(res["is_compliant"])
        self.assertFalse(res["requires_action"])
        self.assertEqual(res["max_authorized_concentration_pct"], 1.0)

    def test_restricted_substance_exceeding_concentration(self):
        # Phenoxyethanol CID 31236 limit is 1.0%; test with 1.8%
        res = check_ingredient_regulation(
            pubchem_cid=31236,
            ingredient_name="Phenoxyethanol",
            concentration_pct=1.8,
            jurisdiction="india",
        )
        self.assertEqual(res["compliance_status"], "restricted_with_conditions")
        self.assertFalse(res["is_compliant"])
        self.assertTrue(res["requires_action"])
        self.assertIn("exceeds authorized limit", res["compliance_notes"].lower())

    def test_restricted_substance_missing_concentration(self):
        # Phenoxyethanol with concentration missing (None)
        res = check_ingredient_regulation(
            pubchem_cid=31236,
            ingredient_name="Phenoxyethanol",
            concentration_pct=None,
            jurisdiction="india",
        )
        self.assertEqual(res["compliance_status"], "restricted_with_conditions")
        self.assertIsNone(res["is_compliant"])  # Must be None, not True
        self.assertTrue(res["requires_action"])
        self.assertIn("incomplete", res["compliance_notes"].lower())

    def test_unlisted_substance_does_not_imply_pre_approval(self):
        # Substance not in restricted annex (e.g. Diisopropyl Sebacate CID 24096)
        res = check_ingredient_regulation(
            pubchem_cid=24096,
            ingredient_name="Diisopropyl Sebacate",
            jurisdiction="india",
        )
        self.assertEqual(res["compliance_status"], "no_specific_restriction_found")
        self.assertIsNone(res["is_compliant"])
        self.assertIn("does not imply that the substance is unconditionally safe", res["message"].lower())

    def test_unverified_identity(self):
        # CID is None
        res = check_ingredient_regulation(
            pubchem_cid=None,
            ingredient_name="UnknownBotanical",
            jurisdiction="india",
        )
        self.assertEqual(res["compliance_status"], "uncertain_missing_identity")
        self.assertIsNone(res["is_compliant"])
        self.assertTrue(res["requires_action"])

    def test_eu_jurisdiction_extensibility(self):
        # Check EU regulation for Octocrylene CID 22571
        res_eu = check_ingredient_regulation(
            pubchem_cid=22571,
            ingredient_name="Octocrylene",
            concentration_pct=8.0,
            jurisdiction="eu",
        )
        self.assertEqual(res_eu["jurisdiction"], "European Union")
        self.assertEqual(res_eu["compliance_status"], "restricted_with_conditions")
        self.assertTrue(res_eu["is_compliant"])


if __name__ == "__main__":
    unittest.main()
