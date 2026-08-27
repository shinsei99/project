#!/usr/bin/env python3
"""英語で届いたメールを日本語に訳して、日本語で検索できるようにする（2026-08-27・オーナー依頼）。

**なぜ要るのか（実測して分かったこと）**

  埋め込みモデルは `intfloat/multilingual-e5-small` で多言語対応しており、
  「PSA shipped」と**英語で聞けば**「Your PSA order has shipped」は 0.860 で出る。
  ところが**日本語で聞くと日本語メールが 0.88〜0.90 で上位を埋め**、
  探している英文メールは**上位800にすら入らない（圏外・スコア0.000）**。
  ＝「英語を認識できない」のではなく、**日本語クエリでの順位が低すぎる**のが原因。

  対策として、英語のみのメールに**日本語の訳文を持たせ、その訳文でベクトルを作る**。
  こうすると日本語クエリと日本語同士で当たるので順位が跳ね上がる。
  訳文は全文検索(FTS)にも入れるので、キーワード検索でも英文メールが出るようになる。

  英語のみのメールは **1,385通**（全55,496通の2.5%）なので、現実的な量。

**方針**
  - 原文は**絶対に消さない**。訳文は別テーブル（`translations`）に足すだけ
  - 訳すのは **件名＋本文の先頭**（検索に効くのはそこ。全文だと遅く、意味も薄まる）
  - claude CLI を使う（`ai_query.py` と同じ作法。[[feedback_claude_subprocess]]）
  - 中断・再開できる（訳し済みは飛ばす）

使い方:
  python3 translate_english.py --limit 5 --dry-run   # 訳文を見るだけ（保存しない）
  python3 translate_english.py --limit 50            # 50通だけ訳す
  python3 translate_english.py                       # 残り全部
  python3 translate_english.py --stats               # 進み具合
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
import db  # noqa: E402

CLAUDE_BIN = shutil.which("claude") or "/opt/homebrew/bin/claude"
MODEL = "claude-sonnet(cli)"
BODY_CHARS = 900           # 渡す本文の長さ。要約するので冒頭で足りる
BATCH = 5                  # 1回のclaude呼び出しで訳す通数
# ★1回の実行で訳す上限（2026-08-27夜の反省）。
#   1,384通を一気に流したら **67分で定額枠を使い切り、445通で力尽きて939通が全滅**した。
#   さらに枠切れ後も188回むだにclaudeを叩き続けた。小分けにすれば数晩で終わり、
#   同じ晩に動く他のジョブ（OCR・業務QA）から枠を奪わない。
DEFAULT_LIMIT = 150
ABORT_AFTER_FAILS = 3      # バッチが連続でこの回数こけたら、その回は諦める（枠切れとみなす）

_CJK = re.compile(r"[぀-ヿ一-鿿]")
_LATIN = re.compile(r"[A-Za-z]")

SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
  message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
  subject_ja TEXT,
  body_ja    TEXT,
  model      TEXT NOT NULL,
  made_at    TEXT NOT NULL
);
"""


def is_english(subject: str, body: str) -> bool:
    """日本語がほぼ無く、英字が十分にあるものを「英語のみ」とみなす。"""
    t = (subject or "") + " " + (body or "")[:1200]
    return len(_CJK.findall(t)) == 0 and len(_LATIN.findall(t)) >= 20


