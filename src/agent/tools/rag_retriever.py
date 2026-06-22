"""
RAG Retriever tool — semantic search over the sustainability knowledge base.
"""

from typing import Optional

from src.rag.vector_store import VectorStore


class RAGRetriever:
    """Queries the ChromaDB sustainability knowledge base."""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search for relevant sustainability knowledge.

        Args:
            query:    Natural language question or topic.
            n_results: Number of chunks to return.
            category:  Optional filter — "regulation", "incentive",
                       "technology", "certification", "benchmark", "resilience"

        Returns list of dicts with text, source, category, distance.
        """
        return self.vector_store.query(
            question=query,
            n_results=n_results,
            category=category,
        )

    def retrieve_for_risks(
        self,
        risk_signals: list[dict],
        n_per_risk: int = 3,
    ) -> list[dict]:
        """
        Retrieve knowledge for multiple risk signals.

        Each risk_signal should have:
            hazard:   str  — "flood", "heat", "wildfire", "transition", "seismic"
            severity: str  — "high", "medium", "low"
            location: str  — city/state for regulation matching

        Returns deduplicated list of relevant chunks.
        """
        _risk_to_queries = {
            "flood": [
                "flood mitigation measures commercial building",
                "FEMA flood hazard mitigation grants funding",
                "flood insurance NFIP premium reduction",
            ],
            "heat": [
                "cool roof heat mitigation commercial building",
                "heat pump HVAC cooling efficiency",
                "urban heat island reduction strategies",
            ],
            "wildfire": [
                "wildfire resilience building hardening ember resistant",
                "defensible space commercial property wildfire",
                "wildfire insurance risk mitigation",
            ],
            "transition": [
                "building performance standard LL97 BERDO compliance",
                "energy efficiency retrofit commercial building",
                "IRA tax credits clean energy commercial",
            ],
            "seismic": [
                "seismic retrofit commercial building risk",
                "earthquake resilience structural upgrades",
            ],
        }

        seen_ids: set[str] = set()
        results: list[dict] = []

        for signal in risk_signals:
            hazard = signal.get("hazard", "")
            queries = _risk_to_queries.get(hazard, [])

            # Also search for location-specific regulations
            location = signal.get("location", "")
            if location:
                queries.append(f"{location} building regulation compliance")

            for query in queries[:n_per_risk]:
                chunks = self.vector_store.query(
                    question=query, n_results=2
                )
                for chunk in chunks:
                    chunk_id = f"{chunk['source']}_{chunk['text'][:50]}"
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        results.append(chunk)

        return results
