"""
ChromaDB vector store wrapper for the ClimateNexus sustainability knowledge base.

Provides semantic search over curated sustainability documents (LEED, LL97,
IRA credits, technology specs, etc.) for the RAG-powered strategy agent.
"""

import logging
import os
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding function using Gemini (or fallback to default)
# ---------------------------------------------------------------------------


def _get_embedding_function():
    """
    Return a ChromaDB-compatible embedding function.

    Uses Gemini text-embedding-004 via the google-genai SDK if
    GOOGLE_API_KEY is set, otherwise falls back to ChromaDB's built-in
    default embeddings.

    Note: ChromaDB's built-in GoogleGenerativeAiEmbeddingFunction is
    broken in chromadb>=1.5 due to passing unsupported 'headers' to
    genai.configure(). This custom wrapper avoids that issue.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai
            from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

            class GeminiEmbeddingFunction(EmbeddingFunction):
                """Custom Gemini embedding function using google-genai SDK."""

                def __init__(self, api_key: str, model_name: str = "gemini-embedding-001"):
                    self._client = genai.Client(api_key=api_key)
                    self._model = model_name

                def __call__(self, input: Documents) -> Embeddings:
                    embeddings = []
                    for text in input:
                        result = self._client.models.embed_content(
                            model=self._model,
                            contents=text,
                        )
                        embeddings.append(result.embeddings[0].values)
                    return embeddings

            logger.info("Using Gemini gemini-embedding-001 for vector store")
            return GeminiEmbeddingFunction(api_key=api_key)
        except Exception as exc:
            logger.warning("Failed to init Gemini embeddings: %s — using default", exc)

    logger.info("Using ChromaDB default embeddings (no GOOGLE_API_KEY set)")
    return None  # ChromaDB uses its built-in default


# ---------------------------------------------------------------------------
# VectorStore class
# ---------------------------------------------------------------------------


class VectorStore:
    """
    Persistent ChromaDB vector store for the sustainability knowledge base.

    Usage:
        vs = VectorStore()
        vs.add_documents([{"id": "...", "text": "...", "metadata": {...}}])
        results = vs.query("What are LL97 penalties?", n_results=5)
    """

    COLLECTION_NAME = "climate_nexus_kb"

    def __init__(self, persist_dir: str = "./data/chroma_db"):
        self.persist_dir = persist_dir
        self._ef = _get_embedding_function()

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get-or-create the collection
        kwargs = {"name": self.COLLECTION_NAME}
        if self._ef is not None:
            kwargs["embedding_function"] = self._ef
        self.collection = self.client.get_or_create_collection(**kwargs)

        logger.info(
            "VectorStore ready — collection '%s' has %d documents",
            self.COLLECTION_NAME,
            self.collection.count(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_documents(
        self,
        documents: list[dict],
    ) -> int:
        """
        Add documents to the vector store.

        Each document is a dict with keys:
            id:       str  — unique identifier
            text:     str  — the document text
            metadata: dict — arbitrary metadata (source, category, etc.)

        Returns the number of documents added.
        """
        if not documents:
            return 0

        ids = [d["id"] for d in documents]
        texts = [d["text"] for d in documents]
        metadatas = [d.get("metadata", {}) for d in documents]

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info("Upserted %d documents into vector store", len(documents))
        return len(documents)

    def query(
        self,
        question: str,
        n_results: int = 5,
        category: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search over the knowledge base.

        Args:
            question:  The search query.
            n_results: Number of results to return.
            category:  Optional filter — one of:
                       "regulation", "incentive", "technology",
                       "certification", "benchmark", "resilience"

        Returns a list of dicts, each with:
            text:     str  — the matched document chunk
            source:   str  — original document filename
            category: str  — document category
            distance: float — similarity distance (lower = more similar)
        """
        where_filter = None
        if category:
            where_filter = {"category": category}

        results = self.collection.query(
            query_texts=[question],
            n_results=n_results,
            where=where_filter,
        )

        output = []
        for i in range(len(results["ids"][0])):
            output.append(
                {
                    "text": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", "unknown"),
                    "category": results["metadatas"][0][i].get("category", "unknown"),
                    "distance": results["distances"][0][i]
                    if results.get("distances")
                    else None,
                }
            )

        return output

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self.collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection (for testing)."""
        self.client.delete_collection(self.COLLECTION_NAME)
        kwargs = {"name": self.COLLECTION_NAME}
        if self._ef is not None:
            kwargs["embedding_function"] = self._ef
        self.collection = self.client.get_or_create_collection(**kwargs)
        logger.info("Vector store reset")
