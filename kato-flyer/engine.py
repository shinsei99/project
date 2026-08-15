"""紙面エンジンの橋渡し — マルチプロダクション（../agent-platform）の型と配色を借りる。

なぜこの形か:
  こちらの `flyer.py` は PIL で座標をべた書きして1枚描くので、**型が1つしか無い**。
  マルチプロダクションには型10種・配色9種・特色アイコン73種・自動フィット（二分探索）が
  すでにあり、実際に紙面が出ている。作り直すより借りる方が速く、質も揃う。

  **コピーはしない。** エンジン側の `flyer_build.py` には
  「同じ処理を3か所に書いたら、画面側だけ用紙が縦固定のまま古くなった」という失敗が
  記録されている。実体は `../agent-platform` の1つだけにする。
  同じリポジトリ内での再利用は `kaitori-dm-maker` → `baikai-generator/services/` に前例がある。

なぜ import ではなく別プロセスか:
  エンジンは `import tools` の時点で16個のアイテム（numpy・moviepy・playwright…）を読む。
  こちらの `.venv` に同じものを入れると、両方の依存が絡んで**どちらも壊れやすくなる**。
  **向こうの `.venv` の python をそのまま呼ぶ**のが確実で、こちらには何も足さなくていい。
  やり取りは stdin/stdout の JSON 1往復だけ。

写真について:
  エンジンは画像を data URI でHTMLに埋め込む（相対パスはブラウザが読めないため）。
  原寸のまま渡すとHTMLが数十MBになり、自動フィットが何度も描き直すぶんだけ遅くなる。
  → ここで **長辺2400px（A4/300dpiの短辺相当）のjpgに落としてキャッシュ**してから渡す。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ENGINE_DIR = APP_DIR.parent / "agent-platform"
ENGINE_PY = ENGINE_DIR / ".venv" / "bin" / "python"
PHOTO_CACHE = APP_DIR / "data" / "render_cache"

# 看板と同じ色。**現地写真に重ねて検証した結果の値**なので、
# エンジン側の似た配色（sunset = #e2701a）で代用しない（HANDOFF.md 参照）。
KATO_PALETTE = {"id": "kato", "name": "橙×濃紺（看板と同じ・既定）",
                "accent": "#f07c1e", "ink": "#1b2340",
                "best_for": "加東の看板・チラシの標準。屋外で木立にも壁にも負けない"}

# エンジン側で動かす中身。向こうの python で実行されるので、
# ここに書けるのは**向こうの環境にあるもの**だけ。
RUNNER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
req = json.load(sys.stdin)
op = req.get("op")

if op == "catalog":
    from core import layouts, palettes
    # マイソク（業者向け）も出す。募集チラシとは別の用途で実際に要る
    out = {"templates": [{"id": t["id"], "name": t["name"], "summary": t["summary"],
                          "best_for": t["best_for"], "photos_min": t["photos_min"],
                          "shape": t["shape"], "orientation": t["orientation"],
                          "genres": list(t["genres"])}
                         for t in layouts.TEMPLATES],
           "palettes": [{"id": p["id"], "name": p["name"], "accent": p["accent"],
                         "ink": p["ink"], "best_for": p.get("best_for", "")}
                        for p in palettes.PALETTES]}
    print(json.dumps(out, ensure_ascii=False))

elif op == "icons":
    from tools import feature_icons
    matched, extra = feature_icons.split(req["names"])
    print(json.dumps({"matched": list(matched), "extra": list(extra)}, ensure_ascii=False))

elif op == "render":
    from core import layouts, flyer_build
    picked = [t for t in layouts.TEMPLATES if t["id"] == req["template"]]
    if not picked:
        raise SystemExit("型が見つかりません: %s" % req["template"])
    tpl = picked[0]
    layout = tpl["build"](req["content"])
    paper = layouts.PAPER_BY_ORIENTATION.get(tpl["orientation"], "A4")
    made = flyer_build.render(layout, req["photos"], req["out_dir"],
                              stem=req["stem"], paper=paper,
                              accent=req["accent"], ink=req["ink"])
    print(json.dumps({k: str(v) for k, v in made.items()}, ensure_ascii=False))
"""


def available() -> tuple[bool, str]:
    """このPCでエンジンを使えるか。使えないなら理由を返す（画面に出して案内する）。"""
    if not ENGINE_DIR.exists():
        return False, "隣に agent-platform がありません（%s）" % ENGINE_DIR
    if not ENGINE_PY.exists():
        return False, "agent-platform の .venv が未作成です（向こうで run.sh を1度動かす）"
    return True, "型と配色は agent-platform から読み込みます"


def _call(payload: dict, timeout: int = 180) -> dict:
    proc = subprocess.run(
        [str(ENGINE_PY), "-c", RUNNER, str(ENGINE_DIR)],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=str(ENGINE_DIR), timeout=timeout,
    )
    if proc.returncode != 0:
        # 向こうの例外はそのまま見せる。握り潰すと原因が分からなくなる
        tail = (proc.stderr or "").strip().splitlines()
        raise RuntimeError("エンジンが失敗しました: " + (tail[-1] if tail else "理由不明"))
    return json.loads(proc.stdout.strip().splitlines()[-1])


