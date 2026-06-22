"""
Knowledge base loader for the ClimateNexus RAG pipeline.

Reads curated markdown documents from src/rag/knowledge/, chunks them,
and upserts into ChromaDB. Idempotent — skips documents already loaded.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

from src.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category detection from filename
# ---------------------------------------------------------------------------

_CATEGORY_MAP = {
    "ll97": "regulation",
    "berdo": "regulation",
    "leed": "certification",
    "energy_star": "benchmark",
    "ira_tax": "incentive",
    "fema_mitigation": "incentive",
    "heat_pump": "technology",
    "cool_roof": "technology",
    "led_lighting": "technology",
    "solar_pv": "technology",
    "bms_upgrade": "technology",
    "flood_mitigation": "resilience",
    "wildfire": "resilience",
    "green_premium": "benchmark",
}


def _detect_category(filename: str) -> str:
    """Infer document category from the filename."""
    name_lower = filename.lower()
    for pattern, category in _CATEGORY_MAP.items():
        if pattern in name_lower:
            return category
    return "general"


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def _chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    Split text into chunks on paragraph boundaries.

    Tries to split on double-newlines (paragraphs) first, then falls
    back to single newlines, then hard-splits at chunk_size.
    """
    # Split on markdown headings and double newlines
    sections = re.split(r"\n(?=#{1,3}\s)", text)

    chunks: list[str] = []
    current_chunk = ""

    for section in sections:
        paragraphs = section.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # Start new chunk with overlap from previous
                if chunks and chunk_overlap > 0:
                    overlap_text = chunks[-1][-chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para

                # Hard-split if a single paragraph exceeds chunk_size
                while len(current_chunk) > chunk_size:
                    split_point = current_chunk.rfind(". ", 0, chunk_size)
                    if split_point == -1:
                        split_point = chunk_size
                    else:
                        split_point += 1  # include the period
                    chunks.append(current_chunk[:split_point].strip())
                    current_chunk = current_chunk[split_point:].strip()

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class KnowledgeLoader:
    """
    Loads markdown documents from the knowledge directory into ChromaDB.

    Usage:
        loader = KnowledgeLoader(vector_store)
        loader.load_all()  # idempotent
    """

    def __init__(
        self,
        vector_store: VectorStore,
        knowledge_dir: Optional[str] = None,
    ):
        self.vector_store = vector_store
        self.knowledge_dir = knowledge_dir or os.path.join(
            os.path.dirname(__file__), "knowledge"
        )

    def load_all(self) -> int:
        """
        Load all .md files from the knowledge directory.

        Returns the total number of chunks upserted.
        """
        knowledge_path = Path(self.knowledge_dir)
        if not knowledge_path.exists():
            logger.warning("Knowledge directory not found: %s", self.knowledge_dir)
            return 0

        md_files = sorted(knowledge_path.glob("*.md"))
        if not md_files:
            logger.warning("No .md files found in %s", self.knowledge_dir)
            return 0

        total_chunks = 0
        for md_file in md_files:
            n = self._load_file(md_file)
            total_chunks += n

        logger.info(
            "Knowledge base loaded: %d files, %d total chunks",
            len(md_files),
            total_chunks,
        )
        return total_chunks

    def _load_file(self, file_path: Path) -> int:
        """Load and chunk a single markdown file."""
        filename = file_path.stem
        category = _detect_category(filename)

        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            return 0

        chunks = _chunk_text(text)

        documents = []
        for i, chunk in enumerate(chunks):
            doc_id = f"{filename}_chunk_{i:03d}"
            documents.append(
                {
                    "id": doc_id,
                    "text": chunk,
                    "metadata": {
                        "source": file_path.name,
                        "category": category,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    },
                }
            )

        n = self.vector_store.add_documents(documents)
        logger.info(
            "Loaded '%s' (%s): %d chunks",
            file_path.name,
            category,
            len(documents),
        )
        return n
