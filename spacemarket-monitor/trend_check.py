#!/usr/bin/env python3
"""予約明細から「なぜ増えた／減ったか」を切り分ける診断レポート（オフライン・読み取り専用）。

★ログイン不要。 入力は `local/reservations_all.json`（`./run.sh fetch` で取り直す）だけ。
  ネットに一切出ないので、何度回しても相手のサーバーに負担をかけない。

★なぜ作ったか（2026-09-03）
  「予約が減った」を1つの数字で見ていると、原因が **入口（見つけてもらう回数）** なのか
  **接客・価格（来た話を取りこぼす）** なのか分からない。ここを最初に分けないと、
  打ち手が「接客改善」に流れて空振りする。実際、加東の2026年の落ち込みは
  **新規客の流入が半減**したためで、成約率・単価・応対はまったく劣化していなかった。

  切り分け方はこの3段:
    ① 申込 → 確定 …… ここが落ちていれば「接客・価格・条件」の問題
    ② 確定の 新規 / リピート …… 新規だけ落ちていれば「入口＝露出」の問題
    ③ 単価・用途・人数・曜日 …… 打ち手を決めるための内訳

出力: reports/trend-<日付>.md
"""
from __future__ import annotations

import collections
import datetime
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sm  # noqa: E402

CONFIRMED = (8, 15)  # 予約完了
PENDING = 0  # 保留中（承認前に流れた／期限切れ）
REFUNDED = 10  # 払い戻し（キャンセル）
WEEKDAYS = "月火水木金土日"


# ---------------------------------------------------------------- 読み込み・下ごしらえ


