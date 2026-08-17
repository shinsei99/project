"""身分証・名刺の画像を自動削除する。

    /usr/bin/python3 purge.py           … 返却から30日を過ぎた画像を消す
    /usr/bin/python3 purge.py --days 7  … 期間を変える
    /usr/bin/python3 purge.py --dry-run … 消さずに対象だけ出す

launchd で1日1回動かす想定（_launchd/com.shinsei.keyline-purge.plist）。

★消す順序が大事。
  ファイルを消してから DB の id_image_purged_at を立てる。
  逆にすると、途中で落ちたときに「DBは消したことになっているのに実体は残る」
  ——気づかないまま個人情報が残り続ける——という最悪の形になる。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import db as dbmod
import ocr

DATA_DIR = Path(__file__).resolve().parent / "data"


def purge_orphans(data_dir: Path, older_than_hours: int = 24) -> int:
    """どの貸出にも紐づかない画像を消す。

    撮影だけして貸出を確定しなかった場合に生まれる。放っておくと
    「誰のものか分からない身分証の画像」が溜まり続ける。
    """
    con = dbmod.connect()
    known = {r["id_image_path"] for r in con.execute(
        "SELECT id_image_path FROM checkout_logs WHERE id_image_path IS NOT NULL")}
    con.close()

    import time
    cutoff = time.time() - older_than_hours * 3600
    removed = 0
    root = data_dir / "id_images"
    if not root.exists():
        return 0
    for f in root.rglob("*.jpg"):
        rel = str(f.relative_to(data_dir))
        if rel in known:
            continue
        if f.stat().st_mtime > cutoff:
            continue        # 撮ったばかりのものは、まだ貸出画面で使われている可能性がある
        f.unlink(missing_ok=True)
        removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="身分証画像の自動削除")
    ap.add_argument("--days", type=int, default=30, help="返却から何日で消すか（既定30）")
    ap.add_argument("--dry-run", action="store_true", help="消さずに対象を表示する")
    args = ap.parse_args()

    con = dbmod.get_db()
    cutoff = dbmod.ts_plus(days=-args.days)

    rows = con.execute(
        """SELECT c.id, c.id_image_path, c.returned_at, a.name
             FROM checkout_logs c JOIN assets a ON a.id = c.asset_id
            WHERE c.id_image_path IS NOT NULL AND c.id_image_purged_at IS NULL
              AND c.returned_at IS NOT NULL AND c.returned_at < ?
            ORDER BY c.returned_at""",
        (cutoff,),
    ).fetchall()

    if args.dry_run:
        print(f"削除対象: {len(rows)}件（返却が {dbmod.fmt_local(cutoff)} より前）")
        for r in rows:
            print(f"  {dbmod.fmt_local(r['returned_at'])}  {r['name']}  {r['id_image_path']}")
        con.close()
        return 0

    n = ocr.purge_old_images(con, DATA_DIR, args.days)
    orphans = purge_orphans(DATA_DIR)
    con.close()

    print(f"身分証画像を {n}件 削除しました（返却から{args.days}日超）")
    if orphans:
        print(f"貸出に紐づかない画像を {orphans}件 削除しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
