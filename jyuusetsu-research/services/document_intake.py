# -*- coding: utf-8 -*-
"""追加資料（任意）を読み取って調査結果に足す。

謄本だけでは埋まらない欄が重説には大量にある。**手元にある資料を上げれば埋まる**ものを
種類ごとに定義し、`claude` CLI に読ませて構造化する。解析の土台（CLIの場所解決・
JSONの取り出し）は共有 `registry_parser.py` を使う（**コピーしない**）。

| 資料 | 主に埋まるところ | 実測した欄の数 |
|---|---|---|
| 管理会社の重要事項調査報告書 | 区分所有重説の管理・修繕・規約 | 61欄 |
| 固定資産評価証明書・課税明細 | 評価額・課税標準（決済案内にも要る） | — |
| 公図・地積測量図 | 境界・私道負担・接道 | 44欄の一部 |
| 建築確認済証・検査済証 | 確認番号・年月日・検査済の有無 | — |
| 建物状況調査・石綿調査・耐震診断 | 石綿12欄・耐震4欄・状況調査3欄 | 18欄 |

## 方針

- **任意**。上げなければ今までどおり動く（欄が空のまま出るだけ）
- **読めなかったら空で返す**。推測で埋めない。エラーで止めない
- いまは **PropertyData に入れて画面に出すところまで**。
  書式のどのセルに入れるかは項目ごとにセルを当てる作業が残っている
  （管理費・修繕積立金の欄は行の作りが規則的なので、`checkbox_fill` と同じやり方で足せる）
"""

import json
import os
import sys
from typing import Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import registry_parser as shared
except Exception:  # 共有モジュールが無い環境でもアプリを止めない
    shared = None


# 資料の種類。key / 画面の名前 / 説明 / AI に出させる JSON / PropertyData へ移す対応
DOCS = [
    {
        "key": "kanri",
        "label": "管理会社の重要事項調査報告書（区分所有）",
        "help": "マンションの管理会社が発行するもの。管理費・修繕積立金・滞納・修繕計画が載っている。",
        "schema": {
            "管理会社名": "（管理業者の商号）",
            "管理形態": "（全部委託／一部委託／自主管理）",
            "管理費月額": "（当該住戸。数値＋円）",
            "修繕積立金月額": "（当該住戸。数値＋円）",
            "管理費等滞納額": "（当該住戸の滞納。無ければ ''）",
            "修繕積立金総額": "（管理組合に積み立てられている総額）",
            "大規模修繕の予定": "（実施時期・内容。無ければ ''）",
            "管理組合名": "",
            "使用細則の有無": "（有／無）",
        },
    },
    {
        "key": "hyoka",
        "label": "固定資産評価証明書・課税明細",
        "help": "評価額・課税標準額。決済案内書の日割り計算にも使う。",
        "schema": {
            "土地評価額": "（円）",
            "建物評価額": "（円）",
            "固定資産税課税標準額": "（円）",
            "都市計画税課税標準額": "（円）",
            "評価年度": "（令和○年度）",
        },
    },
    {
        "key": "kouzu",
        "label": "公図・地積測量図",
        "help": "接道・私道負担・境界の下調べに使う。",
        "schema": {
            "接道状況": "（接している道路の位置・幅員が読み取れれば）",
            "私道負担": "（有／無／不明）",
            "隣接地番": "（分かる範囲。カンマ区切り）",
            "measured_地積": "（測量図の求積。数値＋㎡）",
            "境界標の記載": "（有／無／不明）",
        },
    },
    {
        "key": "kakunin",
        "label": "建築確認済証・検査済証",
        "help": "確認番号と年月日。検査済証の有無は重説の記載事項。",
        "schema": {
            "確認済証番号": "",
            "確認済証交付年月日": "",
            "検査済証番号": "",
            "検査済証交付年月日": "",
            "建築主": "",
        },
    },
    {
        "key": "chousa",
        "label": "建物状況調査・石綿調査・耐震診断の報告書",
        "help": "実施の有無と結果。重説では「調査の記録の有無」を書く。",
        "schema": {
            "建物状況調査の実施": "（有／無）",
            "建物状況調査実施日": "",
            "石綿使用調査の記録": "（有／無）",
            "石綿調査の内容": "",
            "耐震診断の有無": "（有／無）",
            "耐震診断の内容": "",
        },
    },
]

DOC_BY_KEY = {d["key"]: d for d in DOCS}

# 追加資料から入る項目（PropertyData に足すキー）
EXTRA_FIELDS = [k for d in DOCS for k in d["schema"]]


def _prompt(doc: dict, text: str) -> str:
    return (
        "次の不動産関係書類から、指定した項目を抜き出して JSON だけを出力してください。\n"
        "【出力ルール】\n"
        "- JSON オブジェクトのみ。前置き・解説・コードフェンスは付けない\n"
        "- 書いていない項目は空文字 \"\" にする。**推測で埋めない**\n"
        "- 金額は数値＋単位（例: \"12,300円\"）。日付は書面のまま（例: \"令和6年4月1日\"）\n\n"
        "【書類の種類】{}\n\n"
        "【JSON スキーマ】\n{}\n\n"
        "【書類の本文】\n{}"
    ).format(doc["label"],
             json.dumps(doc["schema"], ensure_ascii=False, indent=2),
             text[:60000])


def parse(kind: str, pdf_file) -> Dict[str, str]:
    """1つの資料を読み取る。読めなければ空の辞書（**例外を投げない**）。"""
    doc = DOC_BY_KEY.get(kind)
    if doc is None or pdf_file is None or shared is None:
        return {}
    try:
        text = shared.extract_text(pdf_file)
    except Exception:
        text = ""
    if not str(text or "").strip():
        # テキスト層が無い（スキャンPDF）。謄本と違い画像経路は未対応なので、
        # 黙って空を返さず、呼び出し側が画面に出せるよう印を返す
        return {"_error": "PDFから文字を取り出せませんでした（スキャン画像のPDFかもしれません）。"}

    try:
        raw = shared._invoke_claude(_prompt(doc, text), lambda *_a, **_k: None)
        if not raw:
            return {"_error": "AI解析を実行できませんでした（claude CLI が見つからない等）。"}
        data = json.loads(shared._strip_fence(raw))
    except Exception as exc:
        return {"_error": "読み取りに失敗しました: {}".format(exc)}

    if not isinstance(data, dict):
        return {"_error": "読み取り結果の形式が想定と違いました。"}
    return {k: str(v or "").strip() for k, v in data.items() if k in doc["schema"]}


def parse_all(uploads: Dict[str, object]) -> Dict[str, Dict[str, str]]:
    """{種類: ファイル} をまとめて読み取り、{種類: 結果} を返す。"""
    out: Dict[str, Dict[str, str]] = {}
    for kind, pdf in (uploads or {}).items():
        if pdf is None:
            continue
        out[kind] = parse(kind, pdf)
    return out


def flatten(results: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """読み取り結果を PropertyData へ入れられる1つの辞書にする（エラー印は落とす）。"""
    merged: Dict[str, str] = {}
    for values in (results or {}).values():
        for key, value in (values or {}).items():
            if key.startswith("_") or not str(value or "").strip():
                continue
            merged[key] = str(value).strip()
    return merged
