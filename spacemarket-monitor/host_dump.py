#!/usr/bin/env python3
"""ログイン済みのセッションで、ホスト管理画面の中身を「読むだけ」取得する。

★読み取り専用。 クリックするのは画面内リンクの移動のみで、保存・送信・
  設定変更にあたる操作は一切行わない（そういうコードを置いていない）。

管理画面（dashboard.spacemarket.com）は中身が JavaScript で描かれるため、
HTMLを見るより **画面が裏で呼んでいるAPIの返り値をそのまま保存する**ほうが確実。
このスクリプトは次を local/dump/<日時>/ に残す。

  net/*.json    … 画面が取得したJSON（予約・売上・スペース設定などの元データ）
  page/*.txt    … 各ページの表示テキスト
  page/*.png    … 各ページのスクリーンショット
  index.json    … 巡回したURLと結果の一覧

用途: 最初の1回でこの中身を見て、`host_check.py`（定期レポート）の読み取り先を決める。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sm  # noqa: E402

# 巡回の入口。存在しないURLは 404 として記録するだけで止まらない。
SEED_PATHS = ["/"]
MAX_PAGES = 25


def _slug(url: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", urlparse(url).path.strip("/")) or "root"
    return s[:80]


def main() -> int:
    ctx = sm.open_context(headless=True)
    sm.require_login(ctx)

    stamp = sm.jst_now().replace(" ", "_").replace(":", "")
    out = sm.DUMP_DIR / stamp
    (out / "net").mkdir(parents=True, exist_ok=True)
    (out / "page").mkdir(parents=True, exist_ok=True)

    seen_net: set[str] = set()

    def on_response(resp):
        """画面が受け取ったJSONを保存する（読むだけ・書き換えない）。"""
        try:
            ctype = (resp.headers or {}).get("content-type", "")
            if "json" not in ctype:
                return
            key = f"{resp.request.method} {resp.url}"
            if key in seen_net:
                return
            seen_net.add(key)
            body = resp.json()
        except Exception:
            return
        name = f"{len(seen_net):03d}_{_slug(resp.url)}.json"
        (out / "net" / name).write_text(
            json.dumps(
                {"url": resp.url, "method": resp.request.method, "status": resp.status, "body": body},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    page = ctx.new_page()
    page.on("response", on_response)

    queue = [sm.DASHBOARD + p for p in SEED_PATHS]
    visited: list[dict] = []
    done: set[str] = set()

    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)
        if url in done:
            continue
        done.add(url)
        rec = {"url": url}
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            rec["status"] = resp.status if resp else None
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass  # 常時通信している画面は networkidle にならない。待てた分で進む
            slug = _slug(url)
            (out / "page" / f"{slug}.txt").write_text(
                page.inner_text("body"), encoding="utf-8"
            )
            page.screenshot(path=str(out / "page" / f"{slug}.png"), full_page=True)
            rec["title"] = page.title()

            # 同じ管理画面内のリンクだけ辿る（外部サイトへは出ない）
            hrefs = page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.href)"
            )
            for h in hrefs:
                if h.startswith(sm.DASHBOARD) and h.split("#")[0] not in done:
                    queue.append(h.split("#")[0])
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        visited.append(rec)
        print(f"  {rec.get('status', '-')} {url}")
        time.sleep(sm.POLITE_WAIT_SEC)

    sm.save_json(out / "index.json", {"visited": visited, "json_responses": sorted(seen_net)})
    sm.close_context(ctx)

    print(f"\n保存先: {out}")
    print(f"  ページ {len(visited)}件 / JSON応答 {len(seen_net)}件")
    print("  この中身を見て host_check.py（定期レポート）の読み取り先を決めます。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