def load_rows() -> list:
    path = sm.ROOT / "local" / "reservations_all.json"
    if not path.exists():
        sys.exit(
            f"{path} がありません。\n"
            "  先に予約明細を取ってください（ログインが要ります）:\n"
            "  ./run.sh fetch"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def use_day(r) -> str:
    """利用日（YYYY-MM-DD）。実際に使われた日で並べたいときはこちら。"""
    return (r.get("started_at") or "")[:10]


def apply_month(r) -> str:
    """申込月（YYYY-MM）。需要がいつ来たかを見たいときはこちら。

    利用日で数えると「先の予約が入っているだけ」の月が膨らむので、
    落ち込みの原因を見るときは申込日ベースで揃える。
    """
    return (r.get("created_at") or "")[:7]


def price(r) -> float:
    v = (r.get("billing") or {}).get("total_amount")
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def first_time_users(rows: list) -> dict:
    """利用者ID → その人の最初の確定予約の予約ID。

    ★ホスト単位で見る（施設をまたいでも2回目はリピート）。同じオーナーの別施設へ
      移った人を「新規」と数えると、露出が落ちたかどうかが見えなくなるため。
    """
    first: dict = {}
    for r in sorted(rows, key=lambda x: (x.get("created_at") or "")):
        if r.get("status") not in CONFIRMED:
            continue
        uid = (r.get("user") or {}).get("id")
        if uid and uid not in first:
            first[uid] = r.get("id")
    return first


def room_label(room_id, rows_of_room: list) -> str:
    name = sm.ROOM_NAMES.get(room_id)
    if name:
        return name
    raw = (rows_of_room[0].get("room") or {}).get("name", "")
    return f"★未登録の掲載({room_id}) {raw[:24]}"


# ---------------------------------------------------------------- 集計


def same_period_funnel(rows: list, first: dict, cut_month: int) -> list:
    """1月〜今月でそろえた同期比較（申込月ベース）。

    今年は年の途中なので、去年までと同じ「1月〜今月」で切らないと比べられない。
    """
    out = []
    by_year: dict = collections.defaultdict(list)
    for r in rows:
        m = apply_month(r)
        if m and int(m[5:7]) <= cut_month:
            by_year[m[:4]].append(r)
    for year in sorted(by_year):
        g = by_year[year]
        conf = [r for r in g if r.get("status") in CONFIRMED]
        new = [r for r in conf if first.get((r.get("user") or {}).get("id")) == r.get("id")]
        out.append(
            {
                "year": year,
                "applied": len(g),
                "confirmed": len(conf),
                "new": len(new),
                "repeat": len(conf) - len(new),
                "pending": sum(1 for r in g if r.get("status") == PENDING),
                "refunded": sum(1 for r in g if r.get("status") == REFUNDED),
                "sales": sum(price(r) for r in conf),
            }
        )
    return out


def diagnose(funnel: list) -> list:
    """直近2年を見比べて、入口の問題か接客の問題かを言い切る。"""
    msg: list = []
    if len(funnel) < 2:
        return ["- 比較できる年が足りない（2年ぶん要る）"]
    prev, now = funnel[-2], funnel[-1]

    def pct(a, b):
        return f"{(b - a) / a * 100:+.0f}%" if a else "—"

    rate_prev = prev["confirmed"] / prev["applied"] * 100 if prev["applied"] else 0
    rate_now = now["confirmed"] / now["applied"] * 100 if now["applied"] else 0

    msg.append(
        f"- 申込 {prev['applied']}件 → {now['applied']}件（**{pct(prev['applied'], now['applied'])}**）"
        f" / 確定 {prev['confirmed']}件 → {now['confirmed']}件（{pct(prev['confirmed'], now['confirmed'])}）"
    )
    msg.append(
        f"- 申込→確定の歩留まり {rate_prev:.0f}% → {rate_now:.0f}%"
        f" / 新規 {prev['new']}件 → {now['new']}件（{pct(prev['new'], now['new'])}）"
        f" / リピート {prev['repeat']}件 → {now['repeat']}件（{pct(prev['repeat'], now['repeat'])}）"
    )

    # ★母数が小さい年で言い切らない。 1件の保留で「歩留まりが50%に落ちた」と
    #   出てしまい、実際に 2026年のレセプル福島（申込2件）で誤った判定が出た。
    MIN_N = 10
    if prev["applied"] < MIN_N or now["applied"] < MIN_N:
        msg.append(
            f"- 判定なし: 申込が{MIN_N}件未満の年があり、割合で語ると誤読する"
            "（この施設は件数そのものを見ること）"
        )
        return msg

    drop_in = prev["applied"] and (now["applied"] - prev["applied"]) / prev["applied"] <= -0.15
    drop_rate = rate_prev - rate_now >= 10
    drop_new = prev["new"] and (now["new"] - prev["new"]) / prev["new"] <= -0.15
    drop_rep = prev["repeat"] >= 3 and (now["repeat"] - prev["repeat"]) / prev["repeat"] <= -0.15

    if drop_in and not drop_rate:
        msg.append(
            "- **判定: 入口（見つけてもらう回数）の問題。** 来た話の取りこぼしは増えていないのに、"
            "申込そのものが減っている。打ち手は掲載の見つかりやすさ（タイトル・説明文・設備項目・広告）"
        )
    elif drop_rate:
        msg.append(
            "- **判定: 来た話を取りこぼしている。** 申込→確定の歩留まりが落ちた。"
            "承認の速さ・返答・条件（人数/時間/料金）を先に見ること"
        )
    elif drop_in and drop_rate:
        msg.append("- **判定: 入口と歩留まりの両方が落ちている**")
    else:
        msg.append("- 判定: 前年から大きくは崩れていない")

    if drop_new and not drop_rep and max(prev["repeat"], now["repeat"]) >= 3:
        msg.append(
            "- **新規客だけが減り、リピートは保たれている。** 満足度の問題ではなく、"
            "新しい人に見つかっていないことがはっきりしている"
        )
    elif drop_rep and not drop_new:
        msg.append("- リピートだけが減っている。前年の常連が離れた理由を当たること")
    return msg


def dist_table(rows: list, key, years: list, top: int = 6) -> list:
    """年 × 何か（用途・人数など）の内訳を作る。"""
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        y = use_day(r)[:4]
        if y in years:
            by[y][key(r)] += 1
    return by


# ---------------------------------------------------------------- レポート


def build_report(rows: list, cut_month: int) -> str:
    first = first_time_users(rows)
    by_room = collections.defaultdict(list)
    for r in rows:
        by_room[r.get("room_id")].append(r)

    o: list = []
    o.append(f"# SpaceMarket 予約の増減 診断（{sm.jst_now()} JST 作成）\n")
    o.append(
        f"入力: `local/reservations_all.json`（{len(rows)}件）／"
        f"同期比較は **1月〜{cut_month}月** でそろえた**申込日**ベース。\n"
    )
    o.append(
        "> 「新規」は**ホスト単位**の初回（施設をまたいでも2回目はリピート）。"
        "「申込」は保留・払戻を含む全ステータス。\n"
    )

    # 稼働している掲載を、件数の多い順に
    order = sorted(by_room.items(), key=lambda kv: -len(kv[1]))
    for room_id, rrows in order:
        label = room_label(room_id, rrows)
        conf = [r for r in rrows if r.get("status") in CONFIRMED]
        if not conf:
            continue
        o.append(f"\n---\n\n## {label}（room {room_id}・確定 {len(conf)}件）\n")

        # ① 同期比較（申込ベース）
        funnel = same_period_funnel(rrows, first, cut_month)
        o.append(f"### 同期比較（1〜{cut_month}月・申込日ベース）\n")
        o.append("| 年 | 申込 | 確定 | └新規 | └リピート | 保留 | 払戻 | 成約金額 |")
        o.append("|---|---|---|---|---|---|---|---|")
        for f in funnel:
            o.append(
                f"| {f['year']} | {f['applied']} | **{f['confirmed']}** | {f['new']} | "
                f"{f['repeat']} | {f['pending']} | {f['refunded']} | ￥{f['sales']:,.0f} |"
            )
        o.append("")
        o.extend(diagnose(funnel))

        # ② 年別の全体像（利用日ベース）
        o.append("\n### 年別（利用日ベース・確定のみ）\n")
        o.append("| 年 | 件数 | 成約金額 | 単価中央値 | リード中央値 |")
        o.append("|---|---|---|---|---|")
        years = sorted({use_day(r)[:4] for r in conf if use_day(r)})
        for y in years:
            g = [r for r in conf if use_day(r)[:4] == y]
            leads = []
            for r in g:
                c, s = (r.get("created_at") or "")[:10], use_day(r)
                if c and s:
                    leads.append(
                        (datetime.date.fromisoformat(s) - datetime.date.fromisoformat(c)).days
                    )
            med_price = f"￥{statistics.median([price(r) for r in g]):,.0f}" if g else "—"
            med_lead = f"{statistics.median(leads):.0f}日" if leads else "—"
            o.append(
                f"| {y} | {len(g)} | ￥{sum(price(r) for r in g):,.0f} | {med_price} | {med_lead} |"
            )

        recent = years[-3:]

        # ③ 用途
        o.append(f"\n### 用途（利用日ベース・直近{len(recent)}年）\n")
        ev = dist_table(conf, lambda r: r.get("event_type_text") or "（未設定）", recent)
        for y in recent:
            top = ev[y].most_common(6)
            tot = sum(ev[y].values()) or 1
            o.append(
                f"- **{y}**: " + " / ".join(f"{k} {v}件({v/tot*100:.0f}%)" for k, v in top)
            )

        # ④ 人数（検索の人数フィルタに直結する）
        caps = [r.get("capacity") for r in conf if isinstance(r.get("capacity"), int)]
        if caps:
            ceiling = max(caps)
            at_ceiling = sum(1 for c in caps if c == ceiling)
            o.append(f"\n### 利用人数（確定 {len(caps)}件）\n")
            cnt = collections.Counter(caps)
            o.append("- " + " / ".join(f"{k}名 {cnt[k]}件" for k in sorted(cnt)))
            o.append(
                f"- 最大は **{ceiling}名**で、**{at_ceiling}件（{at_ceiling/len(caps)*100:.0f}%）が"
                f"ちょうど {ceiling}名**。"
                + (
                    f" ★掲載の人数上限が {ceiling}名なら、**{ceiling+1}名以上で探している人には"
                    "一度も表示されていない**（検索は人数で絞られる）。"
                    "実際に何名まで入れるかを確かめて、上限を上げられるなら上げる価値がある"
                    if at_ceiling / len(caps) >= 0.2
                    else ""
                )
            )

        # ⑤ 曜日
        o.append("\n### 利用曜日（直近3年・確定）\n")
        for y in recent:
            wd = collections.Counter()
            for r in conf:
                s = use_day(r)
                if s[:4] == y:
                    wd[datetime.date.fromisoformat(s).weekday()] += 1
            tot = sum(wd.values()) or 1
            we = wd[5] + wd[6]
            o.append(
                f"- **{y}**: "
                + " ".join(f"{WEEKDAYS[i]}{wd[i]}" for i in range(7))
                + f"  （土日 {we}件・{we/tot*100:.0f}%）"
            )

    o.append("\n---\n")
    o.append(
        "## この診断で分からないこと\n\n"
        "- **表示回数（インプレッション）はホスト管理画面のどこにも無い**（2026-09-01 に\n"
        "  API応答50件を全走査して確認）。よって「露出が落ちた」は直接は測れず、\n"
        "  上のように**歩留まり・新規/リピートの切り分けから消去法で言う**しかない\n"
        "- 検索順位（84の利用目的カテゴリすべてで「-」）が圏外なのか未算出なのかは**未確認**\n"
        "- 同エリアの競合が増えたかどうかは、他社の掲載を読まない方針のため**未調査**\n"
    )
    return "\n".join(o) + "\n"


def main() -> int:
    rows = load_rows()
    cut_month = int(sm.jst_today()[5:7])
    md = sm.REPORT_DIR / f"trend-{sm.jst_today()}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_report(rows, cut_month), encoding="utf-8")
    print(f"レポート: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
