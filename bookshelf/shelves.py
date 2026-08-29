# -*- coding: utf-8 -*-
"""77冊を「棚」と「用途（use_scope）」に振り分ける。

**年数の基準は分野ごとに変える**（2026-08-29 オーナー判断・案C）。
理由: 税制は毎年変わるので3年でも古い。一方マーケティング理論や商業集積の見方は
20年経っても変わらない。同じ「5年」で切ると、どちらかで必ず間違える。

use_scope の意味:
  full    … そのまま使える（法令・数値・要件も引いてよい）
  concept … **考え方だけ**。法律・税率・要件・期限は引かない
  none    … 索引に入れない
"""
import json, re

NOW = 2026

# (棚, 古さの基準年数 or None=年数を見ない, 判定に使う語)
# 上から順に判定するので、**強い語（固有名詞）を先に置く**
RULES = [
    # ソフトの操作本だけは入れない。バージョンが現行と別物で、考え方も残らない
    ("索引に入れない",   None, r"Photoshop|Illustrator|フォトショップ"),
    # 私物・読み物。業務にも小説にも使わない
    ("索引に入れない",   None, r"高級時計|ONE PIECE|カイブツ|PROCESS MANIA|天才の証明"),
    ("税務・お金",       3,    r"税金|節税|インボイス|消費税|減価償却|会社のお金|お金の残し方|お金のPDCA"),
    ("経営・理論",       None, r"コトラー|スコアカード|管理会計|マーケティング入門|社会的責任|仕組み化|"
                              r"ファシリテーション|SHARE|セールスコピー|メディアPR|FACTFULNESS|"
                              r"お金2\.0|労働2\.0|革命のファンファーレ|新世代のビジネス|ChatGPT"),
    # 物件の写真・チラシ・現地撮影。image-resizer / photo-inpainter / flyer-creator で使う
    ("販促・撮影",       None, r"カメラマン|デジタル一眼|DPP"),
    # 外構・小修繕の提案。DIY本は工法が急に変わらないので年数を見ない
    ("不動産実務",       5,    r"リフォーム|DIYで|原状回復|賃貸|重要事項|媒介|空き家|企画開発マニュアル"),
    ("不動産実務",       None, r"ウッドデッキ|ガーデンリビング|庭づくり"),
    ("不動産投資・オーナー", 5,  r"不動産投資|ハーバード|コインランドリー|一芸物件|負動産|ストックビジネス|"
                              r"プロップテック|問題だらけの日本の不動産"),
    ("物件企画・地域",   None, r"地域|まちづくり|商業|流通|観光|都市"),
    ("小説資料（政治）", None, r"維新|都構想|議会|議員|選挙|政治|大阪市の歴史|Osaka Metro|日本の正体"),
    # 冠婚葬祭・年中行事。オーナーや入居者との付き合いで出番がある
    ("その他",           None, r"しきたり"),
]


def classify(title: str, year: int):
    for shelf, limit, pat in RULES:
        if re.search(pat, title):
            if shelf == "索引に入れない":
                return shelf, "none"
            if limit is None:
                # 年数を見ない分野＝法令を語らないので、考え方として使う
                return shelf, "concept"
            scope = "full" if year and (NOW - year) <= limit else "concept"
            return shelf, scope
    return "その他", "concept"


if __name__ == "__main__":
    S = "/private/tmp/claude-501/-Users-apple/b1bdf458-cb66-42ac-8dd3-e0a46d301b4a/scratchpad/ocr"
    meta = json.load(open(f"{S}/bookmeta.json", encoding="utf-8"))
    titles = [l.rstrip("\n").split("\t")[1] for l in open(f"{S}/final_titles.tsv", encoding="utf-8") if "\t" in l]
    out = {}
    for t in titles:
        p = str(meta.get(t, {}).get("pubdate") or "")
        y = int(p[:4]) if p[:4].isdigit() else 0
        shelf, scope = classify(t, y)
        out[t] = {"shelf": shelf, "scope": scope, "year": y}
    json.dump(out, open(f"{S}/assign.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 表示
    from collections import defaultdict
    g = defaultdict(list)
    for t, d in out.items():
        g[d["shelf"]].append((d["year"], d["scope"], t))
    for shelf in ["不動産実務", "税務・お金", "不動産投資・オーナー", "物件企画・地域", "販促・撮影",
                  "経営・理論", "小説資料（政治）", "その他", "索引に入れない"]:
        if shelf not in g:
            continue
        rows = sorted(g[shelf])
        n_full = sum(1 for r in rows if r[1] == "full")
        print(f"\n■ {shelf}  {len(rows)}冊（そのまま使える {n_full}冊）")
        for y, sc, t in rows:
            mark = {"full": "✅", "concept": "考え方のみ", "none": "—"}[sc]
            print(f"   {y or '????'}  {mark:<10} {t}")
