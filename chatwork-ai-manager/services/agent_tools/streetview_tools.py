"""現地の店舗名・看板を画像から目視確認するTool（TASK-20260819-004・オーナー依頼）。

依頼: qa.py の WebFetch は HTML→テキスト変換のみで、画像・地図は認識できない。
指定した住所/物件/座標の画像を実際に取得し、claude vision で内容
（看板の店舗名・テナント名など）を読み取れるようにする。gis_geocode / gis_property_search
と同じ「地点特定」の考え方（gis.py の find_property / geocode）をそのまま使う。

現状の制約（2026-08-19時点）:
  Google公式の Street View Static API / Maps Static API は google_maps_api_key
  （Google Cloud・要課金設定）が無いと使えない。新規APIキー発行・課金は
  勝手に行わない決まりのため、**未設定の間は代替としてヘッドレスChromeで
  Googleマップの衛星写真（無料・キー不要）を撮り、そこに乗っているPOIラベルを
  claude visionで読む**。google_maps_api_key を secrets.toml に設定すれば、
  実際の路上写真（Street View）が自動で優先されるようになる（コード変更不要）。

  ヘッドレスChromeで「歩行者視点のストリートビュー」をPegmanドラッグ操作で
  自動取得する方法も試したが、座標へのスナップとWebGLパノラマの描画が
  安定せず（黒画面のまま描画されない事例あり）断念した。公式APIに任せるのが正しい。
"""
import json
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request

from services import config
from services import gis
from services import web_image_store

WORKSPACE = os.path.expanduser("~")

# Playwright(Python)の在り処。共通Visual Agent（~/VISUAL_AGENT.md）と同じ探索順。
# 特定アプリの .venv に依存しない。
_PY_CANDIDATES = [
    os.environ.get("VA_PYTHON"),
    os.path.join(WORKSPACE, "agent-platform", ".venv", "bin", "python"),
    os.path.join(WORKSPACE, ".va-venv", "bin", "python"),
]

# 一度だけ子プロセスで実行する使い捨てスクリプト。
# 常駐ブラウザ(visual_agent.pyのdaemon)は流用しない（呼び出し頻度が低く、都度起動で十分なため）。
_SCREENSHOT_SCRIPT = r"""
import sys, time
from playwright.sync_api import sync_playwright

lat, lon, out_path, mode = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
lat, lon = float(lat), float(lon)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = browser.new_context(viewport={"width": 1200, "height": 900}, locale="ja-JP")
    page = ctx.new_page()
    if mode == "satellite":
        url = f"https://www.google.com/maps/@{lat},{lon},19z/data=!3m1!1e3?hl=ja"
    else:
        url = f"https://www.google.com/maps/@{lat},{lon},19z?hl=ja"
    page.goto(url, wait_until="load", timeout=45000)
    time.sleep(4)
    page.screenshot(path=out_path)
    browser.close()
print("ok")
"""


def _resolve_playwright_python():
    for cand in _PY_CANDIDATES:
        if not cand or not os.path.exists(cand):
            continue
        r = subprocess.run([cand, "-c", "import playwright"], capture_output=True)
        if r.returncode == 0:
            return cand
    return None


def _resolve_point(address=None, lat=None, lon=None, property=None):
    """住所/物件名/緯度経度のいずれかから地点を特定する（gis_distanceと同じ考え方）。"""
    if lat is not None and lon is not None:
        label = address or property or f"{lat},{lon}"
        return {"lat": float(lat), "lon": float(lon), "label": label}, None
    if property:
        p = gis.find_property(property)
        if not p:
            return None, f"物件が見つかりません: {property}"
        if p.get("lat") is None:
            return None, f"座標が未取得の物件です: {p['name']}"
        return {"lat": p["lat"], "lon": p["lon"], "label": p["name"]}, None
    if address:
        g = gis.geocode(address)
        if not g.get("ok"):
            return None, f"住所から座標を特定できません: {address}"
        return {"lat": g["lat"], "lon": g["lon"], "label": g.get("title") or address}, None
    return None, "address / property / lat+lon のいずれかを指定してください"


def _fetch_streetview_static(lat, lon, api_key, out_dir):
    """Google Street View Static API（要 google_maps_api_key・課金設定）。"""
    meta_url = "https://maps.googleapis.com/maps/api/streetview/metadata?" + urllib.parse.urlencode({
        "location": f"{lat},{lon}", "key": api_key,
    })
    try:
        with urllib.request.urlopen(meta_url, timeout=15) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    if meta.get("status") != "OK":
        return None, f"Street View画像なし（status={meta.get('status')}）"
    img_url = "https://maps.googleapis.com/maps/api/streetview?" + urllib.parse.urlencode({
        "size": "640x480", "location": f"{lat},{lon}", "fov": 90, "key": api_key,
    })
    out_path = os.path.join(out_dir, "streetview.jpg")
    try:
        urllib.request.urlretrieve(img_url, out_path)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    return "streetview.jpg", None


