"""KeyLine の Web アプリ本体。

★ Python 3.9 で動かすため、型注釈に `str | None` を使わないこと（`Optional[str]` を使う）。
   FastAPI は起動時に注釈を解決するので、3.10 以降の書き方だとその場で落ちる。

画面は2つ。**アプリは1本**で、URLで役割が分かれる。
    /              管理画面   … 管理者のPCのブラウザ
    /t/<token>     貸出画面   … 鍵管理スマホのSafari（NFCタグから飛んでくる先）
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import (HTMLResponse, JSONResponse, RedirectResponse,
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import auth
import db as dbmod
import ocr
import services as svc
from db import Conflict

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

app = FastAPI(title="KeyLine", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
(APP_DIR / "static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# 画面で使う小道具
templates.env.filters["dt"] = dbmod.fmt_local
templates.env.filters["dt_short"] = lambda ts: dbmod.fmt_local(ts, "%m/%d %H:%M")

STATUS_LABEL = {"in_stock": "保管中", "checked_out": "貸出中",
                "lost": "紛失", "repair": "修理中", "disabled": "無効"}
KIND_LABEL = {"employee": "社員", "vendor": "業者", "customer": "お客様", "other": "その他"}
TYPE_LABEL = {"key": "鍵", "tool": "工具", "card": "カード", "device": "機器", "other": "その他"}
templates.env.globals.update(STATUS_LABEL=STATUS_LABEL, KIND_LABEL=KIND_LABEL,
                             TYPE_LABEL=TYPE_LABEL)


def elapsed_text(minutes: Optional[int]) -> str:
    """経過時間を『3時間12分』の形にする（ご指示13）。"""
    if minutes is None:
        return "-"
    d, h, m = minutes // 1440, (minutes % 1440) // 60, minutes % 60
    if d:
        return f"{d}日{h}時間"
    if h:
        return f"{h}時間{m}分"
    return f"{m}分"


templates.env.filters["elapsed"] = elapsed_text


# ---------------------------------------------------------------------------
# リアルタイム更新（ご指示27）
#
# Supabase Realtime の代わり。単一プロセスで動かすので、変更時に asyncio.Event を
# 立てて、SSEで待っている管理画面に「更新があった」とだけ伝える。
# データ本体は各画面が取り直す。差分を送るより単純で、ずれない。
# ---------------------------------------------------------------------------
class Broadcaster:
    def __init__(self):
        self._waiters = set()

    def notify(self):
        for ev in list(self._waiters):
            ev.set()

    async def stream(self):
        ev = asyncio.Event()
        self._waiters.add(ev)
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                try:
                    await asyncio.wait_for(ev.wait(), timeout=25)
                    yield "event: changed\ndata: {}\n\n"
                except asyncio.TimeoutError:
                    # 25秒ごとに空コメントを送る。無言だとプロキシやSafariに切られる
                    yield ": keepalive\n\n"
                ev.clear()
        finally:
            self._waiters.discard(ev)


bus = Broadcaster()


# ---------------------------------------------------------------------------
# 接続と認証
# ---------------------------------------------------------------------------
def get_con() -> sqlite3.Connection:
    """リクエストごとに接続を開く。SQLiteは接続の使い回しがスレッド跨ぎで危ないため。"""
    return dbmod.connect()


def viewer(request: Request, con: sqlite3.Connection):
    return auth.current_user(con, request.cookies.get(auth.COOKIE_NAME))


def login_redirect(request: Request) -> RedirectResponse:
    nxt = request.url.path
    if request.url.query:
        nxt += "?" + request.url.query
    return RedirectResponse(f"/login?next={nxt}", status_code=303)


def render(request: Request, name: str, user, **ctx) -> HTMLResponse:
    # `now` は画面側で期限超過を判定するのに使う（DB保存形式のUTC文字列のまま比較する）
    return templates.TemplateResponse(
        request, name, {"user": user, "now": dbmod.now_ts(),
                        "flash": request.query_params.get("msg"),
                        "error": request.query_params.get("err"), **ctx})


def back(url: str, msg: Optional[str] = None, err: Optional[str] = None) -> RedirectResponse:
    from urllib.parse import quote
    if msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    if err:
        url += ("&" if "?" in url else "?") + "err=" + quote(err)
    return RedirectResponse(url, status_code=303)


@app.on_event("startup")
def _startup():
    con = dbmod.get_db()
    auth.purge_expired_sessions(con)
    con.close()


# ---------------------------------------------------------------------------
# ログイン
# ---------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/"):
    con = get_con()
    try:
        if viewer(request, con):
            return RedirectResponse(next, status_code=303)
        return render(request, "login.html", None, next=next)
    finally:
        con.close()


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...),
                 next: str = Form("/")):
    con = get_con()
    try:
        token = auth.login(con, email, password, request.headers.get("user-agent"))
        if not token:
            return back(f"/login?next={next}", err="メールアドレスかパスワードが違います")
        resp = RedirectResponse(next or "/", status_code=303)
        resp.set_cookie(
            auth.COOKIE_NAME, token,
            max_age=auth.SESSION_DAYS * 86400,
            httponly=True,      # JSから読めない＝XSSでCookieを盗まれない
            samesite="lax",
            # secure=True は付けない。社内LANの平文HTTPで動かすため、
            # 付けるとCookieが一切送られずログインできなくなる。
            # HTTPS化したらここを True にすること（README参照）。
        )
        return resp
    finally:
        con.close()


@app.post("/logout")
def logout(request: Request):
    con = get_con()
    try:
        auth.logout(con, request.cookies.get(auth.COOKIE_NAME))
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(auth.COOKIE_NAME)
        return resp
    finally:
        con.close()


# ---------------------------------------------------------------------------
# ★ 貸出画面（NFCタグから飛んでくる先）
# ---------------------------------------------------------------------------
@app.get("/t/{token}", response_class=HTMLResponse)
def tag_view(request: Request, token: str):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]

        asset = svc.find_by_token(con, org, token)
        if asset is None:
            # 未登録のNFCタグ（ご指示15）。その場で登録に進める
            return render(request, "tag_unknown.html", user, token=token,
                          boxes=svc.list_boxes(con, org),
                          properties=svc.property_names(con, org))

        if asset["status"] == "checked_out":
            return render(request, "tag_return.html", user, asset=asset,
                          log=svc.open_log(con, asset["id"]), token=token)

        if asset["status"] != "in_stock":
            return render(request, "tag_blocked.html", user, asset=asset, token=token)

        return render(request, "tag_checkout.html", user, asset=asset, token=token,
                      recent=svc.recent_borrowers(con, org),
                      dues=svc.due_choices(), ocr_ok=ocr.is_available())
    finally:
        con.close()


@app.post("/t/{token}/checkout")
def tag_checkout(request: Request, token: str,
                 borrower_id: Optional[str] = Form(None),
                 new_name: Optional[str] = Form(None),
                 new_kind: str = Form("vendor"),
                 new_company: Optional[str] = Form(None),
                 new_phone: Optional[str] = Form(None),
                 due_at: Optional[str] = Form(None),
                 image_path: Optional[str] = Form(None),
                 image_kind: Optional[str] = Form(None),
                 note: Optional[str] = Form(None)):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]

        asset = svc.find_by_token(con, org, token)
        if asset is None:
            return back(f"/t/{token}", err="この鍵は登録されていません")

        try:
            # 一覧から選んでいなければ、入力された名前で新しい貸出先を作る
            if not borrower_id:
                if not (new_name or "").strip():
                    return back(f"/t/{token}", err="貸出先を選ぶか、お名前を入力してください")
                borrower_id = svc.create_borrower(
                    con, org, new_name, new_kind, new_company, new_phone)

            image = (image_path, image_kind) if image_path and image_kind else None
            svc.checkout(con, org, asset["id"], borrower_id,
                         due_at=(due_at or None), image=image, note=note)
        except (Conflict, svc.NotFound, svc.InvalidInput) as e:
            return back(f"/t/{token}", err=str(e))

        bus.notify()
        return back(f"/t/{token}", msg="貸出しました")
    finally:
        con.close()


@app.post("/t/{token}/return")
def tag_return(request: Request, token: str):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]

        asset = svc.find_by_token(con, org, token)
        if asset is None:
            return back(f"/t/{token}", err="この鍵は登録されていません")
        try:
            svc.return_asset(con, org, asset["id"])
        except Conflict as e:
            return back(f"/t/{token}", err=str(e))

        bus.notify()
        return back(f"/t/{token}", msg="返却しました")
    finally:
        con.close()


@app.post("/t/{token}/register")
def tag_register(request: Request, token: str,
                 name: str = Form(...), asset_type: str = Form("key"),
                 property_name: Optional[str] = Form(None),
                 box_id: Optional[str] = Form(None),
                 box_position: Optional[str] = Form(None),
                 item_number: List[str] = Form(default=[]),
                 item_qty: List[str] = Form(default=[]),
                 item_numbers: str = Form(""),
                 note: Optional[str] = Form(None)):
    """未登録タグをその場で管理対象として登録する（ご指示15）。"""
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        try:
            svc.create_asset(con, user["organization_id"], name, asset_type,
                             nfc_token=token, box_id=box_id, box_position=box_position,
                             items=_items(item_number, item_qty, item_numbers),
                             note=note, property_name=property_name)
        except (Conflict, svc.InvalidInput) as e:
            return back(f"/t/{token}", err=str(e))
        bus.notify()
        return back(f"/t/{token}", msg="登録しました")
    finally:
        con.close()


def _items(numbers: List[str], quantities: List[str], raw_text: str = "") -> list:
    """画面から来た鍵番号を `[(番号, 本数), …]` にする。

    入力欄（番号＋本数の行）を優先し、無ければ1行テキストとして読む。
    現場で素早く打ちたいときは『10001, 10003 x3』のような書き方も通る。
    """
    items = svc.parse_items(numbers, quantities)
    if items:
        return items
    return svc.split_item_text(raw_text)


# ---------------------------------------------------------------------------
# OCR（免許証・名刺の撮影）
# ---------------------------------------------------------------------------
@app.post("/api/ocr")
async def api_ocr(request: Request, image: UploadFile = File(...),
                  kind: str = Form("business_card")):
    con = get_con()
    try:
        if not viewer(request, con):
            return JSONResponse({"ok": False, "error": "ログインし直してください"}, 401)

        raw = await image.read()
        if not raw:
            return JSONResponse({"ok": False, "error": "画像を読み取れませんでした"}, 400)
        if len(raw) > 20 * 1024 * 1024:
            return JSONResponse({"ok": False, "error": "画像が大きすぎます"}, 400)

        rel = ocr.save_image(raw, DATA_DIR, dbmod.now_ts())
        try:
            result = ocr.read_document(DATA_DIR / rel, kind)
        except ocr.OcrUnavailable as e:
            # 画像は残す。読み取れなくても「撮った」記録として貸出に添付できる
            return JSONResponse({"ok": False, "error": str(e),
                                 "image_path": rel, "image_kind": kind})
        return JSONResponse({"ok": True, "image_path": rel, "image_kind": kind, **result})
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 管理画面
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        return render(request, "dashboard.html", user,
                      stats=svc.stats(con, org),
                      out=svc.list_assets(con, org, status="checked_out"),
                      recent=svc.history(con, org, limit=15))
    finally:
        con.close()


@app.get("/assets", response_class=HTMLResponse)
def assets_list(request: Request, q: Optional[str] = None, status: Optional[str] = None):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        return render(request, "assets.html", user,
                      assets=svc.list_assets(con, org, status=status, q=q),
                      q=q or "", status=status or "", boxes=svc.list_boxes(con, org))
    finally:
        con.close()


@app.get("/assets/{asset_id}", response_class=HTMLResponse)
def asset_detail(request: Request, asset_id: str):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        try:
            asset = svc.get_asset(con, org, asset_id)
        except svc.NotFound as e:
            return back("/assets", err=str(e))
        return render(request, "asset_detail.html", user, asset=asset,
                      items=svc.list_items(con, asset_id),
                      logs=svc.history(con, org, asset_id=asset_id),
                      boxes=svc.list_boxes(con, org),
                      properties=svc.property_names(con, org),
                      # ★アクセス中のURLではなくLANのIPを使う。localhostで開いている
                      #   管理者が localhost 入りのURLをタグに書く事故を防ぐ（services参照）
                      base_url=svc.lan_base_url())
    finally:
        con.close()


@app.post("/assets/{asset_id}/edit")
def asset_edit(request: Request, asset_id: str,
               name: str = Form(...), asset_type: str = Form("key"),
               property_name: Optional[str] = Form(None),
               box_id: Optional[str] = Form(None),
               box_position: Optional[str] = Form(None),
               item_number: List[str] = Form(default=[]),
               item_qty: List[str] = Form(default=[]),
               item_numbers: str = Form(""), note: Optional[str] = Form(None),
               status: Optional[str] = Form(None)):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back(f"/assets/{asset_id}", err="管理者のみ編集できます")
        try:
            svc.update_asset(con, user["organization_id"], asset_id, name, asset_type,
                             box_id, box_position, _items(item_number, item_qty, item_numbers),
                             note, status, property_name=property_name)
        except (Conflict, svc.NotFound, svc.InvalidInput) as e:
            return back(f"/assets/{asset_id}", err=str(e))
        bus.notify()
        return back(f"/assets/{asset_id}", msg="保存しました")
    finally:
        con.close()


@app.post("/assets/{asset_id}/force-return")
def asset_force_return(request: Request, asset_id: str):
    """管理者による強制返却（ご指示11）。"""
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back(f"/assets/{asset_id}", err="管理者のみ強制返却できます")
        try:
            svc.return_asset(con, user["organization_id"], asset_id, force=True)
        except Conflict as e:
            return back(f"/assets/{asset_id}", err=str(e))
        bus.notify()
        return back(f"/assets/{asset_id}", msg="強制返却しました")
    finally:
        con.close()


@app.get("/assets-new", response_class=HTMLResponse)
def asset_new_form(request: Request):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back("/assets", err="管理者のみ登録できます")
        return render(request, "asset_new.html", user,
                      boxes=svc.list_boxes(con, user["organization_id"]),
                      properties=svc.property_names(con, user["organization_id"]))
    finally:
        con.close()


@app.post("/assets-new")
def asset_new(request: Request, name: str = Form(...), asset_type: str = Form("key"),
              property_name: Optional[str] = Form(None),
              box_id: Optional[str] = Form(None), box_position: Optional[str] = Form(None),
              item_number: List[str] = Form(default=[]),
              item_qty: List[str] = Form(default=[]),
              item_numbers: str = Form(""), note: Optional[str] = Form(None),
              issue_tag: Optional[str] = Form(None)):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back("/assets", err="管理者のみ登録できます")
        try:
            token = svc.issue_nfc_token(con) if issue_tag else None
            aid = svc.create_asset(con, user["organization_id"], name, asset_type,
                                   nfc_token=token, box_id=box_id, box_position=box_position,
                                   items=_items(item_number, item_qty, item_numbers),
                                   note=note, property_name=property_name)
        except (Conflict, svc.InvalidInput) as e:
            return back("/assets-new", err=str(e))
        bus.notify()
        return back(f"/assets/{aid}", msg="登録しました")
    finally:
        con.close()


@app.post("/assets/{asset_id}/issue-tag")
def asset_issue_tag(request: Request, asset_id: str):
    """この管理対象に新しいNFCトークンを発行する（タグの新規貼付・交換）。"""
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back(f"/assets/{asset_id}", err="管理者のみ操作できます")
        try:
            svc.attach_tag(con, user["organization_id"], asset_id, svc.issue_nfc_token(con))
        except (Conflict, svc.NotFound) as e:
            return back(f"/assets/{asset_id}", err=str(e))
        bus.notify()
        return back(f"/assets/{asset_id}", msg="新しいNFCタグのURLを発行しました")
    finally:
        con.close()


@app.get("/boxes", response_class=HTMLResponse)
def boxes_page(request: Request):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        rows = con.execute(
            """SELECT b.*, (SELECT COUNT(*) FROM assets WHERE box_id = b.id) AS asset_count
                 FROM boxes b WHERE b.organization_id = ? ORDER BY b.code""", (org,)).fetchall()
        return render(request, "boxes.html", user, boxes=rows)
    finally:
        con.close()


@app.post("/boxes")
def box_create(request: Request, code: str = Form(...), name: str = Form(...),
               location: Optional[str] = Form(None)):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back("/boxes", err="管理者のみ登録できます")
        try:
            svc.create_box(con, user["organization_id"], code, name, location)
        except (Conflict, svc.InvalidInput) as e:
            return back("/boxes", err=str(e))
        return back("/boxes", msg="登録しました")
    finally:
        con.close()


@app.get("/borrowers", response_class=HTMLResponse)
def borrowers_page(request: Request, q: Optional[str] = None):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        rows = (svc.search_borrowers(con, org, q, 200) if q
                else svc.recent_borrowers(con, org, 200))
        return render(request, "borrowers.html", user, borrowers=rows, q=q or "")
    finally:
        con.close()


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, borrower_id: Optional[str] = None):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        return render(request, "history.html", user,
                      logs=svc.history(con, org, borrower_id=borrower_id, limit=300),
                      borrower=(svc.get_borrower(con, org, borrower_id)
                                if borrower_id else None))
    finally:
        con.close()


@app.get("/events")
async def events(request: Request):
    """管理画面のリアルタイム更新（ご指示27）。"""
    return StreamingResponse(bus.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# 想定外のエラーは技術的な中身を見せない（ご指示26）
# ---------------------------------------------------------------------------
@app.exception_handler(500)
def on_error(request: Request, exc):
    return HTMLResponse(
        "<h1>エラーが発生しました</h1><p>もう一度お試しください。"
        "繰り返す場合は管理者にご連絡ください。</p>", status_code=500)
