"""
CosmoSafe Ingredient Name Correction Module.

Provides reviewable, transparent identification of OCR corruptions
(pipe characters, misplaced punctuation, OCR misspellings, truncations, and merged entries).
Preserves the original OCR text exactly and NEVER silently applies uncertain corrections.
"""

from typing import Optional, Dict, Any, List
import re


VALID_REVIEW_STATUSES = {"proposed", "confirmed", "rejected"}

# Reviewable catalog of known OCR artifacts identified on cosmetic labels
KNOWN_OCR_CORRECTIONS: Dict[str, Dict[str, Any]] = {
    "diisopropy| adipate": {
        "proposed_name": "Diisopropyl Adipate",
        "corruption_type": "character_substitution",
        "correction_rationale": "Pipe character '|' substituted for letter 'l'.",
        "evidence_source": "INCI Standard Monograph: Diisopropyl Adipate (CAS 6938-94-9, PubChem CID 23368); common cosmetic ester emollient.",
        "confidence": "high",
        "uncertainty_notes": "Unambiguous single-character glyph substitution in standard sunscreen ester.",
        "expected_cid": 23368,
        "description": "Pipe character '|' substituted for 'l'.",
    },
    "propylene giycx seanrylate/dicaprate": {
        "proposed_name": "Propylene Glycol Dicaprylate/Dicaprate",
        "corruption_type": "ocr_misspelling",
        "correction_rationale": "Typographical errors 'giycx' -> 'glycol' and 'seanrylate' -> 'dicaprylate'.",
        "evidence_source": "INCI Standard Monograph: Propylene Glycol Dicaprylate/Dicaprate (CAS 68583-52-8 / 7384-98-7); formulation diester vehicle.",
        "confidence": "high",
        "uncertainty_notes": "High confidence for cosmetic sunscreen vehicle; composition is a diester mixture.",
        "expected_cid": None,  # Diester mixture / UVCB
        "description": "'giycx' -> 'glycol', 'seanrylate' -> 'dicaprylate'.",
    },
    "buty wehoxydibenzoylmethane": {
        "proposed_name": "Butyl Methoxydibenzoylmethane",
        "corruption_type": "ocr_misspelling",
        "correction_rationale": "Leading truncation 'Buty' -> 'Butyl' and OCR typo 'Wehoxydibenzoylmethane' -> 'Methoxydibenzoylmethane'.",
        "evidence_source": "INCI Standard Monograph: Butyl Methoxydibenzoylmethane (Avobenzone, CAS 70356-09-1, PubChem CID 51040); ubiquitous UVA filter.",
        "confidence": "high",
        "uncertainty_notes": "Unambiguous UVA sunscreen active.",
        "expected_cid": 51040,
        "description": "'Buty' -> 'Butyl', 'Wehoxydibenzoylmethane' -> 'Methoxydibenzoylmethane'.",
    },
    "arachidy| alcoho! sehenyi alcohol": {
        "proposed_name": "Arachidyl Alcohol / Behenyl Alcohol",
        "corruption_type": "merged_tokens_and_substitution",
        "correction_rationale": "Two separate cosmetic fatty alcohol ingredients merged by OCR segmentation error, with glyph substitutions '|' and '!' for 'l'.",
        "evidence_source": "CIR Cosmetic Ingredient Review: Arachidyl Alcohol (CAS 629-96-9) & Behenyl Alcohol (CAS 661-19-8); common commercial co-emulsifier blend.",
        "confidence": "medium",
        "uncertainty_notes": "Represents TWO discrete chemical substances concatenated into a single label entry. Requires token splitting before individual chemical mapping.",
        "expected_cid": None,
        "description": "Merged entries with pipe '|' and exclamation '!'. Intended: Arachidyl Alcohol and Behenyl Alcohol.",
    },
    "arachidy| glucoside": {
        "proposed_name": "Arachidyl Glucoside",
        "corruption_type": "character_substitution",
        "correction_rationale": "Pipe character '|' substituted for letter 'l'.",
        "evidence_source": "INCI Standard Monograph: Arachidyl Glucoside (CAS 100231-68-3, PubChem CID 9933984); non-ionic surfactant/emulsifier.",
        "confidence": "high",
        "uncertainty_notes": "Single glyph substitution in standard cosmetic glucoside.",
        "expected_cid": 9933984,
        "description": "Pipe character '|' or exclamation mark substituted for 'l'.",
    },
    "arachidy! glucoside": {
        "proposed_name": "Arachidyl Glucoside",
        "corruption_type": "character_substitution",
        "correction_rationale": "Exclamation mark '!' substituted for letter 'l'.",
        "evidence_source": "INCI Standard Monograph: Arachidyl Glucoside (CAS 100231-68-3, PubChem CID 9933984); non-ionic surfactant/emulsifier.",
        "confidence": "high",
        "uncertainty_notes": "Single glyph substitution in standard cosmetic glucoside.",
        "expected_cid": 9933984,
        "description": "Exclamation mark '!' substituted for 'l'.",
    },
    "titanium doxide": {
        "proposed_name": "Titanium Dioxide",
        "corruption_type": "ocr_misspelling",
        "correction_rationale": "Missing letter 'i' in 'Doxide'.",
        "evidence_source": "INCI Standard Monograph: Titanium Dioxide (CAS 13463-67-7, PubChem CID 26042); standard physical UV filter.",
        "confidence": "high",
        "uncertainty_notes": "Unambiguous mineral sunscreen active.",
        "expected_cid": 26042,
        "description": "Missing letter 'i' in 'Doxide'.",
    },
    "ethylhexyi triazone": {
        "proposed_name": "Ethylhexyl Triazone",
        "corruption_type": "character_substitution",
        "correction_rationale": "Letter 'i' substituted for letter 'l' in 'Ethylhexyi'.",
        "evidence_source": "INCI Standard Monograph: Ethylhexyl Triazone (Octyltriazone, CAS 88122-99-0, PubChem CID 11154508); UVB chemical filter.",
        "confidence": "high",
        "uncertainty_notes": "Unambiguous cosmetic UV filter.",
        "expected_cid": 11154508,
        "description": "'i' substituted for 'l' in 'Ethylhexyi'.",
    },
    "butyl gyoo": {
        "proposed_name": "Butylene Glycol",
        "corruption_type": "ocr_truncation",
        "correction_rationale": "Truncation of 'glycol' into 'gyoo'.",
        "evidence_source": "INCI Standard Monograph: Butylene Glycol (1,3-Butanediol, CAS 107-88-0, PubChem CID 9464); standard cosmetic humectant.",
        "confidence": "medium",
        "uncertainty_notes": "Moderate confidence based on cosmetic formulation context; packaging reinspection recommended.",
        "expected_cid": 9464,
        "description": "'gyoo' is an OCR truncation of glycol.",
    },
    "hanioin": {
        "proposed_name": None,
        "corruption_type": "unresolved_ocr_noise",
        "correction_rationale": "Heavily distorted OCR character sequence with multiple possible interpretations.",
        "evidence_source": "No confident dictionary match. Plausible candidates: Allantoin (CAS 97-59-6), Inulin (CAS 9005-80-5).",
        "confidence": "low",
        "uncertainty_notes": "Ambiguous corruption: cannot determine true chemical identity without physical label inspection.",
        "expected_cid": None,
        "description": "Heavily distorted OCR string. Candidate possibilities include Allantoin or Inulin, requires label reinspection.",
    },
    "hydroxyethy! acy'* sodum acryloyidimethyl taurate copolymer": {
        "proposed_name": "Hydroxyethyl Acrylate/Sodium Acryloyldimethyl Taurate Copolymer",
        "corruption_type": "ocr_noise_and_substitution",
        "correction_rationale": "Punctuation noise ('!', ''*') and OCR typos in synthetic copolymer name.",
        "evidence_source": "INCI Standard Monograph: Hydroxyethyl Acrylate/Sodium Acryloyldimethyl Taurate Copolymer (CAS 111286-86-3); synthetic rheology modifier.",
        "confidence": "high",
        "uncertainty_notes": "Identifies a synthetic polymer material; single chemical structure does not exist.",
        "expected_cid": None,
        "description": "Punctuation noise ('!', ''*') and typos in synthetic copolymer mixture.",
    },
    "polyacryale cspolymer-6": {
        "proposed_name": "Polyacrylate Crosspolymer-6",
        "corruption_type": "ocr_misspelling",
        "correction_rationale": "Typos 'polyacryale' -> 'polyacrylate' and 'cspolymer' -> 'crosspolymer'.",
        "evidence_source": "INCI Standard Monograph: Polyacrylate Crosspolymer-6; synthetic crosslinked polymer gelling agent.",
        "confidence": "high",
        "uncertainty_notes": "Identifies a synthetic polymer material; single chemical structure does not exist.",
        "expected_cid": None,
        "description": "'polyacryale' -> 'polyacrylate', 'cspolymer-6' -> 'crosspolymer-6'.",
    },
    'ethylhexyigyoe" \\sotium ethylenediamine disuccinate wine = ee': {
        "proposed_name": "Ethylhexylglycerin / Trisodium Ethylenediamine Disuccinate",
        "corruption_type": "merged_tokens_and_noise",
        "correction_rationale": "Merged ingredient tokens with OCR noise and trailing junk text ('Wine = ee').",
        "evidence_source": "INCI Standard Monographs: Ethylhexylglycerin (CAS 70445-33-9) and Trisodium Ethylenediamine Disuccinate (CAS 178949-82-9); common preservative booster and chelating agent pair.",
        "confidence": "medium",
        "uncertainty_notes": "Represents TWO discrete ingredients with trailing label artifact noise. Token splitting required.",
        "expected_cid": None,
        "description": "Merged ingredients with trailing noise ('Wine = ee'). Intended: Ethylhexylglycerin and Trisodium Ethylenediamine Disuccinate.",
    },
}