def _capture_satellite(lat, lon, out_dir, timeout=60):
    """無料フォールバック: ヘッドレスChromeでGoogleマップ衛星写真をスクリーンショット。"""
    py = _resolve_playwright_python()
    if not py:
        return None, ("Playwright(Python) が見つかりません。"
                       "agent-platform/.venv か ~/.va-venv に入れてください（詳細は ~/VISUAL_AGENT.md）")
    out_path = os.path.join(out_dir, "satellite.png")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_SCREENSHOT_SCRIPT)
        script_path = f.name
    try:
        r = subprocess.run([py, script_path, str(lat), str(lon), out_path, "satellite"],
                            capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(script_path)
    if r.returncode != 0 or not os.path.exists(out_path):
        return None, f"衛星写真の取得に失敗: {(r.stderr or r.stdout).strip()[:400]}"
    return "satellite.png", None


def _analyze_images(tmp_dir, images, point, question):
    """claude vision（既存 ocr_pdf と同じ作法: Read ツール許可＋add_dir）で画像を読む。"""
    from services.claude_client import ClaudeError, run_claude

    names = "\n".join(f"- {fname}（{desc}）" for fname, desc in images)
    ask = f"\n\n特に確認したいこと: {question}" if question else ""
    prompt = (
        f"次の画像ファイル（ディレクトリ {tmp_dir} 内）を Read ツールで開いて見てください。"
        f"地点: {point['label']}（緯度{point['lat']}, 経度{point['lon']}）。\n"
        "画像に写っている店舗名・看板・テナント名・目立つ建物名など、"
        "現地を特定する手がかりになる文字情報を、確認できたものだけ具体的に列挙してください。"
        "読み取れない・写っていない場合は「読み取れませんでした」と正直に書いてください。"
        f"{ask}\n\n対象:\n{names}"
    )
    try:
        env = run_claude(prompt, model="sonnet", timeout=180, add_dir=tmp_dir, allow_read=True)
    except ClaudeError:
        return None
    return (env.get("result") or "").strip() or None


def streetview_lookup(address=None, lat=None, lon=None, property=None, question=None):
    """指定地点の画像（Street View写真、未設定時は衛星写真）を取得し、
    claude visionで店舗名・看板・目立つ建物名を読み取る。

    address / property / lat+lon のいずれかで地点を指定する（gis_geocode / gis_property_searchと
    同じ物件マスタ・GSIジオコーディングを流用）。question で「何を確認したいか」を追加指定できる
    （例: "1階の店舗名は何か"）。
    """
    point, err = _resolve_point(address=address, lat=lat, lon=lon, property=property)
    if err:
        return {"ok": False, "error": err}

    api_key = config.get("google_maps_api_key")
    mode = None
    note = None

    with tempfile.TemporaryDirectory() as tmp:
        images = []
        if api_key:
            fname, ferr = _fetch_streetview_static(point["lat"], point["lon"], api_key, tmp)
            if fname:
                images.append((fname, "Street View 写真"))
                mode = "streetview_api"
            else:
                note = f"Street View取得に失敗したため衛星写真で代替: {ferr}"

        if not images:
            fname, ferr = _capture_satellite(point["lat"], point["lon"], tmp)
            if not fname:
                return {"ok": False, "error": ferr, "point": point}
            images.append((fname, "Googleマップ衛星写真"))
            mode = mode or "satellite_fallback"
            if not api_key:
                note = ("google_maps_api_key 未設定のため衛星写真のみで判定しています。"
                        "路上の看板を直接読みたい場合はキー設定（課金）が必要です。")

        analysis = _analyze_images(tmp, images, point, question)
        if analysis is None:
            return {"ok": False, "error": "画像認識(claude vision)に失敗しました", "point": point}

        # 解析後にディレクトリごと消える前に、実際に使った画像を一時保管庫へ退避する。
        # image_token を chatwork_send_web_image / line_send_web_image に渡せば、
        # 取得したこの画像そのものをChatwork添付・LINE画像pushで送れる（TASK-20260819-005）。
        image_token = web_image_store.save(os.path.join(tmp, images[0][0]))

    return {
        "ok": True, "mode": mode, "lat": point["lat"], "lon": point["lon"],
        "label": point["label"], "analysis": analysis, "note": note,
        "image_token": image_token,
        "image_hint": "この画像自体を送りたい場合は chatwork_send_web_image / line_send_web_image に"
                      "この image_token を渡す（数時間で失効するので、必要な時にすぐ送る）",
    }


# ─── ストリートビューを「人が見る」ための入口（2026-08-21 追加） ────────────────
#
# 2026-08-19 に Google Maps のキーを取得したので、**その地点にSVがあるか**を無料の
# metadata API で確かめられるようになった。ただし **SV画像そのものをAIに読ませることは
# しない**（Maps規約 3.2.3(c)(vii) AIモデルへの利用禁止。API_STATUS.md の D表で
# 「やらない」と決着済み）。ここで返すのは**人が開いて見るためのリンク**で、
# 「画面でSVを見る」は規約上やってよい使い方。
#
# チャットに貼るURLは **キーを含まない公開URL** にしている（Embed URL はキーが
# 剥き出しになるので、社員に配るチャットには流さない。Embedは社内画面用）。

_ROOT_FOR_MAPS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _maps_api():
    import sys
    parent = os.path.dirname(_ROOT_FOR_MAPS)   # /Users/apple
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import google_maps_api
    return google_maps_api


def _public_urls(lat, lon):
    """キーを含まない公開URL。チャットに貼っても資格情報が漏れない。"""
    return {
        "streetview_url": (
            "https://www.google.com/maps/@?api=1&map_action=pano"
            f"&viewpoint={lat},{lon}"
        ),
        "map_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
    }


def streetview_available(address=None, lat=None, lon=None, property=None, radius=50):
    """その地点にストリートビューがあるか／撮影がいつかを調べる（無料のmetadata）。

    リンクを渡す前にこれで確かめると、**開いても何も映らないリンクを送らずに済む**。
    戻り: あり → pano_id・撮影年月（"2021-08"）・実際のパノラマ位置、なし → ok=False。
    """
    point, err = _resolve_point(address=address, lat=lat, lon=lon, property=property)
    if err:
        return {"ok": False, "error": err}
    gm = _maps_api()
    if not gm.server_key():
        return {"ok": False, "error": "GOOGLE_MAPS_SERVER_KEY が未設定です（直下 .env.google-maps）",
                "point": point}
    meta = gm.streetview_metadata(point["lat"], point["lon"], radius=int(radius))
    if not meta:
        return {"ok": False, "label": point["label"], "point": point,
                "error": "この地点にストリートビューはありません（半径 %dm）" % int(radius),
                "hint": "半径を広げるか、前面道路側の座標で引き直す"}
    return {
        "ok": True,
        "label": point["label"],
        "requested": {"lat": point["lat"], "lon": point["lon"]},
        "panorama": {"lat": meta.get("lat"), "lon": meta.get("lon")},
        "captured": meta.get("date"),
        "pano_id": meta.get("pano_id"),
        **_public_urls(meta.get("lat") or point["lat"], meta.get("lon") or point["lon"]),
        "source": "Google Street View Static API (metadata・無料)",
    }


def streetview_link(address=None, lat=None, lon=None, property=None):
    """現地のストリートビューを**人が開いて見る**ためのリンクを作って返す。

    「○○の外観を見たい」「現地の様子を確認したい」ときに、このURLをそのまま伝える。
    あるかどうかと撮影年月も一緒に確かめる（無ければその旨と地図リンクだけ返す）。

    ⚠️ SV画像をこちらで取得してAIに読ませることはしない（Maps規約 3.2.3(c)(vii)）。
       印刷・チラシへの掲載も不可。**画面で見るのは可**。
    """
    point, err = _resolve_point(address=address, lat=lat, lon=lon, property=property)
    if err:
        return {"ok": False, "error": err}
    got = streetview_available(lat=point["lat"], lon=point["lon"], property=None)
    urls = _public_urls(point["lat"], point["lon"])
    if got.get("ok"):
        return {
            "ok": True, "label": point["label"],
            "streetview_url": got["streetview_url"], "map_url": got["map_url"],
            "captured": got.get("captured"),
            "note": "ブラウザで開いて見てください（撮影 %s）。印刷・チラシへの掲載は規約上できません。"
                    % (got.get("captured") or "時期不明"),
        }
    return {
        "ok": True, "label": point["label"], "streetview": False,
        "map_url": urls["map_url"],
        "note": "この地点にストリートビューはありませんでした。地図のリンクだけ返します。",
        "detail": got.get("error"),
    }
