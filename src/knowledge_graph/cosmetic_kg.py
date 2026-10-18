"""
CosmoSafe Cosmetic Safety Knowledge Graph (KG) Module.

Represents typed relationships among:
- Products
- Ingredient list entries
- Chemical substances & identifiers
- QSAR predictions
- Authoritative toxicological evidence & source documents
- Regulatory rules & jurisdictions
- Exposure assumptions
- Warnings, uncertainties, and review decisions

Preserves provenance and explicit uncertainty; never converts statistical correlations
or preliminary screening signals into proven causal safety determinations.
"""

from typing import Dict, Any, List, Optional, Set
import json
from datetime import datetime, timezone


class KnowledgeGraph:
    """Lightweight, serializable in-memory Knowledge Graph for cosmetic safety assessment."""

    def __init__(self, graph_id: str = "cosmosafe_kg"):
        self.graph_id = graph_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        properties: Optional[Dict[str, Any]] = None,
        provenance: Optional[str] = None,
    ) -> str:
        """Add a typed node with properties and provenance tracking."""
        clean_id = str(node_id).strip()
        if clean_id in self.nodes:
            # Update properties if already exists
            if properties:
                self.nodes[clean_id]["properties"].update(properties)
            return clean_id

        self.nodes[clean_id] = {
            "id": clean_id,
            "type": node_type,
            "label": label,
            "properties": properties or {},
            "provenance": provenance or "cosmosafe_pipeline",
        }
        return clean_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: Optional[Dict[str, Any]] = None,
        certainty: str = "established",  # 'established', 'screening_estimate', 'pending_review', 'conditional'
    ) -> None:
        """Add a directed relationship between two existing nodes."""
        if source_id not in self.nodes:
            raise KeyError(f"Source node '{source_id}' does not exist in graph.")
        if target_id not in self.nodes:
            raise KeyError(f"Target node '{target_id}' does not exist in graph.")

        edge_record = {
            "source": source_id,
            "target": target_id,
            "relationship": relationship,
            "certainty": certainty,
            "properties": properties or {},
        }
        self.edges.append(edge_record)

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        """Retrieve neighboring nodes and their connecting relationships."""
        results = []
        for edge in self.edges:
            if direction in ("out", "both") and edge["source"] == node_id:
                results.append({
                    "node": self.nodes[edge["target"]],
                    "relationship": edge["relationship"],
                    "direction": "out",
                    "certainty": edge["certainty"],
                })
            elif direction in ("in", "both") and edge["target"] == node_id:
                results.append({
                    "node": self.nodes[edge["source"]],
                    "relationship": edge["relationship"],
                    "direction": "in",
                    "certainty": edge["certainty"],
                })
        return results

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph to structured dictionary."""
        return {
            "graph_id": self.graph_id,
            "created_at": self.created_at,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
            "node_types_count": self._count_by_key(self.nodes.values(), "type"),
            "relationship_types_count": self._count_by_key(self.edges, "relationship"),
        }

    def to_json(self, indent: int = 2) -> str:
        """Export graph to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def _count_by_key(items, key):
        counts = {}
        for item in items:
            val = item.get(key)
            counts[val] = counts.get(val, 0) + 1
        return counts


