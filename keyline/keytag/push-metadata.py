#!/usr/bin/env python3
"""`store-text.md` の内容を App Store Connect へ流し込む。

**文言の正は `store-text.md` の1つだけ**にするための道具。画面へ手で写すと、
写し間違いと「どちらが最新か分からない」が必ず起きる（改訂のたびに数千字ある）。

    python3 push-metadata.py --dry-run     # 何を書き換えるか出すだけ（既定）
    python3 push-metadata.py --apply       # 実際に書き込む

**書き換えるのは提出前の版だけ。** 配信中の版や審査中の版は API 側が拒否する。
提出（Submit for Review）はしない。**提出は必ず人が画面で行う。**

読み取る節（`store-text.md` の見出し → 送り先）:

| 見出し | 送り先 |
|---|---|
| `## 名前` | appInfoLocalizations.name |
| `## サブタイトル` | appInfoLocalizations.subtitle |
| `## プロモーション用テキスト` | appStoreVersionLocalizations.promotionalText |
| `## キーワード` | appStoreVersionLocalizations.keywords |
| `## 説明` | appStoreVersionLocalizations.description |
| `## 審査ノート` | appStoreReviewDetails.notes |

カテゴリは `## その他の欄` の表から読む（`設定しない` なら副カテゴリを外す）。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import appstore_api as A  # noqa: E402
import requests  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_TEXT = os.path.join(HERE, "store-text.md")
BUNDLE_ID = "com.shinsei99.keytag"
LOCALE = "ja"

# 見出しの先頭一致 → 取り出したいもの
SECTIONS = {
    "名前": "name",
    "サブタイトル": "subtitle",
    "プロモーション用テキスト": "promotionalText",
    "キーワード": "keywords",
    "説明": "description",
    "審査ノート": "notes",
}
LIMITS = {"name": 30, "subtitle": 30, "promotionalText": 170,
          "keywords": 100, "description": 4000, "notes": 4000}


def parse_store_text(path: str) -> dict:
    """見出しごとの**最初のコードフェンス**を取り出す。"""
    text = open(path, encoding="utf-8").read()
    out = {}
    # `## 見出し…` から次の `## ` までを1節として切る
    for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        title, body = m.group(1).strip(), m.group(2)
        key = next((v for k, v in SECTIONS.items() if title.startswith(k)), None)
        if key is None:
            continue
        fence = re.search(r"```\n(.*?)```", body, re.S)
        if fence:
            out[key] = fence.group(1).rstrip("\n")
    # カテゴリ（表から）
    cat = re.search(r"\|\s*カテゴリ（主）\s*\|\s*([^|]+)\|", text)
    sub = re.search(r"\|\s*カテゴリ（副）\s*\|\s*([^|]+)\|", text)
    out["_primary"] = "BUSINESS" if cat and "ビジネス" in cat.group(1) else None
    out["_secondary_none"] = bool(sub and "設定しない" in sub.group(1))
    return out


def patch(path: str, payload: dict) -> dict:
    r = requests.patch(
        "{}{}".format(A.BASE, path),
        headers={"Authorization": "Bearer {}".format(A.token()),
                 "Content-Type": "application/json"},
        json=payload, timeout=60)
    if r.status_code not in (200, 204):
        raise SystemExit("❌ PATCH {} が HTTP {}\n{}".format(path, r.status_code, r.text[:600]))
    return r.json() if r.text.strip() else {}


def show(label: str, old: str, new: str, limit: int = None) -> bool:
    """変わるかどうかを出して、変わるなら True。"""
    old = (old or "").strip()
    new = (new or "").strip()
    if old == new:
        print("  = {:16} 変更なし".format(label))
        return False
    over = ""
    if limit and len(new) > limit:
        over = "  ⚠️ 上限 {} 字を {} 字超過".format(limit, len(new) - limit)
    print("  ★ {:16} {} 字 → {} 字{}".format(label, len(old), len(new), over))
    print("     旧: {}".format(old[:60].replace("\n", " ")))
    print("     新: {}".format(new[:60].replace("\n", " ")))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実際に書き込む（既定は下見だけ）")
    args = ap.parse_args()

    want = parse_store_text(STORE_TEXT)
    missing = [k for k in ("name", "subtitle", "description", "keywords", "notes")
               if not want.get(k)]
    if missing:
        raise SystemExit("❌ store-text.md から取り出せませんでした: {}".format(missing))

    aid = A.app_id(BUNDLE_ID)
    if not aid:
        raise SystemExit("❌ {} が App Store Connect に見つかりません".format(BUNDLE_ID))

    # ── 1枚目: 名前・サブタイトル・カテゴリ（appInfo）
    infos = A._get("/apps/{}/appInfos".format(aid))["data"]
    editable = [d for d in infos
                if (d["attributes"].get("appStoreState") or "") not in ("READY_FOR_SALE",)]
    if not editable:
        raise SystemExit("❌ 編集できる appInfo がありません（配信中の版しか無い）")
    info = editable[0]
    loc = [l for l in A._get("/appInfos/{}/appInfoLocalizations".format(info["id"]))["data"]
           if l["attributes"].get("locale") == LOCALE]
    if not loc:
        raise SystemExit("❌ {} のローカライズがありません".format(LOCALE))
    info_loc = loc[0]

    # ── バージョン側: 説明・キーワード・プロモ（appStoreVersion）
    vers = A._get("/apps/{}/appStoreVersions".format(aid), params={"limit": 5})["data"]
    vedit = [v for v in vers
             if (v["attributes"].get("appStoreState") or "") not in ("READY_FOR_SALE",)]
    if not vedit:
        raise SystemExit("❌ 編集できるバージョンがありません")
    ver = vedit[0]
    vlocs = A._get("/appStoreVersions/{}/appStoreVersionLocalizations".format(ver["id"]))["data"]
    vloc = [l for l in vlocs if l["attributes"].get("locale") == LOCALE]
    if not vloc:
        raise SystemExit("❌ バージョンに {} のローカライズがありません".format(LOCALE))
    vloc = vloc[0]
    rd = A._get("/appStoreVersions/{}/appStoreReviewDetail".format(ver["id"]))["data"]

    print("アプリ  : {} (id {})".format(BUNDLE_ID, aid))
    print("バージョン: {} / {}".format(ver["attributes"].get("versionString"),
                                   ver["attributes"].get("appStoreState")))
    print("─" * 62)

    ia = info_loc["attributes"]
    va = vloc["attributes"]
    changes = {}
    if show("名前", ia.get("name"), want["name"], LIMITS["name"]):
        changes["name"] = want["name"]
    if show("サブタイトル", ia.get("subtitle"), want["subtitle"], LIMITS["subtitle"]):
        changes["subtitle"] = want["subtitle"]

    vchanges = {}
    for key, label in (("promotionalText", "プロモ"), ("keywords", "キーワード"),
                       ("description", "説明")):
        if show(label, va.get(key), want[key], LIMITS[key]):
            vchanges[key] = want[key]

    nchanges = {}
    if show("審査ノート", rd["attributes"].get("notes"), want["notes"], LIMITS["notes"]):
        nchanges["notes"] = want["notes"]

    # カテゴリ
    cats = A._get("/apps/{}/appInfos".format(aid),
                  params={"include": "primaryCategory,secondaryCategory"})
    cur = {}
    for d in cats.get("data", []):
        if d["id"] != info["id"]:
            continue
        for k in ("primaryCategory", "secondaryCategory"):
            v = (d.get("relationships", {}).get(k) or {}).get("data")
            cur[k] = v["id"] if v else None
    drop_secondary = want["_secondary_none"] and cur.get("secondaryCategory")
    print("  {} 主カテゴリ         {}".format("=" if cur.get("primaryCategory") == want["_primary"] else "★",
                                          cur.get("primaryCategory")))
    print("  {} 副カテゴリ         {} {}".format(
        "★" if drop_secondary else "=", cur.get("secondaryCategory"),
        "→ 外す" if drop_secondary else ""))

    over = [k for k, v in list(changes.items()) + list(vchanges.items()) + list(nchanges.items())
            if LIMITS.get(k) and len(v) > LIMITS[k]]
    if over:
        raise SystemExit("\n❌ 文字数が上限を超えている項目があります: {}".format(over))

    if not (changes or vchanges or nchanges or drop_secondary):
        print("\n変更はありません。")
        return 0
    if not args.apply:
        print("\n下見だけです。実際に書き込むには --apply を付けてください。")
        return 0

    print("\n書き込みます…")
    if changes:
        patch("/appInfoLocalizations/{}".format(info_loc["id"]),
              {"data": {"type": "appInfoLocalizations", "id": info_loc["id"],
                        "attributes": changes}})
        print("  ✅ 名前・サブタイトル")
    if vchanges:
        patch("/appStoreVersionLocalizations/{}".format(vloc["id"]),
              {"data": {"type": "appStoreVersionLocalizations", "id": vloc["id"],
                        "attributes": vchanges}})
        print("  ✅ 説明・キーワード・プロモ")
    if nchanges:
        patch("/appStoreReviewDetails/{}".format(rd["id"]),
              {"data": {"type": "appStoreReviewDetails", "id": rd["id"],
                        "attributes": nchanges}})
        print("  ✅ 審査ノート")
    if drop_secondary:
        patch("/appInfos/{}".format(info["id"]),
              {"data": {"type": "appInfos", "id": info["id"],
                        "relationships": {"secondaryCategory": {"data": None}}}})
        print("  ✅ 副カテゴリを外した")

    print("\n★ 提出（Submit for Review）はしていません。画面から人が行ってください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
