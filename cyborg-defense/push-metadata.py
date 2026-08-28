#!/usr/bin/env python3
"""`store-text.md` の内容を App Store Connect へ流し込む（サイボーグ防衛軍）。

**文言の正は `store-text.md` の1つだけ**にするための道具。画面へ手で写すと、
写し間違いと「どちらが最新か分からない」が必ず起きる。

    python3 push-metadata.py            # 何を書き換えるか出すだけ（既定）
    python3 push-metadata.py --apply    # 実際に書き込む

**書き換えるのは提出前の版だけ。** 配信中・審査中の版は API 側が拒否する。
**提出（Submit for Review）はしない。提出は必ず人が画面で行う。**

`keyline/keytag/push-metadata.py` を土台に、このアプリで必要な欄を足してある
（サポートURL・プライバシーURL・カテゴリ・著作権・審査連絡先）。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import appstore_api as A  # noqa: E402
import requests  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_TEXT = os.path.join(HERE, "store-text.md")
BUNDLE_ID = "com.daikyo.cyborgdefense"
LOCALE = "ja"

SUPPORT_URL = "https://shinsei99.github.io/project/cyborg-defense/support.html"
PRIVACY_URL = "https://shinsei99.github.io/project/cyborg-defense/privacy.html"
COPYRIGHT = "2026 SHINSEI PROPERTY MANAGEMENT.K.K."
PRIMARY_CATEGORY = "GAMES"
PRIMARY_SUBCATEGORY = "GAMES_PUZZLE"

# 審査の連絡先（KeyTag と同じ。ASC の「App Review 連絡先」欄）
CONTACT = {
    "contactFirstName": "shinichi",
    "contactLastName": "washimi",
    "contactPhone": "+819085300184",
    "contactEmail": "info@shinsei-pm.co.jp",
    "demoAccountRequired": False,
}

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
    for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        title, body = m.group(1).strip(), m.group(2)
        key = next((v for k, v in SECTIONS.items() if title.startswith(k)), None)
        if key is None:
            continue
        fence = re.search(r"```\n(.*?)```", body, re.S)
        if fence:
            out[key] = fence.group(1).rstrip("\n")
    return out


def _req(method: str, path: str, payload: dict) -> dict:
    r = requests.request(
        method, "{}{}".format(A.BASE, path),
        headers={"Authorization": "Bearer {}".format(A.token()),
                 "Content-Type": "application/json"},
        json=payload, timeout=60)
    if r.status_code not in (200, 201, 204):
        raise SystemExit("❌ {} {} が HTTP {}\n{}".format(method, path, r.status_code, r.text[:800]))
    return r.json() if r.text.strip() else {}


def show(label: str, old, new, limit: int = None) -> bool:
    old = (old or "").strip() if isinstance(old, str) or old is None else old
    new = (new or "").strip() if isinstance(new, str) or new is None else new
    if old == new:
        print("  = {:16} 変更なし".format(label))
        return False
    over = ""
    if limit and isinstance(new, str) and len(new) > limit:
        over = "  ⚠️ 上限 {} 字を {} 字超過".format(limit, len(new) - limit)
    if isinstance(new, str) and len(new) > 60:
        print("  ★ {:16} {} 字 → {} 字{}".format(label, len(old or ""), len(new), over))
        print("     新: {}…".format(new[:56].replace("\n", " ")))
    else:
        print("  ★ {:16} {} → {}".format(label, old, new))
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
    over = [k for k, v in want.items() if LIMITS.get(k) and len(v) > LIMITS[k]]
    if over:
        raise SystemExit("❌ 文字数が上限を超えています: {}".format(over))

    aid = A.app_id(BUNDLE_ID)
    if not aid:
        raise SystemExit("❌ {} が App Store Connect に見つかりません".format(BUNDLE_ID))

    infos = A._get("/apps/{}/appInfos".format(aid))["data"]
    editable = [d for d in infos
                if (d["attributes"].get("appStoreState") or "") not in ("READY_FOR_SALE",)]
    if not editable:
        raise SystemExit("❌ 編集できる appInfo がありません")
    info = editable[0]
    ilocs = A._get("/appInfos/{}/appInfoLocalizations".format(info["id"]))["data"]
    info_loc = next((l for l in ilocs if l["attributes"].get("locale") == LOCALE), None)
    if info_loc is None:
        raise SystemExit("❌ {} のローカライズがありません".format(LOCALE))

    vers = A._get("/apps/{}/appStoreVersions".format(aid), params={"limit": 5})["data"]
    vedit = [v for v in vers
             if (v["attributes"].get("appStoreState") or "") not in ("READY_FOR_SALE",)]
    if not vedit:
        raise SystemExit("❌ 編集できるバージョンがありません")
    ver = vedit[0]
    vlocs = A._get("/appStoreVersions/{}/appStoreVersionLocalizations".format(ver["id"]))["data"]
    vloc = next((l for l in vlocs if l["attributes"].get("locale") == LOCALE), None)
    if vloc is None:
        raise SystemExit("❌ バージョンに {} のローカライズがありません".format(LOCALE))
    rd = A._get("/appStoreVersions/{}/appStoreReviewDetail".format(ver["id"])).get("data")

    print("アプリ  : {} (id {})".format(BUNDLE_ID, aid))
    print("バージョン: {} / {}".format(ver["attributes"].get("versionString"),
                                   ver["attributes"].get("appStoreState")))
    print("─" * 62)

    ia, va = info_loc["attributes"], vloc["attributes"]

    ichanges = {}
    if show("名前", ia.get("name"), want["name"], LIMITS["name"]):
        ichanges["name"] = want["name"]
    if show("サブタイトル", ia.get("subtitle"), want["subtitle"], LIMITS["subtitle"]):
        ichanges["subtitle"] = want["subtitle"]
    if show("プライバシーURL", ia.get("privacyPolicyUrl"), PRIVACY_URL):
        ichanges["privacyPolicyUrl"] = PRIVACY_URL

    vchanges = {}
    for key, label in (("promotionalText", "プロモ"), ("keywords", "キーワード"),
                       ("description", "説明")):
        if show(label, va.get(key), want[key], LIMITS[key]):
            vchanges[key] = want[key]
    if show("サポートURL", va.get("supportUrl"), SUPPORT_URL):
        vchanges["supportUrl"] = SUPPORT_URL

    verchanges = {}
    if show("著作権", ver["attributes"].get("copyright"), COPYRIGHT):
        verchanges["copyright"] = COPYRIGHT

    # 審査ノートの入れ物（appStoreReviewDetail）は、まだ一度も触っていないバージョンには
    # 存在しない。その場合は POST で作る（PATCH しようとしても相手がいない）。
    nchanges = {}
    cur_rd = rd["attributes"] if rd else {}
    if not rd:
        print("  ★ 審査の連絡先欄     まだ無い → 新しく作る")
    for k, label in (("notes", "審査ノート"),):
        if show(label, cur_rd.get(k), want["notes"], LIMITS["notes"]):
            nchanges[k] = want["notes"]
    for k, v in CONTACT.items():
        if show(k, cur_rd.get(k), v):
            nchanges[k] = v

    # ★カテゴリは `include` を付けて読み直さないと relationships に出てこない。
    #   `/apps/{id}/appInfos` の素の応答では primaryCategory が常に null に見えるため、
    #   設定済みでも「未設定」と誤認して毎回 PATCH を投げることになる（2026-08-28 に踏んだ）。
    rel = A._get("/appInfos/{}?include=primaryCategory,primarySubcategoryOne".format(
        info["id"]))["data"]["relationships"]
    cur_primary = (rel.get("primaryCategory") or {}).get("data")
    cur_sub = (rel.get("primarySubcategoryOne") or {}).get("data")
    cur_primary = cur_primary["id"] if cur_primary else None
    cur_sub = cur_sub["id"] if cur_sub else None
    cat_change = {}
    if show("主カテゴリ", cur_primary, PRIMARY_CATEGORY):
        cat_change["primaryCategory"] = {"data": {"type": "appCategories", "id": PRIMARY_CATEGORY}}
    if show("サブカテゴリ", cur_sub, PRIMARY_SUBCATEGORY):
        cat_change["primarySubcategoryOne"] = {
            "data": {"type": "appCategories", "id": PRIMARY_SUBCATEGORY}}

    if not (ichanges or vchanges or verchanges or nchanges or cat_change):
        print("\n変更はありません。")
        return 0
    if not args.apply:
        print("\n下見だけです。実際に書き込むには --apply を付けてください。")
        return 0

    print("\n書き込みます…")
    if ichanges:
        _req("PATCH", "/appInfoLocalizations/{}".format(info_loc["id"]),
             {"data": {"type": "appInfoLocalizations", "id": info_loc["id"],
                       "attributes": ichanges}})
        print("  ✅ 名前・サブタイトル・プライバシーURL")
    if vchanges:
        _req("PATCH", "/appStoreVersionLocalizations/{}".format(vloc["id"]),
             {"data": {"type": "appStoreVersionLocalizations", "id": vloc["id"],
                       "attributes": vchanges}})
        print("  ✅ 説明・キーワード・プロモ・サポートURL")
    if verchanges:
        _req("PATCH", "/appStoreVersions/{}".format(ver["id"]),
             {"data": {"type": "appStoreVersions", "id": ver["id"],
                       "attributes": verchanges}})
        print("  ✅ 著作権")
    if nchanges:
        if rd:
            _req("PATCH", "/appStoreReviewDetails/{}".format(rd["id"]),
                 {"data": {"type": "appStoreReviewDetails", "id": rd["id"],
                           "attributes": nchanges}})
        else:
            _req("POST", "/appStoreReviewDetails",
                 {"data": {"type": "appStoreReviewDetails", "attributes": nchanges,
                           "relationships": {"appStoreVersion": {
                               "data": {"type": "appStoreVersions", "id": ver["id"]}}}}})
        print("  ✅ 審査ノート・連絡先")
    if cat_change:
        _req("PATCH", "/appInfos/{}".format(info["id"]),
             {"data": {"type": "appInfos", "id": info["id"], "relationships": cat_change}})
        print("  ✅ カテゴリ（ゲーム / パズル）")

    print("\n★ 提出（Submit for Review）はしていません。画面から人が行ってください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
