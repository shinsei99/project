"""物件×担当者マスタ（管理物件台帳の「担当」列）から、TODO本文の物件名を突き合わせて
担当者を推定する。TASK-20260826-003（オーナーLINE依頼）。

方針（オーナー確認済み）:
  - 表記ゆれ（略称・通称）は正式名称と完全一致しなくても拾う
    （例: クリスタルコート66→クリスタル66、メゾンドール都島→メゾン）。
  - ただし「どの物件か」まで一意に当てられなくても、候補となる物件の担当者が
    全員同じであれば、その担当者を採用してよい（実務上は物件より担当者が分かれば足りる）。
  - 担当者が割れる/一致する物件が無いときは、**自動設定せず未確定のままにする**（安全側）。
  - 既存TODOへの遡及適用はしない（新規に発生するTODOにのみ適用。オーナー回答済み）。
"""
import re
import unicodedata

from db.connection import query

MIN_CANDIDATE_LEN = 2

# 物件名の途中に挟まる建物種別の一般語。略称突き合わせのためこれを除いた形も候補にする
# （例: 「クリスタルコート66」→「コート」を除いた「クリスタル66」も候補になる）。
_GENERIC_WORDS = [
    "マンション", "コーポ", "ハイツ", "ハイム", "レジデンス", "パレス", "タウン",
    "アパート", "ドール", "ハウス", "ヴィラ", "コート", "ビル", "荘",
    "駐車場", "モータープール", "パーキング", "駐輪場", "ガレージ", "貸土地", "テナント",
]


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"[\s　]+", "", s)
    return s


def _candidates_for_name(norm_name: str) -> set:
    cands = set()
    if len(norm_name) >= MIN_CANDIDATE_LEN:
        cands.add(norm_name)
    stripped = norm_name
    for w in _GENERIC_WORDS:
        stripped = stripped.replace(_normalize(w), "")
    if len(stripped) >= MIN_CANDIDATE_LEN:
        cands.add(stripped)
    for i in range(MIN_CANDIDATE_LEN, len(norm_name)):
        cands.add(norm_name[:i])
    m = re.search(r"(\d+)$", norm_name)
    if m and len(m.group(1)) >= MIN_CANDIDATE_LEN:
        cands.add(m.group(1))
    return cands


def _build_index():
    """候補文字列 → その候補にマッチする物件の担当者集合。"""
    rows = query(
        "SELECT name, assignee_name FROM properties "
        "WHERE active=1 AND assignee_name IS NOT NULL AND assignee_name != ''"
    )
    index = {}
    for r in rows:
        norm_name = _normalize(r["name"])
        for cand in _candidates_for_name(norm_name):
            index.setdefault(cand, set()).add(r["assignee_name"])
    return index


def find_assignee(text: str):
    """TODO本文から物件名を突き合わせ、担当者名を1件に絞れれば返す。絞れなければ None。

    候補となる物件の担当者が複数に割れた場合や、そもそも本文に何も引っかからない場合は
    None（呼び出し側は assignee_name を未確定のまま=nullにしておく）。
    """
    norm_text = _normalize(text)
    if not norm_text:
        return None
    index = _build_index()
    matched = [(cand, assignees) for cand, assignees in index.items() if cand in norm_text]
    if not matched:
        return None
    # 短い/汎用的な候補（例:「京橋」が複数物件の接頭辞に偶然含まれる）に埋もれないよう、
    # 最も長く（＝最も具体的に）一致した候補だけで担当者を決める。
    max_len = max(len(cand) for cand, _ in matched)
    top_tier = [(cand, assignees) for cand, assignees in matched if len(cand) == max_len]
    assignees = set()
    for _, a in top_tier:
        assignees |= a
    if len(assignees) == 1:
        return {
            "assignee_name": next(iter(assignees)),
            "matched_candidates": [c for c, _ in top_tier],
        }
    return None
