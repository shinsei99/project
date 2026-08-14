"""
マイカのデータを骨格にして、図鑑が読む dex テーブルを組み立てる。

これまでは TCGdex（cards）を主にして公式サイトの取得分で補っていたが、
その組み合わせでは日本語版の図鑑として成り立たなかった。

  ・TCGdex … ワザ・HP・効果文は持つが、収録の抜けが多く（M6は0枚）、
              レアリティは英語の粗い区分しか無い
  ・公式    … 画像は綺麗だがファイル名に番号が無く、レアリティも非公開。
              番号が判らないカードは local_id が「†1」のような仮の値になっていた
  ・マイカ  … 番号・総数・レアリティ・収録パックをすべて持つ

そこで **マイカを「カードが存在するという事実」の正**とし、
TCGdex をワザ等の補足として左結合する。セット名・発売日・表紙・
商品分類（拡張パック / 構築デッキ / その他）は今までどおり公式の
products / sets から引く。分類の分け方は変えない。

使い方:
    python build_dex.py
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import sqlite3
import time
from collections import Counter

DB = "data/cards.db"

# dex への挿入は列名を明示する。末尾の img_web は learnbook.py の結果から
# あとで UPDATE で埋めるため、挿入時には触らない（列を足しても壊れないように）
DEX_INSERT = ("INSERT OR REPLACE INTO dex (key, set_code, card_no, total, rarity,"
              " rarity_i, name, img, img_off, pack_id, pack_name, tcg_id, hp, types,"
              " stage, attacks, weaknesses, retreat, descr, illustrator, image_tcgdex)"
              " VALUES (" + ",".join("?" * 21) + ")")
MYCA_LARGE = "data/myca_large"     # 400x559（.jpg 版。拡張子を変えるだけで取れる）
# 一覧表示は data/myca_thumbs（400px から作る180px）を app.py が使う。
# かつて一覧ページの .gif から作った data/myca_images もあったが、400px版が
# 全カード揃ったので1枚も使われなくなり削除した。

# マイカの表記ゆれを吸収する。左が実データ、右が図鑑で使う表記。
RARITY_ALIAS = {
    "ミラー": "ミラー", "キラ": "キラ",
    "●": "●", "◆": "◆", "★": "★", "◇": "◇", "○": "○", "☆": "☆",
}

# レアリティの並び順（低い順）。図鑑の絞り込みと詳細表示で使う。
# 記号（旧裏面）→ 通常 → キラ系 → 特別枠 の順に並べる。
RARITY_ORDER = [
    "●", "○", "◆", "◇", "★", "☆", "e", "キラ", "ミラー",
    "C", "U", "R", "RR", "RRR", "K", "A", "S", "AR", "SR", "SSR", "HR",
    "CHR", "CSR", "TR", "PR", "MA", "SAR", "UR", "BWR", "MUR", "FUR", "PROMO",
]


def setup(con):
    con.executescript("""
    DROP TABLE IF EXISTS dex;
    CREATE TABLE dex (
      key        TEXT PRIMARY KEY,   -- <img_set>/<img_file>。カード1枚を一意に指す
      set_code   TEXT,               -- セット記号（M6 / sv8a / dai1dan …）
      card_no    INTEGER,            -- 印刷されている番号。旧裏面・プロモはNULLあり
      total      INTEGER,            -- 「110/076」の076。特別枠は total を超える
      rarity     TEXT,               -- マイカ由来。図鑑の絞り込みはこれを使う
      rarity_i   INTEGER,            -- 並び順（RARITY_ORDER の位置）
      name       TEXT,
      img        TEXT,               -- マイカ画像のローカルパス（番号と1対1）
      img_off    TEXT,               -- 公式の高画質画像（あれば）
      pack_id    TEXT,
      pack_name  TEXT,
      -- ここから下は TCGdex の補足。無いカードも多い
      tcg_id     TEXT,
      hp         INTEGER,
      types      TEXT,
      stage      TEXT,
      attacks    TEXT,
      weaknesses TEXT,
      retreat    INTEGER,
      descr      TEXT,
      illustrator TEXT,
      image_tcgdex TEXT,
      img_web    TEXT              -- learn-book.com 由来。公式・マイカに無い年代の補完
    );
    CREATE INDEX idx_dex_set  ON dex(set_code);
    CREATE INDEX idx_dex_name ON dex(name);
    CREATE INDEX idx_dex_rar  ON dex(rarity);
    CREATE INDEX idx_dex_no   ON dex(card_no);

    DROP TABLE IF EXISTS dex_sets;
    CREATE TABLE dex_sets (
      set_code  TEXT PRIMARY KEY,
      name      TEXT,               -- 公式のセット名。無ければマイカのパック名
      release   TEXT,
      total     INTEGER,            -- 公式ナンバリングの総数（「/076」の076）
      cards     INTEGER,            -- 図鑑が持っている枚数（特別枠を含む）
      ptype     TEXT,               -- 拡張パック / 構築デッキ / その他
      cover     TEXT,               -- 表紙画像
      images    INTEGER             -- 画像を持っている枚数
    );
    """)
    con.commit()


def nname(s: str | None) -> str:
    """カード名を照合用に潰す。ソース間で表記が揺れるため、これで揃える。

    実測で出た揺れ（マイカ ／ TCGdex）:
      ランプラ―／ランプラー          … 全角ダッシュとカタカナ長音
      タイプ:ヌル／タイプ：ヌル        … 半角コロンと全角コロン
      古びた ずがいの化石／古びたずがいの化石 … 語中の空白
    揺れを潰さないと同じカードが結合できず、ワザや効果文が空のままになる。
    """
    if not s:
        return ""
    s = re.sub(r"[\s　]", "", s)
    s = s.translate(str.maketrans({
        "：": ":", "－": "ー", "―": "ー", "−": "ー", "‐": "ー", "-": "ー", "ｰ": "ー",
        "＆": "&", "’": "'", "”": '"',
    }))
    return s


def rarity_index(r):
    if not r:
        return 99
    try:
        return RARITY_ORDER.index(r)
    except ValueError:
        return 98


def canon_codes(con):
    """セット記号の大小表記を1つに寄せる対応表。

    一覧ページとカード単体ページで大小が違うことがある（一覧は sm9a、
    単体ページはタイトル由来で SM9a）。別のセットとして扱うと同じカードが
    二重に入り、画像の紐づけも切れる（ナイトユニゾンが70枚→140枚になり、
    画像は sm9a 側にだけ35枚付いていた）。

    実測で10組・約2,000枚が該当した（sv4a/SV4a、svD/SVD、sm9a/SM9a …）。
    日本語版の公式表記は小文字始まりなので**小文字側**に寄せる。
    大小違いが実際にある組だけを対象にする（M6 や PMCG1 は触らない）。
    """
    seen = {}
    for src in ("myca", "myca_card"):
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                           (src,)).fetchone():
            continue
        cond = " WHERE status='ok'" if src == "myca_card" else ""
        for (code,) in con.execute(
                f"SELECT DISTINCT set_code FROM {src}{cond}"):
            if code:
                seen.setdefault(code.lower(), set()).add(code)
    out = {}
    for low, variants in seen.items():
        if len(variants) < 2:
            continue
        # 小文字が最も多い表記を正とする（sv4a と SV4a なら sv4a）
        best = min(variants, key=lambda v: (sum(c.isupper() for c in v), v))
        for v in variants:
            if v != best:
                out[v] = best
    return out


def build_set_map(con):
    """TCGdex のセットID → マイカのセット記号の対応表。

    同じパックでも記号の体系が別（マイカ dai1dan ／ TCGdex PMCG1、どちらも
    1996年の第1弾拡張パック）。記号でも名前でも突き合わせられないので、
    **収録カード名の重なり**で判定する。

    これが無いと、マイカで取れた43枚と TCGdex の102枚が別のセットとして扱われ、
    第1弾拡張パックが43枚しか無い図鑑になる（マイカは販売モールなので出品が
    あるカードしか無く、TCGdex側を捨てると残りが永久に埋まらない）。
    """
    # マイカ側は2経路ある。一覧（myca）とカード単体ページ（myca_card）。
    # 単体ページの方が網羅的なので、両方を合わせて対応表を作る。片方だけ見ると
    # 単体ページで取れたセットが対応表から漏れ、TCGdex と統合されない
    # （金、銀、新世界へ… が kinginshinsekai と neo1 に割れていた）。
    myca_names = {}
    for code, name in con.execute("SELECT set_code, name FROM myca"):
        myca_names.setdefault(code, set()).add(nname(name))
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                   "AND name='myca_card'").fetchone():
        for code, name in con.execute(
                "SELECT set_code, name FROM myca_card WHERE status='ok'"):
            if code:
                myca_names.setdefault(code, set()).add(nname(name))

    # 発売年。復刻商品はカード名が原版と完全に重なるため、名前だけで対応づけると
    # 1996年の第1弾拡張パック（102枚）が2023年の「ポケモンカードゲーム Classic」に
    # 吸われる。年が判っていて食い違うものは同じセットとみなさない。
    year = {}
    by_name_rel = {}
    for t, r in con.execute("SELECT title, release FROM products"):
        if r and not str(r).startswith("9"):
            by_name_rel.setdefault(_norm(t), str(r)[:4])
    for n, r in con.execute("SELECT name, release FROM sets"):
        if r and not str(r).startswith("9"):
            by_name_rel.setdefault(_norm(n), str(r)[:4])
    for code, pack in con.execute(
            "SELECT set_code, pack_name FROM myca GROUP BY set_code"):
        y = by_name_rel.get(_norm(pack))
        if y:
            year[code] = y
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                   "AND name='myca_card'").fetchone():
        for code, pack in con.execute(
                """SELECT set_code, pack_name FROM myca_card
                   WHERE status='ok' AND set_code IS NOT NULL GROUP BY set_code"""):
            y = by_name_rel.get(_norm(pack))
            if y:
                year.setdefault(code, y)
    tcg_year = {sid: str(r)[:4] for sid, r in con.execute(
        "SELECT id, release FROM sets") if r and not str(r).startswith("9")}
    # 枚数での照合に使う（名前が英語で当てにならないセットの救済）
    tcg_size = {r[0]: r[1] for r in con.execute(
        "SELECT set_id, COUNT(*) FROM cards GROUP BY set_id")}
    myca_size = {code: len(mn) for code, mn in myca_names.items()}
    cards_count = {}

    # 大小を無視して引けるようにする（TCGdex SM9a ↔ マイカ sm9a）
    myca_lower = {code.lower(): code for code in myca_names}

    out = {}
    for (sid,) in con.execute("SELECT DISTINCT set_id FROM cards"):
        names = {nname(r[0]) for r in con.execute(
            "SELECT name FROM cards WHERE set_id = ?", (sid,))}
        if not names:
            continue
        if sid in myca_names:            # 記号が同じならそれが答え
            out[sid] = sid
            continue
        # 大小だけ違う場合も同じセット。TCGdex は SM9a、マイカは sm9a と
        # 表記が揺れる。これを別セットにすると同じカードが二重に入り、
        # 画像も片方にしか付かない（ナイトユニゾンが70枚→140枚、画像35枚）。
        if sid.lower() in myca_lower:
            out[sid] = myca_lower[sid.lower()]
            continue
        # 重なりの「絶対数」で選ぶと誤る。マイカのスタートデッキ100は439枚あり、
        # 初代パックとも同名カード（ピカチュウ等）が多く重なるため、枚数の
        # 多いセットが何にでも当たってしまう。マイカ側は出品分しか無い部分集合
        # なので、**マイカ側の何割が相手に含まれるか**で見る。
        # 含有率が同じセットは複数ある（数枚だけのセットは何にでも100%含まれる）。
        # 同率なら重なりの多い方を採る。これが無いと「ポケモンジャングル」が
        # TCGdexの48枚とマイカの19枚に分かれて2行になった。
        ty = tcg_year.get(sid)
        best, score, best_ov = None, 0.0, 0
        for code, mn in myca_names.items():
            my = year.get(code)
            if ty and my and ty != my:
                continue                  # 発売年が違う（復刻と原版）
            ov = len(names & mn)
            ratio = ov / len(mn)
            if ratio > score or (ratio == score and ov > best_ov):
                best, score, best_ov = code, ratio, ov
        if best and score >= 0.8 and best_ov >= 3:
            out[sid] = best
            continue

        # ここまでで決まらない場合の救済。TCGdex の日本語版データには
        # カード名が英語のままの行が408枚あり（neo1 の Bayleef、E2、PCG4 …
        # 2000〜2005年のセットに散在）、日本語で照合すると重なりが16%まで
        # 落ちて同じパックだと判定できない。名前が当てにならないので
        # **発売年が一致し、かつ枚数がほぼ同じ**セットを同一とみなす。
        if not ty:
            continue
        n_tcg = len(cards_count.get(sid, ()) or ()) or tcg_size.get(sid, 0)
        for code, size in myca_size.items():
            if year.get(code) != ty or code in out.values():
                continue
            if size and n_tcg and abs(size - n_tcg) <= max(2, n_tcg * 0.1):
                out[sid] = code
                break
    return out


def official_index(con):
    """公式の高画質画像（360px）を引くための索引。(番号で引く, 名前で引く)

    公式のファイル名は通し番号で番号を含まないため、どのカードの絵かを
    確定できるのは次の2通りだけ。

      ・read_official.py がカード画像の印字（「068/076 U」）をAIに読ませて
        番号を入れた行 … 番号で直接紐づく
      ・そのセットに同名のカードが1枚しか無い行 … 名前で一意に決まる

    同名が複数あるカード（M6のギリーは068番のUと101番のSRがある）を
    名前だけで繋ぐと別の絵が出るため、AIが読むまでは採用しない。

    **鍵のセット記号は小文字に潰す。** 公式とマイカで大小が違うことがあり
    （公式 SMP1 ／ マイカ smP1）、そのままだと突き合わせが丸ごと空振りする。
    実測でイワンコ全力デッキ13枚・XY-P 6枚などが繋がっていなかった。
    canon_codes() はマイカ内の表記ゆれしか見ていないのでここでは効かない。
    """
    off_no, off_name, seen = {}, {}, Counter()
    for r in con.execute("""SELECT set_code, name, local, card_no FROM official
                            WHERE status='ok' AND local IS NOT NULL"""):
        code = (r[0] or "").lower()
        seen[(code, nname(r[1]))] += 1
        if r[3]:
            off_no.setdefault((code, r[3]), r[2])
        off_name.setdefault((code, nname(r[1])), r[2])
    return off_no, {k: v for k, v in off_name.items() if seen[k] == 1}


def _low(code):
    """official_index の鍵に合わせてセット記号を小文字にする。"""
    return (code or "").lower()


def build_cards(con, set_map):
    """myca を主に、TCGdex の詳細を名前と番号で左結合する。"""
    # TCGdex 側は local_id が「†1」など番号にならない行が多いので、
    # 番号で当たらなかったものは (セット記号, 名前) でも拾う。
    tcg_by_no, tcg_by_name, tcg_seen = {}, {}, Counter()
    for r in con.execute("""SELECT id, set_id, local_id, name, hp, types, stage, attacks,
                                   weaknesses, retreat, description, illustrator,
                                   image_tcgdex, local_file FROM cards"""):
        lid = str(r[2] or "").split("†")[0].strip()
        # マイカ側の記号でも引けるように、対応表で読み替えた鍵でも登録する
        codes = {r[1], set_map.get(r[1], r[1])}
        for code in codes:
            if lid.isdigit():
                tcg_by_no.setdefault((code, int(lid)), r)
            tcg_by_name.setdefault((code, nname(r[3])), r)
            tcg_seen[(code, nname(r[3]))] += 1

    # 公式の高画質画像（360px）は、番号が確定したものだけ採用する。
    # 公式のファイル名は通し番号で番号を含まないため、確定できるのは次の2通り。
    #
    #   ・read_official.py がカード画像の印字（「068/076 U」）をAIに読ませて
    #     番号を入れた行 … 番号で直接紐づく
    #   ・そのセットに同名のカードが1枚しか無い行 … 名前で一意に決まる
    #
    # 同名が複数あるカード（M6のギリーは068番のUと101番のSRがある）を
    # 名前だけで繋ぐと別の絵が出るため、AIが読むまでは採用しない。
    # 採用しなかったぶんはマイカ画像（番号と1対1）で表示する。
    off_no, off_uniq = official_index(con)

    def off_from_tcg(t, strong, set_code, name):
        """TCGdex のカード記録に付いている公式画像（ingest 時に取得済み）。

        official テーブル経由と違って**カード1枚に紐づいたURL**なので、番号を
        AIに読ませなくても絵が確定する。official 側に無いパック（SM期のサブ
        パック smP など）はこちらにだけ画像がある。
        結合が弱い（名前だけで当てた・その名前がセット内に複数ある）ときは、
        別のカードの絵を出しかねないので使わない。official と同じ判断にする。
        """
        if not t or not t[13]:
            return None
        if not strong and tcg_seen.get((set_code, nname(name)), 0) != 1:
            return None
        return t[13] if os.path.exists(t[13]) else None

    rows, n_img = [], 0
    for m in con.execute("""SELECT set_code, card_no, total, rarity, name,
                                   img_set, img_file, pack_id, pack_name FROM myca"""):
        (set_code, card_no, total, rarity, name,
         img_set, img_file, pack_id, pack_name) = m

        # 同じCDNで拡張子を変えると解像度が変わる（.gif=180px / .jpg=400px）。
        # 400px版を使う。公式の360pxより大きく、1998年の旧裏面カードにも存在する
        img = os.path.join(MYCA_LARGE, img_set, f"{img_file}.jpg")
        if not os.path.exists(img):
            img = None
        else:
            n_img += 1

        # 結合は「番号が一致し、かつ名前も一致」を第一候補にする。
        # 番号だけで繋ぐと別のカードのワザが表示される。実測では M-P（メガ
        # プロモ）でマイカ72番が「ジェット」・TCGdex72番が「ジーランス」と
        # ずれており、プロモは両者で番号の割り当てが違うことが判った。
        t = tcg_by_no.get((set_code, card_no)) if card_no is not None else None
        strong = t is not None and nname(t[3]) == nname(name)   # 番号と名前が両方一致
        if not strong:
            t = tcg_by_name.get((set_code, nname(name)))

        rarity = RARITY_ALIAS.get(rarity, rarity)
        rows.append((
            f"{img_set}/{img_file}", set_code, card_no, total, rarity,
            rarity_index(rarity), name, img,
            (off_no.get((_low(set_code), card_no))
             or off_uniq.get((_low(set_code), nname(name)))
             or off_from_tcg(t, strong, set_code, name)),
            pack_id, pack_name,
            t[0] if t else None, t[4] if t else None, t[5] if t else None,
            t[6] if t else None, t[7] if t else None, t[8] if t else None,
            t[9] if t else None, t[10] if t else None, t[11] if t else None,
            t[12] if t else None,
        ))

    con.executemany(DEX_INSERT, rows)
    con.commit()
    return len(rows), n_img


def unify_pack_names(con):
    """同じパックを指す長短2通りの名前を、セット記号ごとに1つに揃える。

    一覧ページは短く（「天空の覇者」）、カード単体ページは正式名で
    （「ポケモンカードゲームADV 第3弾拡張パック 天空の覇者」）返してくる。
    そのままだと同じパックが2行に割れ、収録枚数が 44枚と10枚に分かれて
    どちらも正解（54枚）にならない。

    片方が他方を含んでいる（部分文字列）ときは同じパックとみなし、
    **長い方**＝正式名に寄せる。
    """
    fixed = 0
    for (code,) in con.execute(
            """SELECT set_code FROM dex WHERE pack_name IS NOT NULL
               GROUP BY set_code HAVING COUNT(DISTINCT pack_name) > 1"""):
        names = [r[0] for r in con.execute(
            """SELECT pack_name FROM dex WHERE set_code = ? AND pack_name IS NOT NULL
               GROUP BY pack_name ORDER BY LENGTH(pack_name) DESC""", (code,))]
        # 表記ゆれを潰した形で比べる。「金、銀、新世界へ…」と
        # 「金、銀、新世界へ...」は三点リーダが違うだけで同じパックなので、
        # 素の部分文字列では拾えない。
        #
        # 寄せる先は「長い方」ではなく **枚数の多い方**。長い方に寄せると、
        # パースを誤った名前（「アララギ博士） （ブラックボルト」）が正しい
        # 「ブラックボルト」322枚を飲み込んでしまう。
        n_by = {n: c for n, c in con.execute(
            """SELECT pack_name, COUNT(*) FROM dex WHERE set_code = ?
               AND pack_name IS NOT NULL GROUP BY pack_name""", (code,))}
        for a in names:
            na = _norm(a)
            for b in names:
                if b == a:
                    continue
                nb = _norm(b)
                if not na or not (na == nb or na in nb or nb in na):
                    continue
                keep, drop = (a, b) if n_by.get(a, 0) >= n_by.get(b, 0) else (b, a)
                if keep == drop:
                    continue
                con.execute(
                    "UPDATE dex SET pack_name = ? WHERE set_code = ? AND pack_name = ?",
                    (keep, code, drop))
                n_by[keep] = n_by.get(keep, 0) + n_by.pop(drop, 0)
                fixed += 1
                break
    con.commit()
    return fixed


def prefer_single_card(con):
    """一覧ページ由来の行を、カード単体ページ由来の内容で上書きする。

    1つのセット記号に複数パックが同居する場合、一覧ページは収録パックを
    取り違えることがある。実測では XY11（冷酷の反逆者＋爆熱の闘士）で、
    一覧が番号50〜59のカードを「爆熱の闘士」に入れていた（正しくは
    爆熱の闘士は1〜31で、50番台は冷酷の反逆者）。カード単体ページは
    そのカード自身のページなので取り違えが起きない。

    同じカード（画像ファイル名が同じ）が両方にあるときは単体ページを採る。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='myca_card'").fetchone():
        return 0
    fixed = 0
    for key, no, total, rarity, pack in con.execute("""
            SELECT img_set || '/' || img_file, card_no, total, rarity, pack_name
            FROM myca_card WHERE status='ok' AND img_file IS NOT NULL"""):
        cur = con.execute(
            "SELECT card_no, pack_name FROM dex WHERE key = ?", (key,)).fetchone()
        if cur and (cur[0] != no or cur[1] != pack):
            con.execute("""UPDATE dex SET card_no=?, total=?, rarity=?,
                           rarity_i=?, pack_name=? WHERE key=?""",
                        (no, total, rarity, rarity_index(rarity), pack, key))
            fixed += 1
    con.commit()
    return fixed


