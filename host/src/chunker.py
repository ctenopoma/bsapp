"""
チャンキング戦略モジュール
固定長分割を使わず、意味的・構造的な境界でテキストを分割する。

利用可能な戦略:
  recursive_semantic  : 再帰的意味分割（汎用・推奨デフォルト）
  sentence_window     : 文ウィンドウ（Q&A・密度の高い情報文書向け）
  semantic            : 意味的チャンキング（低速・最高精度）
  structure_aware     : 構造認識（Markdown・技術文書・仕様書向け）
"""

import re
import math
from typing import List, Optional, Any


# ─── 戦略メタデータ ──────────────────────────────────────────────────────

CHUNK_STRATEGIES = [
    {
        "id": "recursive_semantic",
        "name": "再帰的意味分割（推奨）",
        "description": "段落→文→句の優先順位で意味的な境界を検出して分割。汎用テキストに最適。",
    },
    {
        "id": "sentence_window",
        "name": "文ウィンドウ",
        "description": "文単位で分割後、N文のスライディングウィンドウでグループ化。Q&Aや密度の高い情報文書に有効。",
    },
    {
        "id": "semantic",
        "name": "意味的チャンキング（低速・高精度）",
        "description": "文ごとに埋め込みを計算し、コサイン類似度が下がった箇所をトピック境界として分割。最も高品質だが処理が遅い。",
    },
    {
        "id": "structure_aware",
        "name": "構造認識（Markdown・文書）",
        "description": "Markdownヘッダや番号付き見出し・区切り線を検出してセクション単位で分割。技術文書・仕様書・マニュアルに最適。",
    },
]


# ─── 共通ユーティリティ ──────────────────────────────────────────────────

# 日本語・英語の文末パターン
_SENTENCE_END = re.compile(r'(?<=[。！？!?])\s*|\n{2,}')

# Markdown / 文書構造のヘッダパターン
_HEADER_PATTERN = re.compile(
    r'^(#{1,6} .+|={3,}|-{3,}|\*{3,}'
    r'|第[一二三四五六七八九十百千万零〇]+[章節条項目].*'
    r'|\d+[\.．、]\s*\S)',
    re.MULTILINE,
)


def _split_sentences(text: str) -> List[str]:
    """日英対応の文分割（文末記号・連続改行で区切る）"""
    parts = _SENTENCE_END.split(text)
    return [p.strip() for p in parts if p.strip()]


def _enforce_max_chars(chunks: List[str], max_chars: int) -> List[str]:
    """最大文字数を超えるチャンクを文境界で再分割する安全処置"""
    result = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            result.append(chunk)
            continue
        sentences = _split_sentences(chunk)
        current = ""
        for s in sentences:
            if len(current) + len(s) + 1 <= max_chars:
                current = (current + " " + s).strip()
            else:
                if current:
                    result.append(current)
                current = s
        if current:
            result.append(current)
    return result


# ─── 戦略 1: 再帰的意味分割 ─────────────────────────────────────────────

