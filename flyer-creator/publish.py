"""site/ をサーバーへ上げる。

    .venv/bin/python publish.py            # 差分だけ上げる
    .venv/bin/python publish.py --all      # 全部上げ直す

接続情報は theta-viewer/server/ftp-config.json（gitignore対象）から読む。

二点はまり所がある。
  - Claude Code から動かすときは **サンドボックスを外す**。FTPはデータ用に別の接続を
    張るので、塞がれていると転送だけが無言で止まる
  - サーバーのPASV応答が**内部IPを返す**ので、そのまま繋ぎに行くと届かない。
    makepasv() を上書きして接続先ホストを保つ
"""
from __future__ import annotations

import ftplib
import hashlib
import json
import sys
import time
from pathlib import Path

SITE = Path(__file__).parent / "site"
REMOTE = "/www/htdocs/slowlife"
CONFIG = Path("/Users/apple/theta-viewer/server/ftp-config.json")
STATE = Path(__file__).parent / "data" / "published.json"


class FTP(ftplib.FTP):
    def makepasv(self):
        # PASVが内部IPを返すので、接続に使ったホストの方を採る
        _, port = super().makepasv()
        return self.host, port


def digests() -> dict:
    out = {}
    for p in sorted(SITE.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(SITE).as_posix()
            out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
    return out


def ensure_dir(ftp: FTP, remote_dir: str) -> None:
    path = ""
    for part in remote_dir.strip("/").split("/"):
        path += "/" + part
        try:
            ftp.mkd(path)
        except ftplib.error_perm:
            pass          # 既にある


def main() -> int:
    if not SITE.is_dir():
        print("site/ がありません。先に build_kato.py を動かしてください")
        return 1
    if not CONFIG.exists():
        print(f"FTPの接続情報がありません: {CONFIG}")
        print("別のMacの同じ場所からコピーしてください"
              "（公開リポジトリに入れないよう gitignore してあります）。")
        return 1
    cfg = json.loads(CONFIG.read_text())

    now = digests()
    before = json.loads(STATE.read_text()) if STATE.exists() else {}
    force = "--all" in sys.argv
    targets = sorted(now) if force else sorted(k for k, v in now.items() if before.get(k) != v)

    if not targets:
        print("変わったファイルはありません")
        return 0
    print(f"{len(targets)}ファイルを上げます（全{len(now)}）")

    # データ接続がよく拒否される。PASVで案内されるポートの一部が外から届いていないらしく、
    # 同じファイルでも繋ぎ直すと別のポートになって通る。1ファイルずつ粘る。
    done: set = set()
    made: set = set()
    ftp = None
    for rel in targets:
        for attempt in range(1, 9):
            try:
                if ftp is None:
                    ftp = FTP(cfg["host"], cfg["user"], cfg["pass"], timeout=45)
                    ftp.set_pasv(True)
                remote = f"{REMOTE}/{rel}"
                parent = remote.rsplit("/", 1)[0]
                if parent not in made:
                    ensure_dir(ftp, parent)
                    made.add(parent)
                with (SITE / rel).open("rb") as f:
                    ftp.storbinary(f"STOR {remote}", f)
                done.add(rel)
                print("  ", rel)
                break
            except Exception as e:
                try:
                    if ftp:
                        ftp.close()
                except Exception:
                    pass
                ftp = None                       # next attempt reconnects
                if attempt == 8:
                    print(f"   × {rel}（{attempt}回試して駄目でした: {e}）")
                else:
                    time.sleep(2)
    if ftp:
        try:
            ftp.quit()
        except Exception:
            pass

    if len(done) < len(targets):
        print("上げきれませんでした:", "、".join(r for r in targets if r not in done))
        return 1

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(now, ensure_ascii=False, indent=1))
    print("完了 https://daikyocorp.co.jp/slowlife/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