def ensure_schema(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def pending(conn, limit: int = 0):
    """まだ訳していない英語メールを返す。"""
    sql = ("SELECT m.id, m.subject, COALESCE(m.body_text,'') AS body FROM messages m "
           "LEFT JOIN translations t ON t.message_id = m.id WHERE t.message_id IS NULL")
    rows = [r for r in conn.execute(sql) if is_english(r["subject"], r["body"])]
    return rows[:limit] if limit else rows


def _run_claude(prompt: str, timeout: int = 420) -> str:
    """claude CLI を呼ぶ。env は絞らない・絶対パス（既知の罠）。"""
    proc = subprocess.run([CLAUDE_BIN, "-p", prompt], capture_output=True, text=True,
                          timeout=timeout, cwd=os.path.dirname(os.path.abspath(__file__)))
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude が失敗しました")[:200])
    return (proc.stdout or "").strip()


def _parse_json(text: str):
    """```json …``` や前置きが付いていても JSON 配列を取り出す。"""
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def translate_batch(rows) -> dict:
    """{message_id: (subject_ja, body_ja)}"""
    items = [{"id": r["id"], "subject": (r["subject"] or "")[:200],
              "body": " ".join((r["body"] or "").split())[:BODY_CHARS]} for r in rows]
    prompt = (
        "次は英語で届いたメールです。**日本語で検索できるようにするための要約**を作ってください。\n"
        "・逐語訳はしない。**何のメールか**が日本語で分かることが目的\n"
        "・件名は日本語に訳す（原題の意味が分かるように）\n"
        "・本文は **150〜300字の日本語**にまとめる。書き出しは「〜のメール。」で何の用件か明示\n"
        "・**金額・日付・注文番号・認証番号・会社名・商品ジャンルは必ず残す**（検索の手がかり）\n"
        "・同じ形の明細が並ぶ場合は「ポケモンカード50点（PSA鑑定済み）」のように件数でまとめる\n"
        "・送料・支払方法・発送/出荷・返金といった**動作を表す語は日本語で明示**する\n"
        "・★**書かれていない事柄には触れない**（「発送の案内はありません」のような否定文を書かない。\n"
        "  検索では否定でも語が拾われてしまい、無関係なメールが引っかかる）\n"
        "・出力は JSON 配列だけ。説明や前置きは書かない\n"
        '・形式: [{"id":123,"subject_ja":"…","body_ja":"…"}, …]\n\n'
        + json.dumps(items, ensure_ascii=False)
    )
    data = _parse_json(_run_claude(prompt))
    out = {}
    for d in data or []:
        try:
            out[int(d["id"])] = (str(d.get("subject_ja") or ""), str(d.get("body_ja") or ""))
        except Exception:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="1回に訳す上限（既定 %d。0で全部）" % DEFAULT_LIMIT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--fts-backfill", action="store_true",
                    help="訳し済みの全件について、全文検索の索引に訳文を入れ直す")
    args = ap.parse_args()

    conn = db.connect(config.DB_PATH)
    ensure_schema(conn)

    if args.fts_backfill:
        ids = [r[0] for r in conn.execute("SELECT message_id FROM translations")]
        n = 0
        for mid in ids:
            try:
                if db.fts_apply_translation(conn, mid):
                    n += 1
            except Exception:
                pass
        conn.commit()
        print("全文検索の索引に訳文を入れ直した: %d 件" % n)
        return 0

    if args.stats:
        done = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
        todo = len(pending(conn))
        print("訳し済み %d 通 / これから %d 通" % (done, todo))
        return 0

    rows = pending(conn, args.limit)
    print("これから訳す: %d 通（1回 %d 通ずつ）" % (len(rows), BATCH), flush=True)
    ok = ng = fail_streak = 0
    t0 = time.time()
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        try:
            got = translate_batch(chunk)
            fail_streak = 0
        except Exception as e:
            ng += len(chunk)
            fail_streak += 1
            print("  失敗（%d通）: %s" % (len(chunk), str(e)[:120]), flush=True)
            if fail_streak >= ABORT_AFTER_FAILS:
                print("  ★claude が連続 %d 回こけた（定額枠切れの可能性）。今回はここで終える。"
                      "訳せていない分は次回そのまま続きから拾う。" % fail_streak, flush=True)
                break
            continue
        for r in chunk:
            pair = got.get(r["id"])
            if not pair or not (pair[0] or pair[1]):
                ng += 1
                continue
            if args.dry_run:
                print("  [%s] %s\n        → %s\n        %s" % (
                    r["id"], (r["subject"] or "")[:60], pair[0][:60], pair[1][:100]), flush=True)
            else:
                conn.execute(
                    "INSERT INTO translations(message_id, subject_ja, body_ja, model, made_at) "
                    "VALUES (?,?,?,?,datetime('now')) ON CONFLICT(message_id) DO UPDATE SET "
                    "subject_ja=excluded.subject_ja, body_ja=excluded.body_ja, "
                    "model=excluded.model, made_at=excluded.made_at",
                    (r["id"], pair[0], pair[1], MODEL))
                try:
                    db.fts_apply_translation(conn, r["id"])   # キーワード検索にも訳文を載せる
                except Exception:
                    pass
            ok += 1
        if not args.dry_run:
            conn.commit()
        done = i + len(chunk)
        rate = done / max(1e-6, time.time() - t0)
        print("  %d/%d 済（%.1f通/秒・残り約%.0f分）" % (
            done, len(rows), rate, (len(rows) - done) / max(rate, 1e-6) / 60), flush=True)

    print("\n%s 訳せた %d 通 / 失敗 %d 通 / %.1f分" % (
        "[試算]" if args.dry_run else "[実行]", ok, ng, (time.time() - t0) / 60))
    if not args.dry_run and ok:
        print("★次にやること: python3 embed_backfill.py --retranslated  （訳文でベクトルを作り直す）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
