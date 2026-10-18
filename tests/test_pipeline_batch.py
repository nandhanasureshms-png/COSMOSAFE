import unittest
from unittest.mock import patch, MagicMock
import sys
import json
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from integration.reviewed_label_pipeline import screen_reviewed_ingredients
from integration.structured_report import build_structured_report, validate_report_consistency


# The original 32 ingredients list from the project's dataset
ORIGINAL_32_INGREDIENTS = [
    "Aqua",
    "Octocrylene",
    "Diisopropy| Adipate",
    "Propylene Giycx Seanrylate/Dicaprate",
    "C12-15 Alkyl Benzoate",
    "Diisopropyl Sebacate",
    "Buty Wehoxydibenzoylmethane",
    "Isododecane",
    "Niacinamide",
    "Arachidy| Alcoho! Sehenyi Alcohol",
    "Arachidy! Glucoside",
    "Caprylic/Capric Triglyceride",
    "Titanium Doxide",
    "Ethylhexyi Triazone",
    "PEG-100 Stearate",
    "Glyceryl Stearate",
    "Butyl Gyoo",
    "Linoleic Acid",
    "Linolenic Acid",
    "Panthenol",
    "Sodium Hyaluronate",
    "Hanioin",
    "Tocopherol Acetate",
    "Retinol",
    "Polysorbate 20",
    "Hydroxyethy! Acy'* Sodum Acryloyidimethyl Taurate Copolymer",
    "Xanthan Gum",
    "Polyacryale Cspolymer-6",
    "Silica",
    "Acacia Gum",
    "Phenoxyethanol",
    "Ethylhexyigyoe\" \\sotium Ethylenediamine Disuccinate Wine = ee",
]


