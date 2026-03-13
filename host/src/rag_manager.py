import os
from typing import List

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False

try:
    from langchain_openai import OpenAIEmbeddings
    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    _EMBEDDINGS_AVAILABLE = False

import uuid


class RagManager:
    def __init__(self):
        self._client = None
        self._embeddings = None

        self._qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")

        # Embedding config
        embedding_ip = os.environ.get("EMBEDDING_IP", "127.0.0.1")
        embedding_port = os.environ.get("EMBEDDING_PORT", "11434")
        self._embedding_base_url = f"http://{embedding_ip}:{embedding_port}/v1"
        self._embedding_model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
        self._embedding_api_key = os.environ.get("EMBEDDING_API_KEY", "dummy")
        self.vector_size = int(os.environ.get("VECTOR_SIZE", "768"))

        # Rerank config (prepared for future usage)
        self.rerank_ip = os.environ.get("RERANK_IP", "127.0.0.1")
        self.rerank_port = os.environ.get("RERANK_PORT", "11434")
        self.rerank_base_url = f"http://{self.rerank_ip}:{self.rerank_port}/v1"
        self.rerank_model = os.environ.get("RERANK_MODEL", "reranker")
        self.rerank_api_key = os.environ.get("RERANK_API_KEY", "dummy")

    def _get_client(self):
        if self._client is None:
            if not _QDRANT_AVAILABLE:
                raise RuntimeError("qdrant_client is not installed")
            self._client = QdrantClient(url=self._qdrant_url)
        return self._client

    def _get_embeddings(self):
        if self._embeddings is None:
            if not _EMBEDDINGS_AVAILABLE:
                raise RuntimeError("langchain_openai is not installed")
            self._embeddings = OpenAIEmbeddings(
                model=self._embedding_model,
                base_url=self._embedding_base_url,
                api_key=self._embedding_api_key,
            )
        return self._embeddings

    def init_collection(self, tag: str) -> bool:
        """
        In Qdrant, a collection can represent a tag. Alternatively, we use one collection
        and filter by tag. The spec says "削除・再作成" (delete and recreate).
        So we'll use the tag directly as the collection name.
        """
        client = self._get_client()
        collection_name = f"tag_{tag}"
        if client.collection_exists(collection_name):
            client.delete_collection(collection_name)

        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )
        return True

    def add_text_background(self, tag: str, text: str, job_id: str, status_dict: dict):
        """Background task to chunk and embed text"""
        try:
            status_dict[job_id] = {"status": "processing"}
            client = self._get_client()
            embeddings = self._get_embeddings()
            collection_name = f"tag_{tag}"

            # Simple chunking for now
            chunk_size = 1000
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

            # Embeddings
            vectors = embeddings.embed_documents(chunks)

            # Store in Qdrant
            points = [
                PointStruct(id=str(uuid.uuid4()), vector=vector, payload={"text": chunk})
                for vector, chunk in zip(vectors, chunks)
            ]

            client.upsert(collection_name=collection_name, points=points)
            status_dict[job_id] = {"status": "completed"}
        except Exception as e:
            status_dict[job_id] = {"status": "error", "error_msg": str(e)}

    def search_context(self, tag: str, query: str, limit: int = 3) -> str:
        """Search similar texts. Returns empty string if Qdrant is unavailable."""
        try:
            client = self._get_client()
            embeddings = self._get_embeddings()
            collection_name = f"tag_{tag}"
            if not client.collection_exists(collection_name):
                return ""

            query_vector = embeddings.embed_query(query)
            results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
            )
            context_parts = [hit.payload.get("text", "") for hit in results if hit.payload]
            return "\n\n".join(context_parts)
        except Exception:
            return ""


# Global instance
rag_manager = RagManager()
