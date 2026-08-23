# -*- coding: utf-8 -*-
"""自社（宅地建物取引業者・宅地建物取引士）の情報。**リポジトリ直下の共有モジュール**。

## なぜ要るのか

重要事項説明書・契約書の1枚目には、**毎回まったく同じこと**を書く欄がある。
土地建物の重説（全宅連の公式書式）で実測すると **A欄だけで13箇所**:

    主たる事務所所在地 / TEL / 商号又は名称 / 代表者の氏名 /
    免許証番号（知事名・更新回数・番号の3分割）/
    説明をする宅地建物取引士の氏名 / 登録番号（都道府県・番号の2分割）/
    業務に従事する事務所名 / 事務所所在地

物件ごとに変わるものではないので、**1回登録すれば以後ずっと自動で入る**。
外部APIも課金も不要で、いちばん確実に効く自動化。

## 保存場所

`config/company_profile.json`（リポジトリ直下）。**個人情報を含むので gitignore**。
このファイル（コード側）には、社内で既に使っている値を既定値として持たせてある。
出どころは `agent-platform/config/company.json`（チラシの法定表示に使っている実データ）と
`realestate-valuation/company_profiles.json`。

## 埋まっていない項目について

**推測で埋めない。** 分かっていない項目は空文字にして、画面で「要入力」と出す。
重説の1枚目を間違えると、書面そのものの信頼が落ちるため。

- `代表者`: どのアプリにも入っていなかった
- `宅建士_氏名` / `宅建士_登録番号`: 同上
- `保証協会` と `供託所`: **書式にあらかじめ印刷されている**（全宅連の様式は
  「公益社団法人 全国宅地建物取引業保証協会」「東京法務局」が刷り込み済み）ので、
  こちらから書き込む必要が無い。**触らない**
- `地方本部`: 大阪府知事免許なので大阪府本部のはずだが、**正式名称と所在地を
  確認していない**ので空のままにしてある（要入力）
"""

import json
import os
import re

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_ROOT, "config", "company_profile.json")

# 画面に出す項目（キー, ラベル, 補足）
FIELDS = [
    ("商号", "商号又は名称", ""),
    ("代表者", "代表者の氏名", "**要入力**（社内のどのアプリにも入っていなかった）"),
    ("所在地", "主たる事務所所在地", ""),
    ("TEL", "TEL", ""),
    ("FAX", "FAX", "重説の欄には無いが、他書式で使う"),
    ("免許_知事名", "免許 知事・大臣名", "例: 大阪府知事"),
    ("免許_更新回数", "免許 更新回数", "括弧の中の数字。例: 10"),
    ("免許_番号", "免許 番号", "例: 27334"),
    ("宅建士_氏名", "説明をする宅建士の氏名", "**要入力**"),
    ("宅建士_登録先", "宅建士 登録先", "括弧の中。例: 大阪府"),
    ("宅建士_登録番号", "宅建士 登録番号", "**要入力**"),
    ("事務所名", "業務に従事する事務所名", ""),
    ("事務所所在地", "事務所所在地", ""),
    ("事務所TEL", "事務所TEL", ""),
    ("地方本部", "所属地方本部の名称及び所在地", "**要入力**（大阪府本部のはずだが正式名称未確認）"),
    ("流通機構", "指定流通機構", "媒介契約書で使う"),
]

# 社内で実際に使っている値（agent-platform/config/company.json ほかから）
DEFAULTS = {
    "商号": "大京商事株式会社",
    "代表者": "",
    "所在地": "大阪市都島区東野田町2−3−14",
    "TEL": "06−6353−0418",
    "FAX": "06−6353−0280",
    # 「大阪府知事(10)27334号」を書式の3分割に合わせて分けたもの
    "免許_知事名": "大阪府知事",
    "免許_更新回数": "10",
    "免許_番号": "27334",
    "宅建士_氏名": "",
    "宅建士_登録先": "大阪府",
    "宅建士_登録番号": "",
    "事務所名": "本店",
    "事務所所在地": "大阪市都島区東野田町2−3−14",
    "事務所TEL": "06−6353−0418",
    "地方本部": "",
    "流通機構": "公益社団法人　不動産流通機構",
}

# 入力が要るのに空のままだと書面が不完全になる項目
REQUIRED = ("商号", "代表者", "所在地", "免許_知事名", "免許_番号", "宅建士_氏名", "宅建士_登録番号")


def load() -> dict:
    """保存済みプロファイル。未保存の項目は既定値で補う。"""
    profile = dict(DEFAULTS)
    try:
        with open(_PATH, encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            for key, value in saved.items():
                if key in profile:
                    profile[key] = str(value or "")
    except (FileNotFoundError, ValueError, OSError):
        pass
    return profile


def save(profile: dict) -> str:
    """プロファイルを保存して保存先パスを返す。"""
    data = {key: str(profile.get(key, "") or "").strip() for key, _, _ in FIELDS}
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return _PATH


def missing(profile: dict = None) -> list:
    """必須なのに空の項目名。画面で「要入力」を出すために使う。"""
    profile = profile if profile is not None else load()
    return [k for k in REQUIRED if not str(profile.get(k, "") or "").strip()]


_LICENSE = re.compile(
    r"(?P<gov>.+?知事|国土交通大臣)\s*[（(]\s*(?P<times>\d+)\s*[)）]\s*第?\s*(?P<no>[0-9０-９\-]+)\s*号?"
)


def parse_license(text: str) -> dict:
    """「大阪府知事(10)27334号」のような1行を3分割に直す。

    画面に貼り付けたい人向けの補助。読めなければ空の辞書を返す（**推測しない**）。
    """
    m = _LICENSE.search(str(text or "").replace("　", " "))
    if not m:
        return {}
    return {
        "免許_知事名": m.group("gov").strip(),
        "免許_更新回数": m.group("times"),
        "免許_番号": m.group("no"),
    }