_catalog: dict = {}


def catalog() -> dict:
    """型と配色の一覧。1回だけ取りに行く（プロセスの間は使い回す）。"""
    global _catalog
    if not _catalog:
        _catalog = _call({"op": "catalog"}, timeout=60)
        # 既定の配色を先頭に。**今までと同じ色**で出るようにする
        others = [p for p in _catalog["palettes"] if p["id"] != KATO_PALETTE["id"]]
        _catalog["palettes"] = [KATO_PALETTE] + others
    return _catalog


def templates() -> list[dict]:
    return catalog()["templates"]


def palettes() -> list[dict]:
    return catalog()["palettes"]


def palette(palette_id: str) -> dict:
    for item in palettes():
        if item["id"] == palette_id:
            return item
    return KATO_PALETTE


def prepare_photo(path: str, max_px: int = 2400) -> str:
    """写真をエンジンに渡せる形にする（CR2→jpg・縮小・キャッシュ）。

    元ファイルは触らない。キャッシュの鍵に更新時刻を入れているので、
    撮り直した写真は自動で作り直される。
    """
    import flyer  # load_image は CR2 を sips で開く。ここでも使い回す

    src = Path(path)
    stat = src.stat()
    key = hashlib.sha1(
        ("%s|%d|%d|%d" % (src, stat.st_mtime_ns, stat.st_size, max_px)).encode("utf-8")
    ).hexdigest()[:16]
    out = PHOTO_CACHE / ("%s.jpg" % key)
    if out.exists():
        return str(out)
    PHOTO_CACHE.mkdir(parents=True, exist_ok=True)
    image = flyer.load_image(str(src))
    image.thumbnail((max_px, max_px))
    image.save(out, "JPEG", quality=88)
    return str(out)


ICON_MIN = 3


def split_tags(tags: list[str]) -> tuple[list[str], list[str]]:
    """特徴タグを「絵のあるもの」と「文字で出すもの」に分ける。

    **1〜2個だけアイコンにすると、広い行に絵がぽつんと残って間が抜ける**
    （実際に「眺望良好」1個だけの行ができた）。3個そろわないなら全部文字タグにする。
    """
    names = [t for t in tags if str(t).strip()]
    if not names:
        return [], []
    try:
        got = _call({"op": "icons", "names": names}, timeout=60)
    except Exception:
        return [], names
    matched, extra = got.get("matched") or [], got.get("extra") or []
    if len(matched) < ICON_MIN:
        return [], names
    return matched, extra


def build_content(fl, qr_on: bool = True) -> tuple[dict, list[str]]:
    """`flyer.Flyer` を、エンジンの型が受け取る content に翻訳する。

    型は全て同じ content を受け取る決まりなので、ここさえ合わせれば
    **どの型でも文言を作り直さずに差し替えられる**。
    写真は番号（1始まり）で指定する仕組みなので、並べた順で渡す。
    """
    from properties import ADDRESS, COMPANY, LICENSE

    photos: list[str] = []
    if fl.main_photo:
        photos.append(prepare_photo(fl.main_photo))
    for path in fl.sub_photos:
        photos.append(prepare_photo(path))
    plan_no = None
    if fl.madori:
        photos.append(prepare_photo(fl.madori))
        plan_no = len(photos)

    rooms = list(range(2, len(fl.sub_photos) + 2))
    icons, badges = split_tags(list(fl.tags))
    content = {
        "kicker": fl.kicker,
        # 改行はHTMLでは詰められるので空白に置き換える。級数は文字数から自動で決まる
        "catch": " ".join(x.strip() for x in fl.catch.splitlines() if x.strip()),
        "title": fl.title,
        "sub": fl.rent_note,
        "price": fl.rent,
        "unit": "円 / 月",
        "lead": fl.body,
        # 特徴タグはまず**アイコン**に当てにいく（73種）。足りなければ文字タグで出す
        "icons": icons,
        "badges": badges,
        "spec_rows": [[k, v] for k, v in fl.specs],
        "photos": {"hero": 1 if fl.main_photo else None,
                   "floorplan": plan_no,
                   "rooms": rooms},
        "contact": {"label": "内覧・お問い合わせ", "tel": fl.tel,
                    "company": COMPANY, "address": ADDRESS, "license": LICENSE},
        "qr": fl.qr_url,
        "qr_on": bool(qr_on and fl.qr_url),
        "qr_label": fl.qr_label,
    }
    return content, photos


def render(fl, template_id: str, palette_id: str, out_dir, stem: str = "flyer") -> dict:
    """型と配色を指定して紙面を作る。戻り値は {"html":…, "pdf":…, "png":…}。"""
    colors = palette(palette_id)
    content, photos = build_content(fl)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = _call({"op": "render", "template": template_id, "content": content,
                  "photos": photos, "out_dir": str(out_dir), "stem": stem,
                  "accent": colors["accent"], "ink": colors["ink"]})
    return {k: Path(v) for k, v in made.items()}
