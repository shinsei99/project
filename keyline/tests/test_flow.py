"""Phase 2〜5 のテスト — 実際に起動したサーバーへHTTPで通しで叩く。

test_schema.py が「DBが壊れたデータを拒むか」を見るのに対し、
こちらは「画面から操作したとき、ご指示どおりの流れになるか」を見る。

使い方:
    ターミナル1)  cd ~/keyline && ./run.sh
    ターミナル2)  cd ~/keyline && /usr/bin/python3 tests/test_flow.py

★このテストは**専用の一時DBを作って**動く。本番のDBには触らない。
  そのため run.sh とは別に、テスト用サーバーを自分で起動する。
"""

from __future__ import annotations

import http.cookiejar
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"  … {detail}" if detail and not cond else ""))


class Client:
    """Cookieを保持するだけの薄いHTTPクライアント。"""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            NoRedirect(),
        )

    def get(self, path: str):
        return self._do(urllib.request.Request(self.base + path))

    def post(self, path: str, data: dict = None):
        body = urllib.parse.urlencode(data or {}, doseq=True).encode()
        return self._do(urllib.request.Request(self.base + path, data=body, method="POST"))

    def _do(self, req):
        try:
            r = self.op.open(req, timeout=30)
            return r.status, r.headers.get("Location", ""), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location", ""), e.read().decode("utf-8", "replace")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """303 を追わずに Location をそのまま見たい（成否がクエリに載るため）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def msg_of(location: str) -> str:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    return urllib.parse.unquote(q.get("msg", q.get("err", [""]))[0])


