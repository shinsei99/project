"""意味検索（ベクトル）の system-python 側。torch は持たない。

- 質問のベクトル化だけ .venv-embed の embed_cli.py に subprocess で投げる（重い依存を閲覧UIに載せない）。
- 文書側ベクトルは mail.db から読み、numpy で全件コサイン（55k×384≒84MBの行列積＝1回1秒未満）。
"""
from __future__ import annotations

import base64
import os
import subprocess
from typing import Dict, List, Tuple

import numpy as np

import db

MODEL_NAME = "intfloat/multilingual-e5-small"   # embeddings.MODEL_NAME と一致させる
DIM = 384

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(_HERE, ".venv-embed", "bin", "python")
_CLI = os.path.join(_HERE, "embed_cli.py")


def available() -> bool:
    return os.path.exists(_VENV_PY) and os.path.exists(_CLI)


def embed_query(text: str) -> np.ndarray:
    """質問文 → 正規化済みベクトル (DIM,)。venv の CLI を呼ぶ。"""
    if not available():
        raise RuntimeError("埋め込み環境（.venv-embed）がありません。")
    proc = subprocess.run([_VENV_PY, _CLI, text],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError("ベクトル化に失敗: {}".format((proc.stderr or "").strip()[:300]))
    raw = base64.b64decode(proc.stdout.strip())
    return np.frombuffer(raw, dtype=np.float32)


def search(conn, query: str, top: int = 800) -> Tuple[List[int], Dict[int, float]]:
    """意味が近い順の message_id 列と、id→類似度(0..1) を返す。"""
    ids, blobs = db.load_all_embeddings(conn, MODEL_NAME)
    if not ids:
        return [], {}
    mat = np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(ids), DIM)
    qv = embed_query(query)
    sims = mat @ qv                       # 正規化済み同士なので内積＝コサイン
    order = np.argsort(-sims)[:top]
    ordered_ids = [ids[int(i)] for i in order]
    sim_map = {ids[int(i)]: float(sims[int(i)]) for i in order}
    return ordered_ids, sim_map
