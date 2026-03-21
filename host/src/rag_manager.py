import os
from typing import List

from .chunker import chunk_text

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

    def add_text_background(
        self,
        tag: str,
        text: str,
        job_id: str,
        status_dict: dict,
        strategy: str = "recursive_semantic",
        chunk_size: int = 800,
        overlap: int = 150,
        window_size: int = 5,
        overlap_sentences: int = 1,
        breakpoint_percentile: int = 85,
    ):
        """Background task: チャンキング → エンベディング → Qdrant保存"""
        try:
            status_dict[job_id] = {"status": "processing"}
            client = self._get_client()
            embeddings = self._get_embeddings()
            collection_name = f"tag_{tag}"

            # チャンキング（戦略に応じて分割）
            chunks = chunk_text(
                text,
                strategy=strategy,
                embeddings=embeddings if strategy == "semantic" else None,
                chunk_size=chunk_size,
                overlap=overlap,
                window_size=window_size,
                overlap_sentences=overlap_sentences,
                breakpoint_percentile=breakpoint_percentile,
            )

            if not chunks:
                status_dict[job_id] = {"status": "error", "error_msg": "テキストからチャンクを生成できませんでした。"}
                return

            # エンベディング（semantic は chunking 時に計算済みのため不要な重複なし）
            vectors = embeddings.embed_documents(chunks)

            # コレクションが存在しない場合は自動作成
            if not client.collection_exists(collection_name):
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )

            # Qdrant に保存（チャンキング戦略もペイロードに記録）
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"text": chunk, "strategy": strategy},
                )
                for vector, chunk in zip(vectors, chunks)
            ]

            client.upsert(collection_name=collection_name, points=points)
            status_dict[job_id] = {"status": "completed", "chunk_count": len(chunks)}
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
            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
            )
            context_parts = [hit.payload.get("text", "") for hit in response.points if hit.payload]
            return "\n\n".join(context_parts)
        except Exception:
            return ""

    def delete_chunk(self, tag: str, chunk_id: str):
        """指定IDのチャンクを1件削除する"""
        from qdrant_client.models import PointIdsList
        client = self._get_client()
        collection_name = f"tag_{tag}"
        client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=[chunk_id]),
        )

    def search_with_scores(self, tag: str, query: str, limit: int = 3) -> dict:
        """本番と同じ検索処理をスコア付きで返す"""
        client = self._get_client()
        embeddings = self._get_embeddings()
        collection_name = f"tag_{tag}"
        if not client.collection_exists(collection_name):
            return {"results": [], "context": ""}

        query_vector = embeddings.embed_query(query)
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
        )
        results = [
            {"id": str(h.id), "text": h.payload.get("text", "") if h.payload else "", "score": round(h.score, 4)}
            for h in response.points
        ]
        context = "\n\n".join(r["text"] for r in results)
        return {"results": results, "context": context}

    def list_collections(self) -> List[dict]:
        """タグコレクションの一覧とチャンク数を返す"""
        try:
            client = self._get_client()
            collections = client.get_collections().collections
            result = []
            for col in collections:
                if col.name.startswith("tag_"):
                    tag = col.name[4:]
                    info = client.get_collection(col.name)
                    result.append({"tag": tag, "count": info.points_count or 0})
            return result
        except Exception:
            return []

    def get_chunks(self, tag: str, limit: int = 200) -> dict:
        """タグのチャンク一覧を返す"""
        try:
            client = self._get_client()
            collection_name = f"tag_{tag}"
            if not client.collection_exists(collection_name):
                return {"chunks": [], "total": 0}
            info = client.get_collection(collection_name)
            total = info.points_count or 0
            points, _ = client.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            chunks = [
                {"id": str(p.id), "text": p.payload.get("text", "") if p.payload else ""}
                for p in points
            ]
            return {"chunks": chunks, "total": total}
        except Exception as e:
            return {"chunks": [], "total": 0, "error": str(e)}


# Global instance
rag_manager = RagManager()
