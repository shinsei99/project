"""
図鑑の整合性を検査する。3つのソースを重ねただけでは「間違ったまま揃って
見える」状態になるため、穴と矛盾を機械的に洗い出す。

検査するのは次の6点。

  1. 欠番      … 1〜総数のうち図鑑に無い番号。マイカは販売モールなので
                 出品が無いカードは取れておらず、ここに出る
  2. 総数超過   … 総数を超える番号（特別枠）。これは正常なので数だけ見る
  3. 名前の不一致 … 同じ番号なのにマイカとTCGdexで名前が違う。左結合の
                 誤りを示すので、放置すると別のカードのワザが表示される
  4. レアリティ矛盾 … マイカとTCGdexで食い違うもの。日本語版はマイカが正
  5. レアリティ欠落 … レアリティが取れていないカード
  6. 画像欠落   … 画像が無いカード

使い方:
    python check_dex.py           # 要約
    python check_dex.py --detail  # セットごとの内訳を全部出す
    python check_dex.py --packs   # パックごとに番号の欠けを洗い出す（実務用）
    python check_dex.py M6        # 1セットだけ詳しく見る
"""

from __future__ import annotations

import json
import sqlite3
import sys

from build_dex import nname

DB = "data/cards.db"


def _load_truth():
    """アプリ版に出ている「パックの全体枚数」。Web側には無いので手で書き足す表。

    番号が印字されているパックは番号の最大値が全体枚数と一致するため
    （ロケット団の栄光=132 / 仰天のボルテッカー=121 で確認済み）通常は不要だが、
    最大番号のカード自体が取れていないと過小評価になるので、その保険。
    """
    try:
        raw = json.load(open("data/pack_truth.json", encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception:
        return {}


PACK_TRUTH = _load_truth()

# TCGdex の英語レアリティ → 日本語版のどれに当たるか（矛盾判定に使う大まかな対応）。
# TCGdex は日本語版の細かい区分を持たないので、ここは「明らかな食い違い」だけを
# 拾うための粗い表。SR と SAR の違いのような細部は矛盾として扱わない。
TCG_ROUGH = {
    "Common": {"C", "●", "○"},
    "Uncommon": {"U", "◆", "◇"},
    "Rare": {"R", "★", "☆", "K"},
    "Double rare": {"RR"},
    "Ultra Rare": {"SR", "SAR", "SSR", "UR", "HR", "MA", "MUR", "FUR", "BWR",
                   "S", "A", "K"},   # GXウルトラシャイニーの「S」等もここに入る
    "Illustration rare": {"AR"},
    "Special illustration rare": {"SAR"},
    "Hyper rare": {"UR", "HR"},
    "Shiny rare": {"S", "SSR"},
    "Promo": {"PROMO", "PR", "プロモ"},
}


def gaps(nums, total):
    """欠番を出す。基準は総数ではなく **番号の最大値**。

    総数（「034/054」の054）は公式ナンバリングの枚数で、特別枠（AR/SR/SAR等）
    を含まない。実測では「冷酷の反逆者」が total=54 でも実際は59枚あり、
    番号は1〜59まで連番だった。つまりそのパックの実枚数は「番号の最大値」で、
    1〜最大値に欠けが無ければ揃っている。

    プロモのように番号が飛ぶ商品は判定できない（剣盾期プロモは122枚で
    総数118、番号は118を大きく超える）。最大値が総数の1.5倍を超えるものは
    連番でないと見て判定から外す。
    """
    have = {n for n in nums if n is not None}
    if not have:
        return []
    top = max(have)
    if total and top > total * 1.5:
        return []
    return [i for i in range(1, top + 1) if i not in have]


def check_set(con, code):
    # img_web（learn-book 由来）も画像として数える。列を足したときにここへ
    # 反映し忘れると「画像欠落」が実際より多く出る（2026-08-14に実際に起きた）
    rows = con.execute("""SELECT card_no, total, rarity, name, tcg_id, img,
                                 img_off, image_tcgdex, attacks, img_web
                          FROM dex WHERE set_code = ?""", (code,)).fetchall()
    info = con.execute("SELECT name, total, ptype, release FROM dex_sets WHERE set_code=?",
                       (code,)).fetchone()
    total = info[1] if info else None

    nums = [r[0] for r in rows]
    top = max((n for n in nums if n), default=None)   # 実枚数の目安
    over = [n for n in nums if n and total and n > total]
    miss = gaps(nums, total)
    no_rar = [r for r in rows if not r[2]]
    no_img = [r for r in rows if not r[5] and not r[6] and not r[7] and not r[9]]
    no_atk = [r for r in rows if not r[4]]

    return {
        "code": code, "name": info[0] if info else code,
        "release": info[3] if info else None, "ptype": info[2] if info else None,
        "cards": len(rows), "total": total, "top": top,
        "missing": miss, "over": len(over),
        "no_rarity": len(no_rar), "no_image": len(no_img), "no_attacks": len(no_atk),
    }


def name_conflicts(con, limit=30):
    """同じ番号なのにマイカとTCGdexで名前が違うもの（誤結合の疑い）。"""
    rows = con.execute("""
        SELECT d.set_code, d.card_no, d.name, c.name
        FROM dex d JOIN cards c ON c.id = d.tcg_id
        WHERE d.name IS NOT NULL AND c.name IS NOT NULL AND d.name <> c.name
        ORDER BY d.set_code, d.card_no""").fetchall()
    # 表記ゆれ（ダッシュ・全角コロン・空白）は不一致として扱わない
    return [r for r in rows if nname(r[2]) != nname(r[3])][:limit]


# レアリティではなく「印刷の仕様」を表す表記。同じカードのミラー版などで、
# TCGdex は元のレアリティ（Rare など）しか持たないため、食い違いにはならない。
SPEC_NOT_RARITY = ("ミラー", "キラ", "マスターボール", "モンスターボール",
                   "ノーマル")   # 「ノーマル」も仕様（同一カードの通常版）


def rarity_conflicts(con, limit=30):
    """マイカとTCGdexでレアリティが食い違うもの。粗い対応表で明らかな例だけ拾う。"""
    out = []
    for r in con.execute("""
            SELECT d.set_code, d.card_no, d.name, d.rarity, c.rarity
            FROM dex d JOIN cards c ON c.id = d.tcg_id
            WHERE d.rarity IS NOT NULL AND c.rarity IS NOT NULL
                  AND c.rarity <> 'None'"""):
        if any(w in (r[3] or "") for w in SPEC_NOT_RARITY):
            continue                     # ミラー等は仕様なので食い違いではない
        ok = TCG_ROUGH.get(r[4])
        if ok is not None and r[3] not in ok:
            out.append(r)
        if len(out) >= limit:
            break
    return out


def main():
    args = sys.argv[1:]
    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")

    codes = [r[0] for r in con.execute(
        "SELECT set_code FROM dex_sets ORDER BY (release IS NULL), release DESC")]
    one = next((a for a in args if a in codes), None)
    if one:
        codes = [one]

    reports = [check_set(con, c) for c in codes]

    if one:
        r = reports[0]
        print(f"■ {r['name']}（{r['code']}）"
              f"　{r['release'] or '発売日不明'}　{r['ptype'] or '分類なし'}")
        print(f"  図鑑 {r['cards']}枚 / 実枚数の目安（番号の最大値）{r['top'] or '?'}"
              f" / 公式ナンバリング総数 {r['total'] or '?'}"
              f" / 特別枠 {r['over']}枚")
        print(f"  レアリティ欠落 {r['no_rarity']}枚 / 画像欠落 {r['no_image']}枚"
              f" / ワザ未収録 {r['no_attacks']}枚")
        if r["missing"]:
            print(f"  欠番 {len(r['missing'])}件: {r['missing'][:40]}")
        else:
            print("  欠番 なし")
        return

    n_sets = len(reports)
    cards = sum(r["cards"] for r in reports)
    miss = sum(len(r["missing"]) for r in reports)
    print(f"セット {n_sets} / カード {cards:,}枚")
    print(f"欠番        {miss:,}件"
          f"（総数が判るセットのうち、番号が埋まっていないもの）")
    print(f"レアリティ欠落 {sum(r['no_rarity'] for r in reports):,}枚")
    print(f"画像欠落     {sum(r['no_image'] for r in reports):,}枚")
    print(f"ワザ未収録    {sum(r['no_attacks'] for r in reports):,}枚")
    print(f"特別枠（総数超過）{sum(r['over'] for r in reports):,}枚")

    nc = name_conflicts(con)
    rc = rarity_conflicts(con)
    print(f"\n名前の不一致（TCGdexとの誤結合の疑い） {len(nc)}件"
          + ("（上限まで表示）" if len(nc) >= 30 else ""))
    for s, n, a, b in nc[:10]:
        print(f"   {s} {n}: マイカ「{a}」 ／ TCGdex「{b}」")
    print(f"\nレアリティの食い違い {len(rc)}件"
          + ("（上限まで表示）" if len(rc) >= 30 else ""))
    for s, n, nm, a, b in rc[:10]:
        print(f"   {s} {n} {nm}: マイカ {a} ／ TCGdex {b}")

    worst = sorted((r for r in reports if r["missing"]),
                   key=lambda r: -len(r["missing"]))[:12]
    if worst:
        print(f"\n欠番が多いセット（マイカに出品が無く取れていないカード）:")
        for r in worst:
            print(f"   {r['code']:<10} {r['name'][:22]:<24} "
                  f"{r['cards']:>4}/{r['total'] or '?':>4}枚　欠番{len(r['missing'])}件")

    if "--packs" in args:
        # パック単位の検証。図鑑の入口は商品（パック）なので、こちらが実務的。
        # 番号が印字されているパックは「1〜最大値」に欠けが無いかで判定できる。
        print("\n=== パック単位（番号に欠けがあるものだけ）===")
        bad = 0
        for pn, cnt, top, tot in con.execute("""
                SELECT pack_name, COUNT(*), MAX(card_no), MAX(total)
                FROM dex WHERE pack_name IS NOT NULL
                GROUP BY pack_name ORDER BY MAX(card_no) DESC"""):
            if not top:
                continue
            # 番号が飛ぶのが正常な商品は判定できない。プロモは配布物ごとに
            # 商品が分かれる一方、番号はシリーズ通しで振られるため、
            # 「1枚しか入っていないのに番号が267」という状態が普通に起きる。
            # 取得枚数が最大番号の6割に届かないものは連番でないと見て外す。
            if cnt < top * 0.6:
                continue
            nums = [r[0] for r in con.execute(
                "SELECT card_no FROM dex WHERE pack_name = ?", (pn,))]
            miss = gaps(nums, tot)
            # 正解が判っているパックは、最大値ではなくそちらを基準にする
            truth = PACK_TRUTH.get(pn)
            if truth:
                have = {n for n in nums if n}
                miss = [i for i in range(1, truth + 1) if i not in have]
            if miss:
                bad += 1
                mark = f"（正解{truth}枚）" if truth else ""
                print(f"   {pn[:28]:<30} {cnt:>4}枚 / 最大番号{top:>4}{mark}"
                      f" / 欠け{len(miss):>4}件 {miss[:10]}")
        print(f"   → 欠けのあるパック {bad}件"
              "（番号が連番のパックのみ判定。プロモ等は対象外）")
        con.close()
        return

    if "--detail" in args:
        print("\n=== セットごと ===")
        for r in reports:
            print(f"{r['code']:<10} {r['name'][:24]:<26} {r['cards']:>4}枚"
                  f"　欠番{len(r['missing']):>3}"
                  f"　レア無{r['no_rarity']:>3}　画像無{r['no_image']:>3}")
    con.close()


if __name__ == "__main__":
    main()
