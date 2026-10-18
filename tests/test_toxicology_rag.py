import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evidence.toxicology_rag import (
    retrieve_toxicological_evidence,
    AUTHORITATIVE_TOXICOLOGY_DATABASE,
)


class TestToxicologyRAG(unittest.TestCase):
    def test_retrieve_evidence_for_curated_cid(self):
        # 936: Niacinamide
        res = retrieve_toxicological_evidence(pubchem_cid=936, ingredient_name="Niacinamide")
        self.assertTrue(res["evidence_found"])
        self.assertGreater(res["records_count"], 0)
        self.assertEqual(res["retrieval_status"], "evidence_retrieved")

        # Check endpoints and citations
        summary = res["endpoint_summary"]
        self.assertIn("skin_irritation_corrosion", summary)
        self.assertIn("skin_sensitization", summary)

        first_rec = res["evidence_records"][0]
        self.assertIn("CIR", first_rec["publisher"])
        self.assertTrue(first_rec["url"].startswith("http"))
        self.assertIsNotNone(first_rec["passage"])
        self.assertIsNotNone(first_rec["publication_date"])

    def test_unverified_identity_does_not_invent_evidence(self):
        # Missing CID (None)
        res_none = retrieve_toxicological_evidence(pubchem_cid=None, ingredient_name="UnverifiedExtract")
        self.assertFalse(res_none["evidence_found"])
        self.assertEqual(res_none["records_count"], 0)
        self.assertEqual(res_none["retrieval_status"], "unverified_identity_no_evidence")
        self.assertIn("No verified chemical identity", res_none["rag_synthesis"])

    def test_uncataloged_cid_reports_no_evidence_without_false_negative(self):
        # Fake or uncataloged CID
        res_uncataloged = retrieve_toxicological_evidence(pubchem_cid=99999999, ingredient_name="RareCompound")
        self.assertFalse(res_uncataloged["evidence_found"])
        self.assertEqual(res_uncataloged["records_count"], 0)
        self.assertEqual(res_uncataloged["retrieval_status"], "no_curated_records_found")
        # Ensure it does not say compound is safe
        self.assertIn("does not indicate that the substance is safe or toxic", res_uncataloged["rag_synthesis"])

    def test_keyword_query_filtering(self):
        res_filtered = retrieve_toxicological_evidence(
            pubchem_cid=22571,
            ingredient_name="Octocrylene",
            query_text="sensitization photoallergic",
        )
        self.assertTrue(res_filtered["evidence_found"])
        endpoints = [r["endpoint"] for r in res_filtered["evidence_records"]]
        self.assertIn("skin_sensitization", endpoints)


if __name__ == "__main__":
    unittest.main()
