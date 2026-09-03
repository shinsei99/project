#!/usr/bin/env python3
"""ホスト管理画面から実績・掲載状況を取ってレポートにする（読み取り専用）。

★画面のHTMLは読まない。 管理画面が裏で叩いている REST API を、ログイン済み
  セッションのまま直接 GET する（`host_dump.py` で見つけた。2026-09-01）。
  画面の作りが変わっても壊れにくく、1施設ぶん数百ミリ秒で終わる。

      GET https://mp-gateway.spacemarket.com/rest/1/owners/<slug>/rooms
      GET .../analytics?grouping=monthly&date_range_type=year&year=YYYY
      GET .../calendar?year=YYYY&month=M

  広告出稿（スペマサーチ広告）の申込状況だけは JSON が無いので、画面の文字を読む。

出力: local/host/<日付>.json  ＋  reports/host-<日付>.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sm  # noqa: E402

GATEWAY = sm.GATEWAY

# 掲載名は長いので、社内で使っている呼び名に対応づける（uid は公開ページのURL末尾と同じ）
KNOWN = {
    "ePrMgAswaWYsjRzN": "グリーンガーデン加東",
    "vom4LWVk4aNaD22Z": "レセプル福島",
    "Ew0cUleoB6xuwfHu": "グリーンガーデン秋津",
}


# ログイン済みセッションから API 用ヘッダを取る処理は sm.py に移した（fetch_reservations.py と共用）。
open_session = sm.api_session
get_json = sm.api_get


def amount(field) -> str:
    """API は {amount, amount_text, prefix_text, suffix_text} で返す。表示用に組み立てる。"""
    f = field or {}
    return f"{f.get('prefix_text','')}{f.get('amount_text','')}{f.get('suffix_text','')}"


def num(field) -> float:
    return (field or {}).get("amount") or 0


def ad_status(ctx) -> str:
    """広告出稿ページの申込状況（JSONが無いので画面の文字から拾う）。"""
    page = ctx.new_page()
    try:
        page.goto(
            f"{sm.DASHBOARD}/{page.context._slug}/search_promotions",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        text = page.inner_text("body")
        m = re.search(r"(\d{4}年\d{1,2}月分の申し込み状況)\s*(.{0,60})", text, re.S)
        return f"{m.group(1)}: {m.group(2).strip().splitlines()[0]}" if m else "（取得できず）"
    except Exception as e:
        return f"（取得できず: {type(e).__name__}）"
    finally:
        page.close()


def build_report(slug: str, rooms: list, months: list, ad: str, cal_month: dict, per_room: list) -> str:
    known = KNOWN
    o: list[str] = []
    o.append(f"# SpaceMarket ホスト管理画面 実績（{sm.jst_now()} JST 取得・ホスト {slug}）\n")

    o.append(f"## 掲載 {len(rooms)}件\n")
    o.append("| 掲載名 | 呼び名 | 予約受付 |")
    o.append("|---|---|---|")
    for r in rooms:
        name = known.get(r.get("uid"), "**★把握されていない掲載**")
        o.append(
            f"| {r.get('name','')[:44]} | {name} | "
            f"{'✅ 受付中' if r.get('is_reservation_available') else '❌ **停止中**'} |"
        )

    if per_room:
        o.append("\n## 施設別の実績（今年・受付中のみ）\n")
        o.append("| 施設 | 成約 | 成約金額 | リクエスト | 問合せ | レビュー |")
        o.append("|---|---|---|---|---|---|")
        for name, ms in per_room:
            o.append(
                f"| {name} | {sum(num(m.get('total_conversions_count')) for m in ms):.0f}件 | "
                f"￥{sum(num(m.get('total_sales')) for m in ms):,.0f} | "
                f"{sum(num(m.get('total_request_count')) for m in ms):.0f}件 | "
                f"{sum(num(m.get('total_inquiries_count')) for m in ms):.0f}件 | "
                f"{sum(num(m.get('total_reputations_count')) for m in ms):.0f}件 |"
            )

    o.append("\n## 月次実績・ホスト全体（予約リクエスト送信日ベース）\n")
    o.append("| 年月 | 成約 | 稼働率 | 成約金額 | 収益 | リクエスト | 問合せ | レビュー |")
    o.append("|---|---|---|---|---|---|---|---|")
    tot_sales = tot_conv = 0
    for m in months:
        if not num(m.get("total_request_count")) and not num(m.get("total_sales")):
            continue  # まだ来ていない月は出さない
        tot_sales += num(m.get("total_sales"))
        tot_conv += num(m.get("total_conversions_count"))
        o.append(
            f"| {m['year']}-{m['month']:02d} | {amount(m.get('total_conversions_count'))} | "
            f"{amount(m.get('total_use'))} | {amount(m.get('total_sales'))} | "
            f"{amount(m.get('total_payment'))} | {amount(m.get('total_request_count'))} | "
            f"{amount(m.get('total_inquiries_count'))} | {amount(m.get('total_reputations_count'))} |"
        )
    o.append(f"\n- 期間合計: **成約 {int(tot_conv)}件 / 成約金額 ￥{int(tot_sales):,}**")

    last = months[-1] if months else {}
    o.append(
        f"- 応対品質（検索順位に効く）: 承認率 {amount(last.get('confirm_rate'))} / "
        f"返答率 {amount(last.get('reply_rate'))} / 平均返答時間 {amount(last.get('reply_time_avg'))}"
    )

    o.append(f"\n## 広告出稿（スペマサーチ広告）\n\n- {ad}")

    resv = sum(len(d.get("reservations") or []) for d in cal_month.get("days", []))
    blocks = sum(len(d.get("room_blocks") or []) for d in cal_month.get("days", []))
    o.append(
        f"\n## 当月カレンダー（{cal_month.get('year')}年{cal_month.get('month')}月）\n\n"
        f"- 予約 {resv}件 / ブロック（貸出停止）{blocks}件"
    )
    return "\n".join(o) + "\n"


def main() -> int:
    ctx = sm.open_context(headless=True)
    sm.require_login(ctx)
    slug, headers = open_session(ctx)
    ctx._slug = slug  # ad_status から使う

    year = int(sm.jst_today()[:4])
    month = int(sm.jst_today()[5:7])

    rooms = get_json(ctx, f"{GATEWAY}/owners/{slug}/rooms", headers)
    months = get_json(
        ctx,
        f"{GATEWAY}/owners/{slug}/analytics?grouping=monthly&date_range_type=year&year={year}",
        headers,
    )
    days = get_json(ctx, f"{GATEWAY}/owners/{slug}/calendar?year={year}&month={month}", headers)

    # 施設別の実績。analytics は room_id を付けると1施設ぶんに絞れる（2026-09-01 実測）。
    # 受付を止めている掲載は数字が動かないので出さない。
    per_room = []
    for r in rooms:
        if not r.get("is_reservation_available"):
            continue
        ms = get_json(
            ctx,
            f"{GATEWAY}/owners/{slug}/analytics"
            f"?grouping=monthly&date_range_type=year&year={year}&room_id={r['id']}",
            headers,
        )
        per_room.append((KNOWN.get(r.get("uid"), r.get("name", "")[:24]), ms))
    ad = ad_status(ctx)
    sm.close_context(ctx)

    cal = {"year": year, "month": month, "days": days}
    day = sm.jst_today()
    j = sm.save_json(
        sm.ROOT / "local" / "host" / f"{day}.json",
        {
            "slug": slug,
            "rooms": rooms,
            "analytics": months,
            "per_room": [{"name": n, "months": m} for n, m in per_room],
            "calendar": cal,
            "ad_status": ad,
        },
    )
    md = sm.REPORT_DIR / f"host-{day}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_report(slug, rooms, months, ad, cal, per_room), encoding="utf-8")
    print(f"生データ: {j}\nレポート: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
