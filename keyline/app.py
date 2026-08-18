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
import ndef
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
    """ログイン中の利用者。ブラウザはCookie、ネイティブアプリは Bearer トークン。"""
    token = (auth.bearer_token(request.headers.get("authorization"))
             or request.cookies.get(auth.COOKIE_NAME))
    return auth.current_user(con, token)


# ---------------------------------------------------------------------------
# CORS（/api/ だけ）
#
# ネイティブアプリのオリジンは capacitor://localhost で、ここから見ると別オリジン。
# Cookieは使わず Bearer トークンで認証するので credentials は許可しない
# （許可すると、悪意あるページがブラウザのCookieを使ってAPIを叩けてしまう）。
# ---------------------------------------------------------------------------
APP_ORIGINS = {"capacitor://localhost", "ionic://localhost", "http://localhost"}


@app.middleware("http")
async def cors_for_api(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    origin = request.headers.get("origin", "")
    allow = origin if origin in APP_ORIGINS else ""
    if request.method == "OPTIONS":
        resp = HTMLResponse("", status_code=204)
    else:
        resp = await call_next(request)
    if allow:
        resp.headers["Access-Control-Allow-Origin"] = allow
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Vary"] = "Origin"
    return resp


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
        # タグに何が書けるか（NTAG213は144バイトしかないので、登録時点で見せる）
        tagplan = None
        if asset["nfc_identifier"]:
            tagplan = ndef.plan(
                svc.tag_url(svc.lan_base_url(), asset["nfc_identifier"]),
                asset["property_name"], asset["name"], asset["item_numbers"],
                asset["box_code"], asset["box_position"])
        return render(request, "asset_detail.html", user, asset=asset, tagplan=tagplan,
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


# ---------------------------------------------------------------------------
# 連続登録（箱の前でスマホから、鍵を持ちながら次々に登録する）
#
# ★60本を一度に登録するための画面。物件名とボックスは固定したまま、
#   鍵ごとに違うところだけ打つ。位置は自動で繰り上がる。
#   将来ネイティブアプリが「かざす」を足すときも、登録APIはこれをそのまま使う。
# ---------------------------------------------------------------------------
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        org = user["organization_id"]
        return render(request, "register.html", user,
                      boxes=svc.list_boxes(con, org),
                      properties=svc.property_names(con, org))
    finally:
        con.close()


@app.post("/api/register")
async def api_register(request: Request):
    """鍵を1件登録して、タグに書く内容まで返す。

    画面もアプリもこのAPIを叩く。返り値の `ndef` をそのままタグに書けばよい。
    """
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return JSONResponse({"ok": False, "error": "ログインし直してください"}, 401)
        org = user["organization_id"]
        d = await request.json()

        try:
            token = svc.issue_nfc_token(con)
            aid = svc.create_asset(
                con, org,
                name=(d.get("name") or "").strip(),
                asset_type=d.get("asset_type") or "key",
                nfc_token=token,
                box_id=d.get("box_id") or None,
                box_position=(d.get("box_position") or "").strip() or None,
                items=svc.parse_items(d.get("item_number") or [], d.get("item_qty") or []),
                note=d.get("note"),
                property_name=d.get("property_name"))
        except (Conflict, svc.InvalidInput) as e:
            return JSONResponse({"ok": False, "error": str(e)}, 400)

        asset = svc.get_asset(con, org, aid)
        url = svc.tag_url(svc.lan_base_url(), token)
        plan = ndef.plan(url, asset["property_name"], asset["name"], asset["item_numbers"],
                         asset["box_code"], asset["box_position"])
        bus.notify()
        return JSONResponse({
            "ok": True, "asset_id": aid, "token": token, "url": url,
            "label": (asset["property_name"] + " / " if asset["property_name"] else "") + asset["name"],
            "item_numbers": asset["item_numbers"] or "", "total_keys": asset["total_keys"],
            "box": svc.box_label(asset["box_code"], asset["box_position"]),
            "next_position": svc.next_position(asset["box_position"]),
            "ndef": {"text": plan["text"], "bytes": plan["bytes"],
                     "capacity": plan["capacity"], "truncated": plan["truncated"],
                     "tag": plan["tag"]},
        })
    finally:
        con.close()


# ---------------------------------------------------------------------------
# アプリの連携（ペアリング）
#
# 64文字のトークンをスマホで手打ちさせるのは現実的でないので、
# 管理画面が6桁のコードを出し、アプリはそれを送ってトークンを受け取る。
#
# コードはプロセス内にだけ持つ（10分で失効・使い切り）。
# 再起動で消えるが、10分の一時コードなので作り直せばよく、テーブルを増やす価値がない。
# ---------------------------------------------------------------------------
_PAIR_CODES = {}          # code -> {"user_id", "expires", "label"}
PAIR_TTL_SECONDS = 600


def _pair_gc():
    now = dbmod.now_ts()
    for c in [c for c, v in _PAIR_CODES.items() if v["expires"] <= now]:
        _PAIR_CODES.pop(c, None)


@app.post("/devices/pair")
def device_pair_create(request: Request, label: str = Form("iPhone")):
    """管理画面から6桁コードを発行する。"""
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        if user["role"] != "admin":
            return back("/devices", err="管理者のみ発行できます")
        _pair_gc()
        import secrets as _s
        code = f"{_s.randbelow(1000000):06d}"
        _PAIR_CODES[code] = {"user_id": user["id"], "label": (label or "iPhone").strip()[:40],
                             "expires": dbmod.ts_plus(minutes=PAIR_TTL_SECONDS / 60)}
        return back(f"/devices?code={code}", msg="連携コードを発行しました")
    finally:
        con.close()


@app.post("/api/pair")
async def api_pair(request: Request):
    """アプリが6桁コードを送ってトークンを受け取る。"""
    con = get_con()
    try:
        d = await request.json()
        code = str(d.get("code") or "").strip()
        _pair_gc()
        entry = _PAIR_CODES.pop(code, None)          # 使い切り
        if not entry:
            return JSONResponse({"ok": False, "error": "コードが違うか、期限が切れています"}, 400)
        token = auth.issue_device_token(con, entry["user_id"], entry["label"])
        org = con.execute(
            """SELECT o.name FROM organizations o JOIN users u ON u.organization_id = o.id
                WHERE u.id = ?""", (entry["user_id"],)).fetchone()
        return JSONResponse({"ok": True, "token": token,
                             "organization": org["name"] if org else ""})
    finally:
        con.close()


@app.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request, code: Optional[str] = None):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        return render(request, "devices.html", user, code=code,
                      tokens=auth.list_device_tokens(con, user["id"]),
                      base_url=svc.lan_base_url(), ttl=int(PAIR_TTL_SECONDS / 60))
    finally:
        con.close()


@app.post("/devices/{token_id}/revoke")
def device_revoke(request: Request, token_id: str):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return login_redirect(request)
        auth.revoke_token(con, token_id, user["id"])
        return back("/devices", msg="この端末の連携を解除しました")
    finally:
        con.close()


@app.get("/api/ping")
def api_ping(request: Request):
    """アプリの「接続を確認」用。トークンが有効かどうかもここで分かる。"""
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return JSONResponse({"ok": False, "error": "トークンが無効です"}, 401)
        org = con.execute("SELECT name FROM organizations WHERE id = ?",
                          (user["organization_id"],)).fetchone()
        return JSONResponse({"ok": True, "app": "KeyLine",
                             "organization": org["name"] if org else "",
                             "user": user["display_name"], "role": user["role"]})
    finally:
        con.close()


# ---------------------------------------------------------------------------
# アプリからの貸出・返却
#
# ★これがあると、iOSのバックグラウンドタグ読み取り（平文httpで通知が出るか未検証）
#   に頼らずに済む。アプリでかざして、そのまま貸出・返却まで終わる。
#   画面(/t/<token>)と同じ services を呼ぶので、状態判定や二重貸出の防止は共通。
# ---------------------------------------------------------------------------
def _asset_json(con, org, asset):
    """アプリに返す管理対象の姿。画面に出すものだけを詰める。"""
    return {
        "asset_id": asset["id"],
        "property_name": asset["property_name"] or "",
        "name": asset["name"],
        "label": (asset["property_name"] + " / " if asset["property_name"] else "") + asset["name"],
        "item_numbers": asset["item_numbers"] or "",
        "total_keys": asset["total_keys"],
        "box": svc.box_label(asset["box_code"], asset["box_position"]),
        "box_name": asset["box_name"] or "",
        "status": asset["status"],
        "status_label": STATUS_LABEL.get(asset["status"], asset["status"]),
        "borrower": {
            "id": asset["current_borrower_id"],
            "name": asset["borrower_name"] or "",
            "company": asset["borrower_company"] or "",
            "phone": asset["borrower_phone"] or "",
            "kind": KIND_LABEL.get(asset["borrower_kind"], ""),
        } if asset["current_borrower_id"] else None,
        "checked_out_at": dbmod.fmt_local(asset["checked_out_at"]),
        "due_at": dbmod.fmt_local(asset["due_at"]) if asset["due_at"] else "",
        "elapsed": elapsed_text(asset["elapsed_minutes"]),
        "is_overdue": bool(asset["is_overdue"]),
    }


@app.get("/api/asset")
def api_asset(request: Request, token: str = ""):
    """タグのトークンから、いまの状態と貸出に必要な選択肢をまとめて返す。

    アプリは1往復でこれを取り、貸出画面か返却画面かを決める。
    """
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return JSONResponse({"ok": False, "error": "ログインし直してください"}, 401)
        org = user["organization_id"]

        asset = svc.find_by_token(con, org, token)
        if asset is None:
            return JSONResponse({"ok": True, "found": False, "token": token})

        return JSONResponse({
            "ok": True, "found": True, "token": token,
            "asset": _asset_json(con, org, asset),
            "borrowers": [
                {"id": b["id"], "name": b["name"], "company": b["company"] or "",
                 "kind": KIND_LABEL.get(b["kind"], ""), "open_count": b["open_count"]}
                for b in svc.recent_borrowers(con, org, 20)],
            "dues": [{"label": l, "value": v} for l, v in svc.due_choices()],
        })
    finally:
        con.close()


@app.post("/api/checkout")
async def api_checkout(request: Request):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return JSONResponse({"ok": False, "error": "ログインし直してください"}, 401)
        org = user["organization_id"]
        d = await request.json()

        asset = svc.find_by_token(con, org, str(d.get("token") or ""))
        if asset is None:
            return JSONResponse({"ok": False, "error": "この鍵は登録されていません"}, 404)

        try:
            borrower_id = d.get("borrower_id")
            if not borrower_id:
                if not (d.get("new_name") or "").strip():
                    return JSONResponse({"ok": False, "error": "貸出先を選ぶか、お名前を入力してください"}, 400)
                borrower_id = svc.create_borrower(
                    con, org, d.get("new_name"), d.get("new_kind") or "vendor",
                    d.get("new_company"), d.get("new_phone"))
            svc.checkout(con, org, asset["id"], borrower_id, due_at=(d.get("due_at") or None))
        except (Conflict, svc.NotFound, svc.InvalidInput) as e:
            return JSONResponse({"ok": False, "error": str(e)}, 409)

        bus.notify()
        fresh = svc.get_asset(con, org, asset["id"])
        return JSONResponse({"ok": True, "asset": _asset_json(con, org, fresh)})
    finally:
        con.close()


@app.post("/api/return")
async def api_return(request: Request):
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return JSONResponse({"ok": False, "error": "ログインし直してください"}, 401)
        org = user["organization_id"]
        d = await request.json()

        asset = svc.find_by_token(con, org, str(d.get("token") or ""))
        if asset is None:
            return JSONResponse({"ok": False, "error": "この鍵は登録されていません"}, 404)
        try:
            svc.return_asset(con, org, asset["id"])
        except Conflict as e:
            return JSONResponse({"ok": False, "error": str(e)}, 409)

        bus.notify()
        fresh = svc.get_asset(con, org, asset["id"])
        return JSONResponse({"ok": True, "asset": _asset_json(con, org, fresh)})
    finally:
        con.close()


@app.get("/api/next-position")
def api_next_position(request: Request, box_id: str = ""):
    """そのボックスで次に空いていそうな位置。画面の初期値に使う。"""
    con = get_con()
    try:
        user = viewer(request, con)
        if not user:
            return JSONResponse({"ok": False}, 401)
        return JSONResponse({"ok": True,
                             "position": svc.suggest_position(con, user["organization_id"], box_id)})
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