def detect_ocr_anomalies(raw_name: str) -> List[str]:
    """Flag suspicious OCR artifacts in raw ingredient string."""
    anomalies = []
    if not raw_name or not str(raw_name).strip():
        return ["empty_or_blank"]

    text = str(raw_name).strip()

    if "|" in text:
        anomalies.append("pipe_character")
    if "!" in text:
        anomalies.append("exclamation_mark")
    if "*" in text or "^" in text or "~" in text:
        anomalies.append("misplaced_symbols")
    if "\\" in text or "/" in text and len(text.split("/")) > 2:
        anomalies.append("excessive_slashes")
    if re.search(r"[a-z][A-Z]", text):
        anomalies.append("camel_case_or_broken_spacing")
    if re.search(r"=\s*[a-zA-Z]+", text):
        anomalies.append("trailing_ocr_noise")
    if '"' in text or "'" in text:
        anomalies.append("suspicious_quotes")

    return anomalies


def propose_ingredient_correction(raw_name: Optional[str]) -> Dict[str, Any]:
    """
    Generate a reviewable correction proposal for an ingredient name.
    Does NOT silently apply the correction; stores original and proposal separately.
    By default, review_status is 'proposed' and is_confirmed is False.
    """
    if raw_name is None or not str(raw_name).strip():
        return {
            "original_text": raw_name,
            "original_name": raw_name,
            "normalized_text": "",
            "has_correction_proposal": False,
            "proposed_name": None,
            "corruption_type": "empty_input",
            "correction_rationale": "Input is missing or whitespace.",
            "evidence_source": "Input validation",
            "confidence": "none",
            "uncertainty_notes": "No input provided to evaluate.",
            "review_status": "proposed",
            "reviewed_by": None,
            "reviewer_notes": None,
            "is_confirmed": False,
            "anomalies": ["empty_input"],
            "expected_cid": None,
            "review_required": True,
            "notes": "Input is missing or whitespace.",
        }

    raw_str = str(raw_name).strip()
    normalized_key = re.sub(r"\s+", " ", raw_str.lower())
    anomalies = detect_ocr_anomalies(raw_str)

    known = KNOWN_OCR_CORRECTIONS.get(normalized_key)
    if known:
        rationale = known.get("correction_rationale") or known["description"]
        return {
            "original_text": raw_str,
            "original_name": raw_str,
            "normalized_text": normalized_key,
            "has_correction_proposal": known["proposed_name"] is not None,
            "proposed_name": known["proposed_name"],
            "corruption_type": known["corruption_type"],
            "correction_rationale": rationale,
            "evidence_source": known.get("evidence_source", "Curated cosmetic OCR dictionary"),
            "confidence": known["confidence"],
            "uncertainty_notes": known.get("uncertainty_notes", "Review recommended before scientific confirmation."),
            "review_status": "proposed",
            "reviewed_by": None,
            "reviewer_notes": None,
            "is_confirmed": False,
            "anomalies": anomalies,
            "expected_cid": known.get("expected_cid"),
            "review_required": True,
            "notes": rationale,
        }

    # Heuristic pipe substitution check
    if "|" in raw_str:
        heuristic_fix = raw_str.replace("|", "l")
        rationale = "Automated detection: pipe '|' character replaced with 'l'."
        return {
            "original_text": raw_str,
            "original_name": raw_str,
            "normalized_text": normalized_key,
            "has_correction_proposal": True,
            "proposed_name": heuristic_fix,
            "corruption_type": "character_substitution",
            "correction_rationale": rationale,
            "evidence_source": "Common OCR character glyph substitution heuristic (pipe -> letter l)",
            "confidence": "medium",
            "uncertainty_notes": "Heuristic proposal; requires human confirmation before scientific adoption.",
            "review_status": "proposed",
            "reviewed_by": None,
            "reviewer_notes": None,
            "is_confirmed": False,
            "anomalies": anomalies,
            "expected_cid": None,
            "review_required": True,
            "notes": rationale,
        }

    rationale = "No obvious OCR corruption detected." if not anomalies else f"Anomalies detected: {', '.join(anomalies)}"
    return {
        "original_text": raw_str,
        "original_name": raw_str,
        "normalized_text": normalized_key,
        "has_correction_proposal": False,
        "proposed_name": None,
        "corruption_type": "none_detected" if not anomalies else "unresolved_anomalies",
        "correction_rationale": rationale,
        "evidence_source": "Label OCR inspection",
        "confidence": "high" if not anomalies else "low",
        "uncertainty_notes": "Unresolved OCR artifacts require manual verification." if anomalies else "Clean INCI text.",
        "review_status": "proposed",
        "reviewed_by": None,
        "reviewer_notes": None,
        "is_confirmed": False,
        "anomalies": anomalies,
        "expected_cid": None,
        "review_required": bool(anomalies),
        "notes": rationale,
    }


