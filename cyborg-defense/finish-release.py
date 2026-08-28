#!/usr/bin/env python3
"""App 記録ができたあとを、**1コマンドで審査提出の直前まで**進める。

    python3 finish-release.py            # 何をするかだけ表示（変更しない）
    python3 finish-release.py --apply    # 実行する

やること（上から順に。途中で失敗したら止まる）:

  1. App 記録の確認（無ければ、作るための値を出して終わる）
  2. ipa の検証（`altool --validate-app`）
  3. ipa のアップロード（`altool --upload-app`）※同じ build 番号が既にあれば飛ばす
  4. ビルドの処理待ち（App Store 側の処理。十数分かかる）
  5. バージョン 1.0 へ**ビルドをひも付け**
  6. 文言の流し込み（`push-metadata.py --apply`）
  7. スクリーンショットの流し込み（iPhone / iPad）
  8. 残っている「画面でしかできないこと」を並べて終わる

**App 記録の新規作成だけは API で行えない**（`POST /v1/apps` が
`The resource 'apps' does not allow 'CREATE'` を返す。2026-08-28 実測）。
そこだけは人が App Store Connect の画面で作る。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # 直下の appstore_api.py を使う
import appstore_api as A                            # noqa: E402

BUNDLE_ID = "com.daikyo.cyborgdefense"
APP_NAME = "サイボーグ防衛軍"
SKU = "cyborgdefense2026"
IPA = os.path.join(HERE, "build", "export", "App.ipa")
BUILD_NUMBER = "1"
VERSION_STRING = "1.0"
KEY_ID = "35U53KWY5J"
ISSUER_ID = "e55bd1b7-1481-4ee1-9c7e-8caac82815b1"


def say(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str]) -> int:
    say("  $ " + " ".join(cmd))
    return subprocess.call(cmd)


def api(method: str, path: str, payload: dict) -> None:
    req = urllib.request.Request(
        A.BASE + path, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + A.token(), "Content-Type": "application/json"},
        method=method)
    try:
        urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        raise SystemExit("❌ {} {} → {}\n{}".format(method, path, e.code, e.read().decode()[:400]))


def need_app_record() -> str:
    aid = A.app_id(BUNDLE_ID)
    if aid:
        return aid
    say("""
❌ App Store Connect に App 記録がありません。**ここだけは人の操作が要ります。**

   「マイApp」→「＋」→「新規App」で次を入れてください（3分）:

     プラットフォーム : iOS
     名前             : {name}
     プライマリ言語   : 日本語
     バンドルID       : {bundle}
     SKU              : {sku}
     ユーザーアクセス : 制限なし

   作ったら、このコマンドをもう一度実行すれば最後まで進みます。
   （API では作れません。`POST /v1/apps` は "does not allow CREATE" を返します）
""".format(name=APP_NAME, bundle=BUNDLE_ID, sku=SKU))
    raise SystemExit(2)


def wait_for_build(aid: str, timeout_min: int = 40) -> str:
    """アップロードしたビルドが処理し終わるまで待って、そのビルドIDを返す。"""
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        data = A._get("/builds", {"filter[app]": aid, "limit": 200})["data"]
        for b in data:
            attr = b.get("attributes", {})
            if str(attr.get("version")) == BUILD_NUMBER:
                state = attr.get("processingState")
                if state == "VALID":
                    say("  ビルド {} … VALID".format(BUILD_NUMBER))
                    return b["id"]
                if state in ("INVALID", "FAILED"):
                    raise SystemExit("❌ ビルド {} が {} です。中身を直して build 番号を上げ直すこと"
                                     .format(BUILD_NUMBER, state))
                say("  ビルド {} … {}（処理中。30秒ごとに見ます）".format(BUILD_NUMBER, state))
                break
        else:
            say("  まだ App Store 側に現れていません（アップロード直後は十数分かかります）")
        time.sleep(30)
    raise SystemExit("❌ {}分待ってもビルドが VALID になりませんでした".format(timeout_min))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実際に実行する（既定は表示のみ）")
    args = ap.parse_args()

    if not os.path.exists(IPA):
        raise SystemExit("❌ ipa がありません: {}\n   RELEASE.md の Archive / Export をやり直してください".format(IPA))

    say("■ 1. App 記録の確認")
    aid = need_app_record()
    say("  OK: {} (id {})".format(BUNDLE_ID, aid))

    already = [b for b in A.builds(BUNDLE_ID, aid=aid) if b["version"] == BUILD_NUMBER]
    if already:
        say("■ 2-4. build {} は既に登録済み（{}）。アップロードは飛ばします"
            .format(BUILD_NUMBER, already[0]["state"]))
    elif not args.apply:
        say("■ 2-4.（--apply で）検証 → アップロード → 処理待ち")
    else:
        say("■ 2. 検証")
        if run(["xcrun", "altool", "--validate-app", "-f", IPA, "-t", "ios",
                "--apiKey", KEY_ID, "--apiIssuer", ISSUER_ID]) != 0:
            raise SystemExit("❌ 検証で落ちました。アップロードしても弾かれます")
        say("■ 3. アップロード")
        if run(["xcrun", "altool", "--upload-app", "-f", IPA, "-t", "ios",
                "--apiKey", KEY_ID, "--apiIssuer", ISSUER_ID]) != 0:
            raise SystemExit("❌ アップロードに失敗しました")
        say("■ 4. ビルドの処理待ち")
        wait_for_build(aid)

    if not args.apply:
        say("\n（表示のみ。実行するには --apply を付けてください）")
        return 0

    say("■ 5. バージョン {} へビルドをひも付け".format(VERSION_STRING))
    build_id = wait_for_build(aid)
    vers = A._get("/apps/{}/appStoreVersions".format(aid), {"limit": 10})["data"]
    target = next((v for v in vers
                   if v["attributes"].get("versionString") == VERSION_STRING), None)
    if target is None:
        raise SystemExit("❌ バージョン {} が見つかりません（App 記録の作成直後は自動で作られます）"
                         .format(VERSION_STRING))
    api("PATCH", "/appStoreVersions/{}/relationships/build".format(target["id"]),
        {"data": {"type": "builds", "id": build_id}})
    say("  ひも付け完了")

    say("■ 6. 文言の流し込み")
    if run([sys.executable, os.path.join(HERE, "push-metadata.py"), "--apply"]) != 0:
        raise SystemExit("❌ 文言の流し込みに失敗しました")

    say("■ 7. スクリーンショットの流し込み")
    for device, folder in (("iphone", "screenshots/upload/iphone"),
                           ("ipad", "screenshots/upload/ipad")):
        if run([sys.executable, os.path.join(HERE, "push-screenshots.py"),
                os.path.join(HERE, folder), "--device", device, "--apply"]) != 0:
            raise SystemExit("❌ スクリーンショット（{}）の流し込みに失敗しました".format(device))

    say("""
■ 8. ここから先は App Store Connect の画面でしかできません（オーナー）

   - 価格          : 無料
   - App のプライバシー : 「データを収集していません」
   - 年齢制限      : 暴力表現は「まれ／軽度の漫画・ファンタジー」、ほかは「なし」（4+想定）
   - 内容が揃っているか確認して **「審査へ提出」**

   状態の確認: python3 ../appstore_api.py --review {bundle}
""".format(bundle=BUNDLE_ID))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
