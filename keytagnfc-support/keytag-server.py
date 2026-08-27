#!/usr/bin/env python3
"""KeyTag サーバー連携の**参照実装**（1ファイル・追加インストール不要）。

KeyTag（iOSアプリ）は、鍵の台帳を **端末の中だけ**で持つのが既定です。
そのうえで「複数人で同じ台帳を見たい」会社のために、**自分のサーバー**へ
繋げるようになっています。接続先はアプリの設定画面で入力する方式なので、
**この仕様どおりのサーバーを立てれば、誰でも自分の環境で使えます。**

このファイルは、その仕様を実際に動くコードで示したものです。

    python3 keytag-server.py            # http://0.0.0.0:8765 で起動
    python3 keytag-server.py --port 9000 --db /tmp/keytag.sqlite3

起動すると**ペアリングコード（6桁）**を表示します。アプリの
「設定 > サーバー連携」に、このサーバーのURLと6桁コードを入れれば繋がります。

- **標準ライブラリだけ**で動きます（`http.server` と `sqlite3`）。pip 不要
- 保存先は SQLite ファイル1つ。消したければファイルを消すだけ
- **これは参照実装です。** 認証は最小限（Bearer トークン1本）なので、
  社内LANや VPN の内側で動かしてください。インターネットに直接出す場合は
  HTTPS と、組織に合わせた認証（SSO 等）を足してください

仕様の全文は同じフォルダの `API.md` にあります。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import sqlite3
import string
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

JST = timezone(timedelta(hours=9))
LOCK = threading.Lock()

# 貸出先の種別。アプリの「貸出先を追加」で選ぶ値と対応する
KINDS = {"vendor": "業者", "customer": "お客様", "employee": "社員", "other": "その他"}


# ── データベース ──────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS device (
  token TEXT PRIMARY KEY,          -- アプリに渡す Bearer トークン
  user  TEXT NOT NULL,             -- 誰の端末か（画面に出すだけ）
  paired_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS asset (
  token TEXT PRIMARY KEY,          -- タグURL（/t/<token>）に入る鍵の識別子
  property_name TEXT DEFAULT '',
  name TEXT NOT NULL,
  box_position TEXT DEFAULT '',
  item_numbers TEXT DEFAULT '',    -- "10001 / 10003 ×3" のような表示用文字列
  total_keys INTEGER DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'in_stock',   -- in_stock / checked_out
  borrower_id TEXT DEFAULT '',
  checked_out_at TEXT DEFAULT '',
  due_at TEXT DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS borrower (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  company TEXT DEFAULT '',
  kind TEXT DEFAULT 'other',
  phone TEXT DEFAULT '',
  last_used TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_token TEXT NOT NULL,
  borrower_id TEXT NOT NULL,
  checked_out_at TEXT NOT NULL,
  returned_at TEXT DEFAULT '',
  due_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS pairing (
  code TEXT PRIMARY KEY,
  user TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def fmt_dt(iso: str) -> str:
    """アプリの表示に合わせた "YYYY/MM/DD HH:MM"。空なら空のまま。"""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return d.strftime("%Y/%m/%d %H:%M")


def elapsed_text(iso: str) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if d.tzinfo is None:
        d = d.replace(tzinfo=JST)
    m = max(0, int((datetime.now(JST) - d).total_seconds() // 60))
    days, hours, mins = m // 1440, (m % 1440) // 60, m % 60
    if days:
        return "{}日{}時間".format(days, hours)
    if hours:
        return "{}時間{}分".format(hours, mins)
    return "{}分".format(mins)


def is_overdue(row) -> bool:
    if row["status"] != "checked_out" or not row["due_at"]:
        return False
    try:
        due = datetime.fromisoformat(row["due_at"])
    except ValueError:
        return False
    if due.tzinfo is None:
        due = due.replace(tzinfo=JST)
    return due < datetime.now(JST)


# ── アプリへ返す形 ────────────────────────────────────────────────────────

def asset_json(conn, row) -> dict:
    """アプリの画面がそのまま使える形。**キー名はアプリ側と一対一**。"""
    b = None
    if row["status"] == "checked_out" and row["borrower_id"]:
        br = conn.execute("SELECT * FROM borrower WHERE id=?", (row["borrower_id"],)).fetchone()
        if br:
            b = {"name": br["name"], "company": br["company"],
                 "kind": KINDS.get(br["kind"], br["kind"]), "phone": br["phone"]}
    label = (row["property_name"] + " / " if row["property_name"] else "") + row["name"]
    return {
        "property_name": row["property_name"],
        "name": row["name"],
        "label": label,
        "item_numbers": row["item_numbers"],
        "total_keys": row["total_keys"],
        "box": row["box_position"],
        "box_name": "",
        "status": row["status"],
        "status_label": "貸出中" if row["status"] == "checked_out" else "保管中",
        "borrower": b,
        "checked_out_at": fmt_dt(row["checked_out_at"]),
        "due_at": fmt_dt(row["due_at"]),
        "elapsed": elapsed_text(row["checked_out_at"]),
        "is_overdue": is_overdue(row),
    }


def borrowers_json(conn) -> list:
    """貸出先の候補。**よく使う人・いま借りている人が上**に来るように並べる。"""
    rows = conn.execute("SELECT * FROM borrower ORDER BY last_used DESC").fetchall()
    out = []
    for r in rows:
        n = conn.execute(
            "SELECT COUNT(*) c FROM asset WHERE status='checked_out' AND borrower_id=?",
            (r["id"],)).fetchone()["c"]
        out.append({"id": r["id"], "name": r["name"], "company": r["company"],
                    "kind": KINDS.get(r["kind"], r["kind"]), "open_count": n})
    return out


def dues_json() -> list:
    """返却予定の選択肢。**サーバー側で作る**ので、会社の運用に合わせて変えられる。"""
    now = datetime.now(JST)
    at18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
    out = []
    if at18 > now:
        out.append({"label": "今日 18:00", "value": at18.isoformat(timespec="seconds")})
    out.append({"label": "明日 18:00",
                "value": (at18 + timedelta(days=1)).isoformat(timespec="seconds")})
    out.append({"label": "2時間後",
                "value": (now + timedelta(hours=2)).isoformat(timespec="seconds")})
    out.append({"label": "3日後",
                "value": (now + timedelta(days=3)).isoformat(timespec="seconds")})
    out.append({"label": "指定しない", "value": ""})
    return out


# ── HTTP ─────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "KeyTagRefServer/1.0"

    # --- 小道具 ---------------------------------------------------------
    def _send(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # アプリは WKWebView（capacitor:// 由来）から叩くので CORS を許可する
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text, status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _auth(self):
        """Bearer トークンを検証する。通らなければ None を返して 401 を送る。"""
        h = self.headers.get("Authorization") or ""
        token = h[7:].strip() if h.lower().startswith("bearer ") else ""
        if not token:
            self._send({"ok": False, "error": "認証が必要です"}, 401)
            return None
        row = self.server.conn.execute(
            "SELECT * FROM device WHERE token=?", (token,)).fetchone()
        if row is None:
            self._send({"ok": False, "error": "連携が切れています。もう一度ペアリングしてください"}, 401)
            return None
        return row

    def log_message(self, fmt, *args):       # 既定の標準エラー出力を静かにする
        print("  {} {}".format(self.command, self.path))

    # --- ルーティング ---------------------------------------------------
    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/ping":
            dev = self._auth()
            if dev is None:
                return
            return self._send({"ok": True, "organization": self.server.org, "user": dev["user"]})
        if u.path == "/api/asset":
            dev = self._auth()
            if dev is None:
                return
            token = (parse_qs(u.query).get("token") or [""])[0]
            return self._asset(token)
        if u.path.startswith("/t/"):
            return self._landing(u.path[3:])
        if u.path in ("/", "/index.html"):
            return self._landing(None)
        self._send({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/pair":
            return self._pair(self._body())
        dev = self._auth()
        if dev is None:
            return
        if u.path == "/api/register":
            return self._register(self._body())
        if u.path == "/api/checkout":
            return self._checkout(self._body(), dev)
        if u.path == "/api/return":
            return self._return(self._body())
        self._send({"ok": False, "error": "not found"}, 404)

    # --- 各エンドポイント -----------------------------------------------
    def _pair(self, body):
        """6桁コード → Bearer トークン。**コードは1回使ったら消える。**"""
        code = str(body.get("code") or "").strip()
        conn = self.server.conn
        with LOCK:
            row = conn.execute("SELECT * FROM pairing WHERE code=?", (code,)).fetchone()
            if row is None:
                return self._send({"ok": False, "error": "コードが違います"})
            if row["expires_at"] < now_iso():
                conn.execute("DELETE FROM pairing WHERE code=?", (code,))
                conn.commit()
                return self._send({"ok": False, "error": "コードの有効期限が切れています"})
            token = secrets.token_hex(32)
            conn.execute("INSERT INTO device(token,user,paired_at) VALUES(?,?,?)",
                         (token, row["user"], now_iso()))
            conn.execute("DELETE FROM pairing WHERE code=?", (code,))
            conn.commit()
        print("  → 端末を1台つなぎました（{}）".format(row["user"]))
        return self._send({"ok": True, "token": token, "organization": self.server.org})

    def _register(self, body):
        """アプリの「タグに書き込む」の直前に呼ばれる。**鍵を1件作ってURLを返す。**

        返した URL がそのまま NFC タグに書き込まれる。以後、そのタグをかざすと
        `/api/asset?token=…` でこの鍵が引ける。
        """
        name = str(body.get("name") or "").strip()
        if not name:
            return self._send({"ok": False, "error": "鍵の名称がありません"})
        nums = body.get("item_number") or []
        qtys = body.get("item_qty") or []
        parts, total = [], 0
        for i, num in enumerate(nums):
            q = int(str(qtys[i]).strip() or 1) if i < len(qtys) else 1
            parts.append("{} ×{}".format(num, q) if q > 1 else str(num))
            total += q
        token = secrets.token_hex(8)
        self.server.conn.execute(
            "INSERT INTO asset(token,property_name,name,box_position,item_numbers,"
            "total_keys,status,created_at) VALUES(?,?,?,?,?,?, 'in_stock', ?)",
            (token, str(body.get("property_name") or ""), name,
             str(body.get("box_position") or ""), " / ".join(parts), max(1, total), now_iso()))
        self.server.conn.commit()
        url = "{}/t/{}".format(self.server.base_url, token)
        print("  → 鍵を登録しました: {} （{}）".format(name, url))
        return self._send({"ok": True, "url": url, "token": token})

    def _asset(self, token):
        row = self.server.conn.execute("SELECT * FROM asset WHERE token=?", (token,)).fetchone()
        if row is None:
            return self._send({"ok": True, "found": False})
        return self._send({"ok": True, "found": True,
                           "asset": asset_json(self.server.conn, row),
                           "borrowers": borrowers_json(self.server.conn),
                           "dues": dues_json()})

    def _checkout(self, body, dev):
        """貸出。**二重貸出はここで止める**（2台で同時に押しても壊れないように）。"""
        conn = self.server.conn
        token = str(body.get("token") or "")
        with LOCK:
            row = conn.execute("SELECT * FROM asset WHERE token=?", (token,)).fetchone()
            if row is None:
                return self._send({"ok": False, "error": "この鍵はサーバーにありません"})
            if row["status"] == "checked_out":
                return self._send({"ok": False, "error": "この鍵はすでに貸出中です"})

            bid = str(body.get("borrower_id") or "").strip()
            if not bid:
                nm = str(body.get("new_name") or "").strip()
                if not nm:
                    return self._send({"ok": False, "error": "貸出先がありません"})
                bid = "B" + secrets.token_hex(4)
                conn.execute(
                    "INSERT INTO borrower(id,name,company,kind,phone,last_used) VALUES(?,?,?,?,?,?)",
                    (bid, nm, str(body.get("new_company") or ""),
                     str(body.get("new_kind") or "other"), str(body.get("new_phone") or ""),
                     now_iso()))
            else:
                if conn.execute("SELECT 1 FROM borrower WHERE id=?", (bid,)).fetchone() is None:
                    return self._send({"ok": False, "error": "貸出先が見つかりません"})
                conn.execute("UPDATE borrower SET last_used=? WHERE id=?", (now_iso(), bid))

            at = now_iso()
            conn.execute(
                "UPDATE asset SET status='checked_out', borrower_id=?, checked_out_at=?, due_at=?"
                " WHERE token=?", (bid, at, str(body.get("due_at") or ""), token))
            conn.execute(
                "INSERT INTO history(asset_token,borrower_id,checked_out_at,due_at)"
                " VALUES(?,?,?,?)", (token, bid, at, str(body.get("due_at") or "")))
            conn.commit()
            row = conn.execute("SELECT * FROM asset WHERE token=?", (token,)).fetchone()
        print("  → 貸出: {}（{}）".format(row["name"], dev["user"]))
        return self._send({"ok": True, "asset": asset_json(conn, row)})

    def _return(self, body):
        conn = self.server.conn
        token = str(body.get("token") or "")
        with LOCK:
            row = conn.execute("SELECT * FROM asset WHERE token=?", (token,)).fetchone()
            if row is None:
                return self._send({"ok": False, "error": "この鍵はサーバーにありません"})
            if row["status"] != "checked_out":
                return self._send({"ok": False, "error": "この鍵は貸出中ではありません"})
            conn.execute(
                "UPDATE history SET returned_at=? WHERE asset_token=? AND returned_at=''",
                (now_iso(), token))
            conn.execute(
                "UPDATE asset SET status='in_stock', borrower_id='', checked_out_at='', due_at=''"
                " WHERE token=?", (token,))
            conn.commit()
            row = conn.execute("SELECT * FROM asset WHERE token=?", (token,)).fetchone()
        print("  → 返却: {}".format(row["name"]))
        return self._send({"ok": True, "asset": asset_json(conn, row)})

    def _landing(self, token):
        """タグURL（/t/<token>）を**ブラウザで開いたとき**に見えるページ。

        アプリを入れていない人がタグをかざしても、鍵の状態が読めるようにしておく。
        `None` のときは台帳の一覧（サーバー側で見る画面）。
        """
        conn = self.server.conn
        esc = lambda s: (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
                         .replace(">", "&gt;"))
        head = ("<!doctype html><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>KeyTag</title><style>"
                "body{font-family:-apple-system,system-ui,sans-serif;margin:0;padding:1.2rem;"
                "background:#f6f7f9;color:#1c1c1e}h1{font-size:1.1rem;margin:0 0 1rem}"
                "table{border-collapse:collapse;width:100%;background:#fff;border-radius:.6rem;"
                "overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}"
                "th,td{padding:.55rem .7rem;text-align:left;font-size:.9rem;"
                "border-bottom:1px solid #eee}th{background:#fafafa;font-weight:600}"
                ".out{color:#b3261e;font-weight:600}.in{color:#1b6b3a}"
                ".card{background:#fff;border-radius:.6rem;padding:1rem;"
                "box-shadow:0 1px 3px rgba(0,0,0,.08)}</style>")
        if token:
            row = conn.execute("SELECT * FROM asset WHERE token=?", (token,)).fetchone()
            if row is None:
                return self._html(head + "<h1>この鍵は登録されていません</h1>", 404)
            a = asset_json(conn, row)
            b = a["borrower"] or {}
            body = (head + "<h1>" + esc(a["label"]) + "</h1><div class='card'>"
                    + "<p class='" + ("out" if a["status"] == "checked_out" else "in") + "'>"
                    + esc(a["status_label"]) + ("（返却期限超過）" if a["is_overdue"] else "") + "</p>"
                    + "<p>鍵番号: " + esc(a["item_numbers"]) + "</p>"
                    + "<p>保管場所: " + esc(a["box"]) + "</p>")
            if a["status"] == "checked_out":
                body += ("<p>貸出先: " + esc(b.get("name")) + " " + esc(b.get("company")) + "</p>"
                         "<p>貸出日時: " + esc(a["checked_out_at"])
                         + "（" + esc(a["elapsed"]) + "経過）</p>"
                         "<p>返却予定: " + esc(a["due_at"] or "指定なし") + "</p>")
            return self._html(body + "</div>")

        rows = conn.execute(
            "SELECT * FROM asset ORDER BY status DESC, created_at").fetchall()
        body = head + "<h1>KeyTag 台帳（参照実装）</h1><table>" \
            "<tr><th>物件</th><th>鍵</th><th>鍵番号</th><th>状態</th><th>貸出先</th><th>返却予定</th></tr>"
        for r in rows:
            a = asset_json(conn, r)
            b = a["borrower"] or {}
            body += ("<tr><td>" + esc(a["property_name"]) + "</td><td>" + esc(a["name"])
                     + "</td><td>" + esc(a["item_numbers"]) + "</td><td class='"
                     + ("out" if a["status"] == "checked_out" else "in") + "'>"
                     + esc(a["status_label"]) + "</td><td>" + esc(b.get("name"))
                     + "</td><td>" + esc(a["due_at"]) + "</td></tr>")
        if not rows:
            body += "<tr><td colspan='6'>まだ鍵が登録されていません。</td></tr>"
        return self._html(body + "</table>")


def new_code(conn, user: str, minutes: int = 30) -> str:
    code = "".join(random.choice(string.digits) for _ in range(6))
    conn.execute("INSERT OR REPLACE INTO pairing(code,user,expires_at) VALUES(?,?,?)",
                 (code, user, (datetime.now(JST) + timedelta(minutes=minutes))
                  .isoformat(timespec="seconds")))
    conn.commit()
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="KeyTag サーバー連携の参照実装")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--db", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "keytag.sqlite3"))
    ap.add_argument("--org", default="サンプル商事", help="アプリに表示される組織名")
    ap.add_argument("--user", default="デモ端末", help="ペアリングする端末の名前")
    ap.add_argument("--base-url", default="", help="タグに書くURLの前半（既定は http://<自分のIP>:<port>）")
    args = ap.parse_args()

    conn = connect(args.db)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.conn = conn
    server.org = args.org
    base = args.base_url.rstrip("/")
    if not base:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except OSError:
            ip = "127.0.0.1"
        base = "http://{}:{}".format(ip, args.port)
    server.base_url = base

    code = new_code(conn, args.user)
    print("─" * 62)
    print(" KeyTag サーバー連携 参照実装")
    print("─" * 62)
    print(" サーバーURL     : {}".format(base))
    print(" ペアリングコード : {}   （30分で失効）".format(code))
    print(" 台帳を見る       : {}/".format(base))
    print(" データベース     : {}".format(args.db))
    print("─" * 62)
    print(" アプリの「設定 > サーバー連携」に、上のURLと6桁コードを入れてください。")
    print(" 止めるときは Ctrl+C。")
    print("─" * 62, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終わります。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