def main() -> int:
    import auth
    import db as dbmod
    import services as svc
    import seed

    tmp = Path(tempfile.mkdtemp(prefix="keyline-test-"))
    db_path = tmp / "test.db"
    port = free_port()
    base = f"http://127.0.0.1:{port}"

    # --- 下ごしらえ（テスト専用DB） ---
    os.environ["KEYLINE_DB"] = str(db_path)
    con = dbmod.get_db(db_path)
    oid = seed.ensure_org(con, "テスト社")
    auth.create_user(con, oid, "a@test.local", "password-admin", "管理者", "admin")
    auth.create_user(con, oid, "t@test.local", "password-term", "鍵管理端末", "operator")
    box = svc.create_box(con, oid, "BOX-01", "本社1F鍵ボックス")
    tok = svc.issue_nfc_token(con)
    aid = svc.create_asset(con, oid, "1階エントランスキー", "key", nfc_token=tok, box_id=box,
                           box_position="03", property_name="大阪京橋ビル",
                           items=[("12345", 1), ("12346", 1), ("10003", 3)])
    bid = svc.create_borrower(con, oid, "山田 太郎", "employee")
    con.close()

    # --- サーバー起動 ---
    env = {**os.environ,
           "KEYLINE_DB": str(db_path),
           "KEYLINE_BASE_URL": base,
           "PYTHONPATH": f"{Path.home()}/Library/Python/3.9/lib/python/site-packages"}
    proc = subprocess.Popen(
        ["/usr/bin/python3", "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "error"],
        cwd=str(APP_DIR), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/login", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            err = proc.stderr.read().decode()[-800:] if proc.stderr else ""
            print("サーバーが起動しませんでした:\n" + err)
            return 1

        run(base, tok, aid, bid)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'='*56}\n  成功 {len(PASS)} / 失敗 {len(FAIL)}")
    if FAIL:
        print("  失敗:", ", ".join(FAIL))
    print("=" * 56)
    return 1 if FAIL else 0


def run(base: str, tok: str, aid: str, bid: str) -> None:
    term = Client(base)
    admin = Client(base)
    anon = Client(base)

    print("\n── 認証（ご指示17・29）")
    code, loc, _ = anon.get(f"/t/{tok}")
    check("未ログインは貸出画面を開けない", code == 303 and "/login" in loc, f"{code} {loc}")
    code, loc, _ = term.post("/login", {"email": "t@test.local", "password": "まちがい"})
    check("パスワードが違えば拒否", "err=" in loc, loc)
    code, loc, _ = term.post("/login", {"email": "t@test.local",
                                        "password": "password-term", "next": "/"})
    check("正しければログインできる", code == 303 and "err=" not in loc, loc)
    check("セッションCookieが発行される",
          any(c.name == "keyline_session" for c in term.jar))
    admin.post("/login", {"email": "a@test.local", "password": "password-admin", "next": "/"})

    print("\n── NFCをかざす（ご指示9・15）")
    _, _, html = term.get(f"/t/{tok}")
    check("保管中なら貸出画面が出る", "保管中" in html and "貸出する" in html)
    check("鍵番号が本数つきでまとめて出る", "12345 / 12346 / 10003 ×3" in html, html.count("12345"))
    check("戻す場所が出る", "BOX-01" in html and "03" in html)
    _, _, html = term.get("/t/notregistered999")
    check("未登録タグはその場で登録できる", "未登録のNFCタグ" in html)

    print("\n── 貸出（ご指示9）")
    _, loc, _ = term.post(f"/t/{tok}/checkout", {"borrower_id": bid, "due_at": ""})
    check("貸出できる", msg_of(loc) == "貸出しました", loc)
    _, _, html = term.get(f"/t/{tok}")
    check("かざすと返却画面に変わる", "返却する" in html)
    check("現在の利用者が出る（ご指示10）", "山田 太郎" in html and "現在の利用者" in html)

    print("\n── 二重貸出（ご指示23・28）")
    _, loc, _ = term.post(f"/t/{tok}/checkout", {"borrower_id": bid})
    check("貸出中は再度貸出できない", "すでに貸出中" in msg_of(loc), msg_of(loc))

    print("\n── 返却（ご指示10）")
    _, loc, _ = term.post(f"/t/{tok}/return")
    check("返却できる", msg_of(loc) == "返却しました", loc)
    _, loc, _ = term.post(f"/t/{tok}/return")
    check("保管中のものは返却できない", "貸出中ではありません" in msg_of(loc), msg_of(loc))

    print("\n── 社外への貸出（今回の要件の中心）")
    _, loc, _ = term.post(f"/t/{tok}/checkout", {
        "new_name": "田中 一郎", "new_kind": "vendor",
        "new_company": "〇〇工務店", "new_phone": "090-1234-5678"})
    check("はじめての相手にその場で貸せる", msg_of(loc) == "貸出しました", loc)
    _, _, html = term.get(f"/t/{tok}")
    check("会社名も画面に出る", "〇〇工務店" in html)
    check("電話番号が出る（連絡できる）", "090-1234-5678" in html)
    _, loc, _ = term.post(f"/t/{tok}/checkout", {"new_name": "  "})
    check("貸出先が空なら拒否", "err=" in loc, loc)

    print("\n── 権限（ご指示17）")
    _, loc, _ = term.post(f"/assets/{aid}/force-return")
    check("鍵管理端末は強制返却できない", "管理者のみ" in msg_of(loc), msg_of(loc))
    _, loc, _ = term.post("/assets-new", {"name": "勝手に登録"})
    check("鍵管理端末は管理対象を登録できない", "管理者のみ" in msg_of(loc), msg_of(loc))
    _, loc, _ = admin.post(f"/assets/{aid}/force-return")
    check("管理者は強制返却できる（ご指示11）", msg_of(loc) == "強制返却しました", loc)

    print("\n── 管理画面（ご指示13・14）")
    _, _, html = admin.get("/")
    check("ダッシュボードが開く", "ダッシュボード" in html)
    _, _, html = admin.get("/assets")
    check("管理対象一覧に鍵番号が出る", "12345 / 12346 / 10003 ×3" in html)
    _, _, html = admin.get("/assets?q=12346")
    check("鍵番号で検索できる", "1階エントランスキー" in html)
    _, _, html = admin.get("/assets?q=" + urllib.parse.quote("大阪京橋ビル"))
    check("物件名称で検索できる", "1階エントランスキー" in html)
    _, _, html = admin.get(f"/assets/{aid}")
    check("詳細にタグURLが出る", f"{base}/t/{tok}" in html, "URLが違う")
    check("履歴が出る（ご指示12）", "貸出履歴" in html and "田中 一郎" in html)
    check("強制返却が区別されて残る", "強制返却" in html)
    _, _, html = admin.get("/history")
    check("履歴画面が開く", "貸出履歴" in html)
    _, _, html = admin.get("/borrowers")
    check("貸出先一覧に社外業者が出る", "〇〇工務店" in html)

    print("\n── 登録（ご指示15）")
    _, loc, _ = term.post("/t/freshtag12345678/register",
                          {"name": "テスト201号室", "property_name": "サンプル物件",
                           "item_number": ["A-1", "A-2"], "item_qty": ["1", "1"],
                           "asset_type": "key"})
    check("未登録タグから登録できる", msg_of(loc) == "登録しました", loc)
    _, _, html = term.get("/t/freshtag12345678")
    check("登録したタグで貸出画面が開く", "テスト201号室" in html and "A-1 / A-2" in html)
    check("登録した物件名称が出る", "サンプル物件" in html)

    print("\n── タグ交換（ご指示5）")
    _, loc, _ = admin.post(f"/assets/{aid}/issue-tag")
    check("新しいタグURLを発行できる", "発行しました" in msg_of(loc), msg_of(loc))
    _, _, html = admin.get(f"/assets/{aid}")
    check("交換後も履歴が残る", "田中 一郎" in html)
    check("交換後も鍵番号が残る", "12345" in html)
    check("交換後も物件名称が残る", "大阪京橋ビル" in html)
    # 交換すると古いトークンはどの管理対象にも紐づかなくなる＝拾われても中身が見えない
    _, _, html = term.get(f"/t/{tok}")
    check("交換した古いタグは未登録扱いになる", "未登録のNFCタグ" in html)


if __name__ == "__main__":
    sys.exit(main())
