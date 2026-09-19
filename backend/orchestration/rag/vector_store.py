from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from .document_preparation import RagDocument

logger = logging.getLogger(__name__)


class FaissVectorStore:
    """In-memory FAISS index with metadata kept beside vector rows."""

    def __init__(self, embedding_service: Any) -> None:
        self.embedding_service = embedding_service
        self._signature: Optional[str] = None
        self._documents: List[RagDocument] = []
        self._index = None
        self._fallback_embeddings: Optional[np.ndarray] = None
        self._using_faiss = False

    @property
    def available(self) -> bool:
        return bool(self._documents) and (self._index is not None or self._fallback_embeddings is not None)

    @property
    def using_faiss(self) -> bool:
        return self._using_faiss

    def build_if_needed(self, documents: Sequence[RagDocument]) -> bool:
        signature = self._signature_for(documents)
        if signature == self._signature and self.available:
            return True
        return self.rebuild(documents, signature)

    def rebuild(self, documents: Sequence[RagDocument], signature: Optional[str] = None) -> bool:
        self._signature = signature or self._signature_for(documents)
        self._documents = list(documents)
        self._index = None
        self._fallback_embeddings = None
        self._using_faiss = False

        if not self._documents:
            return False

        try:
            embeddings = self.embedding_service.encode([doc.content for doc in self._documents])
            embeddings = np.asarray(embeddings, dtype=np.float32)
            if embeddings.ndim != 2 or embeddings.shape[0] != len(self._documents):
                raise ValueError("Embedding service returned an invalid matrix shape.")
            embeddings = self._normalize(embeddings)
        except Exception as exc:
            logger.info("RAG embedding generation failed: %s", type(exc).__name__)
            return False

        try:
            import faiss  # type: ignore

            index = faiss.IndexFlatIP(int(embeddings.shape[1]))
            index.add(embeddings)
            self._index = index
            self._using_faiss = True
            return True
        except Exception as exc:
            logger.info("FAISS unavailable for RAG; using numpy fallback search: %s", type(exc).__name__)
            self._fallback_embeddings = embeddings
            return True

    def search(self, query: str, *, top_k: int = 10, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.available or not query.strip():
            return []
        try:
            query_vector = self.embedding_service.encode([query])
            query_vector = self._normalize(np.asarray(query_vector, dtype=np.float32))
        except Exception as exc:
            logger.info("RAG query embedding failed: %s", type(exc).__name__)
            return []

        limit = min(max(int(top_k) * 4, int(top_k)), len(self._documents))
        if self._index is not None:
            scores, indices = self._index.search(query_vector, limit)
            raw_pairs = zip(indices[0].tolist(), scores[0].tolist())
        elif self._fallback_embeddings is not None:
            sims = np.dot(query_vector, self._fallback_embeddings.T)[0]
            order = np.argsort(-sims)[:limit]
            raw_pairs = ((int(idx), float(sims[idx])) for idx in order)
        else:
            return []

        results: List[Dict[str, Any]] = []
        seen_sources = set()
        for idx, score in raw_pairs:
            if idx < 0 or idx >= len(self._documents):
                continue
            doc = self._documents[idx]
            metadata = dict(doc.metadata)
            if source_type and metadata.get("source_type") != source_type:
                continue
            source_id = metadata.get("source_id")
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            results.append(
                {
                    "source_type": metadata.get("source_type"),
                    "source_id": source_id,
                    "title": metadata.get("title") or "",
                    "relevance_score": round(float(score), 4),
                    "metadata": metadata,
                    "content": doc.content,
                    "url": metadata.get("url") or "",
                }
            )
            if len(results) >= top_k:
                break
        return results

    def _signature_for(self, documents: Sequence[RagDocument]) -> str:
        digest = hashlib.sha256()
        for doc in documents:
            digest.update(doc.chunk_id.encode("utf-8", "ignore"))
            digest.update(doc.content.encode("utf-8", "ignore"))
        return digest.hexdigest()

    def _normalize(self, matrix: np.ndarray) -> np.ndarray:
        if matrix.size == 0:
            return matrix.astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (matrix / norms).astype(np.float32)
