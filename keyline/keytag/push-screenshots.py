#!/usr/bin/env python3
"""スクリーンショットを App Store Connect へ入れ替える。

    python3 push-screenshots.py <フォルダ>            # 下見（何をするか出すだけ）
    python3 push-screenshots.py <フォルダ> --apply    # 実際に入れ替える

フォルダの中の `*.png` を**ファイル名順**に並べて、既存のスクショを**全部消してから**
順番どおりに入れ直す。並び順がそのままストアの並びになるので、`01-…` `02-…` と付ける。

寸法は App Store の規定に合わせておくこと（このアプリは iPhone 6.5型＝**1284×2778**）。
シミュレータの素の解像度（iPhone 17 Pro は 1206×2622）は**弾かれる**ので、
`sips -z 2778 1284` で直してから渡す。

アップロードは3段構え（Apple の仕様）:
  ① POST /appScreenshots で枠を予約 → `uploadOperations`（分割アップロードの指示）が返る
  ② 指示どおりにバイト列を PUT する
  ③ PATCH で `uploaded=true` と md5 を送ると、Apple 側が検証して COMPLETE になる
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import appstore_api as A  # noqa: E402
import requests  # noqa: E402

BUNDLE_ID = "com.shinsei99.keytag"
LOCALE = "ja"
DISPLAY_TYPE = "APP_IPHONE_65"     # 6.5型（1284×2778）


def _hdr(extra=None):
    h = {"Authorization": "Bearer {}".format(A.token())}
    h.update(extra or {})
    return h


def api(method: str, path: str, **kw):
    r = requests.request(method, "{}{}".format(A.BASE, path),
                         headers=_hdr({"Content-Type": "application/json"}), timeout=120, **kw)
    if r.status_code >= 300:
        raise SystemExit("❌ {} {} が HTTP {}\n{}".format(method, path, r.status_code, r.text[:500]))
    return r.json() if r.text.strip() else {}


def upload_one(set_id: str, path: str) -> str:
    data = open(path, "rb").read()
    name = os.path.basename(path)
    res = api("POST", "/appScreenshots", json={"data": {
        "type": "appScreenshots",
        "attributes": {"fileName": name, "fileSize": len(data)},
        "relationships": {"appScreenshotSet": {
            "data": {"type": "appScreenshotSets", "id": set_id}}}}})
    sid = res["data"]["id"]
    for op in res["data"]["attributes"]["uploadOperations"]:
        headers = {h["name"]: h["value"] for h in (op.get("requestHeaders") or [])}
        chunk = data[op["offset"]:op["offset"] + op["length"]]
        r = requests.request(op["method"], op["url"], headers=headers, data=chunk, timeout=300)
        if r.status_code >= 300:
            raise SystemExit("❌ 実体のアップロードが HTTP {}: {}".format(r.status_code, r.text[:300]))
    api("PATCH", "/appScreenshots/{}".format(sid), json={"data": {
        "type": "appScreenshots", "id": sid,
        "attributes": {"uploaded": True,
                       "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
    return sid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="*.png の入ったフォルダ（ファイル名順に並べる）")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.folder, "*.png")))
    if not files:
        raise SystemExit("❌ png が見つかりません: {}".format(args.folder))

    aid = A.app_id(BUNDLE_ID)
    ver = A._get("/apps/{}/appStoreVersions".format(aid), params={"limit": 1})["data"][0]
    vloc = [l for l in A._get(
        "/appStoreVersions/{}/appStoreVersionLocalizations".format(ver["id"]))["data"]
        if l["attributes"]["locale"] == LOCALE][0]
    sets = A._get("/appStoreVersionLocalizations/{}/appScreenshotSets".format(vloc["id"]))["data"]
    target = [s for s in sets if s["attributes"]["screenshotDisplayType"] == DISPLAY_TYPE]

    print("アプリ    : {}".format(BUNDLE_ID))
    print("バージョン: {} / {}".format(ver["attributes"]["versionString"],
                                   ver["attributes"]["appStoreState"]))
    print("種別      : {}".format(DISPLAY_TYPE))
    old = []
    if target:
        old = A._get("/appScreenshotSets/{}/appScreenshots".format(target[0]["id"]))["data"]
    print("既存      : {} 枚 ({})".format(
        len(old), ", ".join(o["attributes"].get("fileName") or "?" for o in old) or "なし"))
    print("入れる    : {} 枚".format(len(files)))
    for f in files:
        print("   {}".format(os.path.basename(f)))

    if not args.apply:
        print("\n下見だけです。実際に入れ替えるには --apply を付けてください。")
        return 0

    if not target:
        res = api("POST", "/appScreenshotSets", json={"data": {
            "type": "appScreenshotSets",
            "attributes": {"screenshotDisplayType": DISPLAY_TYPE},
            "relationships": {"appStoreVersionLocalization": {
                "data": {"type": "appStoreVersionLocalizations", "id": vloc["id"]}}}}})
        set_id = res["data"]["id"]
        print("\nセットを作りました: {}".format(set_id))
    else:
        set_id = target[0]["id"]
        for o in old:
            api("DELETE", "/appScreenshots/{}".format(o["id"]))
            print("  🗑 消した: {}".format(o["attributes"].get("fileName")))

    ids = []
    for f in files:
        sid = upload_one(set_id, f)
        ids.append(sid)
        print("  ⬆︎ 入れた: {}".format(os.path.basename(f)))

    # 並び順を明示する（作成順に依存させない）
    api("PATCH", "/appScreenshotSets/{}/relationships/appScreenshots".format(set_id),
        json={"data": [{"type": "appScreenshots", "id": i} for i in ids]})
    print("  ↕︎ 並び順を確定しました")

    done = A._get("/appScreenshotSets/{}/appScreenshots".format(set_id))["data"]
    print("\n結果: {} 枚".format(len(done)))
    for d in done:
        st = (d["attributes"].get("assetDeliveryState") or {}).get("state")
        print("   {}  {}".format(d["attributes"].get("fileName"), st))
    print("\n★ 提出（Submit for Review）はしていません。画面から人が行ってください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
