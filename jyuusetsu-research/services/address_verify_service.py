"""入力された住所（住居表示）が実在するかを、日本郵便の公式データで確かめる。

なぜ要るか（2026-08-21 オーナー指摘）:
  **謄本には住居表示が載っていない**（載るのは「所在＝地番区域」と「地番」だけ）。
  したがって書式の「（住居表示）」欄を埋められるのは**人が入力した住所だけ**で、
  その住所が正しいかを機械で確かめる手段が要る。町域までなら日本郵便が持っている。

できること・できないこと（実測 2026-08-21）:
  - できる: 都道府県・市区町村・**町域**が実在するかの確認、郵便番号の取得、
            入力の表記ゆれ（区の抜け・旧町名）の検出
  - できない: **丁目・街区符号・住居番号（「一丁目4番18号」の部分）の確認**。
            日本郵便のデータは**町名まで**で、丁目すら持たない
            （2026-08-21 実測: 534-0027 は「中野町」で、「中野町一丁目」は 404）。
            ここが正しいかは現地表示・住民票・住居表示台帳でしか分からない
            → **丁目以降は画面で人に入力させる**（`compose()` で結合する）
  - できない: **地番 → 住居表示の変換**。無料の公開APIは存在しない
            （法務局の地番図やゼンリンの住宅地図を見るしかない）

実体は直下の共有クライアント `japanpost_api.py`（他アプリと共通・コピーを作らない）。
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Dict

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 町名より後ろ（丁目・街区・住居番号）を切り出す。
# 「1-4-18」「一丁目4番18号」「2丁目3番1号」のいずれも対象。
# ハイフンに見える文字は種類が多い。**マイソクは全角マイナス U+2212「−」を使うことがある**
# （2026-08-21 実測: 「兵庫県加東市上三草1136−291」で分割に失敗した）。
_HYPHEN = "\\-－ー‐−–—―"
_BANCHI = re.compile(
    r"([0-9０-９][{h}0-9０-９番地号の]*"               # 1-4-18 / 4番18号
    r"|[0-9０-９一二三四五六七八九十]+丁目.*)$".format(h=_HYPHEN))   # 一丁目4番18号


def _split_banchi(address: str):
    """住所を「町域まで」と「街区・住居番号」に分ける。

    日本郵便の住所検索は**番地まで入れると 404**（町域までしか持っていないため）。
    """
    a = str(address or "").strip()
    m = _BANCHI.search(a)
    if not m:
        return a, ""
    head = a[: m.start()].rstrip("　 ")
    return (head or a), m.group(0)


def verify(address: str) -> Dict[str, object]:
    """住所を日本郵便のデータと突き合わせる。

    戻り値:
      {"ok": bool, "status": "一致" / "町域まで一致" / "見つからない" / "確認不可",
       "message": 画面にそのまま出せる説明,
       "zip": 郵便番号, "official": 公式表記の住所, "banchi": 切り出した番地,
       "candidates": 候補（複数見つかったとき）}

    **判定できないとき（資格情報が無い等）は False ではなく "確認不可" を返す。**
    「確認できなかった」と「間違っている」を混同すると、正しい住所を誤りと見せてしまう。
    """
    addr = str(address or "").strip()
    if not addr:
        return {"ok": False, "status": "未入力", "message": "住所が入力されていません。"}

    try:
        import japanpost_api as jp
    except Exception as e:
        return {"ok": False, "status": "確認不可",
                "message": "日本郵便APIの共通クライアントを読み込めません: {}".format(e)}

    town, banchi = _split_banchi(addr)
    try:
        data = jp.address_zip(freeword=town, limit=10)
    except Exception as e:
        msg = str(e)
        if "404" in msg:
            return {"ok": False, "status": "見つからない", "banchi": banchi,
                    "message": "「{}」は日本郵便のデータに見つかりませんでした。"
                               "市区町村・町名の表記をご確認ください。".format(town)}
        return {"ok": False, "status": "確認不可", "banchi": banchi,
                "message": "確認できませんでした（{}）。住所はそのまま使えます。".format(
                    type(e).__name__)}

    addrs = data.get("addresses") or []
    if not addrs:
        return {"ok": False, "status": "見つからない", "banchi": banchi,
                "message": "「{}」に該当する住所がありませんでした。".format(town)}

    def joined(a):
        return "".join(str(a.get(k) or "") for k in ("pref_name", "city_name", "town_name"))

    first = addrs[0]
    official = joined(first)
    zipcode = str(first.get("zip_code") or "")
    zip_fmt = "{}-{}".format(zipcode[:3], zipcode[3:]) if len(zipcode) == 7 else zipcode

    result = {
        "ok": True,
        "zip": zip_fmt,
        "official": official,
        "banchi": banchi,
        "candidates": [joined(a) for a in addrs[1:6]],
    }
    if banchi:
        result["status"] = "町域まで一致"
        result["message"] = (
            "〒{} {} まで公式データと一致しました。"
            "**「{}」は日本郵便のデータに無いため確認できません**"
            "（丁目・番・号は下の欄で入力してください）。".format(zip_fmt, official, banchi))
    else:
        result["status"] = "一致"
        result["message"] = "〒{} {} と一致しました。".format(zip_fmt, official)
    if len(addrs) > 1:
        result["message"] += "　※同名の町域が {} 件あります。".format(len(addrs))
    return result


def split_for_input(address: str):
    """入力欄を2つに割るための分割。戻り: (町名まで, 丁目以降)。

    画面では「町名まで」を日本郵便で確認し、**丁目以降は人に入力させる**。
    """
    return _split_banchi(address)


def compose(town: str, rest: str) -> str:
    """住居表示を組み立てる。`town` は公式表記（あれば）、`rest` は人が入力した丁目以降。"""
    t = str(town or "").strip()
    r = str(rest or "").strip()
    if not r:
        return t
    return "{}{}".format(t, r)
