import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chemical_identity.ingredient_pipeline import process_ingredient


class TestQSARGate(unittest.TestCase):
    @patch("chemical_identity.ingredient_pipeline.predict_nr_ar")
    def test_unverified_ingredient_does_not_call_qsar(self, mock_predict):
        # Unverified mapping with a candidate structure
        unverified_mapping = {
            "status": "needs_review",
            "identity_verified": False,
            "needs_manual_review": True,
            "pubchem_cid": 753,
            "connectivity_smiles": "C(C(CO)O)O",
        }
        res = process_ingredient("Glycerin", approved_mapping=unverified_mapping)
        self.assertFalse(res["toxicity_result"]["screening_eligible"])
        self.assertEqual(res["toxicity_result"]["status"], "not_run")
        self.assertIn("unverified", res["toxicity_result"]["message"].lower())
        mock_predict.assert_not_called()

    @patch("chemical_identity.ingredient_pipeline.predict_nr_ar")
    def test_verified_ingredient_with_invalid_smiles_does_not_crash(self, mock_predict):
        # Mapped and verified, but SMILES is malformed
        bad_smiles_mapping = {
            "status": "mapped",
            "identity_verified": True,
            "needs_manual_review": False,
            "pubchem_cid": 999999,
            "connectivity_smiles": "not-a-valid-smiles-string!!!",
        }
        res = process_ingredient("BadChemical", approved_mapping=bad_smiles_mapping)
        self.assertFalse(res["toxicity_result"]["screening_eligible"])
        self.assertEqual(res["toxicity_result"]["status"], "not_run")
        self.assertEqual(res["toxicity_result"].get("structure_error"), "invalid_smiles")
        mock_predict.assert_not_called()

    @patch("chemical_identity.ingredient_pipeline.predict_nr_ar")
    def test_multi_component_smiles_rejected(self, mock_predict):
        # Mapped and verified, but molecule has multiple fragments (e.g. mixture / salt)
        multi_component_mapping = {
            "status": "mapped",
            "identity_verified": True,
            "needs_manual_review": False,
            "pubchem_cid": 5234,
            "connectivity_smiles": "CCO.CCN",  # ethanol and ethylamine mixture
        }
        res = process_ingredient("MultiComponentChemical", approved_mapping=multi_component_mapping)
        self.assertFalse(res["toxicity_result"]["screening_eligible"])
        self.assertEqual(res["toxicity_result"]["status"], "not_run")
        self.assertEqual(res["toxicity_result"].get("structure_error"), "multi_component")
        mock_predict.assert_not_called()

    @patch("chemical_identity.ingredient_pipeline.predict_nr_ar")
    def test_verified_ingredient_runs_prediction(self, mock_predict):
        mock_predict.return_value = {
            "success": True,
            "endpoint": "NR-AR",
            "predicted_activity": 0,
            "activity_probability": 0.05,
            "decision_threshold": 0.5,
            "maximum_reference_similarity": 0.85,
            "applicability": "reference_similar",
        }
        verified_mapping = {
            "status": "mapped",
            "identity_verified": True,
            "needs_manual_review": False,
            "pubchem_cid": 936,
            "connectivity_smiles": "C1=CC(=CN=C1)C(=O)N",
        }
        res = process_ingredient("Niacinamide", approved_mapping=verified_mapping)
        self.assertTrue(res["toxicity_result"]["screening_eligible"])
        self.assertEqual(res["toxicity_result"]["status"], "completed")
        self.assertIsNotNone(res["toxicity_result"].get("prediction"))
        mock_predict.assert_called_once_with("C1=CC(=CN=C1)C(=O)N")

    @patch("chemical_identity.ingredient_pipeline.predict_nr_ar")
    def test_prediction_failure_handled_gracefully(self, mock_predict):
        mock_predict.side_effect = RuntimeError("Predictor internal failure")
        verified_mapping = {
            "status": "mapped",
            "identity_verified": True,
            "needs_manual_review": False,
            "pubchem_cid": 936,
            "connectivity_smiles": "C1=CC(=CN=C1)C(=O)N",
        }
        res = process_ingredient("Niacinamide", approved_mapping=verified_mapping)
        self.assertTrue(res["toxicity_result"]["screening_eligible"])
        self.assertEqual(res["toxicity_result"]["status"], "prediction_failed")
        self.assertIn("Predictor internal failure", res["toxicity_result"]["message"])


if __name__ == "__main__":
    unittest.main()