def add_myca_cards(con):
    """カード単体ページから取った分（myca_card）を足す。

    一覧やAPIは販売中のカードしか返さないが、カード単体ページ
    （/items/single-card/<ID>）は出品ゼロのカードでも開く。実測では
    ハナダシティジム カスミが 一覧5枚 → API9枚 → 単体ページ25枚 と、
    アプリ版と同じ枚数まで揃った。crawl_myca_cards.py が集めたもの。

    既に一覧から入っているカードは飛ばす（同じ画像ファイル名で判定）。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='myca_card'").fetchone():
        return 0, 0

    have = {r[0] for r in con.execute("SELECT key FROM dex")}
    # マイカに画像が無いカードでも、公式に同じセット・同じ名前が1枚だけ
    # あるなら絵は確定する。ここを見ていなかったため、イワンコ全力デッキや
    # XY-P のエネルギーが画像なしのままになっていた
    off_no, off_uniq = official_index(con)
    rows, sets_touched = [], set()
    # 画像が未登録のカードもデータとして入れる。マイカに og:image が無い
    # ものが少数あり（ペパー、カキツバタ）、画像の有無で落とすと図鑑から
    # カード自体が消えてしまう。
    for (cid, name, set_code, no, total, rarity, pack,
         img_set, img_file, img_url) in con.execute("""
            SELECT card_id, name, set_code, card_no, total, rarity, pack_name,
                   img_set, img_file, img_url
            FROM myca_card WHERE status='ok'"""):
        key = f"{img_set}/{img_file}" if img_file else f"mc/{cid}"
        if key in have:
            continue
        img = None
        if img_file:
            img = os.path.join(MYCA_LARGE, img_set, f"{img_file}.jpg")
        img = img if (img and os.path.exists(img)) else None
        code = _low(set_code or img_set)
        off = None if img else (off_no.get((code, no)) if no else None) \
            or off_uniq.get((code, nname(name)))
        rows.append((
            key, set_code or img_set, no, total, rarity, rarity_index(rarity),
            name, img, off, None, pack,
            None, None, None, None, None, None, None, None, None, None,
        ))
        sets_touched.add(set_code or img_set)
        have.add(key)

    if rows:
        con.executemany(DEX_INSERT,
                        rows)
        con.commit()
    return len(sets_touched), len(rows)


def _load_rarity_en():
    """TCGdex の英語レアリティ → 日本語版の表記（data/rarity_ja.json）。"""
    try:
        raw = json.load(open("data/rarity_ja.json", encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception:
        return {}


RARITY_EN = _load_rarity_en()

# 旧裏面（2003年以前）はカードにレアリティ記号が印刷されている。
# TCGdex は英語の区分しか持たないので、実物の表記に合わせて記号へ直す。
OLD_SYMBOL = {"C": "●", "U": "◆", "R": "★", "R（キラ）": "★"}


def add_tcgdex_only(con, set_map):
    """マイカに無いセットを TCGdex から補う。

    マイカは販売モールなので、出品が無い古いカードは1枚も取れない。実測では
    1996〜2008年の拡張パック（ポケモンジャングル・化石の秘密・neo・e シリーズ
    ・PCG …）が丸ごと欠け、図鑑から2009年以前が消えていた。TCGdex はこの時代を
    セット名・分類つきで持っているので、そこから足す。

    同じセットが二重に出ないよう、**収録カード名の重なり**で対応を判定する。
    セット記号は体系が違う（マイカ dai1dan ／ TCGdex PMCG1）ため記号では
    突き合わせられず、セット名も「第1弾拡張パック」「拡張パック」のように
    揺れるため名前でも足りない。
    """
    # マイカに既に入っているカード。セット記号は対応表でマイカ側に寄せる
    have, have_names = set(), set()
    for code, name in con.execute("SELECT set_code, name FROM myca"):
        have.add((code, nname(name)))
        have_names.add(nname(name))
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                   "AND name='myca_card'").fetchone():
        for code, name in con.execute(
                "SELECT set_code, name FROM myca_card WHERE status='ok'"):
            have.add((code, nname(name)))
            have_names.add(nname(name))

    # マイカに無いカードでも、公式に同じセット・同じ名前の画像が1枚だけ
    # あるなら絵は確定する（番号を持たない旧いプロモなどが該当する）
    off_no, off_uniq = official_index(con)

    rows, sets_touched = [], set()
    for s in con.execute("""SELECT id, name, release, total, official, ptype, cover
                            FROM sets"""):
        sid = s[0]
        cards = con.execute("""SELECT id, local_id, name, rarity, hp, types, stage,
                                      attacks, weaknesses, retreat, description,
                                      illustrator, image_tcgdex, local_file
                               FROM cards WHERE set_id = ?""", (sid,)).fetchall()
        if not cards:
            continue

        # 同じパックがマイカにもあるなら、そのセット記号に合わせて足す。
        # セット単位で捨ててしまうと、マイカで出品があった分しか残らない
        # （第1弾拡張パックが102枚→43枚になっていた）。
        code = set_map.get(sid, sid)
        old = bool(s[2]) and str(s[2]) < "2003"

        # マイカ側にそのパックが揃っているなら、TCGdex からカードは足さない。
        # 名前で重複を弾く仕組みは TCGdex 側が英語名だと効かず（neo1 の
        # Bayleef など408枚）、同じカードが二重に入って「金、銀、新世界へ…」が
        # 96枚→186枚に膨らんだ。カードの存在はマイカが正、TCGdex はワザ等の
        # 補足に徹する（build_cards が左結合で拾う）。
        n_myca = con.execute(
            "SELECT COUNT(*) FROM dex WHERE set_code = ?", (code,)).fetchone()[0]
        if n_myca >= len(cards) * 0.9:
            continue

        for c in cards:
            if (code, nname(c[2])) in have:
                continue                      # マイカ側が既に持っている
            # 公式サイトから名前だけ拾った行（merge_official.py が入れたもの）は
            # 番号・レアリティ・ワザがすべて無い空の行。同じカードがマイカ側に
            # 別のセット記号で入っていることが多く（DP3のフシギダネはマイカの
            # 「ひかる闇」に●付きで存在）、足すと空の重複が増える。
            # 実測で2,046枚のうち1,614枚がマイカに同名で在った。**名前が
            # マイカ側にあれば捨てる**（セット記号の一致は条件にしない。
            # 記号の体系が違うため一致しないことが多い）。
            empty = ("†" in str(c[1] or "")
                     or not (c[7] and c[7] != "[]"))     # ワザが無い
            if empty and nname(c[2]) in have_names:
                continue
            lid = str(c[1] or "").split("†")[0].strip()
            rar = RARITY_EN.get(c[3]) if c[3] and c[3] != "None" else None
            if old and rar in OLD_SYMBOL:
                rar = OLD_SYMBOL[rar]
            # ここに来る行はマイカに無い＝マイカ画像が最初から無い。ingest 時に
            # 公式画像を落としてあれば（SM期のサブパック smP など）それが唯一の絵。
            # 行と TCGdex のカードが1対1なので取り違えは起きない。
            off = c[13] if c[13] and os.path.exists(c[13]) else None
            # 番号では引かない。TCGdex の local_id と公式の印字番号は割り当てが
            # 違うことがあり（M-P はマイカ72番=ジェット／TCGdex72番=ジーランス）、
            # 別のカードの絵になる。名前が一意のときだけにする。
            off = off or off_uniq.get((_low(code), nname(c[2])))
            rows.append((
                f"tcg/{c[0]}", code, int(lid) if lid.isdigit() else None,
                s[4] or s[3], rar, rarity_index(rar), c[2],
                None, off, None, s[1],
                c[0], c[4], c[5], c[6], c[7], c[8], c[9], c[10], c[11], c[12],
            ))
            sets_touched.add(code)

    if rows:
        con.executemany(DEX_INSERT,
                        rows)
        con.commit()
    return len(sets_touched), len(rows)


# 商品名の接頭辞。長いものから順に落とす（「拡張パックデラックス」を
# 「拡張パック」で切ると「デラックス〜」が残ってしまう）。
PRODUCT_PREFIX = (
    # 長いものから順に落とす。マイカ側は「ポケモンカードゲームADV 第3弾拡張パック
    # 天空の覇者」、公式は「第3弾 拡張パック「天空の覇者」」と接頭辞が違う
    "ポケットモンスターカードゲーム", "ポケモンカードゲームADV",
    "ポケモンカードゲームDP", "ポケモンカードゲーム",
    "ポケモンジムジム拡張", "プレミアムチャンピオンパック", "コンセプトパック",
    "拡張パックデラックス", "強化拡張パック", "ハイクラスパック",
    "スペシャルパック", "強化パック", "ジム拡張", "拡張パック",
)


def _norm(s: str | None) -> str:
    """商品名を照合用に潰す。「拡張パック「アビスアイ」」と「アビスアイ」が
    同じものだと分かるようにする。

    公式の商品名には実データで次の揺れがあった。
      拡張パック「スカーレット<big>ex</big >」   … HTMLタグが残っている
      強化拡張パック「ポケモンカード151（イチゴーイチ）」 … 読みの括弧が付く
      コンセプトパック「ポケキュンコレクション」      … 接頭辞の種類が多い
    """
    if not s:
        return ""
    s = html_mod.unescape(s)                            # &amp; などを戻す
    s = re.sub(r"<[^>]*>", "", s)                       # HTMLタグ
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s)            # 読みの括弧
    # 三点リーダの表記ゆれ。マイカは「新世界へ…」（U+2026）、公式は
    # 「新世界へ...」（ピリオド3つ）。揃えないと同じパックだと判定できず、
    # 金、銀、新世界へ… が kinginshinsekai と neo1 に割れる
    s = s.replace("…", "").replace("...", "").replace("‥", "")
    s = re.sub(r"[\s　「」『』【】・｢｣〈〉《》“”'\"]", "", s)
    # 全角の英数字と記号を半角に寄せる。実データの揺れ:
    #   ヒードランＶＳレジギガス ／ ヒードランVSレジギガス
    #   カメックス＋キュレムEX  ／ カメックス+キュレムEX
    #   アルセウスLV．X        ／ アルセウスLV.X
    s = s.translate(str.maketrans(
        "＆＋－．，０１２３４５６７８９"
        "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "&+-.,0123456789"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"))
    # 「第4弾 拡張パック「ロケット団」」と「ロケット団」を同じにする。
    # 序数と接頭辞は前後どちらにも付くので、落とせなくなるまで繰り返す。
    # 接頭辞は連続して付くことがある。
    #   コンセプトパック「ポケットモンスターカードゲーム 拡張パック 20th Anniversary」
    #   → コンセプトパック → ポケットモンスターカードゲーム → 拡張パック の3連
    # 1回しか落とさないと「ポケットモンスターカードゲーム拡張パック20thAnniversary」
    # が残り、マイカ側の「20th Anniversary」と一致しない。
    for _ in range(6):
        before = s
        s = re.sub(r"^第[0-9０-９一二三四五六七八九十]+[弾期集]", "", s)
        for pre in PRODUCT_PREFIX:
            if s.startswith(pre) and len(s) > len(pre):
                s = s[len(pre):]
                break
        s = re.sub(r"第[0-9０-９一二三四五六七八九十]+[弾期集]$", "", s)
        if s == before:
            break
    return s


def myca_release_dates(con):
    """マイカのカードページから取れた発売日を、セット記号ごとにまとめる。

    公式サイトに商品ページが無い古いパックは公式から発売日が取れない。
    マイカのカードページには埋め込みJSONに release_date があり、そこから
    判る（ポケモンジム第1弾 ハナダシティジム カスミ = 1998-04-26）。
    取得は fetch_release_dates.py（パックごとに1枚だけ開く）。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='myca_card'").fetchone():
        return {}
    cols = {r[1] for r in con.execute("PRAGMA table_info(myca_card)")}
    if "release" not in cols:
        return {}
    out = {}
    for code, rel in con.execute(
            """SELECT set_code, release FROM myca_card
               WHERE status='ok' AND release IS NOT NULL AND set_code IS NOT NULL
               GROUP BY set_code, release ORDER BY COUNT(*) DESC"""):
        out.setdefault(code, rel)
    return out


