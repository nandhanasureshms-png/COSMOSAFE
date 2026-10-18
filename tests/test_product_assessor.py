import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from assessment.product_assessor import (
    assess_product_safety,
    VALID_ASSESSMENT_STATUSES,
)


class TestProductAssessor(unittest.TestCase):
    def test_safety_concern_when_prohibited_substance_present(self):
        # Hydroquinone (prohibited) included
        results = [
            {
                "raw_ingredient": "Hydroquinone",
                "primary_status": "verified",
                "mapping": {
                    "pubchem_cid": 785,
                    "identity_verified": True,
                },
            }
        ]
        assessment = assess_product_safety("Bleaching Cream", results, jurisdiction="India")
        self.assertEqual(
            assessment["overall_assessment_status"],
            "Safety concern identified in the assessed scope"
        )
        self.assertGreater(assessment["findings_breakdown"]["safety_concerns_count"], 0)
        self.assertIn("Safety concern", assessment["assessment_summary"])

    def test_not_assessed_when_unverified_ingredients_exist(self):
        # Mixture of verified and unverified ingredients
        results = [
            {
                "raw_ingredient": "Aqua",
                "primary_status": "verified",
                "mapping": {"pubchem_cid": 962, "identity_verified": True},
            },
            {
                "raw_ingredient": "UnknownExtract",
                "primary_status": "needs_review",
                "mapping": {"pubchem_cid": None, "identity_verified": False},
            },
        ]
        assessment = assess_product_safety("Daily Serum", results, jurisdiction="India")
        self.assertEqual(
            assessment["overall_assessment_status"],
            "Not assessed due to missing or uncertain information"
        )
        self.assertEqual(assessment["findings_breakdown"]["unassessed_ingredients_count"], 1)
        self.assertIn("cannot be completed", assessment["assessment_summary"].lower())

    def test_further_review_required_on_active_qsar_or_sensitizer(self):
        # Verified identities, but one has active QSAR prediction
        results = [
            {
                "raw_ingredient": "ActiveTestCompound",
                "primary_status": "verified",
                "mapping": {"pubchem_cid": 936, "identity_verified": True},
                "toxicity": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "endpoint": "NR-AR",
                        "predicted_activity": 1,
                        "activity_probability": 0.88,
                        "decision_threshold": 0.5,
                        "applicability": "reference_similar",
                    },
                },
            }
        ]
        assessment = assess_product_safety("Anti-Aging Lotion", results, jurisdiction="India")
        self.assertEqual(
            assessment["overall_assessment_status"],
            "Further review required"
        )
        self.assertGreater(assessment["findings_breakdown"]["review_triggers_count"], 0)

    def test_no_relevant_concern_when_all_verified_and_clean(self):
        # All verified, compliant, no hazard findings
        results = [
            {
                "raw_ingredient": "Aqua",
                "primary_status": "verified",
                "mapping": {"pubchem_cid": 962, "identity_verified": True},
                "toxicity": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "predicted_activity": 0,
                        "activity_probability": 0.01,
                        "applicability": "reference_similar",
                    },
                },
            },
            {
                "raw_ingredient": "Niacinamide",
                "primary_status": "verified",
                "mapping": {"pubchem_cid": 936, "identity_verified": True},
                "toxicity": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "predicted_activity": 0,
                        "activity_probability": 0.04,
                        "applicability": "reference_similar",
                    },
                },
            },
        ]
        assessment = assess_product_safety("Soothing Gel", results, jurisdiction="India")
        self.assertEqual(
            assessment["overall_assessment_status"],
            "No relevant concern identified within the assessed scope"
        )
        self.assertEqual(assessment["findings_breakdown"]["safety_concerns_count"], 0)
        self.assertEqual(assessment["findings_breakdown"]["unassessed_ingredients_count"], 0)


if __name__ == "__main__":
    unittest.main()
