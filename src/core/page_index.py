"""PageIndex (RAG Indexing) for Playwright HTML snapshots.

This module provides a lightweight RAG-style index that converts HTML snapshots
into vector embeddings and stores them in a vector store (Chroma).

It is designed to support later retrieval of similar elements when a locator fails.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from .html_capture import HTMLSnapshot, ElementNode


@dataclass
class PageIndexConfig:
    """Configuration for PageIndex vector store."""

    persist_directory: str = "./.pageindex"
    collection_name: str = "page_index"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    metadata_keywords: List[str] = None

    def __post_init__(self):
        if self.metadata_keywords is None:
            self.metadata_keywords = ["tag", "xpath", "accessible_name", "url"]


@dataclass
class IndexedElement:
    """Represents an indexed element with embedding metadata."""

    id: str
    text: str
    metadata: Dict[str, Any]


class PageIndex:
    """Index (vector store) for HTML snapshots.

    This class is responsible for:
      - converting HTML snapshot elements into embedding-aware documents
      - storing/retrieving them from a Chroma collection
      - querying the collection for nearest neighbors
    """

    def __init__(self, config: Optional[PageIndexConfig] = None):
        self.config = config or PageIndexConfig()
        # Create a persistent Chroma client in the configured directory.
        settings = Settings(persist_directory=self.config.persist_directory, is_persistent=True)
        self._client = chromadb.Client(settings)

        # Use Chroma's built-in SentenceTransformer embedding function for local embeddings.
        self._chromadb_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.config.embedding_model_name
        )
        self._collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        if self.config.collection_name in [c.name for c in self._client.list_collections()]:
            return self._client.get_collection(name=self.config.collection_name)
        return self._client.create_collection(
            name=self.config.collection_name,
            embedding_function=self._chromadb_ef,
        )

    def clear(self) -> None:
        """Clear the current index (delete all vectors).

        Note: Chroma's `delete` method requires filters, so we delete and recreate
        the collection to ensure a clean state.
        """
        if self.config.collection_name in [c.name for c in self._client.list_collections()]:
            self._client.delete_collection(name=self.config.collection_name)
        self._collection = self._get_or_create_collection()

    def build_index(self, snapshot: HTMLSnapshot, overwrite: bool = True) -> None:
        """Index all elements in a snapshot.

        Args:
            snapshot: HTMLSnapshot to index
            overwrite: If True, clears existing index before adding new data
        """
        if overwrite:
            self.clear()

        documents = []
        metadatas = []
        ids = []
        id_counts: Dict[str, int] = {}

        for element in snapshot.elements:
            entry = self._create_index_entry(snapshot, element)
            base_id = entry.id
            count = id_counts.get(base_id, 0)
            unique_id = base_id if count == 0 else f"{base_id}#{count + 1}"
            id_counts[base_id] = count + 1

            ids.append(unique_id)
            documents.append(entry.text)
            metadatas.append(entry.metadata)

        if not ids:
            return

        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def _create_index_entry(self, snapshot: HTMLSnapshot, element: ElementNode) -> IndexedElement:
        """Create an IndexedElement from an HTML element node."""
        # Compose text for embedding that includes tag, accessible name, and attributes
        parts: List[str] = []
        if element.tag:
            parts.append(element.tag)
        if element.accessible_name:
            parts.append(element.accessible_name)
        elif element.text:
            parts.append(element.text)
        if element.attrs:
            # Include stable attributes that are likely meaningful
            for attr in ["id", "class", "data-testid", "name", "role"]:
                if attr in element.attrs:
                    parts.append(f"{attr}:{element.attrs.get(attr)}")

        text = " | ".join([p for p in parts if p])

        # Generate element ID from timestamp and xpath
        element_id = f"{snapshot.timestamp}:{element.xpath}"

        # Chroma metadata must use primitive types; convert attrs (dict) to JSON string.
        metadata = {
            "url": snapshot.url,
            "xpath": element.xpath,
            "tag": element.tag,
            "accessible_name": element.accessible_name,
            "text": element.text,
            "attrs": json.dumps(element.attrs, ensure_ascii=False) if element.attrs else None,
            "visible": element.visible,
            "children_count": element.children_count,
            "parent_tag": element.parent_tag,
        }

        # Optional: include additional metadata keys
        if self.config.metadata_keywords:
            metadata = {k: v for k, v in metadata.items() if k in (self.config.metadata_keywords + ["attrs"]) or k == "xpath"}

        # Ensure metadata values are serializable for Chroma (primitives only).
        # Drop None values because Chroma's Rust bindings can reject them in bulk adds.
        sanitized: Dict[str, Any] = {}
        for k, v in metadata.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                sanitized[k] = v
            else:
                # Convert complex structures to string
                try:
                    sanitized[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    sanitized[k] = str(v)

        return IndexedElement(id=element_id, text=text, metadata=sanitized)

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query the index for similar elements.

        Args:
            query_text: Text query to embed and search.
            top_k: Number of neighbors to return.

        Returns:
            List of matching metadata results with distances.
        """
        if not query_text:
            return []

        results = self._collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=['metadatas', 'distances', 'documents'],
        )

        # Chroma returns nested lists for each query
        out = []
        if results and len(results.get("metadatas", [])) > 0:
            for i in range(len(results["metadatas"][0])):
                out.append(
                    {
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "document": results["documents"][0][i],
                    }
                )
        return out

    def persist(self) -> None:
        """Persist the index to disk."""
        if hasattr(self._client, "persist"):
            self._client.persist()

    def export_index(self, output_path: str) -> None:
        """Export the current index metadata to JSON."""
        # Chroma returns ids by default; include only supported payload fields.
        data = self._collection.get(include=["metadatas", "documents"])
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def info(self) -> Dict[str, Any]:
        """Return basic information about the index."""
        return {
            "collection": self.config.collection_name,
            "persist_directory": os.path.abspath(self.config.persist_directory),
            "count": self._collection.count(),
        }
