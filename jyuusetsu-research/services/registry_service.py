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
import re
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
                 "種類", "構造", "床面積", "附属建物",
                 "家屋番号記載", "種類記載", "所有者",
                 "抵当権", "土地抵当権", "建物抵当権", "謄本発行日")


def _side_only(result: dict, side: str) -> str:
    """謄本が片側だけのとき、トップレベルの `抵当権` をその側の値として扱う。

    共有パーサが土地/建物ごとの抵当権を返さなかった場合の救済。
    「土地建物」「マンション」のように両方が入っている謄本では**どちらとも決められない**
    ので空文字を返す（推測でどちらかの欄に入れない）。
    """
    kind = str(result.get("物件種別") or "").strip()
    if kind == "マンション":
        kind = "建物"
    if kind != side:
        return ""
    return str(result.get("抵当権") or "").strip()


def _annex_text(result: dict) -> str:
    """附属で買う区分建物（車庫など）を1行にまとめる。

    区分所有では**本体（居宅）と車庫の謄本が別々に発行される**。共有パーサは
    主たる建物を `建物` / `マンション` に入れ、それ以外を `附属建物一覧` に残すので、
    ここでは人が読める形に直すだけにする（**主たる建物の欄には混ぜない**）。
    """
    parts = []
    for x in result.get("附属建物一覧") or []:
        name = str(x.get("室番号") or "").strip()
        num = str(x.get("家屋番号") or "").strip()
        area = str(x.get("床面積") or "").strip()
        kind = str(x.get("種類") or "").strip()
        head = name or kind or "附属建物"
        detail = "・".join([t for t in (num and "家屋番号 " + num, area) if t])
        parts.append("{}（{}）".format(head, detail) if detail else head)
    return " ／ ".join(parts)


_ANNEX_KIND = re.compile(r"車庫|駐車場|駐輪場|物置|倉庫|トランクルーム")


def _annex_kind(annex: dict) -> str:
    """附属の「種類」。空のときだけ**建物の名称から**補う。

    区分建物の謄本をAIに読ませると、種類（表題部①）を取りこぼして
    建物の名称（例「車庫３４１－３４２」）だけ返すことがある（2026-08-24 実測）。
    名称の頭が「車庫」なら種類も車庫なので、そこまでは機械で補ってよい。
    それ以外は**推測しない**（空のままにして人に書かせる）。
    """
    kind = str((annex or {}).get("種類") or "").strip()
    if kind:
        return kind
    m = _ANNEX_KIND.search(str((annex or {}).get("室番号") or ""))
    return m.group(0) if m else ""


def _joined(main_value: str, annexes: list, key: str) -> str:
    """本体と附属を **①本体　②車庫** の形に連記する（書面に書く文字列）。

    会社の書き方に合わせる（2015年の実案件 `重説-ＯＡＰ307号.xlsx`。
    家屋番号・種類・建物の番号は①②で連記し、**床面積は本体のみ**書く）。
    附属が無ければ本体の値をそのまま返すので、書式側は常にこちらを見ればよい。
    """
    main_value = str(main_value or "").strip()
    others = [(_annex_kind(x) if key == "種類" else str((x or {}).get(key) or "").strip())
              for x in annexes or []]
    others = [v for v in others if v]
    if not main_value or not others:
        return main_value
    parts = ["①" + main_value] + ["{}{}".format(mark, v)
                                  for mark, v in zip("②③④⑤⑥", others)]
    return "　".join(parts)


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
    annexes = result.get("附属建物一覧") or []

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
        # 車庫など。**本体の床面積・家屋番号を上書きしない**ように別項目で持つ
        "附属建物": _annex_text(result),
        # 書面に書く文字列（①本体　②車庫）。床面積は本体のみなので連記しない
        "家屋番号記載": _joined(_first(bld.get("家屋番号")), annexes, "家屋番号"),
        "種類記載": _joined(_first(bld.get("種類"), mans.get("名称")), annexes, "種類"),
        # 売主の確認に使うのは登記名義人。無ければ所有者で代用
        "所有者": _first(result.get("登記名義人氏名"), result.get("所有者氏名")),
        # ★抵当権は土地・建物で分けて持つ。重説の乙区欄は土地と建物で行が違うため。
        #   どちらの不動産のものか分からないとき（旧いパーサの戻り値など）は
        #   `抵当権` に置いたままにして、**書式には自動で入れない**（誤った欄に入るくらいなら
        #   空欄で人に確認させる）。ただし謄本が片方だけなら、その側だと分かる。
        "抵当権": _first(result.get("抵当権")),
        "土地抵当権": _first(land.get("抵当権"), _side_only(result, "土地")),
        "建物抵当権": _first(bld.get("抵当権"), mans.get("抵当権"),
                          _side_only(result, "建物")),
        # 謄本は内容そのものは確定として扱う。ただし**発行日が古いと現況と違う**
        # （その後に売買・抵当権設定があるかもしれない）。鮮度の判断に使う。
        "謄本発行日": _first(result.get("証明書発行日")),
    }


def _from_legacy(land_pdfs, building_pdfs) -> Dict[str, str]:
    """共有モジュールが使えないときの従来経路（正規表現）。複数枚可。"""
    merged = {k: "" for k in PROPERTY_KEYS}
    # 従来の正規表現パーサは謄本の「所在」を `所在地` という名前で返すので、
    # ここで `登記所在` へ移し替える（住居表示と混ざらないようにするため）
    def take(d):
        for k, v in d.items():
            if not v:
                continue
            merged["登記所在" if k == "所在地" else k] = v

    for pdf in land_pdfs or []:
        take(parser.parse_land(parser.extract_text(pdf)))
    for pdf in building_pdfs or []:
        take(parser.parse_building(parser.extract_text(pdf)))
    return merged


def _as_list(value) -> list:
    """1枚でも複数枚でもリストにそろえる（Streamlit の複数アップロード対応）。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [v for v in value if v is not None]
    return [value]


def parse_registry(land_pdf=None, building_pdf=None) -> Dict[str, str]:
    """土地・建物の登記簿 PDF を解析して 1 つの辞書にまとめる。

    土地・建物を1回でまとめて渡す（共有パーサが種別を自動判別してマージする）。
    **それぞれ複数枚を渡してよい**（土地が数筆／区分建物が本体＋車庫のとき）。
    主たる建物がどれかは共有パーサが決め、車庫などは `附属建物` に入る。
    """
    pdfs = _as_list(land_pdf) + _as_list(building_pdf)
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

    return _from_legacy(_as_list(land_pdf), _as_list(building_pdf))


def last_used_ai(result: dict) -> bool:
    """共有パーサが AI 解析に成功したか（画面の注記用）。"""
    return bool((result or {}).get("_ai"))
