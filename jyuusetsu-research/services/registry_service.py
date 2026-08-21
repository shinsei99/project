"""登記事項証明書 PDF（土地・建物）を解析し PropertyData 形式に整える。

**解析そのものは直下の共有モジュール `registry_parser.py` に委譲する**
（`baikai-generator`＝媒介契約書ジェネレーターと同じ実体）。本サービスの責任は
その戻り値を `PropertyData` のキーに移し替えることだけ。

## なぜ自前の正規表現をやめたか（2026-08-21）

もともとは `utils.parser` の正規表現で拾っていたが、**実物の謄本では 0/10 項目**しか
取れなかった。理由は登記事項証明書が**罫線アート（`┏━━┯┃`）で組まれた表**で、
見出しが `所 在` `① 地 番` `②地 目` のように半角スペース混じりになるため。
自前パーサは全角スペース前提だった。

共有モジュールは 3 段構えで、実物の謄本で全項目が取れることを確認済み:
  1. pdfplumber でテキストを取り出し `claude` CLI に構造化させる
  2. テキスト層が無いスキャンPDFは、向きを補正して画像として読ませる
  3. どちらも駄目なら正規表現フォールバック

解析失敗時も例外を投げず空欄で返す方針は変えていない。
"""

import os
import sys
from typing import Dict

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import registry_parser as shared
except Exception:  # 共有モジュールが無い環境でもアプリを止めない
    shared = None

from utils import parser  # noqa: E402  フォールバック用に残す

# 謄本から取れる項目。**住居表示は謄本に載っていない**ので `所在地` は入れない
# （謄本の「所在」は `登記所在`）。
PROPERTY_KEYS = ("登記所在", "地番", "地目", "地積", "家屋番号",
                 "種類", "構造", "床面積", "所有者", "抵当権", "謄本発行日")


def _first(*values) -> str:
    for v in values:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def _from_shared(result: dict) -> Dict[str, str]:
    """共有パーサの構造化辞書を PropertyData のキーに移し替える。

    共有パーサは土地・建物・マンションを分けて返すので、
    **区分建物なら専有面積を床面積に**入れる。

    ★謄本の「所在」は **`登記所在`** に入れる。`所在地`（住居表示）には入れない。
      謄本に住居表示は載っていないため、ここで `所在地` を上書きすると
      画面で入力した住居表示が地番表示に置き換わってしまう（2026-08-21 修正）。
    """
    land = result.get("土地") or {}
    bld = result.get("建物") or {}
    mans = result.get("マンション") or {}

    return {
        "登記所在": _first(result.get("物件所在地"), bld.get("所在"), land.get("所在")),
        "地番": _first(land.get("地番")),
        "地目": _first(land.get("地目")),
        "地積": _first(land.get("地積")),
        "家屋番号": _first(bld.get("家屋番号")),
        "種類": _first(bld.get("種類"), mans.get("名称")),
        "構造": _first(bld.get("構造"), mans.get("構造")),
        # 延床面積があればそちらを優先（重説・契約書は延床で書く）
        "床面積": _first(bld.get("延床面積"), mans.get("専有面積"), bld.get("床面積")),
        # 売主の確認に使うのは登記名義人。無ければ所有者で代用
        "所有者": _first(result.get("登記名義人氏名"), result.get("所有者氏名")),
        "抵当権": _first(result.get("抵当権")),
        # 謄本は内容そのものは確定として扱う。ただし**発行日が古いと現況と違う**
        # （その後に売買・抵当権設定があるかもしれない）。鮮度の判断に使う。
        "謄本発行日": _first(result.get("証明書発行日")),
    }


def _from_legacy(land_pdf, building_pdf) -> Dict[str, str]:
    """共有モジュールが使えないときの従来経路（正規表現）。"""
    merged = {k: "" for k in PROPERTY_KEYS}
    # 従来の正規表現パーサは謄本の「所在」を `所在地` という名前で返すので、
    # ここで `登記所在` へ移し替える（住居表示と混ざらないようにするため）
    def take(d):
        for k, v in d.items():
            if not v:
                continue
            merged["登記所在" if k == "所在地" else k] = v

    if land_pdf is not None:
        take(parser.parse_land(parser.extract_text(land_pdf)))
    if building_pdf is not None:
        take(parser.parse_building(parser.extract_text(building_pdf)))
    return merged


def parse_registry(land_pdf=None, building_pdf=None) -> Dict[str, str]:
    """土地・建物の登記簿 PDF を解析して 1 つの辞書にまとめる。

    土地・建物を1回でまとめて渡す（共有パーサが種別を自動判別してマージする）。
    """
    pdfs = [p for p in (land_pdf, building_pdf) if p is not None]
    if not pdfs:
        return {k: "" for k in PROPERTY_KEYS}

    if shared is not None:
        try:
            result = shared.parse_registry(pdfs)
            data = _from_shared(result)
            if any(data.values()):
                return data
        except Exception:
            pass  # 落ちたら従来経路へ

    return _from_legacy(land_pdf, building_pdf)


def last_used_ai(result: dict) -> bool:
    """共有パーサが AI 解析に成功したか（画面の注記用）。"""
    return bool((result or {}).get("_ai"))
