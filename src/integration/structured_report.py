
from collections import Counter
from datetime import datetime, timezone

REPORT_SCHEMA_VERSION = "2.0"

VALID_PRIMARY_STATUSES = (
    "verified",
    "needs_review",
    "not_found",
    "complex_mixture",
    "api_error",
    "invalid_input",
)


def determine_primary_status(mapping, normalized_ingredient):
    """
    Classify an ingredient into exactly one mutually exclusive primary status.
    """
    mapping_status = mapping.get("status", "unknown")
    identity_verified = mapping.get("identity_verified") is True

    if mapping_status == "invalid_input" or not normalized_ingredient:
        return "invalid_input"
    elif mapping_status in ("mapped", "verified") and identity_verified:
        return "verified"
    elif mapping_status == "complex_mixture":
        return "complex_mixture"
    elif mapping_status in ("api_error", "error", "mapping_error"):
        return "api_error"
    elif mapping_status == "not_found":
        return "not_found"
    elif mapping_status == "needs_review":
        return "needs_review"
    else:
        return "needs_review"


def validate_report_consistency(report):
    """
    Validate that the report is internally consistent:
    1. Primary status counts sum to the total input count.
    2. Each input entry has exactly one result record.
    3. Successful predictions do not exceed prediction attempts.
    4. Successful predictions do not exceed screening eligible ingredients.
    5. Screened + not assessed equals total processed.
    6. All not_assessed entries have explainable reasons.
    7. All summary numbers match the per-ingredient records.
    """
    summary = report["summary"]
    results = report["results"]
    total = summary["ingredients_processed"]

    if len(results) != total:
        raise ValueError(
            f"Consistency check failed: len(results) {len(results)} != "
            f"ingredients_processed {total}"
        )

    status_sum = sum(summary["primary_status_counts"].values())
    if status_sum != total:
        raise ValueError(
            f"Consistency check failed: sum of primary_status_counts ({status_sum}) != "
            f"ingredients_processed ({total})"
        )

    if summary["successful_predictions"] > summary["screening_attempts"]:
        raise ValueError(
            "Consistency check failed: successful_predictions > screening_attempts"
        )

    if summary["successful_predictions"] > summary["ingredients_eligible_for_screening"]:
        raise ValueError(
            "Consistency check failed: successful_predictions > ingredients_eligible_for_screening"
        )

    if summary["ingredients_screened"] + summary["ingredients_not_assessed"] != total:
        raise ValueError(
            f"Consistency check failed: screened ({summary['ingredients_screened']}) + "
            f"not_assessed ({summary['ingredients_not_assessed']}) != total ({total})"
        )

    reason_sum = sum(summary["not_assessed_reasons"].values())
    if reason_sum != summary["ingredients_not_assessed"]:
        raise ValueError(
            f"Consistency check failed: sum of not_assessed_reasons ({reason_sum}) != "
            f"ingredients_not_assessed ({summary['ingredients_not_assessed']})"
        )

    for record in results:
        if record["assessment_status"] == "not_assessed":
            if not record.get("assessment_reason"):
                raise ValueError(
                    f"Consistency check failed: missing assessment_reason for {record.get('raw_ingredient')}"
                )
            if not record.get("assessment_message"):
                raise ValueError(
                    f"Consistency check failed: missing assessment_message for {record.get('raw_ingredient')}"
                )

    return True


