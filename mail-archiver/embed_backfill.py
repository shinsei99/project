#!/usr/bin/env python3
"""まだベクトルが無いメールを、ローカルモデルで一括ベクトル化して mail.db に保存する。

- 冪等・再開可（`embeddings` に無い分だけ処理）。初回は全55,000通ぶんで時間がかかる。
- 2時の取り込み後にも毎回呼ぶ → 新着ぶんだけベクトル化されて積み上がる。
- モデルもベクトルも**このMacの中だけ**（外部に出さない）。

使い方:
  /usr/bin/python3 embed_backfill.py            # 全部（無い分）を処理
  /usr/bin/python3 embed_backfill.py --limit 2000   # 今回はこの件数だけ（様子見）
  /usr/bin/python3 embed_backfill.py --retranslated  # 訳した英語メールを訳文で作り直す

★ torch を持っているのは専用 venv だけ。`.venv-embed/bin/python embed_backfill.py …` で叩く
  （閲覧UIの `/usr/bin/python3` には sentence-transformers を載せていない）。
"""
from __future__ import annotations

import argparse
import sys
import time

import config
import db
import embeddings as emb


def retranslated(conn, model: str, args) -> int:
    """訳文でベクトルを作り直す。

    日本語クエリと日本語同士で当たるようにするのが目的なので、
    ベクトルの中身は**原文ではなく訳文**にする（原文は messages にそのまま残る）。
    """
    todo = len(db.messages_retranslated(conn, model, limit=10 ** 9))
    print("訳文で作り直す: {:,} 通".format(todo), flush=True)
    if not todo:
        print("作り直す対象なし。先に translate_english.py で訳してください。", flush=True)
        return 0

    processed = 0
    t0 = time.time()
    while True:
        if args.limit and processed >= args.limit:
            break
        take = args.batch
        if args.limit:
            take = min(take, args.limit - processed)
        rows = db.messages_retranslated(conn, model, limit=take)
        if not rows:
            break
        vecs = emb.embed_passages([r["subject_ja"] or "" for r in rows],
                                  [r["body_ja"] or "" for r in rows])
        db.store_embeddings(conn, model, emb.DIM,
                            [(rows[i]["id"], emb.to_bytes(vecs[i])) for i in range(len(rows))])
        processed += len(rows)
        rate = processed / max(1e-6, time.time() - t0)
        print("  +{}  {:,}/{:,}  {:.0f}通/秒".format(len(rows), processed, todo, rate), flush=True)

    print("完了: {:,} 通を訳文で作り直した（{:.1f}分）".format(
        processed, (time.time() - t0) / 60), flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="今回処理する上限（0=全部）")
    ap.add_argument("--batch", type=int, default=256, help="1バッチの件数")
    ap.add_argument("--retranslated", action="store_true",
                    help="translate_english.py で訳した英語メールを、訳文でベクトル化し直す")
    args = ap.parse_args()

    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)
    model = emb.MODEL_NAME

    if args.retranslated:
        return retranslated(conn, model, args)

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