def confirm_correction(proposal: Dict[str, Any], reviewer: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Explicitly confirm a proposed correction by a human reviewer.
    A correction is NEVER treated as confirmed unless this explicit action occurs.
    """
    if not isinstance(proposal, dict):
        raise TypeError("Proposal must be a dictionary.")
    if not proposal.get("has_correction_proposal") or not proposal.get("proposed_name"):
        raise ValueError("Cannot confirm a correction proposal that has no proposed name.")
    if not reviewer or not str(reviewer).strip():
        raise ValueError("Reviewer identity is required to confirm a correction.")

    updated = dict(proposal)
    updated["review_status"] = "confirmed"
    updated["is_confirmed"] = True
    updated["reviewed_by"] = str(reviewer).strip()
    updated["reviewer_notes"] = notes or "Correction confirmed by reviewer."
    updated["review_required"] = False
    return updated


def reject_correction(proposal: Dict[str, Any], reviewer: str, reason: str) -> Dict[str, Any]:
    """
    Explicitly reject a proposed correction by a human reviewer.
    """
    if not isinstance(proposal, dict):
        raise TypeError("Proposal must be a dictionary.")
    if not reviewer or not str(reviewer).strip():
        raise ValueError("Reviewer identity is required to reject a correction.")
    if not reason or not str(reason).strip():
        raise ValueError("Rejection reason is required.")

    updated = dict(proposal)
    updated["review_status"] = "rejected"
    updated["is_confirmed"] = False
    updated["reviewed_by"] = str(reviewer).strip()
    updated["reviewer_notes"] = str(reason).strip()
    updated["review_required"] = True
    return updated


def analyze_ocr_ingredient_list(raw_ingredients: List[str]) -> List[Dict[str, Any]]:
    """Analyze a batch of OCR ingredients and return reviewable correction proposals."""
    return [propose_ingredient_correction(item) for item in raw_ingredients]
