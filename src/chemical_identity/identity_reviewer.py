"""
CosmoSafe Identity Review Registry Module.

Generates a review list for all ingredients requiring chemical identity verification.
Includes original name, proposed corrected name (if any), candidate chemical identity,
PubChem CID, review reason, evidence, and review status.

Does NOT modify CURATED_CIDS or auto-approve unverified identities.
"""

from pathlib import Path
from typing import List, Dict, Any
import json

from normalization.ingredient_corrections import propose_ingredient_correction


BASE_DIR = Path(__file__).resolve().parents[2]
REVIEW_OUTPUT_PATH = BASE_DIR / "reports" / "toxicity" / "ingredient_identity_review.json"


def generate_identity_review_registry(ingredient_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a comprehensive review list for all ingredients requiring manual review.
    Does NOT auto-approve candidates or alter curated configurations.
    """
    pending_reviews = []
    verified_entries = []

    for item in ingredient_results:
        raw_name = item.get("raw_ingredient")
        mapping = item.get("mapping_result") or item.get("mapping") or {}
        toxicity = item.get("toxicity_result") or item.get("toxicity") or {}

        primary_status = item.get("primary_status") or mapping.get("status")
        identity_verified = mapping.get("identity_verified") is True

        # Task 1 correction metadata
        correction_info = propose_ingredient_correction(raw_name)

        cid = mapping.get("pubchem_cid")
        candidate_cids = mapping.get("candidate_pubchem_cids") or ([cid] if cid else [])

        # Distinguish verified from review-required
        if identity_verified and primary_status in ("verified", "mapped"):
            verified_entries.append({
                "original_name": raw_name,
                "curated_cid": cid,
                "molecular_formula": mapping.get("molecular_formula"),
                "connectivity_smiles": mapping.get("connectivity_smiles"),
                "review_status": "verified_curated_match",
            })
            continue

        # Determine explicit review status and reason
        if primary_status == "needs_review":
            if candidate_cids and len(candidate_cids) > 1:
                review_status = "ambiguous_multiple_candidates"
                evidence_note = f"PubChem returned {len(candidate_cids)} candidates: {candidate_cids[:5]}. Multiple isomers/salts require expert distinction."
            elif cid is not None:
                review_status = "candidate_pending_curated_approval"
                evidence_note = f"Single candidate CID {cid} ({mapping.get('iupac_name')}) identified on PubChem, but not confirmed in curated list. Independent CIR/CosIng review required."
            else:
                review_status = "candidate_missing_structure"
                evidence_note = "Candidate record lacked CID or connectivity SMILES."

        elif primary_status == "not_found":
            if correction_info["has_correction_proposal"]:
                review_status = "ocr_corruption_pending_approval"
                evidence_note = f"OCR corruption detected: '{correction_info['corruption_type']}'. Proposed correction: '{correction_info['proposed_name']}'."
            else:
                review_status = "unresolved_no_candidate"
                evidence_note = "No candidate record found on PubChem. May be heavily corrupted OCR text, proprietary trade name, or unlisted mixture."

        elif primary_status == "complex_mixture":
            review_status = "complex_mixture_unsupported_for_qsar"
            evidence_note = "Ingredient is a botanical extract, fragrance, or polymer. Cannot be represented by a single molecular structure for NR-AR QSAR."

        elif primary_status == "api_error":
            review_status = "transient_service_error"
            evidence_note = f"PubChem query failed: {mapping.get('message')}. Retry query with stable connection."

        elif primary_status == "invalid_input":
            review_status = "invalid_or_blank_input"
            evidence_note = "Input string is blank or empty."

        else:
            review_status = "unverified_general"
            evidence_note = mapping.get("message") or "Unverified identity."

        pending_reviews.append({
            "original_name": raw_name,
            "primary_status": primary_status,
            "review_status": review_status,
            "has_proposed_correction": correction_info["has_correction_proposal"],
            "proposed_correction": correction_info["proposed_name"],
            "correction_type": correction_info["corruption_type"],
            "correction_notes": correction_info["notes"],
            "candidate_chemical_identity": {
                "pubchem_cid": cid,
                "candidate_pubchem_cids": candidate_cids,
                "iupac_name": mapping.get("iupac_name"),
                "molecular_formula": mapping.get("molecular_formula"),
                "connectivity_smiles": mapping.get("connectivity_smiles"),
            },
            "evidence": evidence_note,
            "action_required": (
                "Review candidate CID against trusted chemical databases (CosIng, CIR, PubChem) before adding to CURATED_CIDS."
                if review_status == "candidate_pending_curated_approval"
                else "Confirm OCR correction before chemical identity mapping."
                if review_status == "ocr_corruption_pending_approval"
                else "Document as complex mixture; assess via alternative testing strategies."
                if review_status == "complex_mixture_unsupported_for_qsar"
                else "Inspect label image for correct spelling."
            ),
        })

    registry = {
        "title": "CosmoSafe Chemical Identity Review Registry",
        "description": "Registry of ingredients requiring manual identity review before QSAR toxicity screening.",
        "total_ingredients_audited": len(ingredient_results),
        "verified_identities_count": len(verified_entries),
        "pending_reviews_count": len(pending_reviews),
        "pending_reviews_by_status": {
            "candidate_pending_curated_approval": sum(1 for r in pending_reviews if r["review_status"] == "candidate_pending_curated_approval"),
            "ocr_corruption_pending_approval": sum(1 for r in pending_reviews if r["review_status"] == "ocr_corruption_pending_approval"),
            "complex_mixture_unsupported_for_qsar": sum(1 for r in pending_reviews if r["review_status"] == "complex_mixture_unsupported_for_qsar"),
            "unresolved_no_candidate": sum(1 for r in pending_reviews if r["review_status"] == "unresolved_no_candidate"),
            "transient_service_error": sum(1 for r in pending_reviews if r["review_status"] == "transient_service_error"),
            "ambiguous_multiple_candidates": sum(1 for r in pending_reviews if r["review_status"] == "ambiguous_multiple_candidates"),
            "invalid_or_blank_input": sum(1 for r in pending_reviews if r["review_status"] == "invalid_or_blank_input"),
        },
        "verified_identities": verified_entries,
        "pending_identity_reviews": pending_reviews,
    }

    return registry


def save_identity_review_registry(registry: Dict[str, Any], output_path: Path = REVIEW_OUTPUT_PATH) -> Path:
    """Save review registry to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    return output_path
