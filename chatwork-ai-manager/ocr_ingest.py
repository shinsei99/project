#!/usr/bin/env python3
"""スキャン画像PDFを claude vision で OCR して索引化する（バックグラウンド長時間ジョブ）。

- テキスト層のある PDF は mtime で即スキップ（既に text 取込済み）。
- テキスト層の無い（＝画像）PDF だけを OCR して取込む。
- 中断・再開可（OCR済みは content_hash/mtime で次回スキップ）。
- claude vision を1ファイル1回（先頭 max_pages ページ）呼ぶため時間がかかる。

使い方:
  python3 ocr_ingest.py                 # secrets の knowledge_source_dir 配下の PDF を OCR
  python3 ocr_ingest.py --dir "<folder>"
  python3 ocr_ingest.py --limit 20      # 対象の「先頭N件」だけ見る（テスト用）
  python3 ocr_ingest.py --max-new 300   # ★実際に処理できた件数でN件に達したら終了（夜間バッチ用）
  python3 ocr_ingest.py --max-minutes 300  # ★N分で切り上げる（業務時間に食い込ませない）
  python3 ocr_ingest.py --max-pages 10
  python3 ocr_ingest.py --list batch.txt   # 対象PDFのフルパスを1行1件で指定（全件走査をスキップ）
  python3 ocr_ingest.py --retry-skipped    # 「認識なし」で見送った分をもう一度だけ試す

★ --limit と --max-new は別物（夜間バッチでは --max-new を使う）:
  --limit は「対象リストの先頭N件」を切り出すだけなので、毎晩流すと**同じ先頭N件を
  舐めて終わり**で前に進まない。--max-new は取込済みを飛ばしながら進み、
  **新しく処理できた件数**がNに達したら止まる。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.migrate import migrate  # noqa: E402
from services import config, knowledge  # noqa: E402
from services.settings import set_state  # noqa: E402

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# OCRしても文字が取れなかったファイルの記録。
# なぜ要るか: knowledge.ingest_file() は「テキスト抽出なし」のとき DB に何も書かない。
# つまり記録しないと**毎晩まったく同じファイルを再OCRし続ける**（定額枠の無駄）。
SKIP_PATH = os.path.join(APP_DIR, "logs", "ocr_skiplist.json")
SKIP_MAX_TRIES = 2          # 同じ内容で2回ダメなら以後は飛ばす（mtimeが変われば再挑戦）
ABORT_AFTER_FAILS = 5       # 連続失敗がこの数に達したら中断（CLIの枠切れ・環境異常とみなす）


def _load_skiplist() -> dict:
    try:
        with open(SKIP_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_skiplist(data: dict) -> None:
    os.makedirs(os.path.dirname(SKIP_PATH), exist_ok=True)
    tmp = SKIP_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SKIP_PATH)      # 途中で落ちても壊れた JSON を残さない


def _skip_known(skips: dict, path: str, mtime: float) -> bool:
    e = skips.get(path)
    if not e:
        return False
    if abs(float(e.get("mtime", -1)) - mtime) >= 1:
        return False                # ファイルが差し替わったので、もう一度試す
    return int(e.get("tries", 0)) >= SKIP_MAX_TRIES


def _record_skip(skips: dict, path: str, mtime: float, reason: str) -> None:
    e = skips.get(path) or {}
    same = abs(float(e.get("mtime", -1)) - mtime) < 1
    skips[path] = {
        "mtime": mtime,
        "tries": (int(e.get("tries", 0)) + 1) if same else 1,
        "reason": reason,
        "last": datetime.now().isoformat(timespec="seconds"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--limit", type=int, help="対象リストの先頭N件だけ見る（テスト用）")
    ap.add_argument("--max-new", type=int, help="実際に処理できた件数がNに達したら終了（夜間バッチ用）")
    ap.add_argument("--max-minutes", type=float, help="N分経過したら安全に終了")
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--list", help="対象PDFのフルパスを1行1件で書いたファイル（指定時はフォルダ走査をしない）")
    ap.add_argument("--retry-skipped", action="store_true",
                    help="「認識なし」で見送った分の回数をリセットして、もう一度試す")
    args = ap.parse_args()
    migrate()

    root = args.dir or config.get("knowledge_source_dir")
    if not root or not os.path.isdir(root):
        print(f"フォルダにアクセスできません: {root}（ターミナルから/FDA必要）")
        sys.exit(1)

    if args.list:
        with open(args.list, encoding="utf-8") as f:
            pdfs = [line.strip() for line in f if line.strip()]
        pdfs = [p for p in pdfs if os.path.isfile(p)]
    else:
        pdfs = [p for p in knowledge.iter_supported(root) if p.lower().endswith(".pdf")]
    if args.limit:
        pdfs = pdfs[:args.limit]

    skips = {} if args.retry_skipped else _load_skiplist()
    started = time.time()
    deadline = started + args.max_minutes * 60 if args.max_minutes else None
    budget = f"（上限 {args.max_new}件）" if args.max_new else ""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] PDF {len(pdfs)} 件を確認{budget}", flush=True)

    ocr_ok = text_skip = empty = failed = chunks = known_skip = 0
    streak = 0
    stopped = ""
    for i, p in enumerate(pdfs, 1):
        if deadline and time.time() > deadline:
            stopped = f"時間切れ（{args.max_minutes:.0f}分）"
            break
        rel = os.path.relpath(p, os.path.abspath(root))
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            continue
        if _skip_known(skips, p, mtime):
            known_skip += 1
            continue
        try:
            r = knowledge.ingest_file(p, category=knowledge.category_of(root, p),
                                      ocr_fallback=True, ocr_max_pages=args.max_pages)
            if r.get("unchanged"):
                text_skip += 1
                continue                      # 取込済み＝進捗に数えない
            if r.get("skipped"):
                empty += 1
                streak += 1
                _record_skip(skips, p, mtime, str(r.get("reason") or "テキスト抽出なし"))
                print(f"  [{i}/{len(pdfs)}] 画像認識なし: {rel}", flush=True)
            else:
                ocr_ok += 1
                streak = 0
                chunks += r.get("chunks", 0)
                skips.pop(p, None)            # 取れたので記録から外す
                tag = "OCR" if str(r.get("mime", "")).endswith("-ocr") else "text"
                print(f"  [{i}/{len(pdfs)}] {tag} {r.get('chunks')}ch: {rel}", flush=True)
        except Exception as e:
            failed += 1
            streak += 1
            _record_skip(skips, p, mtime, f"{type(e).__name__}: {e}")
            print(f"  [{i}/{len(pdfs)}] FAIL {rel}: {type(e).__name__}: {e}", flush=True)

        done = ocr_ok + empty + failed        # 実際に手を動かした件数
        if done and done % 25 == 0:
            set_state("ocr_progress", f"{i}/{len(pdfs)} (OCR {ocr_ok})")
            _save_skiplist(skips)             # 途中で落ちても記録を残す
        if streak >= ABORT_AFTER_FAILS:
            stopped = f"連続失敗 {streak} 件（claude CLI の定額枠切れ・環境異常の可能性）"
            break
        if args.max_new and done >= args.max_new:
            stopped = f"上限 {args.max_new} 件に到達"
            break

    _save_skiplist(skips)
    elapsed = time.time() - started
    tail = f" / 中断理由: {stopped}" if stopped else ""
    set_state("ocr_progress",
              f"{'中断' if stopped else '完了'} OCR {ocr_ok} / 認識なし {empty} / 失敗 {failed}")
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 終了 {elapsed/60:.1f}分{tail}", flush=True)
    print(f"OCR取込 {ocr_ok} / 既取込スキップ {text_skip} / 認識なし {empty} / "
          f"失敗 {failed} / 見送り済み飛ばし {known_skip} / 追加チャンク {chunks}", flush=True)
    print(f"索引合計: {knowledge.stats()}", flush=True)


if __name__ == "__main__":
    main()
