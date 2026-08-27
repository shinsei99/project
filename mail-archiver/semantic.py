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


_CJK_RE = __import__("re").compile(r"[぀-ヿ一-鿿]")
_LAT_RE = __import__("re").compile(r"[A-Za-z]")


def detect_lang_wanted(query: str) -> str:
    """質問文から「英語のメール」「日本語のメール」という指定を読み取る。

    ★これを見ていなかったため「英語で送られてるメール」と書いても全く効かず、
      日本語メールに埋もれていた（2026-08-27 オーナー指摘）。
      LLMに解釈させるまでもない決定的な指定なので、ここで直接見る。
    """
    q = query or ""
    if any(w in q for w in ("英語", "英文", "English", "english")):
        return "en"
    if any(w in q for w in ("日本語", "和文")):
        return "ja"
    return ""


def _filter_by_lang(conn, ids: set, lang: str) -> set:
    """英語のみ／日本語を含む、で絞る（件名＋本文の冒頭で判定）。"""
    if not lang or ids is None:
        return ids
    out = set()
    qmarks = ",".join("?" * len(ids)) if ids else ""
    if not qmarks:
        return ids
    for r in conn.execute(
            "SELECT id, subject, substr(COALESCE(body_text,''),1,1200) AS b "
            "FROM messages WHERE id IN (%s)" % qmarks, list(ids)):
        t = (r[1] or "") + " " + (r[2] or "")
        cjk = len(_CJK_RE.findall(t))
        lat = len(_LAT_RE.findall(t))
        if lang == "en" and cjk == 0 and lat >= 20:
            out.add(r[0])
        elif lang == "ja" and cjk >= 10:
            out.add(r[0])
    return out or ids          # 1件も残らないなら絞りを諦める（何も出ないより良い）

def _ids_in_period(conn, date_from: str = "", date_to: str = "") -> set:
    """期間で絞った message_id の集合。指定が無ければ None（＝絞らない）。"""
    if not date_from and not date_to:
        return None
    sql = "SELECT id FROM messages WHERE 1=1"
    args = []
    if date_from:
        sql += " AND date(date_utc) >= date(?)"
        args.append(date_from)
    if date_to:
        sql += " AND date(date_utc) <= date(?)"
        args.append(date_to)
    return {r[0] for r in conn.execute(sql, args)}


def _ids_with_terms(conn, terms) -> set:
    """指定の語を**すべて**含む message_id の集合（件名・差出人・本文・訳文を見る）。

    「psaから」のような差出人・固有名詞の指定は、意味ベクトルだけだと弱く埋もれる。
    `ai_query.parse_query` が既に `keywords_all` として抜き出しているので、それで先に絞る。
    """
    terms = [t.strip() for t in (terms or []) if t and t.strip()]
    if not terms:
        return None
    out = None
    for t in terms:
        like = "%" + t + "%"
        got = {r[0] for r in conn.execute(
            "SELECT m.id FROM messages m LEFT JOIN translations tr ON tr.message_id=m.id "
            "WHERE m.subject LIKE ? OR m.from_addr LIKE ? OR m.from_name LIKE ? "
            "OR m.body_text LIKE ? OR tr.subject_ja LIKE ? OR tr.body_ja LIKE ?",
            (like, like, like, like, like, like))}
        out = got if out is None else (out & got)
        if not out:
            break
    return out


def search(conn, query: str, top: int = 800,
           date_from: str = "", date_to: str = "",
           must_terms=None, lang: str = "") -> Tuple[List[int], Dict[int, float]]:
    """意味が近い順の message_id 列と、id→類似度(0..1) を返す。

    `date_from` / `date_to` を渡すと**その期間の中だけ**で順位を付ける（2026-08-27）。
    「今月のもの」と指定しているのに全期間から探していたため、
    5万通の中に埋もれて目当てのメールが上位800にすら入らないことがあった
    （英語メールで実際に発生。期間で絞れば候補が数百通になり、確実に上位へ出る）。
    """
    ids, blobs = db.load_all_embeddings(conn, MODEL_NAME)
    if not ids:
        return [], {}
    mat = np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(ids), DIM)
    qv = embed_query(query)
    sims = mat @ qv                       # 正規化済み同士なので内積＝コサイン

    keep = _ids_in_period(conn, date_from, date_to)
    with_terms = _ids_with_terms(conn, must_terms)
    if with_terms:
        keep = with_terms if keep is None else (keep & with_terms)
    lang = lang or detect_lang_wanted(query)
    if lang:
        base = keep if keep is not None else set(ids)
        keep = _filter_by_lang(conn, base, lang)
    if keep is not None:
        mask = np.array([mid in keep for mid in ids])
        if mask.any():
            sims = np.where(mask, sims, -1.0)   # 期間外は最下位へ落とす
            top = min(top, int(mask.sum()))
        # 期間内が1通も無いときは絞り込みを諦める（何も出ないより全期間で出す）

    order = np.argsort(-sims)[:top]
    ordered_ids = [ids[int(i)] for i in order]
    sim_map = {ids[int(i)]: float(sims[int(i)]) for i in order}
    return ordered_ids, sim_map
