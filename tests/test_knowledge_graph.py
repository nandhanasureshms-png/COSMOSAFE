import unittest
import sys
import json
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from knowledge_graph.cosmetic_kg import (
    KnowledgeGraph,
    build_cosmosafe_knowledge_graph,
)


class TestKnowledgeGraph(unittest.TestCase):
    def test_basic_node_and_edge_creation(self):
        kg = KnowledgeGraph("test_kg")
        n1 = kg.add_node("prod_1", "Product", "Daily Moisturizer", {"brand": "EcoCare"}, "user_spec")
        n2 = kg.add_node("sub_1", "ChemicalSubstance", "Niacinamide", {"cid": 936}, "pubchem")

        self.assertEqual(n1, "prod_1")
        self.assertEqual(len(kg.nodes), 2)

        kg.add_edge("prod_1", "sub_1", "CONTAINS_SUBSTANCE", {"concentration": 2.0}, certainty="established")
        self.assertEqual(len(kg.edges), 1)

        # Non-existent node edge should raise KeyError
        with self.assertRaises(KeyError):
            kg.add_edge("prod_1", "non_existent_node", "INVALID_REL")

    def test_neighbor_queries(self):
        kg = KnowledgeGraph("query_kg")
        kg.add_node("p", "Product", "Sunscreen")
        kg.add_node("i1", "IngredientEntry", "Aqua")
        kg.add_node("i2", "IngredientEntry", "Octocrylene")

        kg.add_edge("p", "i1", "CONTAINS")
        kg.add_edge("p", "i2", "CONTAINS")

        neighbors_out = kg.get_neighbors("p", direction="out")
        self.assertEqual(len(neighbors_out), 2)

        neighbors_in = kg.get_neighbors("i1", direction="in")
        self.assertEqual(len(neighbors_in), 1)
        self.assertEqual(neighbors_in[0]["node"]["id"], "p")

    def test_build_cosmosafe_knowledge_graph(self):
        mock_results = [
            {
                "raw_ingredient": "Niacinamide",
                "normalized_ingredient": "niacinamide",
                "primary_status": "verified",
                "mapping": {
                    "pubchem_cid": 936,
                    "iupac_name": "pyridine-3-carboxamide",
                    "connectivity_smiles": "C1=CC(=CN=C1)C(=O)N",
                    "identity_verified": True,
                },
                "toxicity": {
                    "status": "completed",
                    "prediction": {
                        "success": True,
                        "endpoint": "NR-AR",
                        "predicted_activity": 0,
                        "activity_probability": 0.04,
                        "applicability": "reference_similar",
                    },
                },
                "toxicological_evidence": {
                    "evidence_records": [
                        {
                            "endpoint": "skin_irritation_corrosion",
                            "finding": "non_irritating",
                            "evidence_type": "clinical",
                            "publisher": "CIR",
                        }
                    ]
                },
                "regulatory_status": {
                    "compliance_status": "no_specific_restriction_found",
                    "legal_basis": "Cosmetic Rules 2020",
                },
            }
        ]

        kg = build_cosmosafe_knowledge_graph(
            product_name="Test Cream",
            ingredient_results=mock_results,
            jurisdiction="India",
        )

        data = kg.to_dict()
        self.assertGreater(data["node_count"], 4)
        self.assertGreater(data["edge_count"], 3)

        # Check node types
        types = data["node_types_count"]
        self.assertIn("Product", types)
        self.assertIn("IngredientEntry", types)
        self.assertIn("ChemicalSubstance", types)
        self.assertIn("QSARPrediction", types)
        self.assertIn("EvidenceRecord", types)
        self.assertIn("Jurisdiction", types)

        # Check JSON export
        json_str = kg.to_json()
        self.assertIn("Test Cream", json_str)
        self.assertIn("pyridine-3-carboxamide", json_str)

    def test_qsar_prediction_nodes_and_edges_exist_for_screened_ingredients(self):
        """
        Regression test: ensure QSAR prediction data in flattened report structure
        correctly generates QSARPrediction nodes and HAS_QSAR_PREDICTION relationships.
        Fails if QSAR predictions exist but their graph relationships are missing.
        """
        mock_serialized_results = [
            {
                "raw_ingredient": "Aqua",
                "normalized_ingredient": "aqua",
                "primary_status": "verified",
                "mapping": {
                    "pubchem_cid": 962,
                    "iupac_name": "oxidane",
                    "connectivity_smiles": "O",
                    "identity_verified": True,
                },
                "toxicity": {
                    "status": "completed",
                    "endpoint": "NR-AR",
                    "predicted_activity": 0,
                    "activity_probability": 0.0,
                    "decision_threshold": 0.5,
                    "maximum_reference_similarity": 0.166667,
                    "applicability": "low_similarity",
                    "model_type": "RandomForestClassifier",
                    "error": None,
                },
            },
            {
                "raw_ingredient": "Octocrylene",
                "normalized_ingredient": "octocrylene",
                "primary_status": "verified",
                "mapping": {
                    "pubchem_cid": 22571,
                    "iupac_name": "octocrylene",
                    "connectivity_smiles": "CCCCC(CC)COC(=O)C(=C(C1=CC=CC=C1)C2=CC=CC=C2)C#N",
                    "identity_verified": True,
                },
                "toxicity": {
                    "status": "completed",
                    "endpoint": "NR-AR",
                    "predicted_activity": 0,
                    "activity_probability": 0.05,
                    "decision_threshold": 0.5,
                    "applicability": "reference_similar",
                    "model_type": "RandomForestClassifier",
                    "error": None,
                },
            },
            {
                "raw_ingredient": "Diisopropy| Adipate",
                "normalized_ingredient": "diisopropy| adipate",
                "primary_status": "not_found",
                "mapping": {
                    "pubchem_cid": None,
                    "identity_verified": False,
                },
                "toxicity": {
                    "status": "not_run",
                    "predicted_activity": None,
                    "error": None,
                },
            },
        ]

        kg = build_cosmosafe_knowledge_graph(
            product_name="Regression Test Sunscreen",
            ingredient_results=mock_serialized_results,
            jurisdiction="India",
        )

        data = kg.to_dict()
        node_types = data["node_types_count"]
        rel_types = data["relationship_types_count"]

        # QSARPrediction nodes must be created for both screened ingredients
        self.assertIn("QSARPrediction", node_types, "Regression: QSARPrediction node type is missing from graph")
        self.assertEqual(node_types["QSARPrediction"], 2)

        # HAS_QSAR_PREDICTION edges must connect substance to QSAR prediction
        self.assertIn("HAS_QSAR_PREDICTION", rel_types, "Regression: HAS_QSAR_PREDICTION relationship is missing from graph")
        self.assertEqual(rel_types["HAS_QSAR_PREDICTION"], 2)

        # Validate specific substance-to-QSAR edge
        qsar_edges = [e for e in kg.edges if e["relationship"] == "HAS_QSAR_PREDICTION"]
        self.assertEqual(len(qsar_edges), 2)
        sources = {e["source"] for e in qsar_edges}
        targets = {e["target"] for e in qsar_edges}
        self.assertIn("substance:cid_962", sources)
        self.assertIn("substance:cid_22571", sources)
        self.assertIn("qsar:nr_ar_962", targets)
        self.assertIn("qsar:nr_ar_22571", targets)

    def test_actual_report_knowledge_graph_qsar_edges(self):
        """
        Verify that building the knowledge graph from actual report results
        produces QSAR prediction relationships for all screened ingredients.
        """
        report_file = SRC_DIR.parent / "data" / "toxicity_report.json"
        if not report_file.exists():
            return
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)

        screened = [r for r in report.get("results", []) if r.get("assessment_status") == "assessed"]
        if not screened:
            return

        kg = build_cosmosafe_knowledge_graph(
            product_name="Report Graph",
            ingredient_results=report.get("results", []),
            jurisdiction="India",
        )
        data = kg.to_dict()
        self.assertIn("QSARPrediction", data["node_types_count"])
        self.assertEqual(data["node_types_count"]["QSARPrediction"], len(screened))
        self.assertIn("HAS_QSAR_PREDICTION", data["relationship_types_count"])
        self.assertEqual(data["relationship_types_count"]["HAS_QSAR_PREDICTION"], len(screened))


if __name__ == "__main__":
    unittest.main()
