"""ローカルの埋め込みモデルでメール本文をベクトル化する（外部に一切出さない）。

モデル: intfloat/multilingual-e5-small（384次元・日本語対応・軽量）。
e5系は用途で接頭辞が要る: 文書は "passage: "、質問は "query: "。付け忘れると精度が落ちる。

ベクトルは L2 正規化して保存する（コサイン類似＝内積で引けるように）。
初回のモデル読み込みだけ数秒かかる（以後キャッシュ）。torch は arm64 ネイティブが要る
（[[feedback_claude_subprocess]] と同じ arch 不一致の罠。x86_64 wheel だと dlopen で落ちる）。
"""
from __future__ import annotations

import threading
from typing import List

import numpy as np

MODEL_NAME = "intfloat/multilingual-e5-small"
DIM = 384

_model = None
_lock = threading.Lock()


def get_model():
    """SentenceTransformer を1度だけ読み込む（スレッド安全）。"""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def _prep(text: str, limit: int = 2000) -> str:
    # 長い本文は頭を使う（件名＋冒頭で意味は概ね取れる。全文だと遅く・薄まる）
    return " ".join((text or "").split())[:limit]


def embed_passages(subjects: List[str], bodies: List[str]) -> np.ndarray:
    """文書側。件名＋本文冒頭を1本にして "passage: " を付けて埋め込む。"""
    texts = ["passage: {} {}".format(_prep(s, 200), _prep(b))
             for s, b in zip(subjects, bodies)]
    vecs = get_model().encode(texts, normalize_embeddings=True,
                              batch_size=64, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    """質問側。"query: " を付けて1本を埋め込む（正規化済み・(DIM,)）。"""
    v = get_model().encode(["query: " + _prep(text, 400)],
                           normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(v, dtype=np.float32)[0]


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def matrix_from_blobs(blobs) -> np.ndarray:
    """保存した vec バイト列を (N, DIM) の行列に戻す。"""
    if not blobs:
        return np.zeros((0, DIM), dtype=np.float32)
    return np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(blobs), DIM)
