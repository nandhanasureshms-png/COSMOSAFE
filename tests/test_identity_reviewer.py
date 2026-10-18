import unittest
import sys
import json
import tempfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chemical_identity.identity_reviewer import (
    generate_identity_review_registry,
    save_identity_review_registry,
)


class TestIdentityReviewer(unittest.TestCase):
    def test_registry_generation(self):
        sample_results = [
            # 1. Verified curated ingredient
            {
                "raw_ingredient": "Niacinamide",
                "primary_status": "verified",
                "mapping_result": {
                    "status": "mapped",
                    "identity_verified": True,
                    "pubchem_cid": 936,
                    "molecular_formula": "C6H6N2O",
                    "connectivity_smiles": "C1=CC(=CN=C1)C(=O)N",
                },
            },
            # 2. Needs review - single candidate unverified
            {
                "raw_ingredient": "Glycerin",
                "primary_status": "needs_review",
                "mapping_result": {
                    "status": "needs_review",
                    "identity_verified": False,
                    "pubchem_cid": 753,
                    "candidate_pubchem_cids": [753],
                    "iupac_name": "propane-1,2,3-triol",
                    "molecular_formula": "C3H8O3",
                    "connectivity_smiles": "C(C(CO)O)O",
                },
            },
            # 3. Needs review - ambiguous multiple candidates
            {
                "raw_ingredient": "AmbiguousIsomer",
                "primary_status": "needs_review",
                "mapping_result": {
                    "status": "needs_review",
                    "identity_verified": False,
                    "candidate_pubchem_cids": [101, 102, 103],
                },
            },
            # 4. Not found - with known OCR corruption
            {
                "raw_ingredient": "Diisopropy| Adipate",
                "primary_status": "not_found",
                "mapping_result": {
                    "status": "not_found",
                    "identity_verified": False,
                },
            },
            # 5. Not found - unknown string
            {
                "raw_ingredient": "CompletelyUnknown12345",
                "primary_status": "not_found",
                "mapping_result": {
                    "status": "not_found",
                    "identity_verified": False,
                },
            },
            # 6. Complex mixture
            {
                "raw_ingredient": "Lavender Essential Oil",
                "primary_status": "complex_mixture",
                "mapping_result": {
                    "status": "complex_mixture",
                    "identity_verified": False,
                },
            },
            # 7. API Error
            {
                "raw_ingredient": "NetworkTimeoutChem",
                "primary_status": "api_error",
                "mapping_result": {
                    "status": "api_error",
                    "message": "Connection reset by peer",
                    "identity_verified": False,
                },
            },
            # 8. Invalid input
            {
                "raw_ingredient": "   ",
                "primary_status": "invalid_input",
                "mapping_result": {
                    "status": "invalid_input",
                    "identity_verified": False,
                },
            },
        ]

        registry = generate_identity_review_registry(sample_results)

        self.assertEqual(registry["total_ingredients_audited"], 8)
        self.assertEqual(registry["verified_identities_count"], 1)
        self.assertEqual(registry["pending_reviews_count"], 7)

        # Check verified entry
        verified = registry["verified_identities"][0]
        self.assertEqual(verified["original_name"], "Niacinamide")
        self.assertEqual(verified["curated_cid"], 936)
        self.assertEqual(verified["review_status"], "verified_curated_match")

        # Check pending entries
        pending = registry["pending_identity_reviews"]
        self.assertEqual(len(pending), 7)

        # Glycerin: candidate pending curated approval
        gly = next(p for p in pending if p["original_name"] == "Glycerin")
        self.assertEqual(gly["review_status"], "candidate_pending_curated_approval")
        self.assertEqual(gly["candidate_chemical_identity"]["pubchem_cid"], 753)
        self.assertIn("CIR/CosIng review required", gly["evidence"])

        # Ambiguous: multiple candidates
        amb = next(p for p in pending if p["original_name"] == "AmbiguousIsomer")
        self.assertEqual(amb["review_status"], "ambiguous_multiple_candidates")

        # Diisopropy| Adipate: OCR corruption detected
        adipate = next(p for p in pending if p["original_name"] == "Diisopropy| Adipate")
        self.assertEqual(adipate["review_status"], "ocr_corruption_pending_approval")
        self.assertTrue(adipate["has_proposed_correction"])
        self.assertEqual(adipate["proposed_correction"], "Diisopropyl Adipate")

        # Complex mixture
        lav = next(p for p in pending if p["original_name"] == "Lavender Essential Oil")
        self.assertEqual(lav["review_status"], "complex_mixture_unsupported_for_qsar")

        # Sum of breakdown matches total pending
        status_breakdown = registry["pending_reviews_by_status"]
        self.assertEqual(sum(status_breakdown.values()), 7)

    def test_save_registry_to_file(self):
        registry = {
            "title": "Test Registry",
            "total_ingredients_audited": 1,
            "verified_identities_count": 0,
            "pending_reviews_count": 1,
            "verified_identities": [],
            "pending_identity_reviews": [{"original_name": "TestChem", "review_status": "unresolved_no_candidate"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test_review.json"
            save_identity_review_registry(registry, out_file)
            self.assertTrue(out_file.exists())
            with out_file.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["title"], "Test Registry")


if __name__ == "__main__":
    unittest.main()
