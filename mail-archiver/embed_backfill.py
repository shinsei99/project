#!/usr/bin/env python3
"""まだベクトルが無いメールを、ローカルモデルで一括ベクトル化して mail.db に保存する。

- 冪等・再開可（`embeddings` に無い分だけ処理）。初回は全55,000通ぶんで時間がかかる。
- 2時の取り込み後にも毎回呼ぶ → 新着ぶんだけベクトル化されて積み上がる。
- モデルもベクトルも**このMacの中だけ**（外部に出さない）。

使い方:
  /usr/bin/python3 embed_backfill.py            # 全部（無い分）を処理
  /usr/bin/python3 embed_backfill.py --limit 2000   # 今回はこの件数だけ（様子見）
"""
from __future__ import annotations

import argparse
import sys
import time

import config
import db
import embeddings as emb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="今回処理する上限（0=全部）")
    ap.add_argument("--batch", type=int, default=256, help="1バッチの件数")
    args = ap.parse_args()

    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)
    model = emb.MODEL_NAME

    done_start = db.embedding_count(conn, model)
    total_msgs = db.stats(conn)["messages"]
    remaining = total_msgs - done_start
    print("モデル: {} / 済 {:,} / 残り約 {:,} 通".format(model, done_start, max(0, remaining)),
          flush=True)
    if remaining <= 0:
        print("すべてベクトル化済み。", flush=True)
        return 0

    processed = 0
    t0 = time.time()
    while True:
        if args.limit and processed >= args.limit:
            break
        take = args.batch
        if args.limit:
            take = min(take, args.limit - processed)
        rows = db.messages_missing_embedding(conn, model, limit=take)
        if not rows:
            break
        subs = [r["subject"] or "" for r in rows]
        bodies = [r["body_text"] or "" for r in rows]
        vecs = emb.embed_passages(subs, bodies)
        items = [(rows[i]["id"], emb.to_bytes(vecs[i])) for i in range(len(rows))]
        db.store_embeddings(conn, model, emb.DIM, items)
        processed += len(rows)
        done = db.embedding_count(conn, model)
        rate = processed / max(1e-6, time.time() - t0)
        eta = (total_msgs - done) / max(1e-6, rate)
        print("  +{}  累計 {:,}/{:,}  {:.0f}通/秒  残り約 {:.0f}分".format(
            len(rows), done, total_msgs, rate, eta / 60), flush=True)

    print("完了: 今回 {:,} 通処理 / 済 {:,} 通（{:.1f}分）".format(
        processed, db.embedding_count(conn, model), (time.time() - t0) / 60), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
