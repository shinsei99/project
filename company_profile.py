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

## 値の出どころ（2026-08-23）

**過去に実際に交付した重説から取った。** 推測で埋めていない。

    共有フォルダ/契約・書類/★仲介（賃貸・売買）/賃貸/★事業用（店舗・事務所）/
    2022.10.17_K1ビル…/重説事業用賃貸借　K1ビル　20221003.xlsx

同じ書式（建物貸借用・事業用）の白紙に自社情報を流し込み、**この実物と
12欄すべてが一字一句一致する**ことを確認済み。表記は実物に合わせて
**全角**（`大阪市都島区東野田町２丁目３番１４号` / `０６－６３５３－０４１８`）。
既存の書面と見た目を揃えるため、半角に直さないこと。

**推測で埋めない。** 分からない項目は空文字にして、画面で「要入力」と出す。
重説の1枚目を間違えると、書面そのものの信頼が落ちるため。

- `保証協会` と `供託所`: **書式にあらかじめ印刷されている**（全宅連の様式は
  「公益社団法人 全国宅地建物取引業保証協会」「東京法務局」が刷り込み済み）ので、
  こちらから書き込む必要が無い。**触らない**
- `地方本部`: **実物の重説でも空欄**だった（書式に「※地方本部一覧参照」と
  印刷されている）。実務がそうなっているので、こちらも空のままにする
- `免許年月日`: **2022年版の書式にはこの行があったが、2026年4月版には無い**
  （事業用貸借で実測）。いまの200本では使わないので項目に持たない
"""

import json
import os
import re

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_ROOT, "config", "company_profile.json")

# 画面に出す項目（キー, ラベル, 補足）
FIELDS = [
    ("商号", "商号又は名称", ""),
    ("代表者", "代表者の氏名", "書式には役職も入れる（例: 代表取締役　○○　○○）"),
    ("所在地", "主たる事務所所在地", ""),
    ("TEL", "TEL", ""),
    ("FAX", "FAX", "重説の欄には無いが、他書式で使う"),
    ("免許_知事名", "免許 知事・大臣名", "例: ○○県知事 / 国土交通大臣"),
    ("免許_更新回数", "免許 更新回数", "括弧の中の数字。例: 10"),
    ("免許_番号", "免許 番号", "括弧の後ろの番号"),
    ("宅建士_氏名", "説明をする宅建士の氏名", "重説に記名する人。担当が変われば変える"),
    ("宅建士_登録先", "宅建士 登録先", "括弧の中。登録した都道府県"),
    ("宅建士_登録番号", "宅建士 登録番号", "括弧の後ろの番号"),
    ("事務所名", "業務に従事する事務所名", ""),
    ("事務所所在地", "事務所所在地", ""),
    ("事務所TEL", "事務所TEL", ""),
    ("地方本部", "所属地方本部の名称及び所在地", "**実務では空欄**（書式に「地方本部一覧参照」と印刷されている）"),
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
