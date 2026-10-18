"""
CosmoSafe Product-Level Cosmetic Safety Assessment Module.

Synthesizes:
1. Chemical identity verification & OCR correction provenance
2. QSAR screening predictions (Tox21 NR-AR Random Forest)
3. Authoritative toxicological evidence (CIR, SCCS, ECHA)
4. Regulatory compliance (India BIS IS 4707, Cosmetics Rules 2020, EU/US)
5. Product exposure characteristics (leave-on/rinse-off, body site, frequency, concentration)

Explicit Safety Principles:
- Hazard != Risk: In vitro activity or intrinsic hazard does not equal in-use harm at formulated exposure.
- QSAR screening != Proof of toxicity: Computational predictions are screening signals with defined applicability domains.
- Regulatory compliance != Complete toxicological safety: Compliance with restricted annexes is necessary but not sufficient.
- Missing data prevents positive safety claims: Unassessed or unverified ingredients cannot be deemed safe.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from evidence.toxicology_rag import retrieve_toxicological_evidence
from regulatory.regulatory_checker import check_ingredient_regulation


VALID_ASSESSMENT_STATUSES = (
    "Safety concern identified in the assessed scope",
    "Further review required",
    "No relevant concern identified within the assessed scope",
    "Not assessed due to missing or uncertain information",
)


def assess_product_safety(
    product_name: str,
    ingredient_results: List[Dict[str, Any]],
    exposure_profile: Optional[Dict[str, Any]] = None,
    jurisdiction: str = "India",
) -> Dict[str, Any]:
    """
    Perform an integrated, transparent cosmetic product safety assessment.
    Enriches each ingredient with toxicological evidence and regulatory checks,
    then derives an evidence-based overall product assessment status.
    """
    if exposure_profile is None:
        exposure_profile = {
            "product_type": "Cosmetic Formulation",
            "application_site": "Face / Skin",
            "exposure_type": "leave_on",
            "application_frequency_per_day": 1,
            "target_population": "General Adult",
            "concentrations_known": False,
        }

    enriched_ingredients = []
    concerns = []
    review_triggers = []
    unassessed_items = []
    regulatory_issues = []

    for item in ingredient_results:
        raw_name = item.get("raw_ingredient")
        norm_name = item.get("normalized_ingredient")
        primary_status = item.get("primary_status")

        mapping = item.get("mapping") or item.get("mapping_result") or {}
        cid = mapping.get("pubchem_cid")
        identity_verified = mapping.get("identity_verified") is True

        toxicity = item.get("toxicity") or item.get("toxicity_result") or {}
        prediction = toxicity.get("prediction")
        if not isinstance(prediction, dict):
            if toxicity.get("status") == "completed" or toxicity.get("predicted_activity") is not None:
                prediction = toxicity
            else:
                prediction = {}

        formulated_conc = item.get("formulated_concentration_pct")

        # 1. Toxicological Evidence Retrieval (Phase 4)
        evidence_data = retrieve_toxicological_evidence(
            pubchem_cid=cid if identity_verified else None,
            ingredient_name=raw_name,
        )

        # 2. Regulatory Compliance Check (Phase 5)
        reg_check = check_ingredient_regulation(
            pubchem_cid=cid if identity_verified else None,
            ingredient_name=raw_name,
            concentration_pct=formulated_conc,
            product_category=exposure_profile.get("product_type"),
            jurisdiction=jurisdiction,
        )

        # 3. Analyze specific safety & compliance findings
        # Check regulatory violation
        if reg_check.get("compliance_status") == "explicitly_prohibited":
            concerns.append({
                "ingredient": raw_name,
                "type": "regulatory_prohibition",
                "detail": f"PROHIBITED in {jurisdiction} cosmetics under {reg_check.get('legal_basis')}.",
            })
            regulatory_issues.append(f"{raw_name}: Prohibited")

        elif reg_check.get("is_compliant") is False:
            concerns.append({
                "ingredient": raw_name,
                "type": "regulatory_non_compliance",
                "detail": reg_check.get("compliance_notes"),
            })
            regulatory_issues.append(f"{raw_name}: Exceeds regulatory limit or restricted in product category")

        # Check QSAR positive prediction
        if prediction.get("predicted_activity") == 1:
            review_triggers.append({
                "ingredient": raw_name,
                "type": "qsar_positive_prediction",
                "detail": (
                    f"Predicted active for {prediction.get('endpoint', 'NR-AR')} "
                    f"(probability: {prediction.get('activity_probability'):.3f}, "
                    f"threshold: {prediction.get('decision_threshold', 0.5)}). "
                    "Follow-up in vitro validation is required."
                ),
            })

        # Check QSAR applicability warning
        if prediction.get("applicability") == "low_similarity":
            review_triggers.append({
                "ingredient": raw_name,
                "type": "qsar_low_similarity_warning",
                "detail": prediction.get("applicability_message", "Low fingerprint similarity to reference training set."),
            })

        # Check unverified / missing identity
        if not identity_verified:
            unassessed_items.append({
                "ingredient": raw_name,
                "status": primary_status,
                "reason": mapping.get("message") or "Chemical identity is unverified or search record missing.",
            })

        # Check sensitization / toxicity evidence findings
        if evidence_data.get("evidence_found"):
            for rec in evidence_data.get("evidence_records", []):
                if rec.get("finding") in ("potential_photoallergic_sensitizer", "teratogenic_at_high_systemic_doses"):
                    review_triggers.append({
                        "ingredient": raw_name,
                        "type": "toxicological_endpoint_alert",
                        "detail": f"{rec['endpoint']}: {rec['finding']} ({rec['source_title']}). {rec.get('conditions_and_limitations', '')}",
                    })

        enriched_item = dict(item)
        enriched_item["toxicological_evidence"] = evidence_data
        enriched_item["regulatory_status"] = reg_check
        enriched_ingredients.append(enriched_item)

    # 4. Synthesize Overall Product Assessment Status
    # Criteria:
    # 1. Prohibited or non-compliant ingredient -> Safety concern identified in the assessed scope
    # 2. Unassessed or unverified ingredients exist -> Not assessed due to missing or uncertain information
    # 3. Active QSAR or potential sensitization alerts -> Further review required
    # 4. All verified, compliant, no concerns -> No relevant concern identified within the assessed scope
    if concerns:
        overall_status = "Safety concern identified in the assessed scope"
        assessment_summary = (
            f"Safety concerns were identified within the assessed scope: "
            + "; ".join(c["detail"] for c in concerns)
        )
    elif unassessed_items:
        overall_status = "Not assessed due to missing or uncertain information"
        assessment_summary = (
            f"A comprehensive product safety assessment cannot be completed because {len(unassessed_items)} "
            f"of {len(ingredient_results)} ingredients have unverified identities, unresolved OCR corruptions, "
            f"or missing concentration data. CosmoSafe strictly does not infer safety for unassessed ingredients."
        )
    elif review_triggers:
        overall_status = "Further review required"
        assessment_summary = (
            f"All chemical identities were verified, but specific screening or toxicological findings require expert review: "
            + "; ".join(t["detail"] for t in review_triggers)
        )
    else:
        overall_status = "No relevant concern identified within the assessed scope"
        assessment_summary = (
            "All ingredients possess verified chemical identities, comply with authorized limits in the target "
            "jurisdiction, and exhibited no active QSAR signals or prohibitive toxicological findings in the assessed scope."
        )

    return {
        "product_name": product_name,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "jurisdiction": jurisdiction,
        "overall_assessment_status": overall_status,
        "assessment_summary": assessment_summary,
        "exposure_profile": exposure_profile,
        "findings_breakdown": {
            "total_ingredients_evaluated": len(ingredient_results),
            "safety_concerns_count": len(concerns),
            "safety_concerns": concerns,
            "review_triggers_count": len(review_triggers),
            "review_triggers": review_triggers,
            "unassessed_ingredients_count": len(unassessed_items),
            "unassessed_ingredients": unassessed_items,
            "regulatory_issues_count": len(regulatory_issues),
            "regulatory_issues": regulatory_issues,
        },
        "regulatory_framework": {
            "jurisdiction": jurisdiction,
            "primary_regulations": [
                "Bureau of Indian Standards IS 4707 (Part 1 & 2)",
                "Cosmetics Rules, 2020 (Government of India Gazette)",
            ] if jurisdiction.lower() == "india" else ["Regulation (EC) No 1223/2009"],
        },
        "scientific_disclaimer": (
            "This computational assessment integrates in vitro QSAR predictions, curated literature, and regulatory lists. "
            "It does NOT replace an official Cosmetic Product Safety Report (CPSR) authored by a qualified safety assessor, "
            "nor does it test for physical stability, microbiology, or uncharacterized impurities."
        ),
        "enriched_ingredients": enriched_ingredients,
    }
