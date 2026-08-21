"""マイソクの記載を、謄本と公的データに突き合わせて確かめる。

**なぜ要るか（2026-08-21 オーナー指示）**
マイソクは他社が作った広告資料で、誤り・古い情報・省略が混ざる。読み取った値を
そのまま重説へ流すと、**他社の誤りをこちらの重説に転記してしまう**。
そこで、こちらで確かめられるものは全部突き合わせてから使う。

**「判定不可」と「不一致」を混同しない。**
比べる相手が無いときは 🟢 でも 🔴 でもなく ⚪ を返す。
（`legal-crosscheck` で、データが無いのに 🟢一致 と出す偽の合格が実際にあった。
  同じ作りにしない。）

**謄本は確定として扱う（2026-08-21 オーナー判断）。**
食い違ったときに疑うのはマイソクのほうで、謄本ではない。
ただし**謄本は発行日が古いと現況と違う**（その後に売買・抵当権設定があり得る）ので、
発行日だけは別に見る（`registry_age()`）。

突き合わせる相手:
  住所   → 日本郵便の公式データ（町名まで）＋ 謄本の「所在」（謄本が正）
  最寄駅 → 国土地理院ベースの調査結果（`address_service`）
  種目   → 謄本の「種類」「地目」（謄本が正）
"""
from __future__ import annotations

import re
from typing import Dict, List

from services import address_verify_service as AV

OK, DIFF, UNKNOWN = "🟢", "🟡", "⚪"


def _norm(s: str) -> str:
    """比較用。空白・全角半角のゆれ・ハイフンの種類を吸収する。"""
    t = str(s or "")
    t = t.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    t = re.sub(r"[\s　]", "", t)
    t = re.sub(r"[－ー‐−–—―]", "-", t)
    return t


def _town(s: str) -> str:
    """住所から町名までを取り出す（丁目・番地を落とす）。"""
    return _norm(AV.split_for_input(s)[0])


def _row(item, mai_value, result, note, ref=""):
    return {"項目": item, "マイソク": mai_value or "（記載なし）",
            "照合先": ref, "結果": result, "説明": note}


def check(mai: Dict[str, str], reg: Dict[str, str],
          data: Dict[str, str]) -> List[dict]:
    """マイソク（mai）を、謄本（reg）と調査結果（data）に突き合わせる。

    戻り値は画面にそのまま表で出せる行の一覧。
    """
    rows: List[dict] = []
    if not mai:
        return rows

    # ── 住所 ─────────────────────────────────────────────
    addr = mai.get("所在地", "")
    if not addr:
        rows.append(_row("所在地", "", UNKNOWN, "マイソクに住所の記載がありません。"))
    else:
        v = AV.verify(addr)
        if v["status"] in ("一致", "町域まで一致"):
            rows.append(_row("所在地（実在）", addr, OK,
                             "日本郵便の公式データと町名まで一致（〒{}）。"
                             "丁目以降は確認できません。".format(v.get("zip", "")),
                             v.get("official", "")))
        elif v["status"] == "見つからない":
            rows.append(_row("所在地（実在）", addr, DIFF,
                             "日本郵便のデータに該当する町名がありません。"
                             "誤記か、古い町名の可能性があります。"))
        else:
            rows.append(_row("所在地（実在）", addr, UNKNOWN, v["message"]))

        # 謄本の所在と町名レベルで一致するか
        reg_addr = (reg or {}).get("登記所在", "")
        if not reg_addr:
            rows.append(_row("所在地（謄本と）", addr, UNKNOWN,
                             "謄本を読み込んでいないため照合できません。"))
        else:
            a, b = _town(addr), _town(reg_addr)
            if a and b and (a.endswith(b) or b.endswith(a) or a == b):
                rows.append(_row("所在地（謄本と）", addr, OK,
                                 "謄本の所在と町名まで一致。", reg_addr))
            else:
                rows.append(_row("所在地（謄本と）", addr, DIFF,
                                 "謄本の所在と町名が違います。**謄本が正**なので、"
                                 "マイソクの誤りか別物件かを確認してください。", reg_addr))

    # ── 最寄駅 ───────────────────────────────────────────
    mai_access = mai.get("交通", "")
    got_station = (data or {}).get("最寄駅", "")
    if not mai_access:
        rows.append(_row("最寄駅", "", UNKNOWN, "マイソクに交通の記載がありません。"))
    elif not got_station:
        rows.append(_row("最寄駅", mai_access, UNKNOWN,
                         "住所調査ができていないため照合できません。"))
    else:
        # 駅名だけ取り出して比べる（「京橋駅（大阪長堀鶴見緑地線）」→「京橋」）
        name = re.split(r"[（(]", got_station)[0].replace("駅", "").strip()
        if name and name in _norm(mai_access):
            rows.append(_row("最寄駅", mai_access, OK,
                             "調査結果の最寄駅と一致。", got_station))
        else:
            rows.append(_row("最寄駅", mai_access, DIFF,
                             "調査した最寄駅と違います。徒歩分数の記載も含めて"
                             "確認してください（広告は別の駅を書くことがあります）。",
                             "{}／{}".format(got_station, (data or {}).get("駅距離", ""))))

    # ── 種目 ─────────────────────────────────────────────
    kind = mai.get("種目", "")
    reg_kind = " ".join(x for x in ((reg or {}).get("種類", ""),
                                    (reg or {}).get("地目", "")) if x)
    if not kind:
        rows.append(_row("種目", "", UNKNOWN, "マイソクに種目の記載がありません。"))
    elif not reg_kind:
        rows.append(_row("種目", kind, UNKNOWN,
                         "謄本の種類・地目が取れていないため照合できません。"))
    else:
        pairs = [("戸建", ("居宅",)), ("マンション", ("居宅", "共同住宅")),
                 ("土地", ("宅地", "雑種地", "田", "畑")), ("売地", ("宅地", "雑種地"))]
        hit = None
        for word, expect in pairs:
            if word in kind:
                hit = any(e in reg_kind for e in expect)
                break
        if hit is None:
            rows.append(_row("種目", kind, UNKNOWN,
                             "この種目は自動で判定できません。", reg_kind))
        elif hit:
            rows.append(_row("種目", kind, OK, "謄本の種類・地目と矛盾しません。", reg_kind))
        else:
            rows.append(_row("種目", kind, DIFF,
                             "謄本の種類・地目と食い違います（**謄本が正**）。", reg_kind))
    return rows


