import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
import requests

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chemical_identity.pubchem_mapper import (
    map_ingredient_to_chemical,
    is_complex_ingredient,
    CURATED_CIDS,
)


class TestPubChemMapper(unittest.TestCase):
    def test_invalid_and_blank_input(self):
        result_none = map_ingredient_to_chemical(None)
        self.assertEqual(result_none["status"], "invalid_input")
        self.assertFalse(result_none["identity_verified"])

        result_empty = map_ingredient_to_chemical("   ")
        self.assertEqual(result_empty["status"], "invalid_input")
        self.assertFalse(result_empty["identity_verified"])

        result_punct = map_ingredient_to_chemical(",,,...")
        self.assertEqual(result_punct["status"], "invalid_input")
        self.assertFalse(result_punct["identity_verified"])

    def test_complex_ingredients(self):
        for name in ["Fragrance", "Parfum", "Lavender Essential Oil", "Mineral Oil", "Green Tea Extract"]:
            result = map_ingredient_to_chemical(name)
            self.assertEqual(result["status"], "complex_mixture")
            self.assertFalse(result["identity_verified"])
            self.assertTrue(result["needs_manual_review"])

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_curated_match_verified(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 936,
                        "ConnectivitySMILES": "C1=CC(=CN=C1)C(=O)N",
                        "MolecularFormula": "C6H6N2O",
                        "MolecularWeight": "122.12",
                        "IUPACName": "pyridine-3-carboxamide",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp

        result = map_ingredient_to_chemical("Niacinamide")
        self.assertEqual(result["status"], "mapped")
        self.assertTrue(result["identity_verified"])
        self.assertFalse(result["needs_manual_review"])
        self.assertEqual(result["pubchem_cid"], 936)

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_candidate_not_in_curated_remains_needs_review(self, mock_get):
        # Candidate found on PubChem, but not curated -> MUST NOT be auto-verified
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 753,
                        "ConnectivitySMILES": "C(C(CO)O)O",
                        "MolecularFormula": "C3H8O3",
                        "MolecularWeight": "92.09",
                        "IUPACName": "propane-1,2,3-triol",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp

        result = map_ingredient_to_chemical("Glycerin")
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["identity_verified"])
        self.assertTrue(result["needs_manual_review"])
        self.assertEqual(result["pubchem_cid"], 753)
        self.assertEqual(result["candidate_pubchem_cids"], [753])

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_cid_mismatch_results_in_review(self, mock_get):
        # Curated chemical ("aqua", expected CID 962), but PubChem returns different CID (e.g. 99999)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 99999,
                        "ConnectivitySMILES": "O",
                        "MolecularFormula": "H2O",
                        "MolecularWeight": "18.015",
                        "IUPACName": "oxidane",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp

        result = map_ingredient_to_chemical("Aqua")
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["identity_verified"])
        self.assertTrue(result["needs_manual_review"])

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_pubchem_not_found_vs_api_error(self, mock_get):
        # 404 returns not_found
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_get.return_value = mock_resp_404

        result_nf = map_ingredient_to_chemical("definitely_not_a_real_chemical_12345")
        self.assertEqual(result_nf["status"], "not_found")
        self.assertFalse(result_nf["identity_verified"])

        # Timeout returns api_error
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        result_to = map_ingredient_to_chemical("ChemicalWithTimeout")
        self.assertEqual(result_to["status"], "api_error")
        self.assertIn("timed out", result_to["message"].lower())

        # Connection error / HTTP 500 returns api_error
        mock_get.side_effect = requests.exceptions.ConnectionError("Remote end closed connection")
        result_conn = map_ingredient_to_chemical("ChemicalWithConnError")
        self.assertEqual(result_conn["status"], "api_error")

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_multiple_candidates_require_review(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {"CID": 101, "ConnectivitySMILES": "CC"},
                    {"CID": 102, "ConnectivitySMILES": "CCC"},
                ]
            }
        }
        mock_get.return_value = mock_resp
        mock_get.side_effect = None

        result = map_ingredient_to_chemical("AmbiguousChemical")
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["identity_verified"])
        self.assertEqual(result["candidate_pubchem_cids"], [101, 102])

    def test_complex_ingredients_regression(self):
        """
        Regression test: Xanthan Gum, Acacia Gum, Caprylic/Capric Triglyceride,
        C12-15 Alkyl Benzoate, and Polyacrylate Crosspolymer-6 must be classified
        as complex_mixture, not not_found or single chemicals.
        """
        test_cases = [
            "Xanthan Gum",
            "Acacia Gum",
            "Caprylic/Capric Triglyceride",
            "C12-15 Alkyl Benzoate",
            "Polyacrylate Crosspolymer-6",
        ]
        for name in test_cases:
            self.assertTrue(
                is_complex_ingredient(name),
                f"Expected is_complex_ingredient('{name}') to be True"
            )
            res = map_ingredient_to_chemical(name)
            self.assertEqual(
                res["status"],
                "complex_mixture",
                f"Expected '{name}' to have status 'complex_mixture', got '{res['status']}'"
            )
            self.assertFalse(res["identity_verified"])
            self.assertTrue(res["needs_manual_review"])
            self.assertIsNone(res["pubchem_cid"])

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_named_single_substance_with_broad_keyword_not_complex_mixture(self, mock_get):
        """
        Regression test: Do not classify an ingredient as a complex mixture
        solely because its name contains broad keywords such as 'oil' or 'gum'.
        Named single substances (e.g. Wintergreen Oil = Methyl Salicylate,
        or Gummiferin) must be distinguished.
        """
        # Case A: Wintergreen Oil contains keyword "oil" but is a named single substance (Methyl Salicylate)
        self.assertFalse(
            is_complex_ingredient("Wintergreen Oil"),
            "Wintergreen Oil must not be flagged as a complex mixture"
        )

        # Mock PubChem lookup for Wintergreen Oil / methyl salicylate alias
        def mock_call(url, *args, **kwargs):
            resp = MagicMock()
            if "methyl%20salicylate" in url.lower():
                resp.status_code = 200
                resp.json.return_value = {
                    "PropertyTable": {
                        "Properties": [
                            {
                                "CID": 4133,
                                "ConnectivitySMILES": "COC(=O)C1=CC=CC=C1O",
                                "MolecularFormula": "C8H8O3",
                                "MolecularWeight": "152.15",
                                "IUPACName": "methyl 2-hydroxybenzoate",
                            }
                        ]
                    }
                }
            else:
                resp.status_code = 404
            return resp

        mock_get.side_effect = mock_call
        res_wintergreen = map_ingredient_to_chemical("Wintergreen Oil")
        self.assertEqual(res_wintergreen["status"], "mapped")
        self.assertTrue(res_wintergreen["identity_verified"])
        self.assertEqual(res_wintergreen["pubchem_cid"], 4133)

        # Case B: Gummiferin contains substring "gum" but is a single substance
        self.assertFalse(
            is_complex_ingredient("Gummiferin"),
            "Gummiferin must not be classified as complex solely due to substring 'gum'"
        )

        mock_resp_gum = MagicMock()
        mock_resp_gum.status_code = 200
        mock_resp_gum.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 101834999,
                        "ConnectivitySMILES": "CC(C)...",
                        "MolecularFormula": "C31H44K2O18S2",
                        "MolecularWeight": "806.9",
                        "IUPACName": "dipotassium;gummiferin",
                    }
                ]
            }
        }
        mock_get.side_effect = None
        mock_get.return_value = mock_resp_gum

        res_gum = map_ingredient_to_chemical("Gummiferin")
        self.assertNotEqual(res_gum["status"], "complex_mixture")
        self.assertEqual(res_gum["status"], "needs_review")

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_unresolved_ocr_text_not_classified_as_complex_mixture(self, mock_get):
        """
        Regression test: Unresolved OCR corruptions must NOT be classified as
        complex_mixture without verified identity evidence; they must remain
        in not_found or review status.
        """
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_get.return_value = mock_404
        mock_get.side_effect = None

        # Polyacryale Cspolymer-6 is misspelled OCR text; should not be classified
        # as complex_mixture before manual correction/confirmation
        self.assertFalse(is_complex_ingredient("Polyacryale Cspolymer-6"))
        res_poly = map_ingredient_to_chemical("Polyacryale Cspolymer-6")
        self.assertEqual(res_poly["status"], "not_found")

        # Hanioin is unresolved OCR noise
        self.assertFalse(is_complex_ingredient("Hanioin"))
        res_han = map_ingredient_to_chemical("Hanioin")
        self.assertEqual(res_han["status"], "not_found")

        # Punctuation corrupted string
        noise_str = "Hydroxyethy! Acy'* Sodum Acryloyidimethyl Taurate Copolymer"
        self.assertFalse(is_complex_ingredient(noise_str))
        res_noise = map_ingredient_to_chemical(noise_str)
        self.assertEqual(res_noise["status"], "not_found")

    def test_sodium_hyaluronate_biopolymer_not_assigned_single_structure(self):
        """Sodium Hyaluronate is a biopolymer polysaccharide, not a discrete small molecule."""
        # 1. Recognized as complex material
        self.assertTrue(is_complex_ingredient("Sodium Hyaluronate"))
        self.assertTrue(is_complex_ingredient("Hyaluronic Acid"))
        self.assertTrue(is_complex_ingredient("Hyaluronic Acid, Sodium Salt"))

        # 2. Mapping routes to complex_mixture and does NOT invent a single small-molecule structure
        res = map_ingredient_to_chemical("Sodium Hyaluronate")
        self.assertEqual(res["status"], "complex_mixture")
        self.assertFalse(res["identity_verified"])
        self.assertTrue(res["needs_manual_review"])
        self.assertIsNone(res["pubchem_cid"])
        self.assertIsNone(res["connectivity_smiles"])
        self.assertIsNone(res["canonical_smiles"])
        self.assertIn("biopolymer", res["message"].lower())

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_mismatched_inchikey_or_formula_blocks_verification(self, mock_get):
        """Curated CID match is blocked if returned InChIKey or Formula conflicts with reference data."""
        # Case A: InChIKey conflict
        mock_resp_key = MagicMock()
        mock_resp_key.status_code = 200
        mock_resp_key.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 962,
                        "ConnectivitySMILES": "O",
                        "MolecularFormula": "H2O",
                        "MolecularWeight": "18.015",
                        "InChIKey": "WRONG_INCHIKEY_12345-N",
                        "IUPACName": "oxidane",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp_key
        mock_get.side_effect = None

        res_key = map_ingredient_to_chemical("Aqua")
        self.assertEqual(res_key["status"], "needs_review")
        self.assertFalse(res_key["identity_verified"])
        self.assertTrue(res_key["needs_manual_review"])
        self.assertIn("Identifier conflict", res_key["message"])
        self.assertIn("InChIKey", res_key["message"])

        # Case B: Formula conflict
        mock_resp_form = MagicMock()
        mock_resp_form.status_code = 200
        mock_resp_form.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 962,
                        "ConnectivitySMILES": "O",
                        "MolecularFormula": "CH4",
                        "MolecularWeight": "18.015",
                        "InChIKey": "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
                        "IUPACName": "oxidane",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp_form

        res_form = map_ingredient_to_chemical("Aqua")
        self.assertEqual(res_form["status"], "needs_review")
        self.assertFalse(res_form["identity_verified"])
        self.assertIn("Identifier conflict", res_form["message"])
        self.assertIn("MolecularFormula", res_form["message"])

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_missing_identifiers_blocks_verification(self, mock_get):
        """Records with missing CID or missing SMILES cannot be verified."""
        # Missing SMILES
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 962,
                        "ConnectivitySMILES": None,
                        "CanonicalSMILES": None,
                        "MolecularFormula": "H2O",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp
        mock_get.side_effect = None

        res = map_ingredient_to_chemical("Aqua")
        self.assertEqual(res["status"], "needs_review")
        self.assertFalse(res["identity_verified"])
        self.assertIn("missing a CID or molecular structure", res["message"])

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_seven_assessment_gap_candidates_remain_unverified(self, mock_get):
        """The 7 candidate substances from the assessment gap must NOT be auto-approved."""
        candidates = [
            ("Glyceryl Stearate", 24699, "CCCCCCCCCCCCCCCCCC(=O)OCC(CO)O", "glyceride"),
            ("Linoleic Acid", 5280450, "CCCCCC=CCC=CCCCCCCCC(=O)O", "isomer"),
            ("Linolenic Acid", 5280934, "CCC=CCC=CCC=CCCCCCCCC(=O)O", "isomer"),
            ("Panthenol", 4678, "CC(C)(CO)C(C(=O)NCCCO)O", "panthenol"),
            ("Tocopherol Acetate", 86472, "CC1=C(C2=C(CCC(O2)(C)CCCC(C)CCCC(C)CCCC(C)C)C(=C1C)OC(=O)C)C", "stereoisomer"),
            ("Retinol", 445354, "CC1=C(C(CCC1)(C)C)C=CC(=CC=CC(=CCO)C)C", "isomerization"),
            ("Silica", 24261, "O=[Si]=O", "polymer network"),
        ]

        for name, cid, smiles, variance_keyword in candidates:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": cid,
                            "ConnectivitySMILES": smiles,
                            "MolecularFormula": "C10H20O",
                            "MolecularWeight": "200.0",
                            "IUPACName": name,
                        }
                    ]
                }
            }
            mock_get.return_value = mock_resp
            mock_get.side_effect = None

            res = map_ingredient_to_chemical(name)
            # MUST remain needs_review with identity_verified: False
            self.assertEqual(
                res["status"],
                "needs_review",
                f"Candidate '{name}' must remain needs_review, got '{res['status']}'"
            )
            self.assertFalse(res["identity_verified"])
            self.assertTrue(res["needs_manual_review"])
            self.assertEqual(res["pubchem_cid"], cid)
            self.assertIn(variance_keyword.lower(), res["message"].lower())

    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_identifier_sources_and_retrieval_status_recorded(self, mock_get):
        """Store the source and retrieval outcome for each identifier."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 936,
                        "ConnectivitySMILES": "C1=CC(=CN=C1)C(=O)N",
                        "InChIKey": "DFPAKSUCGFBDDF-UHFFFAOYSA-N",
                        "InChI": "InChI=1S/C6H6N2O/c7-6(9)5-2-1-3-8-4-5/h1-4H,(H2,7,9)",
                        "MolecularFormula": "C6H6N2O",
                        "MolecularWeight": "122.12",
                        "IUPACName": "pyridine-3-carboxamide",
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp
        mock_get.side_effect = None

        res = map_ingredient_to_chemical("Niacinamide")
        self.assertEqual(res["status"], "mapped")
        self.assertTrue(res["identity_verified"])

        # Check identifier_sources dictionary
        sources = res["identifier_sources"]
        self.assertIn("pubchem_cid", sources)
        self.assertIn("connectivity_smiles", sources)
        self.assertIn("canonical_smiles", sources)
        self.assertIn("inchikey", sources)
        self.assertIn("inchi", sources)
        self.assertIn("molecular_formula", sources)
        self.assertIn("molecular_weight", sources)
        self.assertIn("iupac_name", sources)
        self.assertIn("cas_number", sources)

        self.assertEqual(sources["pubchem_cid"]["status"], "retrieved")
        self.assertEqual(sources["inchikey"]["status"], "retrieved")
        self.assertEqual(sources["molecular_formula"]["status"], "retrieved")
        self.assertEqual(sources["cas_number"]["status"], "retrieved")
        self.assertEqual(res["cas_number"], "98-92-0")

        # Check retrieval_status summary dictionary
        retrieval = res["retrieval_status"]
        self.assertEqual(retrieval["status"], "success")
        self.assertTrue(retrieval["structure_retrieved"])
        self.assertTrue(retrieval["identifiers_complete"])


if __name__ == "__main__":
    unittest.main()
