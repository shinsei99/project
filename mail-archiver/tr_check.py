#!/usr/bin/env python3
"""訳文でベクトルを作り直したあと、日本語クエリでの順位が上がったかを見る確認用。

  .venv-embed/bin/python embed_backfill.py --retranslated   # 先にこれ
  .venv-embed/bin/python tr_check.py 26996                  # そのあとこれ

torch を持っているのは `.venv-embed` だけなので、必ずそちらの python で叩く。
"""
import sys

sys.path.insert(0, ".")

import config  # noqa: E402
import db  # noqa: E402
import semantic  # noqa: E402

QUERIES = [
    "psaから 家に発送したというメール 今月のもの",
    "PSAの支払い明細 レシート",
    "英語で送られてるメール psaから 家に発送したというメール 今月のもの",
]


def main() -> int:
    mid = int(sys.argv[1]) if len(sys.argv) > 1 else 26996
    conn = db.connect(config.DB_PATH)
    row = conn.execute("SELECT subject FROM messages WHERE id=?", (mid,)).fetchone()
    if not row:
        print("id %d が見つかりません" % mid)
        return 1
    tr = conn.execute("SELECT subject_ja FROM translations WHERE message_id=?", (mid,)).fetchone()
    print("原文: %s" % row["subject"])
    print("訳文: %s" % (tr["subject_ja"] if tr else "（未訳）"))
    print("\n■ 日本語クエリでの順位（上位800まで見る）")
    for q in QUERIES:
        ids, sc = semantic.search(conn, q, top=800)
        rank = {m: n + 1 for n, m in enumerate(ids)}
        print("   %-42s -> 順位 %-6s スコア %.3f"
              % (q[:42], rank.get(mid, "圏外"), sc.get(mid, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
