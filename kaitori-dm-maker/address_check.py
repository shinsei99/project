# -*- coding: utf-8 -*-
"""宛先住所を日本郵便の公式データと突き合わせる（2026-08-23 追加）。

**DMは1通ずつ郵送費がかかる。** 台帳の住所は謄本・空地調査からの手入力で、
郵便番号の空欄・旧町名・誤字が混ざる。出す前に公式データと照合して、
「そのまま出してよい宛先」と「人が直す宛先」を分ける。

実体は**直下の共有クライアント `japanpost_api.py`**（他アプリと同じ1本。コピーを作らない）。
資格情報は直下 `.env.japanpost`（本番・gitignore）。

判定は `japanpost_api.verify()` に任せる:
  一致 / 不一致 / 補完（郵便番号が空欄→住所から特定） / 候補（市区町村どまり） /
  不明 / 住所なし

**照合結果はメモリ（Streamlit のセッション）にだけ持つ。**
氏名と住所は個人情報なので、キャッシュをファイルに書かない。
"""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# そのまま出してよい状態／人が見るべき状態
OK_STATUSES = ("一致", "補完")
NG_STATUSES = ("不一致", "候補", "不明", "住所なし")

ICONS = {"一致": "✅ 一致", "補完": "🟡 郵便番号を補完", "不一致": "🔴 不一致",
         "候補": "🟠 候補どまり", "不明": "⚫️ 不明", "住所なし": "⚫️ 住所なし",
         "": "— 未照合"}


def _import():
    import japanpost_api
    return japanpost_api


def is_configured() -> bool:
    """`.env.japanpost` に資格情報があるか（無ければ画面に照合ボタンを出さない）。"""
    try:
        env = _import()._load_env()
    except Exception:
        return False
    return bool(env.get("JAPANPOST_CLIENT_ID") and env.get("JAPANPOST_SECRET_KEY"))


def rec_key(rec) -> tuple:
    """同じ宛先は1回しか問い合わせないためのキー（郵便番号＋住所）。"""
    jp = _import()
    return (jp.zip_digits(rec.get("postal")), str(rec.get("addr") or "").strip())


def verify_records(recs, cache: dict, progress=None) -> dict:
    """宛先を順に照合して `cache` を埋める（キー: rec_key）。

    progress: 0.0〜1.0 と件数を受ける関数（Streamlit の progress bar 用）。
    **すでに照合済みの宛先は問い合わせない**（APIのレート制限に配慮）。
    """
    jp = _import()
    todo = []
    for rec in recs:
        key = rec_key(rec)
        if key not in cache and key not in todo:
            todo.append(key)

    for i, (postal, addr) in enumerate(todo, 1):
        try:
            cache[(postal, addr)] = jp.verify(postal, addr)
        except Exception as e:  # 1件失敗しても止めない
            cache[(postal, addr)] = {"status": "不明", "zip_code": postal, "official": "",
                                     "message": "照合に失敗しました: {}".format(e)}
        if progress:
            progress(i / len(todo), i, len(todo))
    return cache


def apply_suggestions(recs, cache: dict) -> int:
    """郵便番号が空欄の宛先に、照合で特定できた郵便番号を入れる。戻り値は埋めた件数。"""
    filled = 0
    for rec in recs:
        if str(rec.get("postal") or "").strip():
            continue
        res = cache.get(rec_key(rec))
        if res and res.get("status") == "補完" and res.get("zip_code"):
            rec["postal"] = res["zip_code"]
            rec["postal_filled"] = True
            filled += 1
            # 郵便番号を入れるとキーが変わる。同じ結果を新しいキーにも置いておかないと
            # 次の集計で「未照合」に戻ってしまう（照合し直すのは無駄なAPIコール）
            cache.setdefault(rec_key(rec), res)
    return filled


def status_of(rec, cache: dict) -> str:
    """その宛先の照合結果（未照合なら空文字）。"""
    res = cache.get(rec_key(rec))
    return res.get("status", "") if res else ""


def summarize(recs, cache: dict) -> dict:
    """状態ごとの件数（未照合は "未照合"）。"""
    counts = {}
    for rec in recs:
        key = status_of(rec, cache) or "未照合"
        counts[key] = counts.get(key, 0) + 1
    return counts


def problems(recs, cache: dict):
    """人が直すべき宛先だけを取り出す（表に出す用）。"""
    out = []
    for rec in recs:
        res = cache.get(rec_key(rec))
        if not res or res.get("status") not in NG_STATUSES:
            continue
        out.append({
            "状態": ICONS.get(res["status"], res["status"]),
            "名義人": rec.get("name", ""),
            "〒": rec.get("postal", ""),
            "住所（台帳）": rec.get("addr", ""),
            "公式データ": res.get("official", ""),
            "どうするか": res.get("message", ""),
        })
    return out
