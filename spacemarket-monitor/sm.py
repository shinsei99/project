#!/usr/bin/env python3
"""spacemarket-monitor の共通部分。

★このツールは読み取り専用。 掲載内容・料金・露出設定を「変更する」コードは
  意図的に1行も置いていない。変更はオーナーの承認を挟んで別途行う（README参照）。

ブラウザは Playwright の永続プロファイル（local/profile）で開く。
**パスワードはこのリポジトリのどこにも持たない。** 最初の1回だけ人が
`login.py` で手動ログインし、そのセッション（Cookie）をプロファイルに残す方式。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE_DIR = ROOT / "local" / "profile"
DUMP_DIR = ROOT / "local" / "dump"
REPORT_DIR = ROOT / "reports"

BASE = "https://www.spacemarket.com"
DASHBOARD = "https://dashboard.spacemarket.com"
LOGIN_URL = f"{BASE}/login/"

# 相手のサーバーに負荷をかけない（利用規約 第9条(9)「運営を妨害するおそれのある行為」を避ける）。
# 1ページごとにこの秒数だけ待つ。
POLITE_WAIT_SEC = 3.0

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def facilities() -> list[dict]:
    data = json.loads((ROOT / "facilities.json").read_text(encoding="utf-8"))
    return data["facilities"]


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "playwright が入っていません。\n"
            "  agent-platform/.venv の python で実行してください:\n"
            "  ~/agent-platform/.venv/bin/python spacemarket-monitor/<script>.py\n"
            "  （run.sh を使えば自動で選ばれます）"
        )
    return sync_playwright


def open_context(headless: bool = True):
    """永続プロファイルでブラウザを開く。context を返す（呼び出し側で close する）。

    channel="chrome" ＝ Mac にインストール済みの Google Chrome 本体を使う。
    Chrome が無いPCでは Playwright 同梱の Chromium に落とす。
    """
    sync_playwright = _playwright()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    kwargs = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        user_agent=UA,
        viewport={"width": 1440, "height": 900},
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
    )
    try:
        ctx = pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        ctx = pw.chromium.launch_persistent_context(**kwargs)
    ctx._pw = pw  # close() のときに一緒に止めるため持たせておく
    return ctx


def close_context(ctx) -> None:
    try:
        ctx.close()
    finally:
        pw = getattr(ctx, "_pw", None)
        if pw is not None:
            pw.stop()


def logged_in(ctx) -> bool:
    """ホスト管理画面が開けるか＝ログイン済みかを判定する。

    dashboard.spacemarket.com は未ログインだと 401 を返す（2026-09-01 実測）。
    """
    page = ctx.new_page()
    try:
        resp = page.goto(DASHBOARD + "/", wait_until="domcontentloaded", timeout=60_000)
        status = resp.status if resp else 0
        return status == 200
    except Exception:
        return False
    finally:
        page.close()


def require_login(ctx) -> None:
    if not logged_in(ctx):
        close_context(ctx)
        sys.exit(
            "ホスト管理画面にログインできていません。\n"
            "  先に手動ログインしてください（1回だけ・パスワードは人が入れる）:\n"
            "  ./spacemarket-monitor/run.sh login"
        )


def save_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def jst_today() -> str:
    """JSTの日付。launchd から呼んでも環境変数 TZ に左右されないようにする。"""
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


def jst_now() -> str:
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
