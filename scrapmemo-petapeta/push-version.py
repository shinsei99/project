#!/usr/bin/env python3
"""スクラップメモ 1.0.5 を App Store Connect に用意する。

  --dry-run（既定）: 何をするか出すだけ
  --apply         : バージョン作成／最新情報の書き込み／build のひも付け

提出（Submit for Review）はしない。提出は人が画面で行う。
"""
from __future__ import annotations
import argparse
import os
import re
import sys

ROOT = "/Users/apple"
sys.path.insert(0, ROOT)
import appstore_api as A  # noqa: E402
import requests  # noqa: E402

BUNDLE = "com.shinsei99.scrapmemo"
LOCALE = "ja"
VERSION = "1.0.5"
BUILD = "9"
NOTES_MD = os.path.join(ROOT, "scrapmemo-petapeta", "RELEASE_NOTES.md")


def whats_new() -> str:
    text = open(NOTES_MD, encoding="utf-8").read()
    m = re.search(r"^## 1\.0\.5 .*?\n(.*?)(?=^## )", text, re.S | re.M)
    if not m:
        raise SystemExit("❌ RELEASE_NOTES.md に 1.0.5 の節が無い")
    fence = re.search(r"```\n(.*?)```", m.group(1), re.S)
    if not fence:
        raise SystemExit("❌ 1.0.5 の節にコードフェンスが無い")
    return fence.group(1).rstrip("\n")


def _req(method: str, path: str, payload: dict | None = None) -> dict:
    r = requests.request(
        method, "{}{}".format(A.BASE, path),
        headers={"Authorization": "Bearer {}".format(A.token()),
                 "Content-Type": "application/json"},
        json=payload, timeout=60)
    if r.status_code not in (200, 201, 204):
        raise SystemExit("❌ {} {} が HTTP {}\n{}".format(method, path, r.status_code, r.text[:800]))
    return r.json() if r.text.strip() else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    note = whats_new()
    print("「このバージョンの新機能」({} 字):\n---\n{}\n---\n".format(len(note), note))
    if len(note) > 4000:
        raise SystemExit("❌ 4000字を超えている")

    aid = A.app_id(BUNDLE)
    if not aid:
        raise SystemExit("❌ アプリが見つからない")

    # 1) 1.0.5 のバージョンがあるか
    vers = A._get("/apps/{}/appStoreVersions".format(aid), params={"limit": 10})["data"]
    for v in vers:
        print("  既存: {} {}".format(v["attributes"].get("versionString"),
                                     v["attributes"].get("appStoreState")))
    target = next((v for v in vers if v["attributes"].get("versionString") == VERSION), None)

    if target is None:
        print("\n★ バージョン {} を新規作成する".format(VERSION))
        if apply:
            target = _req("POST", "/appStoreVersions", {
                "data": {
                    "type": "appStoreVersions",
                    "attributes": {"platform": "IOS", "versionString": VERSION},
                    "relationships": {"app": {"data": {"type": "apps", "id": aid}}},
                }})["data"]
            print("   作成: id={}".format(target["id"]))
        else:
            return 0
    else:
        print("\n= バージョン {} は既にある（state={}）".format(
            VERSION, target["attributes"].get("appStoreState")))

    vid = target["id"]

    # 2) ja の「このバージョンの新機能」
    locs = A._get("/appStoreVersions/{}/appStoreVersionLocalizations".format(vid))["data"]
    loc = next((l for l in locs if l["attributes"].get("locale") == LOCALE), None)
    if loc is None:
        raise SystemExit("❌ {} のローカライズが無い".format(LOCALE))
    old = (loc["attributes"].get("whatsNew") or "").strip()
    if old == note.strip():
        print("= 最新情報 変更なし")
    else:
        print("★ 最新情報 {} 字 → {} 字".format(len(old), len(note)))
        if apply:
            _req("PATCH", "/appStoreVersionLocalizations/{}".format(loc["id"]), {
                "data": {"type": "appStoreVersionLocalizations", "id": loc["id"],
                         "attributes": {"whatsNew": note}}})
            print("   書き込んだ")

    # 3) build 9 をひも付ける
    raw = A._get("/builds", {"filter[app]": aid, "filter[version]": BUILD, "limit": 5})["data"]
    b9 = raw[0] if raw else None
    if not b9:
        print("… build {} はまだ App Store Connect に出てきていない（処理中）".format(BUILD))
        return 0
    state = b9["attributes"].get("processingState")
    print("build {} の状態: {}".format(BUILD, state))
    if state != "VALID":
        print("… VALID になるまで待つ")
        return 0

    cur = A._get("/appStoreVersions/{}/build".format(vid)).get("data")
    if cur and cur.get("id") == b9["id"]:
        print("= build {} は既にひも付いている".format(BUILD))
    else:
        print("★ build {} をひも付ける".format(BUILD))
        if apply:
            _req("PATCH", "/appStoreVersions/{}/relationships/build".format(vid),
                 {"data": {"type": "builds", "id": b9["id"]}})
            print("   ひも付けた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
