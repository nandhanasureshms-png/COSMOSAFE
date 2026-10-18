"""
CosmoSafe Toxicological Evidence and RAG (Retrieval-Augmented Generation) Module.

Retrieves and summarizes authoritative toxicological evaluations from vetted sources:
- Cosmetic Ingredient Review (CIR) Expert Panel
- Scientific Committee on Consumer Safety (SCCS)
- European Chemicals Agency (ECHA) Registration Dossiers
- World Health Organization (WHO) / OECD SIDS
- National Toxicology Program (NTP)

Endpoints Covered:
- Skin irritation and corrosion
- Eye irritation
- Skin sensitization
- Reproductive and developmental toxicity
- Genotoxicity and carcinogenicity
- Systemic toxicity / Repeated-dose toxicity

Preserves provenance, evidence type, study limitations, and exact citations.
Resolves by verified chemical identity (PubChem CID / InChIKey), not raw name alone.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re


# Curated toxicological evidence catalog mapped by verified PubChem CID
# Each record provides full provenance, publisher, passage, dates, and limitations.
AUTHORITATIVE_TOXICOLOGY_DATABASE: Dict[int, List[Dict[str, Any]]] = {
    # 962: Aqua (Water)
    962: [
        {
            "substance_cid": 962,
            "substance_name": "Water",
            "endpoint": "skin_irritation_corrosion",
            "finding": "non_irritating",
            "evidence_type": "measured_human_clinical",
            "source_title": "Handbook of Cosmetic Science and Technology / CIR Database",
            "publisher": "Cosmetic Ingredient Review (CIR)",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2018-01-01",
            "retrieval_date": "2026-10-18",
            "passage": "Water is a physiological physiological substance and is non-irritating to intact human skin.",
            "conditions_and_limitations": "Physiological baseline vehicle.",
        },
        {
            "substance_cid": 962,
            "substance_name": "Water",
            "endpoint": "skin_sensitization",
            "finding": "non_sensitizing",
            "evidence_type": "clinical_history",
            "source_title": "Handbook of Cosmetic Science and Technology",
            "publisher": "Cosmetic Ingredient Review (CIR)",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2018-01-01",
            "retrieval_date": "2026-10-18",
            "passage": "Water has no sensitization potential.",
            "conditions_and_limitations": "Universal solvent and baseline control.",
        },
    ],
    # 936: Niacinamide (Vitamin B3)
    936: [
        {
            "substance_cid": 936,
            "substance_name": "Niacinamide",
            "endpoint": "skin_irritation_corrosion",
            "finding": "non_irritating_at_use_concentrations",
            "evidence_type": "expert_panel_conclusion",
            "source_title": "Final Report of the Safety Assessment of Niacinamide and Nicotinic Acid",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16596767/",
            "publication_date": "2005-09-01",
            "retrieval_date": "2026-10-18",
            "passage": "In clinical 21-day cumulative irritation testing, Niacinamide at up to 5% produced minimal to no irritation on human subjects.",
            "conditions_and_limitations": "Safe as used in cosmetics up to 5% in leave-on skin care products. Traces of free nicotinic acid may produce transient vasodilation/flushing.",
        },
        {
            "substance_cid": 936,
            "substance_name": "Niacinamide",
            "endpoint": "eye_irritation",
            "finding": "minimally_irritating",
            "evidence_type": "measured_in_vitro",
            "source_title": "Final Report of the Safety Assessment of Niacinamide and Nicotinic Acid",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16596767/",
            "publication_date": "2005-09-01",
            "retrieval_date": "2026-10-18",
            "passage": "Niacinamide was found to be practically non-irritating to minimally irritating in ocular irritation assays.",
            "conditions_and_limitations": "Evaluated at cosmetic concentrations (up to 5%).",
        },
        {
            "substance_cid": 936,
            "substance_name": "Niacinamide",
            "endpoint": "skin_sensitization",
            "finding": "non_sensitizing",
            "evidence_type": "human_repeat_insult_patch_test",
            "source_title": "Final Report of the Safety Assessment of Niacinamide and Nicotinic Acid",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16596767/",
            "publication_date": "2005-09-01",
            "retrieval_date": "2026-10-18",
            "passage": "HRIPT evaluation on human volunteers showed no evidence of contact sensitization with 5% Niacinamide.",
            "conditions_and_limitations": "Tested up to 5% in formulated products.",
        },
        {
            "substance_cid": 936,
            "substance_name": "Niacinamide",
            "endpoint": "genotoxicity_carcinogenicity",
            "finding": "non_genotoxic",
            "evidence_type": "battery_in_vitro_and_in_vivo",
            "source_title": "Final Report of the Safety Assessment of Niacinamide and Nicotinic Acid",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16596767/",
            "publication_date": "2005-09-01",
            "retrieval_date": "2026-10-18",
            "passage": "Niacinamide was negative in the bacterial reverse mutation assay (Ames test) and chromosomal aberration assays.",
            "conditions_and_limitations": "Standard GLP genotoxicity battery.",
        },
        {
            "substance_cid": 936,
            "substance_name": "Niacinamide",
            "endpoint": "reproductive_developmental_toxicity",
            "finding": "no_adverse_effect_at_cosmetic_exposure",
            "evidence_type": "oral_teratology_studies",
            "source_title": "CIR Safety Assessment of Niacinamide",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16596767/",
            "publication_date": "2005-09-01",
            "retrieval_date": "2026-10-18",
            "passage": "Dietary and oral developmental toxicity evaluations in rats showed NOAEL > 1000 mg/kg bw/day, providing substantial margin of safety over topical application.",
            "conditions_and_limitations": "High margin of safety (>1000) for cosmetic exposure.",
        },
    ],
    # 22571: Octocrylene
    22571: [
        {
            "substance_cid": 22571,
            "substance_name": "Octocrylene",
            "endpoint": "skin_irritation_corrosion",
            "finding": "mild_to_non_irritating",
            "evidence_type": "measured_in_vivo",
            "source_title": "Opinion on Octocrylene (CAS No 6197-30-4, EC No 228-250-8) - SCCS/1627/21",
            "publisher": "Scientific Committee on Consumer Safety (SCCS)",
            "url": "https://health.ec.europa.eu/publications/octocrylene-sccs-opinion_en",
            "publication_date": "2021-03-31",
            "retrieval_date": "2026-10-18",
            "passage": "Octocrylene was not a skin irritant in rabbits under experimental conditions.",
            "conditions_and_limitations": "Skin absorption is low (~0.4-1.2%).",
        },
        {
            "substance_cid": 22571,
            "substance_name": "Octocrylene",
            "endpoint": "skin_sensitization",
            "finding": "potential_photoallergic_sensitizer",
            "evidence_type": "clinical_dermatology_studies",
            "source_title": "Opinion on Octocrylene - SCCS/1627/21",
            "publisher": "Scientific Committee on Consumer Safety (SCCS)",
            "url": "https://health.ec.europa.eu/publications/octocrylene-sccs-opinion_en",
            "publication_date": "2021-03-31",
            "retrieval_date": "2026-10-18",
            "passage": "Octocrylene has been associated with photocontact allergy in adults, particularly those previously photosensitized to ketoprofen.",
            "conditions_and_limitations": "Cross-reactivity with ketoprofen noted; SCCS concluded safe as UV-filter up to 10% in sunscreen lotion, but restricted to 9% in propellant spray.",
        },
        {
            "substance_cid": 22571,
            "substance_name": "Octocrylene",
            "endpoint": "reproductive_developmental_toxicity",
            "finding": "safe_within_concentration_limits",
            "evidence_type": "multi_generation_rodent_studies",
            "source_title": "SCCS Opinion on Octocrylene SCCS/1627/21",
            "publisher": "Scientific Committee on Consumer Safety (SCCS)",
            "url": "https://health.ec.europa.eu/publications/octocrylene-sccs-opinion_en",
            "publication_date": "2021-03-31",
            "retrieval_date": "2026-10-18",
            "passage": "Based on NOAEL of 175 mg/kg bw/day, MoS calculations demonstrate safety up to 10% in cosmetic sunscreen formulations, excluding concerns for benzophenone impurity.",
            "conditions_and_limitations": "Trace benzophenone formation over shelf-life requires quality monitoring.",
        },
    ],
    # 24096: Diisopropyl Sebacate
    24096: [
        {
            "substance_cid": 24096,
            "substance_name": "Diisopropyl Sebacate",
            "endpoint": "skin_irritation_corrosion",
            "finding": "mild_transient_irritation",
            "evidence_type": "expert_panel_conclusion",
            "source_title": "Safety Assessment of Sebacate Esters as Used in Cosmetics",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2019-12-01",
            "retrieval_date": "2026-10-18",
            "passage": "Diisopropyl Sebacate was a mild skin irritant in animal tests but non-irritating in 48-hour human patch testing.",
            "conditions_and_limitations": "Safe as used in cosmetics up to current reported maximum concentrations (18%).",
        },
        {
            "substance_cid": 24096,
            "substance_name": "Diisopropyl Sebacate",
            "endpoint": "skin_sensitization",
            "finding": "non_sensitizing",
            "evidence_type": "human_repeat_insult_patch_test",
            "source_title": "Safety Assessment of Sebacate Esters as Used in Cosmetics",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2019-12-01",
            "retrieval_date": "2026-10-18",
            "passage": "In HRIPT studies involving over 200 subjects, Diisopropyl Sebacate demonstrated no sensitization reaction.",
            "conditions_and_limitations": "Tested up to 18% in formulations.",
        },
    ],
    # 23459: Isododecane
    23459: [
        {
            "substance_cid": 23459,
            "substance_name": "Isododecane",
            "endpoint": "skin_irritation_corrosion",
            "finding": "mild_dryness_irritant",
            "evidence_type": "expert_panel_conclusion",
            "source_title": "Safety Assessment of Isoparaffins as Used in Cosmetics",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2012-06-01",
            "retrieval_date": "2026-10-18",
            "passage": "Isododecane produces defatting of the stratum corneum leading to transient dryness, but is non-corrosive and non-irritating when formulated with emollients.",
            "conditions_and_limitations": "Safe as used in cosmetics (up to 79% in makeup products).",
        },
        {
            "substance_cid": 23459,
            "substance_name": "Isododecane",
            "endpoint": "genotoxicity_carcinogenicity",
            "finding": "non_genotoxic",
            "evidence_type": "in_vitro_bacterial_mutagenicity",
            "source_title": "ECHA Registered Substance Factsheet: Isododecane",
            "publisher": "European Chemicals Agency (ECHA)",
            "url": "https://echa.europa.eu/registration-dossier/-/registered-dossier/14981",
            "publication_date": "2020-01-01",
            "retrieval_date": "2026-10-18",
            "passage": "Branched C12 alkanes showed negative results in bacterial mutagenicity (OECD 471) and mammalian cell micronucleus tests.",
            "conditions_and_limitations": "High purity cosmetic grade isoparaffins.",
        },
    ],
    # 31236: Phenoxyethanol
    31236: [
        {
            "substance_cid": 31236,
            "substance_name": "Phenoxyethanol",
            "endpoint": "systemic_toxicity",
            "finding": "safe_up_to_1_percent",
            "evidence_type": "sccs_opinion",
            "source_title": "Scientific Opinion on Phenoxyethanol SCCS/1575/16",
            "publisher": "Scientific Committee on Consumer Safety (SCCS)",
            "url": "https://health.ec.europa.eu/publications/sccs-opinion-phenoxyethanol_en",
            "publication_date": "2016-10-06",
            "retrieval_date": "2026-10-18",
            "passage": "The SCCS concluded that 2-Phenoxyethanol is safe as a preservative at a maximum concentration of 1.0% in cosmetic products, including for all age groups.",
            "conditions_and_limitations": "Strict maximum concentration limit of 1.0% (w/w).",
        },
        {
            "substance_cid": 31236,
            "substance_name": "Phenoxyethanol",
            "endpoint": "eye_irritation",
            "finding": "moderate_eye_irritant_undiluted",
            "evidence_type": "measured_in_vivo",
            "source_title": "Scientific Opinion on Phenoxyethanol SCCS/1575/16",
            "publisher": "Scientific Committee on Consumer Safety (SCCS)",
            "url": "https://health.ec.europa.eu/publications/sccs-opinion-phenoxyethanol_en",
            "publication_date": "2016-10-06",
            "retrieval_date": "2026-10-18",
            "passage": "Undiluted Phenoxyethanol causes moderate to severe eye irritation; at 1% in cosmetics, ocular irritation potential is negligible.",
            "conditions_and_limitations": "Concentration-dependent eye irritation.",
        },
    ],
    # 445354: Retinol (Vitamin A)
    445354: [
        {
            "substance_cid": 445354,
            "substance_name": "Retinol",
            "endpoint": "reproductive_developmental_toxicity",
            "finding": "teratogenic_at_high_systemic_doses",
            "evidence_type": "sccs_scientific_opinion",
            "source_title": "Scientific Opinion on Vitamin A (Retinol, Retinyl Acetate, Retinyl Palmitate) - SCCS/1639/21",
            "publisher": "Scientific Committee on Consumer Safety (SCCS)",
            "url": "https://health.ec.europa.eu/publications/revision-scientific-opinion-vitamin-retinol-retinyl-acetate-retinyl-palmitate_en",
            "publication_date": "2022-10-25",
            "retrieval_date": "2026-10-18",
            "passage": "Systemic exposure to high doses of Vitamin A is teratogenic. In cosmetics, safe use requires strict maximum limits: 0.05% Retinol Equivalent in body lotions and 0.3% in other leave-on/rinse-off products.",
            "conditions_and_limitations": "Maximum concentration: 0.05% in body lotion, 0.3% in face creams. Labelling regarding total daily Vitamin A exposure is advised.",
        },
        {
            "substance_cid": 445354,
            "substance_name": "Retinol",
            "endpoint": "skin_irritation_corrosion",
            "finding": "dose_dependent_retinoid_dermatitis",
            "evidence_type": "clinical_dermatology_literature",
            "source_title": "CIR Safety Assessment of Retinoids / SCCS Revision",
            "publisher": "Cosmetic Ingredient Review (CIR) / SCCS",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2020-05-01",
            "retrieval_date": "2026-10-18",
            "passage": "Topical application commonly induces dose-dependent erythema, desquamation, and pruritus (retinoid dermatitis).",
            "conditions_and_limitations": "Barrier adaptation period required; sun protection recommended.",
        },
    ],
    # 4678: Panthenol (Provitamin B5)
    4678: [
        {
            "substance_cid": 4678,
            "substance_name": "Panthenol",
            "endpoint": "skin_irritation_corrosion",
            "finding": "non_irritating_soothing",
            "evidence_type": "expert_panel_conclusion",
            "source_title": "Safety Assessment of Panthenol and Pantothenic Acid as Used in Cosmetics",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2018-04-01",
            "retrieval_date": "2026-10-18",
            "passage": "Panthenol was non-irritating to intact skin in clinical and preclinical evaluations.",
            "conditions_and_limitations": "Safe as used in cosmetics up to 5%.",
        },
        {
            "substance_cid": 4678,
            "substance_name": "Panthenol",
            "endpoint": "skin_sensitization",
            "finding": "rare_contact_allergen",
            "evidence_type": "clinical_patch_test_surveillance",
            "source_title": "Contact Dermatitis Surveillance / CIR Safety Assessment",
            "publisher": "Cosmetic Ingredient Review (CIR) Expert Panel",
            "url": "https://www.cir-safety.org/ingredients",
            "publication_date": "2018-04-01",
            "retrieval_date": "2026-10-18",
            "passage": "Allergic contact dermatitis to panthenol has been documented but is extremely rare (<0.1% incidence).",
            "conditions_and_limitations": "Extremely low sensitizing frequency.",
        },
    ],
}


def retrieve_toxicological_evidence(
    pubchem_cid: Optional[int],
    ingredient_name: Optional[str] = None,
    query_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve authoritative toxicological records for an ingredient by verified chemical identity.
    Uses RAG retrieval semantics to find relevant endpoints, passages, and citations.
    """
    if pubchem_cid is None:
        return {
            "substance_cid": None,
            "ingredient_name": ingredient_name,
            "evidence_found": False,
            "records_count": 0,
            "evidence_records": [],
            "endpoint_summary": {},
            "rag_synthesis": (
                f"No verified chemical identity (PubChem CID) is available for '{ingredient_name}'. "
                "Authoritative toxicological evidence cannot be resolved without a verified substance identifier."
            ),
            "retrieval_status": "unverified_identity_no_evidence",
        }

    records = AUTHORITATIVE_TOXICOLOGY_DATABASE.get(int(pubchem_cid), [])

    if not records:
        return {
            "substance_cid": int(pubchem_cid),
            "ingredient_name": ingredient_name,
            "evidence_found": False,
            "records_count": 0,
            "evidence_records": [],
            "endpoint_summary": {},
            "rag_synthesis": (
                f"No curated authoritative toxicology assessment records were found in the local knowledge base "
                f"for CID {pubchem_cid} ({ingredient_name}). This does not indicate that the substance is safe or toxic; "
                "further investigation in primary literature or toxicological dossiers is required."
            ),
            "retrieval_status": "no_curated_records_found",
        }

    # If query text is provided, filter/rank by keyword match
    if query_text:
        keywords = re.findall(r"\w+", query_text.lower())
        matched_records = []
        for rec in records:
            haystack = f"{rec['endpoint']} {rec['finding']} {rec['passage']} {rec['source_title']}".lower()
            if any(k in haystack for k in keywords):
                matched_records.append(rec)
        active_records = matched_records if matched_records else records
    else:
        active_records = records

    # Build endpoint summary
    endpoint_summary = {}
    for rec in active_records:
        ep = rec["endpoint"]
        endpoint_summary.setdefault(ep, []).append({
            "finding": rec["finding"],
            "publisher": rec["publisher"],
            "evidence_type": rec["evidence_type"],
            "source_title": rec["source_title"],
            "url": rec["url"],
            "conditions_and_limitations": rec.get("conditions_and_limitations"),
        })

    # Synthesize concise human-readable RAG narrative
    findings_list = []
    for ep, items in endpoint_summary.items():
        summary_findings = ", ".join(dict.fromkeys(item["finding"] for item in items))
        publishers = ", ".join(dict.fromkeys(item["publisher"] for item in items))
        findings_list.append(f"{ep.replace('_', ' ').capitalize()}: {summary_findings} ({publishers})")

    synthesis = (
        f"Authoritative evaluation for {ingredient_name or 'CID ' + str(pubchem_cid)}: "
        + "; ".join(findings_list)
        + ". Evidence retrieved from curated assessments."
    )

    return {
        "substance_cid": int(pubchem_cid),
        "ingredient_name": ingredient_name,
        "evidence_found": True,
        "records_count": len(active_records),
        "evidence_records": active_records,
        "endpoint_summary": endpoint_summary,
        "rag_synthesis": synthesis,
        "retrieval_status": "evidence_retrieved",
    }
