import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from integration.structured_report import (
    build_structured_report,
    validate_report_consistency,
)


class TestStructuredReport(unittest.TestCase):
    def test_empty_input(self):
        report = build_structured_report([])
        self.assertEqual(report["summary"]["ingredients_processed"], 0)
        self.assertEqual(report["summary"]["ingredients_screened"], 0)
        self.assertEqual(report["summary"]["ingredients_not_assessed"], 0)
        self.assertEqual(report["summary"]["ingredients_with_warnings"], 0)
        self.assertEqual(report["results"], [])
        self.assertTrue(validate_report_consistency(report))

    def test_primary_status_sum_and_counts(self):
        sample_results = [
            # 1. Verified & assessed with reference_similar
            {
                "raw_ingredient": "Niacinamide",
                "normalized_ingredient": "niacinamide",
                "mapping_result": {
                    "status": "mapped",
                    "identity_verified": True,
                    "pubchem_cid": 936,
                    "connectivity_smiles": "C1=CC(=CN=C1)C(=O)N",
                },
                "toxicity_result": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "applicability": "reference_similar",
                        "predicted_activity": 0,
                    },
                },
            },
            # 2. Verified & assessed with low_similarity warning
            {
                "raw_ingredient": "Aqua",
                "normalized_ingredient": "aqua",
                "mapping_result": {
                    "status": "mapped",
                    "identity_verified": True,
                    "pubchem_cid": 962,
                    "connectivity_smiles": "O",
                },
                "toxicity_result": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "applicability": "low_similarity",
                        "applicability_message": "Low fingerprint similarity.",
                        "predicted_activity": 0,
                    },
                },
            },
            # 3. Needs review
            {
                "raw_ingredient": "Glycerin",
                "normalized_ingredient": "glycerin",
                "mapping_result": {
                    "status": "needs_review",
                    "identity_verified": False,
                    "pubchem_cid": 753,
                    "connectivity_smiles": "C(C(CO)O)O",
                },
                "toxicity_result": {"status": "not_run"},
            },
            # 4. Not found
            {
                "raw_ingredient": "UnknownChem",
                "normalized_ingredient": "unknownchem",
                "mapping_result": {"status": "not_found", "identity_verified": False},
                "toxicity_result": {"status": "not_run"},
            },
            # 5. Complex mixture
            {
                "raw_ingredient": "Fragrance",
                "normalized_ingredient": "fragrance",
                "mapping_result": {"status": "complex_mixture", "identity_verified": False},
                "toxicity_result": {"status": "not_run"},
            },
            # 6. API Error
            {
                "raw_ingredient": "FailedLookupChem",
                "normalized_ingredient": "failedlookupchem",
                "mapping_result": {"status": "api_error", "identity_verified": False},
                "toxicity_result": {"status": "not_run"},
            },
            # 7. Invalid input
            {
                "raw_ingredient": "   ",
                "normalized_ingredient": None,
                "mapping_result": {"status": "invalid_input", "identity_verified": False},
                "toxicity_result": {"status": "not_run"},
            },
        ]

        report = build_structured_report(sample_results)
        summary = report["summary"]

        self.assertEqual(summary["ingredients_processed"], 7)
        self.assertEqual(len(report["results"]), 7)

        # Primary status counts sum check
        status_counts = summary["primary_status_counts"]
        self.assertEqual(status_counts["verified"], 2)
        self.assertEqual(status_counts["needs_review"], 1)
        self.assertEqual(status_counts["not_found"], 1)
        self.assertEqual(status_counts["complex_mixture"], 1)
        self.assertEqual(status_counts["api_error"], 1)
        self.assertEqual(status_counts["invalid_input"], 1)
        self.assertEqual(sum(status_counts.values()), 7)

        # Screening counts
        self.assertEqual(summary["ingredients_screened"], 2)
        self.assertEqual(summary["ingredients_not_assessed"], 5)
        self.assertEqual(summary["successful_predictions"], 2)

        # Not assessed reasons check
        reasons = summary["not_assessed_reasons"]
        self.assertEqual(reasons["identity_needs_review"], 1)
        self.assertEqual(reasons["chemical_not_found"], 1)
        self.assertEqual(reasons["complex_mixture"], 1)
        self.assertEqual(reasons["pubchem_api_error"], 1)
        self.assertEqual(reasons["invalid_input"], 1)
        self.assertEqual(sum(reasons.values()), 5)

        # Warning checks:
        # Aqua has 1 warning (low_similarity)
        # Niacinamide has 0 warnings
        # The 5 unassessed have 1 warning each (reason for not being assessed)
        # Total ingredients with warnings = 1 + 5 = 6
        self.assertEqual(summary["ingredients_with_warnings"], 6)
        self.assertEqual(summary["total_warnings"], 6)
        self.assertEqual(summary["warning_counts"]["low_similarity"], 1)

        # Consistency validation passes
        self.assertTrue(validate_report_consistency(report))

    def test_duplicate_entries_handled(self):
        sample_results = [
            {
                "raw_ingredient": "Aqua",
                "normalized_ingredient": "aqua",
                "mapping_result": {
                    "status": "mapped",
                    "identity_verified": True,
                    "pubchem_cid": 962,
                    "connectivity_smiles": "O",
                },
                "toxicity_result": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "applicability": "reference_similar",
                        "predicted_activity": 0,
                    },
                },
            },
            {
                "raw_ingredient": "Aqua",
                "normalized_ingredient": "aqua",
                "mapping_result": {
                    "status": "mapped",
                    "identity_verified": True,
                    "pubchem_cid": 962,
                    "connectivity_smiles": "O",
                },
                "toxicity_result": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "applicability": "reference_similar",
                        "predicted_activity": 0,
                    },
                },
            },
        ]
        report = build_structured_report(sample_results)
        self.assertEqual(report["summary"]["ingredients_processed"], 2)
        self.assertEqual(len(report["results"]), 2)
        # Second item receives duplicate_entry warning
        warnings_first = report["results"][0]["warnings"]
        warnings_second = report["results"][1]["warnings"]
        self.assertEqual(len(warnings_first), 0)
        self.assertEqual(len(warnings_second), 1)
        self.assertEqual(warnings_second[0]["code"], "duplicate_entry")


if __name__ == "__main__":
    unittest.main()