def summary(rows: List[dict]) -> str:
    """1行の要約（画面の見出し用）。"""
    if not rows:
        return ""
    n_ok = sum(1 for r in rows if r["結果"] == OK)
    n_diff = sum(1 for r in rows if r["結果"] == DIFF)
    n_unk = sum(1 for r in rows if r["結果"] == UNKNOWN)
    return "🟢 一致 {} ／ 🟡 要確認 {} ／ ⚪ 判定不可 {}".format(n_ok, n_diff, n_unk)


# 謄本の鮮度。**内容は確定として扱うが、発行日が古いと現況と違う**
# （その後に売買・抵当権設定・分筆があり得る）。決済実務の目安で線を引く。
FRESH_DAYS = 30      # これ以内なら新しい
STALE_DAYS = 90      # これを超えたら取り直しを促す

_WAREKI = {"令和": 2018, "平成": 1988, "昭和": 1925}


def parse_wareki(text: str):
    """「令和7年5月1日」→ date。読めなければ None。西暦表記にも対応する。"""
    import datetime
    t = _norm(text)
    m = re.search(r"(令和|平成|昭和)(\d+)年(\d+)月(\d+)日", t)
    if m:
        base = _WAREKI[m.group(1)]
        try:
            return datetime.date(base + int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except ValueError:
            return None
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", t)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def registry_age(reg: Dict[str, str], today=None) -> dict:
    """謄本の発行日から鮮度を返す。

    戻り: {"結果": 🟢/🟡/⚪, "発行日": …, "日数": n, "説明": …}
    **読めないときは 🟡 ではなく ⚪**（古いと決めつけない）。
    """
    import datetime
    raw = (reg or {}).get("謄本発行日", "")
    if not raw:
        return {"結果": UNKNOWN, "発行日": "", "日数": None,
                "説明": "謄本の発行日を読み取れませんでした。書面の末尾で確認してください。"}
    d = parse_wareki(raw)
    if not d:
        return {"結果": UNKNOWN, "発行日": raw, "日数": None,
                "説明": "発行日「{}」を日付として解釈できませんでした。".format(raw)}
    today = today or datetime.date.today()
    days = (today - d).days
    if days < 0:
        return {"結果": UNKNOWN, "発行日": raw, "日数": days,
                "説明": "発行日が未来の日付です。読み取り誤りの可能性があります。"}
    if days <= FRESH_DAYS:
        note = "発行から {} 日。新しい謄本です。".format(days)
        return {"結果": OK, "発行日": raw, "日数": days, "説明": note}
    if days <= STALE_DAYS:
        note = ("発行から {} 日。内容は確定として扱えますが、"
                "決済までに動きがないか確認してください。".format(days))
        return {"結果": OK, "発行日": raw, "日数": days, "説明": note}
    return {"結果": DIFF, "発行日": raw, "日数": days,
            "説明": "発行から **{} 日** 経っています。その後に売買・抵当権設定・分筆が"
                    "あるかもしれません。**最新の謄本を取り直してください。**".format(days)}
