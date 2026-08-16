"""out/ をサーバーへ上げる。

    python3 publish.py            # 差分だけ上げる
    python3 publish.py --all      # 全部上げ直す

公開先: https://daikyocorp.co.jp/ai-lab/
接続情報は theta-viewer/server/ftp-config.json（gitignore対象）から読む。

**flyer-creator/publish.py と同じはまり所が2つある**（あちらの記録から流用）。
  - Claude Code から動かすときは **サンドボックスを外す**。FTPはデータ用に別の接続を
    張るので、塞がれていると転送だけが無言で止まる
  - サーバーのPASV応答が**内部IPを返す**ので、そのまま繋ぎに行くと届かない。
    makepasv() を上書きして接続先ホストを保つ

先に `npm run build` を済ませておくこと（out/ が無ければ止まる）。
"""
from __future__ import annotations

import ftplib
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "out"
REMOTE = "/www/htdocs/ai-lab"
CONFIG = Path("/Users/apple/theta-viewer/server/ftp-config.json")
STATE = Path(__file__).parent / ".published.json"


class FTP(ftplib.FTP):
    def makepasv(self):
        # PASVが内部IPを返すので、接続に使ったホストの方を採る
        _, port = super().makepasv()
        return self.host, port


def digests() -> dict:
    out = {}
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(OUT).as_posix()
            out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
    return out


def ensure_dir(ftp: FTP, remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    path = ""
    for part in parts:
        path += "/" + part
        try:
            ftp.mkd(path)
        except ftplib.error_perm:
            pass  # 既にある


def main() -> int:
    if not OUT.exists():
        print("out/ がありません。先に `npm run build` を実行してください。", file=sys.stderr)
        return 1
    if not CONFIG.exists():
        print(f"FTP設定がありません: {CONFIG}", file=sys.stderr)
        return 1

    cfg = json.loads(CONFIG.read_text())
    now = digests()
    before = {}
    if STATE.exists() and "--all" not in sys.argv:
        before = json.loads(STATE.read_text())

    targets = [rel for rel, h in now.items() if before.get(rel) != h]
    if not targets:
        print("変更なし。上げるものはありません。")
        return 0

    print(f"{len(targets)} 件を転送します（全 {len(now)} 件）")

    ftp = FTP(cfg["host"], timeout=60)
    ftp.login(cfg["user"], cfg["pass"])
    ftp.set_pasv(True)
    made: set[str] = set()

    for i, rel in enumerate(targets, 1):
        remote_path = f"{REMOTE}/{rel}"
        remote_dir = remote_path.rsplit("/", 1)[0]
        if remote_dir not in made:
            ensure_dir(ftp, remote_dir)
            made.add(remote_dir)
        with (OUT / rel).open("rb") as f:
            ftp.storbinary(f"STOR {remote_path}", f)
        print(f"  [{i}/{len(targets)}] {rel}")

    ftp.quit()
    STATE.write_text(json.dumps(now, indent=2))
    print("\n完了: https://daikyocorp.co.jp/ai-lab/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
