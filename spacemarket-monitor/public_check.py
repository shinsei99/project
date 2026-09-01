#!/usr/bin/env python3
"""公開ページ（ログイン不要）から3施設の現状を取る。

SpaceMarket の掲載ページは Next.js で、`<script id="__NEXT_DATA__">` に
ページの元データがそのまま入っている（2026-09-01 実測）。HTMLの見た目を
セレクタで拾うのではなく**このJSONを読む**ので、デザイン変更で壊れない。

取れるもの（ブラウザもログインも不要）:
  単価（時間/日）・プラン・**即予約可否**・最低利用時間・清掃オプション
  レビュー数/点数と5項目の内訳・直近レビュー日・写真枚数・定員・面積
  **ホストの評価指標**（rank / 返信の速さ / 承認しやすさ / 返信率）
    → これは SpaceMarket 内の検索順位＝露出に効く数値なので、露出強化の起点になる

出力: local/public/<日付>.json  ＋  reports/public-<日付>.md
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sm  # noqa: E402

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class _Redirect308(urllib.request.HTTPRedirectHandler):
    """SpaceMarket は末尾スラッシュ無しのURLに 308 を返す。

    urllib の `redirect_request` は 301/302/303/307 しか許可せず、それ以外は
    HTTPError を投げる（308 が許可されるのは Python 3.11 以降。手元の
    agent-platform/.venv は 3.9.6）。**コードを 307 に読み替えて**渡すことで
    どのバージョンでも追える。これが無いと全ページ取得が 308 で落ちる。
    """

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_307(req, fp, 307, msg, headers)

    https_error_308 = http_error_308


_OPENER = urllib.request.build_opener(_Redirect308)


def fetch_room(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": sm.UA, "Accept-Language": "ja"})
    with _OPENER.open(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", "replace")
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise RuntimeError(f"__NEXT_DATA__ が見つからない（掲載ページの作りが変わった可能性）: {url}")
    return json.loads(m.group(1))["props"]["pageProps"]["data"]["room"]


def _results(node) -> list:
    """GraphQL の {results: [...]} 形。無ければ空。"""
    if isinstance(node, dict):
        return node.get("results") or []
    if isinstance(node, list):
        return node
    return []


def summarize(fac: dict, room: dict) -> dict:
    rep = room.get("reputationSummary") or {}
    owner = room.get("owner") or {}
    plans = _results(room.get("plans"))
    photos = _results(room.get("thumbnails"))
    reputations = _results(room.get("reputations"))

    # ページに載っている直近レビューの利用日（＝いつ最後に使われたかの目安）
    latest = None
    for r in reputations:
        started = ((r.get("reservation") or {}).get("startedAt") or "")[:10]
        if started and (latest is None or started > latest):
            latest = started

    prices = _results(room.get("prices")) or (room.get("prices") or [])
    price = prices[0] if prices else {}

    return {
        "key": fac["key"],
        "name": fac["name"],
        "url": fac["url"],
        "room_id": room.get("id"),
        "title": room.get("pageTitle"),
        "space_type": (room.get("space") or {}).get("spaceTypeText"),
        "access": (room.get("space") or {}).get("primaryNearbyStation"),
        "capacity": room.get("capacity"),
        "area_m2": room.get("area"),
        "description_chars": len(room.get("description") or ""),
        "photo_count": len(photos),
        "price_min": price.get("minPrice"),
        "price_max": price.get("maxPrice"),
        "price_unit": price.get("maxUnitText") or price.get("minUnitText"),
        "reservation_available": room.get("isReservationAvailable"),
        "instant_book": room.get("hasDirectReservationPlans"),  # 即予約
        "inquiry_only": room.get("isInquiryOnly"),
        "id_required": room.get("isIdentificationNeeded"),
        "policy_type": room.get("policyType"),
        "review_score": rep.get("score"),
        "review_count": rep.get("count"),
        "review_breakdown": {
            "ホスト": rep.get("ownerPoint"),
            "価格": rep.get("pricePoint"),
            "入退室": rep.get("entryExitPoint"),
            "清潔さ": rep.get("cleanlinessPoint"),
            "情報の正確さ": rep.get("accuracyPoint"),
        },
        "latest_review_used_on": latest,
        "plans": [
            {
                "name": p.get("name"),
                "hourly": p.get("hourlyPriceText"),
                "daily": p.get("dailyPriceText"),
                "min_hours": p.get("minRequiredHour"),
                "instant_book": p.get("directReservationAccepted"),
                "cleaning_option": p.get("optionCleaningPriceText"),
            }
            for p in plans
        ],
        "owner": {
            "corp": owner.get("corpName"),
            "rank": owner.get("rank"),
            "reply_time": owner.get("replyTimeAvgText"),
            "reply_time_eval": owner.get("replyTimeAvgEvaluation"),
            "confirm_rate": owner.get("confirmRateText"),
            "confirm_rate_eval": owner.get("confirmRateEvaluation"),
            "reply_rate": owner.get("replyRateText"),
            "reply_rate_eval": owner.get("replyRateEvaluation"),
            "reputation_score": owner.get("reputationScore"),
            "reputation_count": owner.get("reputationCount"),
        },
    }


def _point(v) -> str:
    """レビュー内訳の1項目を表示用にする。

    SpaceMarket は施設によって内訳を 0 で返す（レセプル福島・グリーンガーデン秋津が該当。
    総合点と件数は正しく返る）。**0 は「評価0点」ではなく「内訳なし」**なので、
    点数として並べると誤読する。
    """
    return "—" if not v else str(v)


def to_markdown(rows: list[dict]) -> str:
    out: list[str] = []
    out.append(f"# SpaceMarket 3施設 現状（公開ページ・{sm.jst_now()} JST 取得）\n")
    out.append("※ログイン不要の公開情報のみ。予約実績・売上・特集応募状況はホスト管理画面側（`host_dump.py`）。\n")

    out.append("## 掲載スペック\n")
    out.append("| 施設 | 単価 | 定員 | 面積 | 写真 | 説明文 | 即予約 | 予約受付 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        unit = r["price_unit"] or ""
        price = f"¥{r['price_min']:,}〜¥{r['price_max']:,}/{unit}" if r["price_min"] else "—"
        out.append(
            f"| {r['name']} | {price} | {r['capacity']}名 | {r['area_m2']}㎡ | "
            f"{r['photo_count']}枚 | {r['description_chars']}字 | "
            f"{'✅' if r['instant_book'] else '❌'} | {'✅' if r['reservation_available'] else '❌'} |"
        )

    out.append("\n## 評価（＝SpaceMarket内の検索順位に効く）\n")
    out.append("| 施設 | 総合 | 件数 | 直近利用 | ホスト | 価格 | 入退室 | 清潔さ | 正確さ |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        b = r["review_breakdown"]
        cells = " | ".join(_point(b[k]) for k in ("ホスト", "価格", "入退室", "清潔さ", "情報の正確さ"))
        out.append(
            f"| {r['name']} | {r['review_score']} | **{r['review_count']}件** | "
            f"{r['latest_review_used_on'] or '—'} | {cells} |"
        )
    if any(not any(r["review_breakdown"].values()) for r in rows):
        out.append(
            "\n> 「—」は SpaceMarket が内訳を返していない施設（総合点と件数は返る）。"
            "こちらの取得漏れではない（2026-09-01 に生データで確認）。"
        )

    own = rows[0]["owner"] if rows else {}
    out.append("\n## ホストアカウント（3施設共通）\n")
    out.append(f"- 事業者: {own.get('corp')}")
    out.append(f"- ホストランク: {own.get('rank')}")
    out.append(f"- 返信の速さ: {own.get('reply_time')}（{own.get('reply_time_eval')}）")
    out.append(f"- 返信率: {own.get('reply_rate')}（{own.get('reply_rate_eval')}）")
    out.append(f"- 承認しやすさ: {own.get('confirm_rate')}（{own.get('confirm_rate_eval')}）")
    out.append(f"- ホスト評価: {own.get('reputation_score')}（{own.get('reputation_count')}件）")

    out.append("\n## プラン\n")
    for r in rows:
        out.append(f"### {r['name']}")
        if not r["plans"]:
            out.append("- （プランなし）")
        for p in r["plans"]:
            out.append(
                f"- **{p['name']}** … 時間 {p['hourly']} / 日 {p['daily']}"
                f"（最低 {p['min_hours']}時間・即予約 {'✅' if p['instant_book'] else '❌'}"
                f"・清掃 {p['cleaning_option'] or '—'}）"
            )
        out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    rows = []
    for fac in sm.facilities():
        print(f"取得中: {fac['name']} … ", end="", flush=True)
        try:
            room = fetch_room(fac["url"])
        except (urllib.error.URLError, RuntimeError) as e:
            print(f"失敗（{e}）")
            continue
        rows.append(summarize(fac, room))
        print("OK")
        time.sleep(sm.POLITE_WAIT_SEC)

    if not rows:
        print("1件も取れませんでした。", file=sys.stderr)
        return 1

    day = sm.jst_today()
    j = sm.save_json(sm.ROOT / "local" / "public" / f"{day}.json", rows)
    md = sm.REPORT_DIR / f"public-{day}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(to_markdown(rows), encoding="utf-8")
    print(f"\n生データ: {j}\nレポート: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
