import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from normalization.ingredient_corrections import (
    detect_ocr_anomalies,
    propose_ingredient_correction,
    confirm_correction,
    reject_correction,
    analyze_ocr_ingredient_list,
    KNOWN_OCR_CORRECTIONS,
    VALID_REVIEW_STATUSES,
)


class TestIngredientCorrections(unittest.TestCase):
    def test_detect_ocr_anomalies(self):
        # Empty input
        self.assertEqual(detect_ocr_anomalies(""), ["empty_or_blank"])
        self.assertEqual(detect_ocr_anomalies("   "), ["empty_or_blank"])

        # Pipe character
        pipe_anomalies = detect_ocr_anomalies("Diisopropy| Adipate")
        self.assertIn("pipe_character", pipe_anomalies)

        # Exclamation mark
        excl_anomalies = detect_ocr_anomalies("Arachidy! Glucoside")
        self.assertIn("exclamation_mark", excl_anomalies)

        # Misplaced symbols (*, ^, ~)
        sym_anomalies = detect_ocr_anomalies("Hydroxyethy! Acy'* Sodum")
        self.assertIn("misplaced_symbols", sym_anomalies)
        self.assertIn("exclamation_mark", sym_anomalies)

        # Trailing OCR noise
        noise_anomalies = detect_ocr_anomalies('Ethylhexyigyoe" \\sotium Wine = ee')
        self.assertIn("trailing_ocr_noise", noise_anomalies)

        # Clean string
        clean_anomalies = detect_ocr_anomalies("Niacinamide")
        self.assertEqual(clean_anomalies, [])

    def test_propose_known_corruptions(self):
        # 1. Pipe character substitution
        res1 = propose_ingredient_correction("Diisopropy| Adipate")
        self.assertEqual(res1["original_name"], "Diisopropy| Adipate")
        self.assertTrue(res1["has_correction_proposal"])
        self.assertEqual(res1["proposed_name"], "Diisopropyl Adipate")
        self.assertEqual(res1["corruption_type"], "character_substitution")
        self.assertEqual(res1["confidence"], "high")
        self.assertTrue(res1["review_required"])
        self.assertEqual(res1["expected_cid"], 23368)

        # 2. Misspelling / OCR typo
        res2 = propose_ingredient_correction("Buty Wehoxydibenzoylmethane")
        self.assertTrue(res2["has_correction_proposal"])
        self.assertEqual(res2["proposed_name"], "Butyl Methoxydibenzoylmethane")
        self.assertEqual(res2["corruption_type"], "ocr_misspelling")
        self.assertEqual(res2["expected_cid"], 51040)

        # 3. Truncation
        res3 = propose_ingredient_correction("Butyl Gyoo")
        self.assertTrue(res3["has_correction_proposal"])
        self.assertEqual(res3["proposed_name"], "Butylene Glycol")

        # 4. Unresolved OCR noise
        res4 = propose_ingredient_correction("Hanioin")
        self.assertFalse(res4["has_correction_proposal"])
        self.assertIsNone(res4["proposed_name"])
        self.assertEqual(res4["corruption_type"], "unresolved_ocr_noise")

    def test_clean_and_empty_inputs(self):
        # Clean input
        res_clean = propose_ingredient_correction("Niacinamide")
        self.assertEqual(res_clean["original_name"], "Niacinamide")
        self.assertFalse(res_clean["has_correction_proposal"])
        self.assertIsNone(res_clean["proposed_name"])
        self.assertEqual(res_clean["corruption_type"], "none_detected")
        self.assertEqual(res_clean["confidence"], "high")

        # Empty / None input
        res_none = propose_ingredient_correction(None)
        self.assertFalse(res_none["has_correction_proposal"])
        self.assertEqual(res_none["corruption_type"], "empty_input")

    def test_heuristic_pipe_character_handling(self):
        # Uncataloged string with pipe character
        res_heuristic = propose_ingredient_correction("Methy|paraben")
        self.assertTrue(res_heuristic["has_correction_proposal"])
        self.assertEqual(res_heuristic["proposed_name"], "Methylparaben")
        self.assertEqual(res_heuristic["corruption_type"], "character_substitution")
        self.assertTrue(res_heuristic["review_required"])

    def test_analyze_ocr_ingredient_list_preserves_length(self):
        items = ["Aqua", "Diisopropy| Adipate", "Niacinamide", ""]
        proposals = analyze_ocr_ingredient_list(items)
        self.assertEqual(len(proposals), len(items))
        self.assertEqual(proposals[0]["original_name"], "Aqua")
        self.assertEqual(proposals[1]["original_name"], "Diisopropy| Adipate")

    def test_preservation_of_original_text_and_separation(self):
        """Preserve raw OCR verbatim, separate normalized and proposed text, record full provenance."""
        raw_input = "  Diisopropy| Adipate  "
        proposal = propose_ingredient_correction(raw_input)

        # 1. Exact raw text preserved verbatim
        self.assertEqual(proposal["original_text"], "Diisopropy| Adipate")
        self.assertEqual(proposal["original_name"], "Diisopropy| Adipate")

        # 2. Normalized text and proposed correction stored separately
        self.assertEqual(proposal["normalized_text"], "diisopropy| adipate")
        self.assertEqual(proposal["proposed_name"], "Diisopropyl Adipate")
        self.assertNotEqual(proposal["original_text"], proposal["proposed_name"])

        # 3. Provenance and review tracking metadata recorded
        self.assertEqual(proposal["corruption_type"], "character_substitution")
        self.assertTrue(bool(proposal["correction_rationale"]))
        self.assertIn("INCI", proposal["evidence_source"])
        self.assertEqual(proposal["confidence"], "high")
        self.assertTrue(bool(proposal["uncertainty_notes"]))

        # 4. By default, review status is 'proposed' and NOT confirmed
        self.assertEqual(proposal["review_status"], "proposed")
        self.assertFalse(proposal["is_confirmed"])
        self.assertIsNone(proposal["reviewed_by"])
        self.assertIsNone(proposal["reviewer_notes"])

    def test_correction_review_states_and_transitions(self):
        """Test proposed, confirmed, and rejected review states with explicit reviewer actions."""
        raw = "Buty Wehoxydibenzoylmethane"
        proposal = propose_ingredient_correction(raw)

        # Initial state is strictly 'proposed'
        self.assertEqual(proposal["review_status"], "proposed")
        self.assertFalse(proposal["is_confirmed"])

        # Confirm correction explicitly
        confirmed = confirm_correction(proposal, reviewer="Safety Assessor Dr. Rao", notes="Verified against product dossier.")
        self.assertEqual(confirmed["review_status"], "confirmed")
        self.assertTrue(confirmed["is_confirmed"])
        self.assertEqual(confirmed["reviewed_by"], "Safety Assessor Dr. Rao")
        self.assertIn("Verified", confirmed["reviewer_notes"])
        self.assertFalse(confirmed["review_required"])

        # Original proposal dictionary is not mutated
        self.assertEqual(proposal["review_status"], "proposed")
        self.assertFalse(proposal["is_confirmed"])

        # Reject correction explicitly
        rejected = reject_correction(proposal, reviewer="Safety Assessor Dr. Rao", reason="Alternative active filter suspected.")
        self.assertEqual(rejected["review_status"], "rejected")
        self.assertFalse(rejected["is_confirmed"])
        self.assertEqual(rejected["reviewed_by"], "Safety Assessor Dr. Rao")
        self.assertEqual(rejected["reviewer_notes"], "Alternative active filter suspected.")

        # Rejection/Confirmation guardrails
        with self.assertRaises(ValueError):
            # Cannot confirm without reviewer
            confirm_correction(proposal, reviewer="")

        with self.assertRaises(ValueError):
            # Cannot reject without reason
            reject_correction(proposal, reviewer="Dr. Rao", reason="")

        # Cannot confirm an unresolvable noise string with no proposed name
        noise_proposal = propose_ingredient_correction("Hanioin")
        with self.assertRaises(ValueError):
            confirm_correction(noise_proposal, reviewer="Dr. Rao")

    def test_merged_ingredients_handling(self):
        """Test identification and transparent flagging of concatenated/merged ingredients."""
        # Case 1: Fatty alcohol blend
        merged1 = propose_ingredient_correction("Arachidy| Alcoho! Sehenyi Alcohol")
        self.assertTrue(merged1["has_correction_proposal"])
        self.assertEqual(merged1["proposed_name"], "Arachidyl Alcohol / Behenyl Alcohol")
        self.assertEqual(merged1["corruption_type"], "merged_tokens_and_substitution")
        self.assertEqual(merged1["confidence"], "medium")
        self.assertIn("Represents TWO discrete chemical substances", merged1["uncertainty_notes"])
        self.assertIsNone(merged1["expected_cid"])

        # Case 2: Preservative blend with trailing noise
        merged2 = propose_ingredient_correction('Ethylhexyigyoe" \\sotium Ethylenediamine Disuccinate Wine = ee')
        self.assertTrue(merged2["has_correction_proposal"])
        self.assertEqual(merged2["proposed_name"], "Ethylhexylglycerin / Trisodium Ethylenediamine Disuccinate")
        self.assertEqual(merged2["corruption_type"], "merged_tokens_and_noise")
        self.assertEqual(merged2["confidence"], "medium")
        self.assertIn("Token splitting required", merged2["uncertainty_notes"])

    def test_ambiguous_corrections_not_silently_converted(self):
        """Unresolved OCR noise must NOT propose speculative names or auto-confirm."""
        ambiguous = propose_ingredient_correction("Hanioin")
        self.assertFalse(ambiguous["has_correction_proposal"])
        self.assertIsNone(ambiguous["proposed_name"])
        self.assertEqual(ambiguous["corruption_type"], "unresolved_ocr_noise")
        self.assertEqual(ambiguous["confidence"], "low")
        self.assertIn("Ambiguous corruption", ambiguous["uncertainty_notes"])
        self.assertEqual(ambiguous["review_status"], "proposed")
        self.assertFalse(ambiguous["is_confirmed"])

    def test_corrupted_text_types(self):
        """Test various OCR corruption types (punctuation noise, typos, glyph substitutions)."""
        # Glyph substitution with exclamation mark
        res_excl = propose_ingredient_correction("arachidy! glucoside")
        self.assertTrue(res_excl["has_correction_proposal"])
        self.assertEqual(res_excl["proposed_name"], "Arachidyl Glucoside")
        self.assertEqual(res_excl["corruption_type"], "character_substitution")

        # Typo
        res_typo = propose_ingredient_correction("titanium doxide")
        self.assertTrue(res_typo["has_correction_proposal"])
        self.assertEqual(res_typo["proposed_name"], "Titanium Dioxide")
        self.assertEqual(res_typo["corruption_type"], "ocr_misspelling")

        # Complex copolymer with symbol noise
        res_poly = propose_ingredient_correction("hydroxyethy! acy'* sodum acryloyidimethyl taurate copolymer")
        self.assertTrue(res_poly["has_correction_proposal"])
        self.assertEqual(res_poly["proposed_name"], "Hydroxyethyl Acrylate/Sodium Acryloyldimethyl Taurate Copolymer")
        self.assertEqual(res_poly["corruption_type"], "ocr_noise_and_substitution")


if __name__ == "__main__":
    unittest.main()