def build_cosmosafe_knowledge_graph(
    product_name: str,
    ingredient_results: List[Dict[str, Any]],
    exposure_profile: Optional[Dict[str, Any]] = None,
    jurisdiction: str = "India",
) -> KnowledgeGraph:
    """
    Construct an end-to-end knowledge graph connecting a cosmetic product to its ingredients,
    chemical substances, QSAR predictions, toxicological evidence, and regulatory rules.
    """
    kg = KnowledgeGraph(graph_id=f"kg_{product_name.lower().replace(' ', '_')}")

    # 1. Product Node
    prod_id = f"product:{product_name.lower().replace(' ', '_')}"
    kg.add_node(
        node_id=prod_id,
        node_type="Product",
        label=product_name,
        properties={"product_name": product_name, "jurisdiction": jurisdiction},
        provenance="user_product_input",
    )

    # 2. Exposure Profile Node
    if exposure_profile:
        exp_id = f"exposure:{prod_id}"
        kg.add_node(
            node_id=exp_id,
            node_type="ExposureProfile",
            label=f"Exposure: {exposure_profile.get('product_type', 'Cosmetic')}",
            properties=exposure_profile,
            provenance="product_specification",
        )
        kg.add_edge(prod_id, exp_id, "HAS_EXPOSURE_PROFILE", certainty="established")

    # 3. Jurisdiction Node
    jur_id = f"jurisdiction:{jurisdiction.lower()}"
    kg.add_node(
        node_id=jur_id,
        node_type="Jurisdiction",
        label=jurisdiction,
        properties={"country": jurisdiction},
        provenance="regulatory_scope",
    )

    # 4. Ingredients and related scientific/regulatory subgraphs
    for idx, item in enumerate(ingredient_results, start=1):
        raw_name = item.get("raw_ingredient") or f"ingredient_{idx}"
        ing_id = f"ingredient_entry:{idx}_{raw_name.lower().replace(' ', '_')[:30]}"

        # Ingredient Entry Node
        kg.add_node(
            node_id=ing_id,
            node_type="IngredientEntry",
            label=raw_name,
            properties={
                "entry_order": idx,
                "raw_text": raw_name,
                "normalized": item.get("normalized_ingredient"),
                "primary_status": item.get("primary_status"),
            },
            provenance="label_ocr_or_input_list",
        )
        kg.add_edge(prod_id, ing_id, "CONTAINS_INGREDIENT_ENTRY", properties={"position": idx})

        # Chemical Substance Node (if mapped or verified)
        mapping = item.get("mapping") or item.get("mapping_result") or {}
        cid = mapping.get("pubchem_cid")
        identity_verified = mapping.get("identity_verified") is True

        if cid:
            subst_id = f"substance:cid_{cid}"
            kg.add_node(
                node_id=subst_id,
                node_type="ChemicalSubstance",
                label=mapping.get("iupac_name") or raw_name,
                properties={
                    "pubchem_cid": cid,
                    "smiles": mapping.get("connectivity_smiles"),
                    "formula": mapping.get("molecular_formula"),
                    "identity_verified": identity_verified,
                },
                provenance="pubchem_compound_database",
            )
            certainty = "established" if identity_verified else "pending_review"
            kg.add_edge(ing_id, subst_id, "MAPS_TO_SUBSTANCE", certainty=certainty)

            # QSAR Prediction Node (if evaluated)
            toxicity = item.get("toxicity") or item.get("toxicity_result") or {}
            prediction = toxicity.get("prediction")
            if not isinstance(prediction, dict):
                # Handle flattened toxicity structure from serialized reports
                if toxicity.get("status") == "completed" or toxicity.get("predicted_activity") is not None:
                    prediction = toxicity
                else:
                    prediction = {}

            has_valid_pred = (
                prediction.get("predicted_activity") is not None
                and prediction.get("error") is None
                and (prediction.get("success") is not False)
                and (prediction.get("status") in ("completed", None) or prediction.get("success") is True)
            )

            if has_valid_pred:
                qsar_id = f"qsar:nr_ar_{cid}"
                if qsar_id not in kg.nodes:
                    kg.add_node(
                        node_id=qsar_id,
                        node_type="QSARPrediction",
                        label=f"NR-AR Prediction (CID {cid})",
                        properties={
                            "endpoint": prediction.get("endpoint") or "NR-AR",
                            "predicted_activity": prediction.get("predicted_activity"),
                            "activity_probability": prediction.get("activity_probability"),
                            "applicability": prediction.get("applicability"),
                            "decision_threshold": prediction.get("decision_threshold", 0.5),
                        },
                        provenance="trained_random_forest_model",
                    )
                kg.add_edge(
                    subst_id,
                    qsar_id,
                    "HAS_QSAR_PREDICTION",
                    certainty="screening_estimate",
                    properties={"disclaimer": "Computational in vitro assay prediction; not human safety proof."},
                )

            # Toxicology Evidence Nodes (if retrieved)
            evidence_info = item.get("toxicological_evidence")
            if evidence_info and evidence_info.get("evidence_records"):
                for e_idx, rec in enumerate(evidence_info["evidence_records"]):
                    ev_id = f"evidence:{cid}_{rec['endpoint']}_{e_idx}"
                    kg.add_node(
                        node_id=ev_id,
                        node_type="EvidenceRecord",
                        label=f"{rec['endpoint']}: {rec['finding']}",
                        properties={
                            "endpoint": rec["endpoint"],
                            "finding": rec["finding"],
                            "evidence_type": rec["evidence_type"],
                            "passage": rec.get("passage"),
                            "source_title": rec.get("source_title"),
                        },
                        provenance=rec.get("publisher", "authoritative_assessment"),
                    )
                    kg.add_edge(subst_id, ev_id, "HAS_TOXICITY_EVIDENCE", certainty="established")

            # Regulatory Rule Nodes (if checked)
            reg_info = item.get("regulatory_status")
            if reg_info and reg_info.get("legal_basis"):
                rule_id = f"reg_rule:{jurisdiction.lower()}_{cid}"
                kg.add_node(
                    node_id=rule_id,
                    node_type="RegulatoryRule",
                    label=f"{reg_info.get('compliance_status')}: {reg_info.get('legal_basis')[:40]}",
                    properties={
                        "compliance_status": reg_info.get("compliance_status"),
                        "legal_basis": reg_info.get("legal_basis"),
                        "max_concentration": reg_info.get("max_authorized_concentration_pct"),
                        "effective_date": reg_info.get("effective_date"),
                    },
                    provenance=reg_info.get("source_citation", "official_gazette"),
                )
                kg.add_edge(subst_id, rule_id, "GOVERNED_BY_RULE", certainty="established")
                kg.add_edge(rule_id, jur_id, "ENFORCED_IN_JURISDICTION", certainty="established")

        # Warning Nodes for any anomalies / unassessed status
        warnings = item.get("warnings") or []
        for w_idx, w in enumerate(warnings):
            warn_id = f"warning:{ing_id}_{w_idx}"
            kg.add_node(
                node_id=warn_id,
                node_type="WarningDecision",
                label=f"Warning: {w.get('code')}",
                properties={"code": w.get("code"), "message": w.get("message")},
                provenance="cosmosafe_safety_filter",
            )
            kg.add_edge(ing_id, warn_id, "PRODUCES_WARNING", certainty="conditional")

    return kg
