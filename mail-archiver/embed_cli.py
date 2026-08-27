#!/usr/bin/env python3
"""質問文を1本ベクトル化して base64(float32) で標準出力に返す（.venv-embed で実行）。

閲覧UI（system python / streamlit）は重い torch を持たないので、質問のベクトル化だけ
このCLIを subprocess で呼ぶ。文書側の一括処理は embed_backfill.py（同じ venv）。
"""
import base64
import sys

import embeddings as emb


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    vec = emb.embed_query(text)
    sys.stdout.write(base64.b64encode(vec.tobytes()).decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
