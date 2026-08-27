# -*- coding: utf-8 -*-
"""自社（宅地建物取引業者・乙）情報を名称で登録・呼び出しするための簡易ストア。

data/companies.json に {登録名: プロファイル辞書} の形で保存する。
個人情報のためリポジトリには含めない（.gitignore で data/ を除外）。

## 自社は共通マスタから来る（2026-08-27・二重管理をやめた）

自社の商号・代表者・所在地・免許番号は、**リポジトリ直下の `company_profile`**
（`config/company_profile.json`）が正本。重説アプリ（AI重説アシスタント）も
チラシもそこを見ている。ここに同じものを別途登録すると、**片方だけ直したときに
書面によって免許番号が違う**という事故になる。

そこで一覧の先頭に `自社（共通マスタ）` を**読み取り専用**で出す。
このアプリで編集・削除はできない（直すのは共通マスタ側）。
このストアは、**自社以外**（共同仲介の相手方など）を登録するために残す。
"""

import json
import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE, "data")
_PATH = os.path.join(_DATA_DIR, "companies.json")
# baikai-generator/services → baikai-generator → リポジトリ直下
_ROOT = os.path.dirname(_BASE)

# プロファイルが持つ項目（excel_builder の otsu と対応）
FIELDS = ["商号", "代表者", "所在地", "免許番号", "TEL", "流通機構"]

# 共通マスタから読む自社。一覧の先頭に出す固定の名前
SELF_NAME = "自社（共通マスタ）"


def self_profile() -> dict:
    """共通マスタ（直下 `company_profile`）の自社情報を、このアプリの項目に直す。

    共通マスタが無い・空のPCでは空 dict を返す（このアプリは今までどおり動く）。
    """
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    try:
        import company_profile
    except ImportError:
        return {}
    try:
        p = company_profile.load()
    except Exception:
        return {}
    if not str(p.get("商号") or "").strip():
        return {}
    return {
        "商号": p.get("商号", ""),
        "代表者": p.get("代表者", ""),
        "所在地": p.get("所在地", ""),
        # 重説は3分割の欄、媒介契約書は1行の欄なので組み立て直す
        "免許番号": company_profile.format_license(p),
        "TEL": p.get("TEL", ""),
        "流通機構": p.get("流通機構", "") or "公益社団法人　不動産流通機構",
    }


def _stored() -> dict:
    """このアプリが自分で保存したぶんだけ（共通マスタの自社は含まない）。"""
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_all() -> dict:
    """{登録名: プロファイル} を返す。自社は共通マスタから先頭に足す。"""
    data = _stored()
    me = self_profile()
    if me:
        # 共通マスタを正とする（同名がローカルに残っていても上書きする）
        data = {SELF_NAME: me, **{k: v for k, v in data.items() if k != SELF_NAME}}
    return data


def save(name: str, profile: dict) -> None:
    """名称 name でプロファイルを保存（既存は上書き）。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("登録名を入力してください。")
    if name == SELF_NAME:
        raise ValueError(
            "「{}」は共通マスタ（config/company_profile.json）が正本です。"
            "直すのは AI重説アシスタントの「自社情報」画面から行ってください。".format(SELF_NAME))
    os.makedirs(_DATA_DIR, exist_ok=True)
    data = _stored()
    data[name] = {k: (profile.get(k, "") or "").strip() for k in FIELDS}
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete(name: str) -> None:
    """名称 name のプロファイルを削除。共通マスタの自社は消せない。"""
    if name == SELF_NAME:
        raise ValueError("「{}」は共通マスタなので、ここからは削除できません。".format(SELF_NAME))
    data = _stored()
    if name in data:
        del data[name]
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def names() -> list:
    """登録名の一覧。**自社（共通マスタ）を先頭**に、残りは名前順。"""
    rest = sorted(k for k in load_all() if k != SELF_NAME)
    return ([SELF_NAME] if self_profile() else []) + rest


def is_readonly(name: str) -> bool:
    """このアプリからは直せない登録か（共通マスタ由来）。"""
    return name == SELF_NAME