def chunk_recursive_semantic(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> List[str]:
    """
    階層的セパレータで再帰的に分割する。
    大きい区切り（段落）→ 文末記号 → 句読点 の優先順位で試みる。
    セパレータが見つからない場合のみ、次の細かい区切りに降格する。
    """
    # 日本語・英語の優先順付きセパレータ
    separators = [
        "\n\n\n", "\n\n", "\n",
        "。", "！", "？", "…",
        ". ", "! ", "? ",
        "、", "，", ", ",
        " ",
    ]

    def _merge(parts: List[str]) -> List[str]:
        """部品リストを chunk_size 以内でグリーディーにマージする"""
        chunks: List[str] = []
        current = ""
        for part in parts:
            if not part:
                continue
            if len(current) + len(part) <= chunk_size:
                current += part
            else:
                if current:
                    chunks.append(current)
                current = part
        if current:
            chunks.append(current)
        return chunks

    def _split(text: str, seps: List[str]) -> List[str]:
        if len(text) <= chunk_size:
            return [text]
        if not seps:
            # 最終手段: 文字数で強制分割
            return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

        sep = seps[0]
        parts = text.split(sep)
        if len(parts) == 1:
            # このセパレータでは分割できなかった → 次へ
            return _split(text, seps[1:])

        # セパレータを末尾に復元（改行系以外）
        rejoined = []
        for i, p in enumerate(parts):
            if i < len(parts) - 1 and sep not in ("\n\n\n", "\n\n", "\n", " "):
                rejoined.append(p + sep)
            else:
                rejoined.append(p)

        # chunk_size を超えるピースをさらに再帰分割
        fine: List[str] = []
        for piece in rejoined:
            if not piece.strip():
                continue
            if len(piece) > chunk_size:
                fine.extend(_split(piece, seps[1:]))
            else:
                fine.append(piece)

        return _merge(fine)

    raw_chunks = _split(text.strip(), separators)

    # オーバーラップ付与: 前チャンクの末尾 overlap 文字を先頭に付加
    if overlap > 0 and len(raw_chunks) > 1:
        overlapped = [raw_chunks[0]]
        for i in range(1, len(raw_chunks)):
            prev = raw_chunks[i - 1]
            prefix = prev[-overlap:] if len(prev) > overlap else prev
            overlapped.append(prefix + raw_chunks[i])
        raw_chunks = overlapped

    return _enforce_max_chars([c for c in raw_chunks if c.strip()], chunk_size * 2)


# ─── 戦略 2: 文ウィンドウ ────────────────────────────────────────────────

def chunk_sentence_window(
    text: str,
    window_size: int = 5,
    overlap_sentences: int = 1,
    max_chars: int = 1500,
) -> List[str]:
    """
    文単位で分割後、N文のスライディングウィンドウでグループ化する。
    文脈が失われにくく、Q&Aや高密度情報文書に有効。
    overlap_sentences: 隣接チャンクで共有する文数。
    """
    sentences = _split_sentences(text)
    if not sentences:
        return [text] if text.strip() else []

    step = max(1, window_size - overlap_sentences)
    chunks: List[str] = []

    for i in range(0, len(sentences), step):
        window = sentences[i:i + window_size]
        chunk = "".join(window)
        # ウィンドウが max_chars を超える場合は文数を減らして調整
        if len(chunk) > max_chars:
            trimmed = []
            total = 0
            for s in window:
                if total + len(s) <= max_chars:
                    trimmed.append(s)
                    total += len(s)
                else:
                    break
            chunk = "".join(trimmed)
        if chunk.strip():
            chunks.append(chunk)

    return chunks


# ─── 戦略 3: 意味的チャンキング (Semantic Chunking) ─────────────────────

def chunk_semantic(
    text: str,
    embeddings: Any,
    breakpoint_percentile: int = 85,
    min_chunk_chars: int = 150,
) -> List[str]:
    """
    文ごとに埋め込みを計算し、隣接文間のコサイン類似度を測定する。
    類似度の低い箇所（統計的外れ値）をトピック境界として分割する。
    breakpoint_percentile: 類似度分布の何パーセンタイル以下を境界とするか（高いほど細かく分割）。
    """
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError("semantic strategy requires numpy")

    sentences = _split_sentences(text)
    if len(sentences) <= 2:
        return [text.strip()] if text.strip() else []

    # 各文の埋め込みを取得
    vectors = np.array(embeddings.embed_documents(sentences))

    # 隣接文間のコサイン類似度を計算
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-10, norms)
    normed = vectors / norms

    similarities = np.einsum("ij,ij->i", normed[:-1], normed[1:])  # shape: (n-1,)

    # 類似度が低い（= トピックが変わる）箇所を境界と見なす
    threshold = float(np.percentile(similarities, 100 - breakpoint_percentile))

    chunks: List[str] = []
    current: List[str] = [sentences[0]]

    for i, sim in enumerate(similarities):
        if sim <= threshold and len("".join(current)) >= min_chunk_chars:
            chunks.append("".join(current))
            current = [sentences[i + 1]]
        else:
            current.append(sentences[i + 1])

    if current:
        chunks.append("".join(current))

    return [c for c in chunks if c.strip()]


# ─── 戦略 4: 構造認識チャンキング ────────────────────────────────────────

def chunk_structure_aware(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> List[str]:
    """
    Markdown の見出し・番号付きセクション・区切り線などを検出し、
    セクション単位で分割する。各セクションが chunk_size を超える場合は
    再帰的意味分割でさらに細分化する。
    技術文書・仕様書・マニュアルに最適。
    """
    positions = [m.start() for m in _HEADER_PATTERN.finditer(text)]

    if not positions:
        # 構造が検出できなければ再帰的意味分割にフォールバック
        return chunk_recursive_semantic(text, chunk_size=chunk_size, overlap=overlap)

    # 先頭にセクション境界を追加してセクション分割
    boundaries = sorted(set([0] + positions + [len(text)]))
    sections = [text[boundaries[i]:boundaries[i + 1]].strip() for i in range(len(boundaries) - 1)]
    sections = [s for s in sections if s]

    chunks: List[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            sub = chunk_recursive_semantic(section, chunk_size=chunk_size, overlap=overlap)
            chunks.extend(sub)

    return [c for c in chunks if c.strip()]


# ─── ディスパッチャ ──────────────────────────────────────────────────────

def chunk_text(
    text: str,
    strategy: str = "recursive_semantic",
    embeddings: Optional[Any] = None,
    chunk_size: int = 800,
    overlap: int = 150,
    window_size: int = 5,
    overlap_sentences: int = 1,
    breakpoint_percentile: int = 85,
) -> List[str]:
    """テキストを指定戦略でチャンキングして返す"""
    text = text.strip()
    if not text:
        return []

    if strategy == "recursive_semantic":
        return chunk_recursive_semantic(text, chunk_size=chunk_size, overlap=overlap)

    elif strategy == "sentence_window":
        return chunk_sentence_window(
            text,
            window_size=window_size,
            overlap_sentences=overlap_sentences,
        )

    elif strategy == "semantic":
        if embeddings is None:
            raise ValueError("semantic strategy requires embeddings instance")
        return chunk_semantic(text, embeddings, breakpoint_percentile=breakpoint_percentile)

    elif strategy == "structure_aware":
        return chunk_structure_aware(text, chunk_size=chunk_size, overlap=overlap)

    else:
        raise ValueError(f"Unknown chunking strategy: {strategy!r}")
