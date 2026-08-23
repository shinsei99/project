# -*- coding: utf-8 -*-
"""自社（宅地建物取引業者・宅地建物取引士）の情報。**リポジトリ直下の共有モジュール**。

## なぜ要るのか

重要事項説明書・契約書の1枚目には、**毎回まったく同じこと**を書く欄がある。
土地建物の重説（全宅連の公式書式）で実測すると **12箇所**:

    主たる事務所所在地 / TEL / 商号又は名称 / 代表者の氏名 /
    免許証番号（知事名・更新回数・番号の3分割）/
    説明をする宅地建物取引士の氏名 / 登録番号（都道府県・番号の2分割）/
    業務に従事する事務所名 / 事務所所在地

物件ごとに変わるものではないので、**1回登録すれば以後ずっと自動で入る**。
外部APIも課金も不要で、いちばん確実に効く自動化。

## 保存場所 — **値はここ（コード）に書かない**

実データは `config/company_profile.json`（リポジトリ直下）。**gitignore**。

**このリポジトリは public なので、コードに会社情報の既定値を書かない。**
免許番号や所在地は広告への法定表示項目ではあるが、社内の作法は
「会社情報は gitignore 側に置く」（`agent-platform/config/company.json` と同じ）。
ここには**空の雛形だけ**を持ち、値は各PCのローカルに置く。

**別PCへは Dropbox で運ぶ**（`secrets-manifest.txt` に載せてあるので
`./secrets-sync.sh export` / `import` が拾う）。運び終わったら置き場は消すこと。

値の出どころ（このPCで設定済み）: `agent-platform/config/company.json`
（チラシの法定表示に使っている実データ）と `realestate-valuation/company_profiles.json`。

## 埋まっていない項目について

**推測で埋めない。** 分かっていない項目は空文字にして、画面で「要入力」と出す。
重説の1枚目を間違えると、書面そのものの信頼が落ちるため。

- `代表者`: どのアプリにも入っていなかった
- `宅建士_氏名` / `宅建士_登録番号`: 同上
- `保証協会` と `供託所`: **書式にあらかじめ印刷されている**（全宅連の様式は
  「公益社団法人 全国宅地建物取引業保証協会」「東京法務局」が刷り込み済み）ので、
  こちらから書き込む必要が無い。**触らない**
- `地方本部`: 免許を受けた都道府県の本部のはずだが、**正式名称と所在地を
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
    ("免許_知事名", "免許 知事・大臣名", "例: ○○県知事 / 国土交通大臣"),
    ("免許_更新回数", "免許 更新回数", "括弧の中の数字。例: 10"),
    ("免許_番号", "免許 番号", "括弧の後ろの番号"),
    ("宅建士_氏名", "説明をする宅建士の氏名", "**要入力**"),
    ("宅建士_登録先", "宅建士 登録先", "括弧の中。登録した都道府県"),
    ("宅建士_登録番号", "宅建士 登録番号", "**要入力**"),
    ("事務所名", "業務に従事する事務所名", ""),
    ("事務所所在地", "事務所所在地", ""),
    ("事務所TEL", "事務所TEL", ""),
    ("地方本部", "所属地方本部の名称及び所在地", "**要入力**（正式名称と所在地が未確認）"),
    ("流通機構", "指定流通機構", "媒介契約書で使う"),
]

# **空の雛形**。実データは config/company_profile.json（gitignore）に置く。
# ここに値を書くと public リポジトリに会社情報が載るので、書かないこと。
DEFAULTS = {key: "" for key, _label, _note in FIELDS}

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
    """「○○県知事(10)第12345号」のような1行を3分割に直す。

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