def build_sets(con):
    """セットの見出し情報。名前・発売日・表紙・分類は公式（sets / products）が正。

    マイカのパック名は「拡張パック メガシンフォニア」のように商品名そのままで、
    セット記号との対応が1対1にならない（同じ記号に複数パックがぶら下がる）。
    そこで記号ごとに「最も枚数の多いパック名」を代表として持たせる。

    公式との突き合わせは2段。まずセット記号（M6 など）で引き、当たらなければ
    代表パック名で引く。マイカは記号を持たない商品も多いので、名前での照合が
    無いと大半が「分類なし」に落ちてしまう。分類そのものは公式に従う。
    """
    myca_release = myca_release_dates(con)
    by_code, by_name = {}, {}
    for r in con.execute(
            "SELECT id, name, release, total, official, ptype, cover FROM sets"):
        by_code[r[0]] = r
        if r[1]:
            by_name.setdefault(_norm(r[1]), r)
    # products は総数を持たないが、sets に無い商品（スターターセット等）を拾える
    for r in con.execute("SELECT title, ptype, release, cover FROM products"):
        by_name.setdefault(_norm(r[0]),
                           (None, r[0], r[2], None, None, r[1], r[3]))

    rows = []
    for r in con.execute("""
            SELECT d.set_code, COUNT(*) AS cards, SUM(d.img IS NOT NULL OR d.img_off IS NOT NULL OR d.img_web IS NOT NULL) AS images,
                   MAX(d.total) AS total,
                   (SELECT pack_name FROM dex x WHERE x.set_code = d.set_code
                      GROUP BY pack_name ORDER BY COUNT(*) DESC LIMIT 1) AS pack_name
            FROM dex d GROUP BY d.set_code"""):
        code, cards, images, total, pack_name = r
        o = by_code.get(code) or by_name.get(_norm(pack_name))
        name = (o[1] if o and o[1] and "名称未取得" not in o[1] else None) or pack_name or code
        release = o[2] if o and o[2] and not str(o[2]).startswith("9") else None
        # 公式から取れないぶんはマイカのカードページの発売日で補う
        if not release:
            release = myca_release.get(code)
        rows.append((code, name, release, total or (o[4] if o else None),
                     cards, o[5] if o else None, o[6] if o else None, images))

    con.executemany("INSERT OR REPLACE INTO dex_sets VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


# 中身が既存パックと同じ「詰め合わせ」商品。一覧に出すと同じカードが
# 二重に並ぶので除く（例:「拡張パック メガシンフォニア ポケモンセンターセット」）。
#
# 「拡張パックデラックス「ブラックボルト」」は除かない。中身は同じだが公式が
# 拡張パックとして独立した商品にしており、公式の一覧が188件なので数を合わせる。
DUP_PRODUCT = ("ポケモンセンターセット", "スペシャルセット",
               "同時購入", "セット同時")


def clean_title(s: str) -> str:
    """表示用に商品名からHTMLタグだけ落とす（「」や副題は残す）。"""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", s or "")).strip()


def _load_alias():
    """公式の商品名 → マイカの収録パック名の手動対応表。

    命名の差が大きく自動照合できないものだけを data/product_alias.json に書く。
    実例: 公式「メガバトルデッキ60「タブンネEX」」／マイカ「メガバトルデッキ60
    MタブンネEX」（Mの有無）、公式「構築済み60枚デッキ「雷震!バンギラスex」」／
    マイカ「構築済みデッキ 雷震! バンギラスex」。
    """
    try:
        raw = json.load(open("data/product_alias.json", encoding="utf-8"))
        return {_norm(k): v for k, v in raw.items() if not k.startswith("_")}
    except Exception:
        return {}


PRODUCT_ALIAS = _load_alias()


def build_products(con):
    """公式の商品一覧を図鑑の入口にする。

    セット記号ごとに並べると、公式の商品と1対1にならない（プロモが細かく
    割れる／TCGdex の分割が公式と違う）。公式サイトの拡張パックは187商品なので、
    そちらを軸にして、各商品に収録カードのセットを紐づける。
    """
    con.executescript("""
    DROP TABLE IF EXISTS dex_products;
    CREATE TABLE dex_products (
      title    TEXT,      -- 表示用の商品名
      ptype    TEXT,      -- 拡張パック / 構築デッキ / その他の商品
      release  TEXT,
      cover    TEXT,
      set_code TEXT,      -- 収録カードのセット記号（判らなければNULL）
      pack_name TEXT,     -- マイカの収録パック名。1つの記号に複数パックが
                          -- 同居するとき（XY11 = 冷酷の反逆者＋爆熱の闘士、
                          -- S-Pに至っては14パック）はこちらで絞る
      cards    INTEGER,
      images   INTEGER
    );
    CREATE INDEX idx_dp_type ON dex_products(ptype);
    """)

    # セット記号 → 発売年（同名パックの選び分けに使う）
    set_year = {}
    for code, rel in con.execute("SELECT set_code, release FROM dex_sets"):
        if rel and not str(rel).startswith("9"):
            set_year[code] = str(rel)[:4]

    # 公式の商品名 → セット記号。名前で当たらない商品を記号で救うために使う
    by_title_code = {}
    for sid, name in con.execute("SELECT id, name FROM sets WHERE name IS NOT NULL"):
        by_title_code.setdefault(_norm(name), sid)

    # 同じ名前のセットが複数ある（「拡張パック」は初代・ADV期の両方に存在）。
    # 収録カードが揃っている方を商品の対応先にする。
    sets = {}
    for code, name, cards, images, release in con.execute(
            "SELECT set_code, name, cards, images, release FROM dex_sets"):
        k = _norm(name)
        if k not in sets or (cards or 0) > (sets[k][1] or 0):
            sets[k] = (code, cards, images, release)

    # 公式の商品はそのまま全件並べる。中身が同じでも公式が別商品として
    # 扱っているもの（拡張パックデラックス「ブラックボルト」）は別行にする。
    # 公式の拡張パックは188件で、その数に合わせる。
    # マイカの収録パック名でも引けるようにする。1つのセット記号に複数パックが
    # 同居する場合（XY11 = 冷酷の反逆者＋爆熱の闘士）、記号だけでは片方しか
    # 出せず、もう一方が「収録カード0枚」になっていた。
    # パック名が同じでもセット記号が違えば別の商品。「スターターパック」は
    # 1996年（96枚）と2016年の20th（84枚）に存在し、まとめて数えると180枚に
    # なってしまう。(パック名, セット記号) の粒度で数え、候補が複数あるときは
    # 商品の発売年に一致するものを選ぶ。
    packs, packs_raw, packs_multi = {}, {}, {}
    # 既定はパック名でまとめる。同じパックが複数のセット記号に散らばることが
    # 普通にあるため（対戦スターターパックSP は Pt に36枚、Pt-2 に4枚）、
    # 記号で割ると1つの商品が分断される。
    for pn, code, cards, images in con.execute(
            """SELECT pack_name,
                      (SELECT set_code FROM dex x WHERE x.pack_name = d.pack_name
                         GROUP BY set_code ORDER BY COUNT(*) DESC LIMIT 1),
                      COUNT(*), SUM(img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL)
               FROM dex d WHERE pack_name IS NOT NULL
               GROUP BY pack_name ORDER BY COUNT(*) DESC"""):
        packs.setdefault(_norm(pn), (pn, code, cards, images))
        packs_raw.setdefault(re.sub(r"[\s　「」『』【】・｢｣]", "", pn),
                             (pn, code, cards, images))
    # 記号ごとの内訳も持つ。同名パックが**発売年の違うセット**にまたがる場合
    # （「スターターパック」は1996年に96枚、2016年の20thに84枚）だけ、
    # 商品の発売年に合う方を選ぶために使う。
    for pn, code, cards, images in con.execute(
            """SELECT pack_name, set_code, COUNT(*), SUM(img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL)
               FROM dex WHERE pack_name IS NOT NULL
               GROUP BY pack_name, set_code ORDER BY COUNT(*) DESC"""):
        packs_multi.setdefault(_norm(pn), []).append((pn, code, cards, images))

    rows, used_sets, used_names = [], set(), set()
    for title, ptype, release, cover in con.execute(
            "SELECT title, ptype, release, cover FROM products"):
        if any(w in title for w in DUP_PRODUCT):
            continue
        key = _norm(title)
        # 手動の対応表を先に見る
        alias = PRODUCT_ALIAS.get(key)
        if alias and alias.startswith("@"):
            # 「@20th」のようにセット記号で指定された場合。同名で別時代の
            # パックを区別するのに使う（スターターパックは1996年と2016年）
            code = alias[1:]
            # 「@NULL」はセット記号が印字されていないカードを指す。マイカは
            # 同名パックを版ごとに記号で分けており（はじめてセットは HS 57枚と
            # HXY 51枚）、記号なしの版もある（スターターパック1996年版96枚）
            if code == "NULL":
                n = con.execute(
                    """SELECT COUNT(*), SUM(img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL) FROM dex
                       WHERE set_code IS NULL AND pack_name = ?""",
                    (clean_title(title).strip("「」"),)).fetchone()
                if not n or not n[0]:
                    # 商品名とパック名が違う場合は名前を正規化して探す
                    row = con.execute(
                        """SELECT pack_name, COUNT(*), SUM(img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL) FROM dex
                           WHERE set_code IS NULL GROUP BY pack_name""").fetchall()
                    hit = [r for r in row if _norm(r[0]) == key]
                    n = (hit[0][1], hit[0][2]) if hit else None
                    pk = (hit[0][0], None, n[0], n[1] or 0) if hit else None
                else:
                    pk = (clean_title(title).strip("「」"), None, n[0], n[1] or 0)
            else:
                n = con.execute("""SELECT COUNT(*), SUM(img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL),
                                          (SELECT pack_name FROM dex WHERE set_code=?
                                             GROUP BY pack_name
                                             ORDER BY COUNT(*) DESC LIMIT 1)
                                   FROM dex WHERE set_code = ?""",
                                (code, code)).fetchone()
                pk = (n[2], code, n[0], n[1] or 0) if n and n[0] else None
        else:
            pk = packs.get(_norm(alias)) if alias else packs.get(key)
        s = sets.get(key)
        if not pk and not s:
            # マイカのパック名が商品名の前半だけ、という場合を拾う。
            #   公式  「プレミアムチャンピオンパック「EX×M×BREAK」」
            #   マイカ「プレミアムチャンピオンパック」（副題なし・CP4に140枚）
            # 短い側が長い側の先頭に一致し、かつ他の商品と取り合いにならない
            # ものだけ採用する。
            #
            # ここでは _norm を通す前の名前で比べる。_norm は
            # 「プレミアムチャンピオンパック」を接頭辞として落とすので、
            # 正規化後は「EX×M×BREAK」になってしまい前方一致が成立しない。
            raw = re.sub(r"[\s　「」『』【】・｢｣]", "", clean_title(title))
            cands = [v for pn, v in packs_raw.items()
                     if pn and len(pn) >= 8 and raw.startswith(pn)]
            # 逆向きも見る。公式「バトルアカデミー」に対しマイカは
            # 「いつでもどこでも バトルアカデミー」と接頭辞が付く（同じ商品で
            # 発売日も同じ）。前方一致だけでは拾えないので後方一致も許す。
            if not cands and len(raw) >= 6:
                cands = [v for pn, v in packs_raw.items()
                         if pn and pn.endswith(raw) and len(pn) <= len(raw) * 3]
            # さらに逆。公式が「いつでもどこでも バトルアカデミー」でマイカが
            # 「バトルアカデミー」（接頭辞なし）の場合。商品名の末尾がパック名
            # と一致するなら同じものとみなす。
            if not cands:
                cands = [v for pn, v in packs_raw.items()
                         if pn and len(pn) >= 6 and raw.endswith(pn)
                         and len(raw) <= len(pn) * 3]
            if len(cands) == 1:
                pk = cands[0]
        if not pk and not s:
            # 名前で当たらない場合、公式のセット名から記号を引いて探す
            code = by_title_code.get(key)
            if code:
                n = con.execute(
                    """SELECT COUNT(*), SUM(img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL) FROM dex
                       WHERE set_code = ?""", (code,)).fetchone()
                if n and n[0]:
                    s = (code, n[0], n[1] or 0, None)
        used_names.add(key)
        # 同名のパックが複数セットにある場合、発売年が近い方を選ぶ
        # 同名パックが「別の時代」にまたがる場合だけ、商品の発売年で選び分ける。
        # 同じパックがセット記号の揺れで複数に散っているだけ（対戦スターターパックSP
        # が Pt に36枚・Pt-2 に4枚）のときに割ってはいけない。年の開きが5年以上
        # あるものを「別の時代」とみなす（スターターパックは1996年と2016年）。
        cand_list = packs_multi.get(_norm(alias) if alias else key)
        if pk and cand_list and len(cand_list) > 1 and release:
            years = sorted({int(set_year[c[1]]) for c in cand_list
                            if set_year.get(c[1], "").isdigit()})
            if len(years) > 1 and years[-1] - years[0] >= 5:
                y = str(release)[:4]
                best = max((c for c in cand_list if set_year.get(c[1]) == y),
                           key=lambda c: c[2], default=None)
                # 年が合っても枚数が極端に少ないなら選ばない。マイカは同じ
                # パックのカードを複数の記号に散らすことがあり（対戦スターター
                # パックSP は Pt に36枚・Pt-2 に4枚で、Pt は2003年の
                # ギフトボックス扱い）、年だけで選ぶと4枚の方を採ってしまう。
                if best and best[2] >= pk[2] * 0.5:
                    pk = best
        if pk:
            # パック名で当たった。収録カードはパック単位で数える
            pack_name, code, cards, images = pk
            used_sets.add(code)
            release = release or (s[3] if s else None)
            rows.append((clean_title(title), ptype, release, cover,
                         code, pack_name, cards, images or 0))
        else:
            if s:
                used_sets.add(s[0])
            release = release or (s[3] if s else None)
            rows.append((clean_title(title), ptype, release, cover,
                         s[0] if s else None, None,
                         s[1] if s else 0, s[2] if s else 0))

    # 公式に商品ページが無いセット（1996〜2008年のパック・プロモ等）も入口が要る。
    # 商品として既に出ているものは足さない。実データでは公式商品
    # 「第4弾 拡張パック「ロケット団」」とセット「ロケット団」が二重に並んでいた
    # ので、セット記号と名前の両方で既出かどうかを見る。
    for code, name, release, cards, ptype, cover, images in con.execute(
            """SELECT set_code, name, release, cards, ptype, cover, images
               FROM dex_sets"""):
        if code in used_sets or _norm(name) in used_names:
            continue
        # 詰め合わせ商品は公式側で除いているので、セット名でも入れない
        # （TCGdex は「VMAXスペシャルセット イーブイヒーローズ」を
        #   独立したセットとして持っているが、中身は本編と同じ）
        if name and any(w in name for w in DUP_PRODUCT):
            continue
        used_names.add(_norm(name))
        rows.append((name, ptype, release, cover, code, None, cards, images))
    # 中身が同じ商品は1行にまとめる。公式が別名で2つ登録していても
    # （「バトルアカデミー」と「いつでもどこでも バトルアカデミー」は
    # どちらも svI の91枚）、図鑑としては同じものを2回見せる必要がない。
    # 同じ (分類, パック名 or セット記号, 発売日) を指すものを1つに寄せ、
    # 名前は**短い方**を採る（公式の正式名がどちらとも言えないため、
    # 一覧で読みやすい方を選ぶ）。
    # 拡張パックは統合しない。公式が別商品として売っているものは
    # そのまま並べる（拡張パックデラックスは本編と中身が同じだが、
    # 公式の拡張パックは188件なのでその数に合わせる）。
    seen_body, uniq = {}, []
    for r in rows:
        title, ptype, release, cover, code, pack, cards, images = r
        if not cards or ptype == "拡張パック":
            uniq.append(r)
            continue
        body = (ptype, pack or code, release)
        prev = seen_body.get(body)
        if prev is None:
            seen_body[body] = len(uniq)
            uniq.append(r)
        elif len(title) < len(uniq[prev][0]):
            # 短い名前に差し替える（表紙が付いている方を優先）
            keep_cover = uniq[prev][3] or cover
            uniq[prev] = (title, ptype, release, keep_cover, code, pack, cards, images)

    con.executemany("INSERT INTO dex_products VALUES (?,?,?,?,?,?,?,?)", uniq)
    con.commit()
    return len(uniq)


def add_learnbook(con):
    """learnbook.py が取得した画像を img_web に入れる。

    公式・マイカ・TCGdex のどこにも画像が無い年代（eシリーズ・PCG4/9・
    1996年の第1弾）だけを補う。**この列は最後の手段**で、app.py の表示も
    公式 → マイカ → learn-book の順に落とす。出所が分かるよう列を分けてある
    （第三者サイト由来なので、公式画像と同じ扱いにはしない）。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='learnbook'").fetchone():
        return 0
    n = 0
    for key, local in con.execute(
            """SELECT dex_key, local FROM learnbook
               WHERE dex_key IS NOT NULL AND local IS NOT NULL"""):
        if not os.path.exists(local):
            continue
        # **`img_web IS NULL` が要る。** これが無いと、先に呼ぶ `add_pcgsearch()`
        # の 593×834 を learn-book の 356×500 が上書きしてしまう
        n += con.execute("UPDATE dex SET img_web = ? WHERE key = ? AND img IS NULL "
                         "AND img_off IS NULL AND img_web IS NULL",
                         (local, key)).rowcount
    con.commit()
    return n


def add_pcgsearch(con):
    """pcgsearch.py が取得した画像を img_web に入れる。

    eシリーズの穴埋め。593×834・透かし無しで**手持ちで最良の画質**なので、
    learn-book・スニダンより**先に**呼んで優先させる。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='pcgsearch'").fetchone():
        return 0
    n = 0
    for key, local in con.execute(
            """SELECT dex_key, local FROM pcgsearch
               WHERE dex_key IS NOT NULL AND local IS NOT NULL"""):
        if not os.path.exists(local):
            continue
        n += con.execute("UPDATE dex SET img_web = ? WHERE key = ? "
                         "AND img IS NULL AND img_off IS NULL", (local, key)).rowcount
    con.commit()
    return n


def _add_web_table(con, table):
    """<table>.dex_key / .local を img_web に入れる共通処理。

    **`img_web IS NULL` を条件に入れる**こと。呼ぶ順が優先順位になり、
    先に入った良い画像を後から上書きしない（画質の良い順に呼ぶ）。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name=?", (table,)).fetchone():
        return 0
    n = 0
    for key, local in con.execute(
            f"""SELECT dex_key, local FROM {table}
                WHERE dex_key IS NOT NULL AND local IS NOT NULL"""):
        if not os.path.exists(local):
            continue
        n += con.execute("UPDATE dex SET img_web = ? WHERE key = ? AND img IS NULL "
                         "AND img_off IS NULL AND img_web IS NULL",
                         (local, key)).rowcount
    con.commit()
    return n


def add_cardrush(con):
    """カードラッシュ由来（868×1212・透かし無し）。M-P など他に取得元が無い分。"""
    return _add_web_table(con, "cardrush")


def add_extra_images(con):
    """手で1枚ずつ確かめて拾った分（`extra_images.py`）。

    ⚠️ 晴れる屋2 由来の2枚（XY-P スーパーボール / M-P 079 ふしぎなアメ）は
    **うっすら「HARERUYA」の透かし入り**。他に取得元が無いので許容している
    （2026-08-14・ユーザー承認）。透かし無しが見つかったら差し替えること。
    どれが該当するかは `extra_images.source = 'hareruya2'` で引ける。
    """
    return _add_web_table(con, "extra_images")


def add_trophy_guess(con):
    """トロフィーカードに**推定で**絵を当てる（`trophy.py`）。

    ⚠️ 確証ではない。新しい資料が出たら差し替えること。該当行と根拠は
    `SELECT dex_key, guess, confidence, reason FROM trophy_guess` で引ける。
    """
    return _add_web_table(con, "trophy_guess")


def add_placeholder(con):
    """実物の画像がどこにも無い分に、**参考画像**を入れる（`placeholder.py`）。

    ⚠️ **これはカードの実像ではない。** 同じ系統の別のカードを土台にして、
    受賞者の顔写真・氏名・大会名をぼかし、「参考画像」と重ねたもの。
    mc/11250 は見出しプレートを別カードから借りている。
    **一番最後に呼ぶ**こと（本物が1枚でもあればそちらを優先する）。
    該当は `SELECT dex_key, base, note FROM placeholder_images` で引ける。
    """
    return _add_web_table(con, "placeholder_images")


def add_snkrdunk(con):
    """snkrdunk.py が取得した画像を img_web に入れる。

    learn-book にも無かった年代の穴埋め（E4 069 グランブル等）。列は
    learn-book と同じ `img_web`＝**第三者サイト由来**の枠を使う。出所を細かく
    知りたいときは `snkrdunk` / `learnbook` テーブルを引く。
    **`add_learnbook()` の後に呼ぶこと**（learn-book を優先する）。
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='snkrdunk'").fetchone():
        return 0
    n = 0
    for key, local in con.execute(
            """SELECT dex_key, local FROM snkrdunk
               WHERE dex_key IS NOT NULL AND local IS NOT NULL"""):
        if not os.path.exists(local):
            continue
        n += con.execute("UPDATE dex SET img_web = ? WHERE key = ? AND img IS NULL "
                         "AND img_off IS NULL AND img_web IS NULL",
                         (local, key)).rowcount
    con.commit()
    return n


ERROR_SUFFIX = "（表面加工エラー）"


def add_error_variants(con):
    """「（表面加工エラー）」の行に、同じカードの通常版の画像を入れる。

    マイカは印刷エラー品を別商品として出品するので、dex には
    「メガリザードンXex（表面加工エラー）」のような行ができる。カードの種類では
    ないから絵は通常版とまったく同じで、**マイカはこの出品に画像を付けていない**。

    表面加工のエラーなので、対象は加工が特別な枠に限られる。実際 M2a の10枚は
    **MA レアリティの223〜232番ちょうど10枚と1対1で一致した**（同じ名前が
    MA 枠に2つある例は無い）。SAR や MUR にも同名のカードがあるので、
    **名前だけで引くと別の絵を出す**（メガカイリューex は MA 232 / SAR 246 /
    MUR 250 の3種類ある）。必ず同じ set_code・同じレアリティ枠で一意に
    決まるものだけを採ること。

    出所は通常版と同じ（公式またはマイカ）なので、列は分けていない。
    """
    n = 0
    for key, set_code, name in con.execute(
            f"""SELECT key, set_code, name FROM dex
                WHERE name LIKE '%{ERROR_SUFFIX}'
                  AND img IS NULL AND img_off IS NULL AND img_web IS NULL"""):
        base = name[:-len(ERROR_SUFFIX)].strip()
        # 同じセットの中で、その名前を持つ「加工が特別な枠」の行を探す。
        # 候補が1つに決まらないなら採らない（別の絵を出すくらいなら空のままにする）
        cand = con.execute(
            """SELECT img, img_off FROM dex
               WHERE set_code = ? AND name = ? AND rarity = 'MA'
                 AND (img IS NOT NULL OR img_off IS NOT NULL)""",
            (set_code, base)).fetchall()
        if len(cand) != 1:
            continue
        img, img_off = cand[0]
        n += con.execute("UPDATE dex SET img = ?, img_off = ? WHERE key = ?",
                         (img, img_off, key)).rowcount
    con.commit()
    return n


# eシリーズは同じカードが「キラ版」と「通常版」の2枚組で入っている。
# learn-book はこの2枚に**同じ写真1枚**を使っており（`e02` のキラカード一覧が
# 通常一覧と同じ `e2004.jpg` を出す）、片割れの番号はページに載っていない。
# その結果、dex では組の片方だけ画像が付く。
TWIN_SETS = ("E1", "E2", "E3", "E4", "E5")
TWIN_NO = re.compile(r"\s*-\d{3}/\d{3}\s*$")     # 「MUK -004/092」→「MUK」


def add_twin_images(con):
    """eシリーズの2枚組のうち、画像が無い方に相方の画像を入れる。

    **番号の隣り合わせでは決められない。** キラが先の組（E3 70キラ/71通常）と
    後の組（E3 72通常/73キラ）が混在する。そこで
    **カード名（番号の接尾辞を落とす）＋HP＋ワザが完全一致**する行を相方とし、
    **候補がちょうど1件のときだけ**採る。実測: E1〜E5 の未収録108枚のうち
    88枚が一意に決まり、候補が複数になった行は0件だった。

    絵が同じと判断した根拠は、learn-book が「（キラカード）一覧」と通常の一覧に
    **同じ画像ファイルを使っている**こと（＝サイト側も1枚の絵として扱っている）。
    キラ加工の有無までは再現できない。ユーザー承認済み（2026-08-14）。

    相方の画像は全て `img_web`（learn-book 由来）にあるので、そのまま同じ列へ
    入れる。公式・マイカ由来だと誤解されないようにするため。
    """
    n = 0
    for sc in TWIN_SETS:
        rows = con.execute(
            """SELECT key, name, hp, attacks, img, img_off, img_web
               FROM dex WHERE set_code = ?""", (sc,)).fetchall()
        have, by_stat = {}, {}
        for key, name, hp, atk, i, o, w in rows:
            if (i or o or w) and atk is not None:
                have.setdefault((TWIN_NO.sub("", name or ""), hp, atk), []).append(w)
                if hp is not None:
                    by_stat.setdefault((hp, atk), []).append(w)
        for key, name, hp, atk, i, o, w in rows:
            if i or o or w or atk is None:
                continue
            cand = have.get((TWIN_NO.sub("", name or ""), hp, atk), [])
            # 名前で決まらないときだけ、HP＋ワザで引き直す。この年代は dex 側の
            # 名前が壊れており（E2 は48番が "nidooking"、49番が "ニドギング" で
            # 同じカード）、名前一致だけだと組が見つからないことがある。
            # **HP が無い行（トレーナー・エネルギー）は対象外**。ワザが空の行が
            # 全部同じ鍵になって候補が10件並ぶため（実測: E2 85 戦いキューブ01）
            if not cand and hp is not None:
                cand = by_stat.get((hp, atk), [])
            if len(cand) != 1 or not cand[0]:
                continue          # 相方がいない／複数いるなら空のままにする
            n += con.execute("UPDATE dex SET img_web = ? WHERE key = ?",
                             (cand[0], key)).rowcount
    con.commit()
    return n


# 1996年の第1弾は、①「スターターパック」と「拡張パック」が**同じ札を分け合って
# いる**（README「learn-book.com からの補完」参照）うえ、②同じ拡張パックが
# マイカ `dai1dan` ／ TCGdex `PMCG1` の2つの記号で dex に入っている。
# そのため「片方の記号にだけ絵がある」行ができる。
FIRST_SERIES = ("dai1dan", "PMCG1")
FIRST_SERIES_PACK = "第1弾スターターパック"

# TCGdex 側の壊れた名前 → マイカ側の正しい名前。**同じカードだと確かめたものだけ**。
# この年代は番号の体系も違う（PMCG1 の19番＝マイカ 1st1020）ので番号では引けず、
# 名前が一致しないと相方を見つけられない。
#   ウィンディ        小さい「ィ」の違いだけ。dai1dan/1st1020
#   詐欺師オーク教授   英語名 Imposter Professor Oak の直訳。dai1dan/1st1082
#     （learn-book の pmcg01 ページにも「にせオーキドはかせ」として載っている）
FIRST_SERIES_ALIAS = {
    "ウィンディ": "ウインディ",
    "詐欺師オーク教授": "にせオーキドはかせ",
}


# 「この行の絵は、この行と同じ」と**手で確かめて決めた**対応。
# 自動の規則（名前・番号・レアリティ）では拾えないものだけをここに書く。
#
# 映画公開記念VSパック 波導のルカリオ（PCG-27・2005-07-16）に同梱された
# 特殊悪／特殊鋼エネルギー。マイカはこの2枚に画像を持っていない。
# **マスターキット（PCG-26）が 2005-07-15 発売で1日違い**なので同じ刷り。
# ※ この商品の 020/020 は「ダークメタルエネルギー」で、それは別カード
#   （`PCG-27/pcgm2020`）として既に画像がある。混同しないこと。
# --- トロフィーカード（No.Xトレーナー）について -------------------------------
# **カード本体に大会の地区名は入っていない。** マンダラケの出品
# （第2回公式トーナメントシリーズ カメックスメガバトル 関西大会 優勝・1998年8月22日）
# の実物写真で確認した。「関西大会」と入っているのは**アクリル盾の金属プレート**で、
# 中のカードは dex の `puromo01_042`（第2回）とまったく同じ文面・同じ絵。
# → **同じシリーズなら地区が違っても同じカード。**
#
# ただし**シリーズ間では文面が違う**（実物で確認済み）:
#   puromo01_011  「…第1回ポケモンカードゲーム日本一決定戦への参加権…」
#   puromo01_042  「…第2回ポケモンカードゲーム日本一決定戦への参加権…」
# なので「No.Xトレーナーは全部1種類」ではない。**流用はシリーズ単位でしか成り立たない。**
#
# mc/500-520 は**推定で第2回シリーズ（カメックスメガバトル）**とした。根拠:
#   ・マイカのIDは発売順で、直前が 490 コロコロ98年8月号、直後が
#     530「カメックスメガバトル出場記念」＝1998年8月の位置にぴったり収まる
#   ・マンダラケの盾も 1998年8月22日 カメックスメガバトル
#   ・マイカが同じカードを配布イベントごとに別商品として出すのは既知
#     （XY-P のサナが「トレーナーズパック」と「デッキ構築ゼミ」で2行に割れていた）
# **マイカが大会名を持っていないので確証ではない。** 別シリーズだった場合は
# 文面の違う絵を出すことになる。
#
# 残り18枚（960-1050=1999年 / 11250-11270=2000年 / 16510-16570=2001年）は
# **その年代のシリーズの絵が dex にも外部にも無い**ので流用できない。
SAME_PRINT = {
    "mc/42710": "PCG-26/pcgmks011",        # 特殊悪エネルギー
    "mc/42720": "PCG-26/pcgmks012",        # 特殊鋼エネルギー
    "mc/500": "puromo01/puromo01_042",     # No.1トレーナー（第2回＝カメックスメガバトル）
    "mc/510": "puromo01/puromo01_043",     # No.2トレーナー（同上）
    "mc/520": "puromo01/puromo01_044",     # No.3トレーナー（同上）

    # マサラタウンカップの3枚 → ピカチュウ版・第1回（`puromo01_011-013`）。
    # スニダンの記事 https://snkrdunk.com/articles/18349/ に
    # 「1997年に開かれた第2回ポケモンカード公式トーナメント『マサラタウンカップ』にて
    #  成績上位者に贈られたカード。このトーナメントではポケカ史上初の日本一決定戦への
    #  参加権を得ることができ…」とあり、**記事のカード画像の文面が
    # 「第1回ポケモンカードゲーム日本一決定戦への参加権」**＝`puromo01_011` と同一だった。
    #
    # ⚠️ **食い違いが1つある。** マイカはこの3枚をカードID 11130-11150（前後が
    # 2000年のカード）に置いているが、記事は1997年としている。ただし
    # **この3行は `release` が空**で、マイカのID順は日付が無い行では当てにならない。
    # カード本体の文面のほうを採った。
    "mc/11130": "puromo01/puromo01_011",   # No.1トレーナー（マサラタウンカップ）
    "mc/11140": "puromo01/puromo01_012",   # No.2トレーナー（同上）
    "mc/11150": "puromo01/puromo01_013",   # No.3トレーナー（同上）

    # 2001年ブロック（mc/16490-16580）の名前つき4枚。どの商品のカードかが
    # 分かれば dex の中に同じカードがある、という典型例。出所はユーザー提供の情報。
    # マイカのIDの位置（2001年4〜7月）とも矛盾しない。
    "mc/16490": "puromoneo/neop044",       # ひかるミュウ … 月刊コロコロコミック01年5月号の付録
    "mc/16540": "vs/vs0041",               # ヤナギのラプラス … 2001年7月「ポケモンカード★VS」
                                           #   第1弾 リーダーズポケモン 水炎ハーフデッキ
    "mc/16580": "puromoneo/neop047",       # ハネッコ … 『ポケモンカードになったワケ 5巻』のおまけ
    # ひかるコイキングは候補が2つある（拡張パック第3弾「めざめる伝説」と
    # ポケモンカードファンクラブ 600ポイント）。**実物を見比べたところ同じ絵柄
    # （No.129・同じイラスト）**だったので、プロモ行にはプロモ配布のほうを当てた。
    "mc/16500": "puromoneo/neop046",       # ひかるコイキング
}


def add_same_print(con):
    """SAME_PRINT に書いた対応で、同じ刷りの行から絵を借りる。"""
    n = 0
    for key, src in SAME_PRINT.items():
        row = con.execute(
            """SELECT img, img_off, img_web FROM dex
               WHERE key = ? AND (img IS NOT NULL OR img_off IS NOT NULL
                                  OR img_web IS NOT NULL)""", (src,)).fetchone()
        if not row:
            continue
        n += con.execute(
            """UPDATE dex SET img = ?, img_off = ?, img_web = ?
               WHERE key = ? AND img IS NULL AND img_off IS NULL
                 AND img_web IS NULL""", (*row, key)).rowcount
    con.commit()
    return n


def add_official_by_name(con):
    """公式にそのセット・その名前のカードが**1枚しか無い**なら、その画像を入れる。

    マイカは同じカードを配布イベントごとに別商品として出すことがあり、dex では
    同じ名前の行が2つに分かれて片方にしか画像が付かない。実例（2026-08-14）:

        XY-P サナ  「公認自主イベント トレーナーズパック」 画像あり
        XY-P サナ  「デッキ構築ゼミ」                  画像なし  ← 同じカード

    公式（pokemon-card.com）には XY-P のサナが **32197 の1枚だけ**で、
    実物を見比べても同じカード（EVENTスタンプ・Illus. Ken Sugimori・©2016）だった。
    別の刷りがあるなら公式にも2枚あるはずなので、**公式で一意**を根拠にする。

    セット記号は `-` `_` と大小の違いを潰して比べる（dex `XY-P` ／ 公式 `XYP`）。
    """
    def norm(s):
        return re.sub(r"[-_\s]", "", s or "").upper()

    off = {}
    for name, sc, local in con.execute(
            "SELECT name, set_code, local FROM official WHERE local IS NOT NULL"):
        off.setdefault((norm(sc), name), []).append(local)

    n = 0
    for key, sc, name in con.execute(
            """SELECT key, set_code, name FROM dex
               WHERE img IS NULL AND img_off IS NULL AND img_web IS NULL
                 AND set_code IS NOT NULL AND name IS NOT NULL"""):
        cand = off.get((norm(sc), name), [])
        if len(cand) != 1 or not os.path.exists(cand[0]):
            continue
        n += con.execute("UPDATE dex SET img_off = ? WHERE key = ?",
                         (cand[0], key)).rowcount
    con.commit()
    return n


def add_dual_code_twins(con):
    """同じセットが2つの記号で入っている分を、番号で突き合わせて埋める。

    TCGdex とマイカでセット記号が違うことがあり、**同じカードが2行に分かれて
    片方にしか画像が無い**状態が起きる。実例（2026-08-14）:

        tcg/SM1p-059  set_code=SM1p  59番 UR ジュナイパーGX  画像なし
        SM1p/SM1p_059 set_code=sm1+  59番 HR ジュナイパーGX  画像あり  ← 同じカード

    レアリティの表記が UR / HR と割れるのは出所が違うだけ。
    **カード名・番号・総数の3つが一致**し、候補がちょうど1件のものだけ採る。

    これで「SM1p・SM2p は公式に画像があるが同名2件（通常GXとSR）で確定できない」
    という積み残しが解消した（59番の UR と 52番の SR は番号で区別できる）。
    """
    n = 0
    rows = con.execute(
        """SELECT key, card_no, total, name FROM dex
           WHERE img IS NULL AND img_off IS NULL AND img_web IS NULL
             AND card_no IS NOT NULL AND name IS NOT NULL""").fetchall()
    for key, no, total, name in rows:
        cand = con.execute(
            """SELECT img, img_off, img_web FROM dex
               WHERE name = ? AND card_no = ? AND total IS ? AND key <> ?
                 AND (img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL)""",
            (name, no, total, key)).fetchall()
        if len(cand) != 1:
            continue
        i, o, w = cand[0]
        n += con.execute(
            "UPDATE dex SET img = ?, img_off = ?, img_web = ? WHERE key = ?",
            (i, o, w, key)).rowcount
    con.commit()
    return n


def add_first_series_twins(con):
    """1996年 第1弾の中で、同じカードの別の行から絵を借りる。

    相手は**同じ1996年第1弾の中**（`dai1dan` / `PMCG1`）に限る。名前だけで
    全セットから探すと別年代の同名カードを拾う（コクーンは全体で22件ある）。
    候補がちょうど1件のときだけ採る。
    """
    n = 0
    rows = con.execute(
        f"""SELECT key, name FROM dex
            WHERE img IS NULL AND img_off IS NULL AND img_web IS NULL
              AND (set_code = 'PMCG1' OR pack_name = ?)""",
        (FIRST_SERIES_PACK,)).fetchall()
    for key, name in rows:
        cand = con.execute(
            f"""SELECT img, img_off, img_web FROM dex
                WHERE name = ? AND key <> ? AND set_code IN {FIRST_SERIES}
                  AND (img IS NOT NULL OR img_off IS NOT NULL OR img_web IS NOT NULL)""",
            (FIRST_SERIES_ALIAS.get(name, name), key)).fetchall()
        if len(cand) != 1:
            continue
        i, o, w = cand[0]
        n += con.execute(
            "UPDATE dex SET img = ?, img_off = ?, img_web = ? WHERE key = ?",
            (i, o, w, key)).rowcount
    con.commit()
    return n


def main():
    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")
    setup(con)

    t0 = time.time()
    # 同じパックの別記号（マイカ dai1dan ／ TCGdex PMCG1）を先に対応づける
    set_map = build_set_map(con)
    n, n_img = build_cards(con, set_map)
    # マイカに出品が無く取れなかったセット（2009年以前の拡張パック等）を
    # TCGdex から補う。これが無いと図鑑から初期のパックが丸ごと消える
    # 一覧より単体ページの方が正確なので、重なる分は単体ページで上書きする
    n_fix = prefer_single_card(con)
    # カード単体ページ経由で取れた分（出品ゼロのカードを含む）
    n_ms, n_mc = add_myca_cards(con)
    n_ts, n_tc = add_tcgdex_only(con, set_map)
    # 同じパックの長短2通りの名前を揃える（一覧は短く、単体ページは正式名）
    n_uni = unify_pack_names(con)
    n_pcg = add_pcgsearch(con)          # eシリーズは pcg-search が最良（先に当てる）
    n_cr = add_cardrush(con)            # カードラッシュ（868x1212・M-P など）
    n_ex = add_extra_images(con)        # 手で確かめた1枚もの
    n_tr = add_trophy_guess(con)        # トロフィーカード（★推定★）
    n_ph = add_placeholder(con)         # 実物が無い分の★参考画像★（最後に当てる）
    n_web = add_learnbook(con)          # 公開元が無い年代を learn-book で補う
    n_snk = add_snkrdunk(con)           # learn-book にも無かった分をスニダンで補う
    n_err = add_error_variants(con)     # 「（表面加工エラー）」に通常版の絵を入れる
    n_twin = add_twin_images(con)       # eシリーズの2枚組（キラ/通常）で絵を共有
    n_same = add_same_print(con)        # 手で確かめた「同じ刷り」から借りる
    n_offn = add_official_by_name(con)  # 公式にそのセット・その名前が1枚だけなら採る
    n_dual = add_dual_code_twins(con)   # 同じセットが2記号に割れている分を番号で埋める
    n_1st = add_first_series_twins(con)  # 1996年第1弾の記号違い・商品違いで絵を共有
    n_sets = build_sets(con)
    n_prod = build_products(con)

    q = lambda s: con.execute(s).fetchone()[0]
    total = n + n_mc + n_tc
    print(f"dex        {total:,}枚（マイカ一覧 {n:,}"
          f" ＋ カード単体ページ {n_mc:,}／{n_ms}セット"
          f" ＋ TCGdexのみ {n_tc:,}／{n_ts}セット）")
    print(f"マイカ画像   {n_img:,}枚")
    print(f"pcg-search  {n_pcg:,}枚（eシリーズ・593x834）")
    print(f"カードラッシュ  {n_cr:,}枚（868x1212）")
    print(f"1枚もの      {n_ex:,}枚（うち晴れる屋2の2枚は透かし入り）")
    print(f"トロフィー    {n_tr:,}枚（★推定★ trophy_guess を参照）")
    print(f"参考画像     {n_ph:,}枚（★実物ではない★ placeholder_images を参照）")
    print(f"learn-book  {n_web:,}枚（公開元が無い年代の補完）")
    print(f"スニダン     {n_snk:,}枚（learn-book にも無かった分）")
    print(f"エラー品     {n_err:,}枚（表面加工エラー → 通常版の絵）")
    print(f"2枚組       {n_twin:,}枚（eシリーズ キラ/通常 で絵を共有）")
    print(f"同じ刷り     {n_same:,}枚（手で確かめた対応）")
    print(f"公式・名前一意 {n_offn:,}枚（同じカードの別配布）")
    print(f"記号違い     {n_dual:,}枚（同じセットが2記号に割れている分）")
    print(f"1996年第1弾  {n_1st:,}枚（記号違い・商品違いで絵を共有）")
    print(f"レアリティ   {q('SELECT COUNT(*) FROM dex WHERE rarity IS NOT NULL'):,}枚"
          f"（{q('SELECT COUNT(DISTINCT rarity) FROM dex')}種）")
    print(f"ワザ等の補足 {q('SELECT COUNT(*) FROM dex WHERE tcg_id IS NOT NULL'):,}枚")
    print(f"商品（入口）  {n_prod}件"
          + (f" / パック名の統合 {n_uni}件" if n_uni else "")
          + (f" / 単体ページで訂正 {n_fix}件" if n_fix else ""))
    print(f"セット      {n_sets}種"
          f" / うち分類あり {q('SELECT COUNT(*) FROM dex_sets WHERE ptype IS NOT NULL')}")
    print(f"        {time.time()-t0:.0f}秒")

    print("\n分類ごとの商品数（図鑑の入口）:")
    for r in con.execute("""SELECT IFNULL(ptype,'（分類なし）'), COUNT(*), SUM(cards)
                            FROM dex_products GROUP BY ptype ORDER BY COUNT(*) DESC"""):
        print(f"   {r[0]:<10} {r[1]:>4}セット {r[2]:>7,}枚")
    con.close()


if __name__ == "__main__":
    main()