class TestPipelineBatch(unittest.TestCase):
    @patch("chemical_identity.pubchem_mapper.requests.get")
    def test_32_inputs_produce_32_records_and_correct_counts(self, mock_get):
        """
        Simulate the exact 32 ingredients with deterministic mocked PubChem responses:
        - 5 Curated verified matches (Aqua, Octocrylene, Diisopropyl Sebacate, Isododecane, Niacinamide)
        - 8 Candidates needing review (Glyceryl Stearate, Linoleic Acid, Linolenic Acid, Panthenol,
          Tocopherol Acetate, Retinol, Silica, Phenoxyethanol)
        - 1 API failure (Arachidy! Glucoside)
        - 18 Not found
        """
        verified_cids = {
            "Aqua": (962, "O"),
            "Octocrylene": (22571, "CCCCC(CC)COC(=O)C(=C(C1=CC=CC=C1)C2=CC=CC=C2)C#N"),
            "Diisopropyl Sebacate": (24096, "CC(C)OC(=O)CCCCCCCCC(=O)OC(C)C"),
            "Isododecane": (23459, "CC(C)CC(C)(C)CC(C)(C)C"),
            "Niacinamide": (936, "C1=CC(=CN=C1)C(=O)N"),
        }

        review_cids = {
            "Glyceryl Stearate": (24699, "CCCCCCCCCCCCCCCCCC(=O)OCC(CO)O"),
            "Linoleic Acid": (5280450, "CCCCCC=CCC=CCCCCCCCC(=O)O"),
            "Linolenic Acid": (5280934, "CCC=CCC=CCC=CCCCCCCCC(=O)O"),
            "Panthenol": (4678, "CC(C)(CO)C(C(=O)NCCCO)O"),
            "Tocopherol Acetate": (86472, "CC1=C(C2=C(CCC(O2)(C)CCCC(C)CCCC(C)CCCC(C)C)C(=C1C)OC(=O)C)C"),
            "Retinol": (445354, "CC1=C(C(CCC1)(C)C)C=CC(=CC=CC(=CCO)C)C"),
            "Silica": (24261, "O=[Si]=O"),
            "Phenoxyethanol": (31236, "C1=CC=C(C=C1)OCCO"),
        }

        def mock_pubchem_call(url, timeout=15):
            from urllib.parse import unquote
            unquoted_url = unquote(url).lower()

            for name, (cid, smiles) in verified_cids.items():
                if name.lower() in unquoted_url:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "PropertyTable": {
                            "Properties": [
                                {
                                    "CID": cid,
                                    "ConnectivitySMILES": smiles,
                                    "MolecularFormula": "C",
                                    "MolecularWeight": "100.0",
                                    "IUPACName": name,
                                }
                            ]
                        }
                    }
                    return resp

            for name, (cid, smiles) in review_cids.items():
                if name.lower() in unquoted_url:
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.json.return_value = {
                        "PropertyTable": {
                            "Properties": [
                                {
                                    "CID": cid,
                                    "ConnectivitySMILES": smiles,
                                    "MolecularFormula": "C",
                                    "MolecularWeight": "100.0",
                                    "IUPACName": name,
                                }
                            ]
                        }
                    }
                    return resp

            if "arachidy" in url.lower() and "glucoside" in url.lower():
                import requests
                raise requests.exceptions.ConnectionError("PubChem remote end closed connection")

            # Default 404 for the remaining 18 OCR-misspelled or unknown ingredients
            resp_404 = MagicMock()
            resp_404.status_code = 404
            return resp_404

        mock_get.side_effect = mock_pubchem_call

        results = screen_reviewed_ingredients(ORIGINAL_32_INGREDIENTS)

        # 1. 32 inputs produce 32 result records
        self.assertEqual(len(results), 32)

        report = build_structured_report(results)
        summary = report["summary"]

        # 2. Total processed is 32
        self.assertEqual(summary["ingredients_processed"], 32)

        # 3. Primary status counts sum to 32
        status_counts = summary["primary_status_counts"]
        self.assertEqual(status_counts["verified"], 5)
        self.assertEqual(status_counts["needs_review"], 8)
        self.assertEqual(status_counts["not_found"], 11)
        self.assertEqual(status_counts["api_error"], 1)
        self.assertEqual(status_counts["complex_mixture"], 7)
        self.assertEqual(status_counts["invalid_input"], 0)
        self.assertEqual(sum(status_counts.values()), 32)

        # 4. Candidates found is 13 (5 verified + 8 review)
        self.assertEqual(summary["pubchem_candidate_records_found"], 13)

        # 5. Screened is 5, not assessed is 27
        self.assertEqual(summary["ingredients_screened"], 5)
        self.assertEqual(summary["ingredients_not_assessed"], 27)

        # 6. Not assessed reasons sum to 27
        not_assessed = summary["not_assessed_reasons"]
        self.assertEqual(not_assessed["identity_needs_review"], 8)
        self.assertEqual(not_assessed["chemical_not_found"], 11)
        self.assertEqual(not_assessed["pubchem_api_error"], 1)
        self.assertEqual(not_assessed["complex_mixture"], 7)
        self.assertEqual(sum(not_assessed.values()), 27)

        # 7. Consistency validation passes
        self.assertTrue(validate_report_consistency(report))

    def test_duplicate_and_blank_handling_in_batch(self):
        batch = [
            "Aqua",
            "",
            "   ",
            "Aqua",
            "Niacinamide",
        ]
        # Should not drop blank entries or duplicates
        results = screen_reviewed_ingredients(batch)
        self.assertEqual(len(results), 5)

        report = build_structured_report(results)
        self.assertEqual(report["summary"]["ingredients_processed"], 5)
        self.assertEqual(report["summary"]["primary_status_counts"]["invalid_input"], 2)
        self.assertEqual(report["summary"]["primary_status_counts"]["verified"], 3)
        self.assertEqual(sum(report["summary"]["primary_status_counts"].values()), 5)
        self.assertTrue(validate_report_consistency(report))


if __name__ == "__main__":
    unittest.main()