def build_structured_report(
    ingredient_results,
    pipeline_status="completed",
    product_name="Cosmetic Formulation",
    exposure_profile=None,
    jurisdiction="India",
    include_knowledge_graph=True,
):
    results = []

    # Track duplicates across input entries while preserving each entry
    seen_raw = set()
    duplicate_indices = set()
    for idx, item in enumerate(ingredient_results):
        raw = item.get("raw_ingredient")
        if raw is not None and str(raw).strip():
            raw_key = str(raw).strip().casefold()
            if raw_key in seen_raw:
                duplicate_indices.add(idx)
            else:
                seen_raw.add(raw_key)

    for idx, item in enumerate(ingredient_results):
        mapping = item.get("mapping_result") or item.get("mapping") or {}
        toxicity = item.get("toxicity_result") or item.get("toxicity") or {}
        prediction = toxicity.get("prediction")
        if not prediction and (toxicity.get("predicted_activity") is not None or toxicity.get("status") == "completed"):
            prediction = {
                "success": toxicity.get("status") == "completed" and toxicity.get("error") is None,
                "endpoint": toxicity.get("endpoint"),
                "predicted_activity": toxicity.get("predicted_activity"),
                "activity_probability": toxicity.get("activity_probability"),
                "decision_threshold": toxicity.get("decision_threshold"),
                "maximum_reference_similarity": toxicity.get("maximum_reference_similarity"),
                "applicability": toxicity.get("applicability"),
                "applicability_message": toxicity.get("applicability_message"),
                "model_type": toxicity.get("model_type"),
                "interpretation": toxicity.get("interpretation"),
                "limitations": toxicity.get("limitations", []),
                "error": toxicity.get("error"),
            }
        elif not prediction:
            prediction = {}

        raw_ingredient = item.get("raw_ingredient")
        normalized_ingredient = item.get("normalized_ingredient")

        mapping_status = mapping.get("status", "unknown")
        toxicity_status = toxicity.get("status", "unknown")

        identity_verified = mapping.get("identity_verified") is True

        # Has candidate structure in PubChem
        has_candidate = bool(
            mapping.get("pubchem_cid")
            and mapping.get("connectivity_smiles")
        )

        # Mutually exclusive primary status
        primary_status = determine_primary_status(mapping, normalized_ingredient)

        # Screening status and eligibility
        successful_screen = (
            toxicity_status == "completed"
            and prediction.get("success") is True
        )
        failed_prediction = (
            toxicity_status == "prediction_failed"
            or (bool(prediction) and prediction.get("success") is False)
        )
        screening_attempted = successful_screen or failed_prediction
        screening_eligible = bool(toxicity.get("screening_eligible", screening_attempted))

        if successful_screen:
            assessment_status = "assessed"
            assessment_reason = "screened_successfully"
            assessment_message = (
                "NR-AR assay prediction completed. This is not "
                "a determination of cosmetic safety."
            )
        else:
            assessment_status = "not_assessed"
            if failed_prediction:
                assessment_reason = "prediction_failed"
                assessment_message = (
                    toxicity.get("message")
                    or prediction.get("error")
                    or "Not assessed: QSAR prediction failed."
                )
            elif toxicity.get("structure_error") == "invalid_smiles":
                assessment_reason = "invalid_structure"
                assessment_message = (
                    "Not assessed: candidate SMILES could not be parsed by RDKit."
                )
            elif toxicity.get("structure_error") == "multi_component":
                assessment_reason = "complex_mixture"
                assessment_message = (
                    "Not assessed: multiple molecular components detected; "
                    "single-component structure required."
                )
            elif primary_status == "invalid_input":
                assessment_reason = "invalid_input"
                assessment_message = (
                    mapping.get("message")
                    or "Not assessed: ingredient name is missing, blank, or invalid."
                )
            elif primary_status == "complex_mixture":
                assessment_reason = "complex_mixture"
                assessment_message = (
                    mapping.get("message")
                    or "Not assessed: this ingredient may be a complex "
                    "mixture or material without one suitable "
                    "molecular structure."
                )
            elif primary_status == "api_error":
                assessment_reason = "pubchem_api_error"
                assessment_message = (
                    mapping.get("message")
                    or "Not assessed: the chemical identity service "
                    "encountered an error."
                )
            elif primary_status == "not_found":
                assessment_reason = "chemical_not_found"
                assessment_message = (
                    mapping.get("message")
                    or "Not assessed: no usable PubChem record was found."
                )
            elif primary_status == "needs_review":
                assessment_reason = "identity_needs_review"
                assessment_message = (
                    mapping.get("message")
                    or "Not assessed: the candidate identity has not "
                    "passed the required identity review."
                )
            else:
                assessment_reason = "not_assessed_identity_unverified"
                assessment_message = (
                    toxicity.get("message")
                    or "Not assessed: chemical identity is unverified."
                )

        # Build list of warnings for this specific ingredient
        warnings = []
        if prediction.get("applicability") == "low_similarity":
            warnings.append({
                "code": "low_similarity",
                "message": (
                    prediction.get("applicability_message")
                    or "The input has low maximum fingerprint similarity to reference dataset. Treat this prediction cautiously."
                ),
            })

        if assessment_status == "not_assessed":
            warnings.append({
                "code": assessment_reason,
                "message": assessment_message,
            })

        if idx in duplicate_indices:
            warnings.append({
                "code": "duplicate_entry",
                "message": f"Duplicate input entry: '{raw_ingredient}' appears multiple times in input list.",
            })

        proposed_correction = item.get("proposed_correction")
        if proposed_correction is None:
            try:
                from normalization.ingredient_corrections import propose_ingredient_correction
                proposed_correction = propose_ingredient_correction(raw_ingredient)
            except Exception:
                proposed_correction = None

        # Toxicological Evidence Retrieval (Phase 4)
        try:
            from evidence.toxicology_rag import retrieve_toxicological_evidence
            cid_val = mapping.get("pubchem_cid") if identity_verified else None
            toxicological_evidence = retrieve_toxicological_evidence(
                pubchem_cid=cid_val,
                ingredient_name=raw_ingredient,
            )
        except Exception as e:
            toxicological_evidence = {
                "evidence_found": False,
                "error": str(e),
                "rag_synthesis": "Evidence retrieval temporarily unavailable.",
            }

        # Regulatory Compliance Check (Phase 5)
        try:
            from regulatory.regulatory_checker import check_ingredient_regulation
            cid_val = mapping.get("pubchem_cid") if identity_verified else None
            regulatory_status = check_ingredient_regulation(
                pubchem_cid=cid_val,
                ingredient_name=raw_ingredient,
                concentration_pct=item.get("formulated_concentration_pct"),
                product_category=exposure_profile.get("product_type") if exposure_profile else None,
                jurisdiction=jurisdiction,
            )
        except Exception as e:
            regulatory_status = {
                "compliance_status": "check_failed",
                "error": str(e),
                "message": f"Regulatory lookup error: {e}",
            }

        results.append({
            "raw_ingredient": raw_ingredient,
            "normalized_ingredient": normalized_ingredient,
            "proposed_correction": proposed_correction,
            "primary_status": primary_status,
            "assessment_status": assessment_status,
            "assessment_reason": assessment_reason,
            "assessment_message": assessment_message,
            "warnings": warnings,
            "screening_eligible": screening_eligible,
            "screening_attempted": screening_attempted,
            "mapping": {
                "status": mapping_status,
                "message": mapping.get("message"),
                "identity_verified": identity_verified,
                "has_candidate_record": has_candidate,
                "needs_manual_review": mapping.get(
                    "needs_manual_review", not identity_verified
                ),
                "matched_search_term": mapping.get(
                    "matched_search_term"
                ),
                "candidate_pubchem_cids": mapping.get(
                    "candidate_pubchem_cids", []
                ),
                "pubchem_cid": mapping.get("pubchem_cid"),
                "canonical_smiles": mapping.get("canonical_smiles"),
                "connectivity_smiles": mapping.get(
                    "connectivity_smiles"
                ),
                "inchikey": mapping.get("inchikey"),
                "inchi": mapping.get("inchi"),
                "molecular_formula": mapping.get(
                    "molecular_formula"
                ),
                "molecular_weight": mapping.get(
                    "molecular_weight"
                ),
                "iupac_name": mapping.get("iupac_name"),
                "cas_number": mapping.get("cas_number"),
                "synonyms": mapping.get("synonyms", []),
                "identifier_sources": mapping.get(
                    "identifier_sources", {}
                ),
                "retrieval_status": mapping.get(
                    "retrieval_status", {}
                ),
            },
            "toxicity": {
                "status": toxicity_status,
                "message": toxicity.get("message"),
                "endpoint": prediction.get("endpoint"),
                "predicted_activity": prediction.get(
                    "predicted_activity"
                ),
                "activity_probability": prediction.get(
                    "activity_probability"
                ),
                "decision_threshold": prediction.get(
                    "decision_threshold"
                ),
                "maximum_reference_similarity": prediction.get(
                    "maximum_reference_similarity"
                ),
                "applicability": prediction.get("applicability"),
                "applicability_message": prediction.get(
                    "applicability_message"
                ),
                "model_type": prediction.get("model_type"),
                "interpretation": prediction.get("interpretation"),
                "limitations": prediction.get("limitations", []),
                "error": prediction.get("error"),
            },
            "toxicological_evidence": toxicological_evidence,
            "regulatory_status": regulatory_status,
        })

    # Derive summary strictly from per-ingredient records
    primary_counts = Counter(r["primary_status"] for r in results)
    for status_key in VALID_PRIMARY_STATUSES:
        primary_counts.setdefault(status_key, 0)

    candidate_count = sum(1 for r in results if r["mapping"]["has_candidate_record"])
    eligible_count = sum(1 for r in results if r.get("screening_eligible"))
    attempts_count = sum(1 for r in results if r.get("screening_attempted"))
    successful_count = sum(1 for r in results if r["assessment_status"] == "assessed")
    failed_count = sum(1 for r in results if r.get("screening_attempted") and r["assessment_status"] != "assessed")
    not_assessed_count = sum(1 for r in results if r["assessment_status"] == "not_assessed")

    not_assessed_reasons = Counter(
        r["assessment_reason"] for r in results if r["assessment_status"] == "not_assessed"
    )

    ingredients_with_warnings_count = sum(1 for r in results if len(r["warnings"]) > 0)
    total_warnings_count = sum(len(r["warnings"]) for r in results)
    warning_counts = Counter(w["code"] for r in results for w in r["warnings"])

    if ingredients_with_warnings_count and pipeline_status == "completed":
        pipeline_status = "completed_with_warnings"

    # Product-level Safety Assessment (Phase 7)
    try:
        from assessment.product_assessor import assess_product_safety
        product_assessment = assess_product_safety(
            product_name=product_name,
            ingredient_results=results,
            exposure_profile=exposure_profile,
            jurisdiction=jurisdiction,
        )
    except Exception as e:
        product_assessment = {
            "overall_assessment_status": "Not assessed due to missing or uncertain information",
            "assessment_summary": f"Product assessment module encountered error: {e}",
            "error": str(e),
        }

    # Knowledge Graph Construction (Phase 6)
    kg_summary = {}
    kg_data = None
    if include_knowledge_graph:
        try:
            from knowledge_graph.cosmetic_kg import build_cosmosafe_knowledge_graph
            kg = build_cosmosafe_knowledge_graph(
                product_name=product_name,
                ingredient_results=results,
                exposure_profile=exposure_profile,
                jurisdiction=jurisdiction,
            )
            kg_data = kg.to_dict()
            kg_summary = {
                "node_count": kg_data["node_count"],
                "edge_count": kg_data["edge_count"],
                "node_types": kg_data["node_types_count"],
                "relationship_types": kg_data["relationship_types_count"],
            }
        except Exception as e:
            kg_summary = {"error": str(e)}

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_status": pipeline_status,
        "product_metadata": {
            "product_name": product_name,
            "target_jurisdiction": jurisdiction,
            "exposure_profile": exposure_profile or {
                "product_type": "Cosmetic Formulation",
                "exposure_type": "leave_on",
                "concentrations_known": False,
            },
        },
        "product_assessment": product_assessment,
        "summary": {
            "ingredients_processed": len(results),
            "primary_status_counts": dict(primary_counts),
            "pubchem_candidate_records_found": candidate_count,
            "ingredients_mapped_verified": primary_counts["verified"],
            "ingredients_needing_identity_review": primary_counts["needs_review"],
            "ingredients_not_found": primary_counts["not_found"],
            "complex_ingredients": primary_counts["complex_mixture"],
            "api_or_processing_errors": primary_counts["api_error"],
            "invalid_input_entries": primary_counts["invalid_input"],
            "ingredients_eligible_for_screening": eligible_count,
            "screening_attempts": attempts_count,
            "successful_predictions": successful_count,
            "failed_predictions": failed_count,
            "ingredients_screened": successful_count,
            "ingredients_not_assessed": not_assessed_count,
            "not_assessed_reasons": dict(not_assessed_reasons),
            "ingredients_with_warnings": ingredients_with_warnings_count,
            "total_warnings": total_warnings_count,
            "warning_counts": dict(warning_counts),
        },
        "knowledge_graph_summary": kg_summary,
        "knowledge_graph": kg_data,
        "important_notice": (
            "PubChem candidate records are not automatically verified "
            "ingredient identities. NR-AR results are assay-specific "
            "computational predictions, not determinations of cosmetic "
            "safety or human health risk. A missing prediction does not "
            "mean that an ingredient is safe or toxic. Identity evidence, "
            "model applicability, and limitations must be considered."
        ),
        "scientific_disclaimer": (
            "This automated cosmetic safety evaluation is generated for screening, research, "
            "and formulation triage. It separates intrinsic hazard alerts from exposure-driven risk "
            "and regulatory compliance. It does not replace an official Cosmetic Product Safety Report (CPSR)."
        ),
        "results": results,
    }

    validate_report_consistency(report)
    return report

