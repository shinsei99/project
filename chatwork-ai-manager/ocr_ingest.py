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
from services.knowledge import OcrSkippedByQuotaSaver, OcrUnavailable  # noqa: E402
from services.settings import set_state  # noqa: E402

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# OCRしても文字が取れなかったファイルの記録。
# なぜ要るか: knowledge.ingest_file() は「テキスト抽出なし」のとき DB に何も書かない。
# つまり記録しないと**毎晩まったく同じファイルを再OCRし続ける**（定額枠の無駄）。
SKIP_PATH = os.path.join(APP_DIR, "logs", "ocr_skiplist.json")
SKIP_MAX_TRIES = 2          # 同じ内容で2回ダメなら以後は飛ばす（mtimeが変われば再挑戦）
# ★「文字が取れなかった」は中断の判定に数えない（2026-08-28）。
#   数えていたため、同じ業者の点検報告書が5件続いただけで **その晩の作業が21秒で全部止まった**。
#   中断すべきなのは claude 自体が落ちているとき（OcrUnavailable）だけ。
ABORT_AFTER_BACKEND_FAILS = 3   # claude が連続でこの回数こければ、その晩は諦める
# ★書類側の失敗も中断の判定に数えていた（2026-08-29に判明。上と同じ間違いの繰り返し）。
#   8/28の晩は `OSError: [Errno 11] Resource deadlock avoided` が3件続いただけで
#   「claude が連続3回こけた」と誤って表示し、**2秒・2件で撤退**した（予定は300件）。
#   原因は Dropbox(CloudStorage) の**未ダウンロード（オンラインのみ）**ファイルで、
#   claude とは無関係。→ 読めないファイルは `unreadable` として数えるだけにし、
#   書類側の失敗はここまで連続したときだけ「環境がおかしい」とみなす。
ABORT_AFTER_DOC_FAILS = 50


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

    ocr_ok = text_skip = empty = failed = chunks = known_skip = unreadable = 0
    postponed = 0       # 節約モードで後日に回した数（撤退の理由にしない）
    streak = 0          # claude（バックエンド）が連続でこけた回数。これだけが撤退の理由
    doc_streak = 0      # 書類側の失敗が連続した回数。桁違いに大きいときだけ異常とみなす
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
                # 本当に文字が無い。見送りに記録するが、**中断の判定には数えない**
                empty += 1
                _record_skip(skips, p, mtime, str(r.get("reason") or "テキスト抽出なし"))
                print(f"  [{i}/{len(pdfs)}] 画像認識なし: {rel}", flush=True)
            else:
                ocr_ok += 1
                streak = 0
                doc_streak = 0
                chunks += r.get("chunks", 0)
                skips.pop(p, None)            # 取れたので記録から外す
                tag = "OCR" if str(r.get("mime", "")).endswith("-ocr") else "text"
                print(f"  [{i}/{len(pdfs)}] {tag} {r.get('chunks')}ch: {rel}", flush=True)
        except OcrSkippedByQuotaSaver:
            # ★節約モード中。**撤退の理由にしない**（2026-09-01 に踏んだ）。
            #   claudeが壊れているわけではないので、Visionで読める書類は最後まで処理を続ける。
            postponed += 1
            print(f"  [{i}/{len(pdfs)}] 後日に回す（節約モード中・Visionでは読めなかった）: {rel}",
                  flush=True)
        except OcrUnavailable as e:
            # claude 側が落ちている。**見送りリストには入れない**（この書類のせいではない）
            failed += 1
            streak += 1
            print(f"  [{i}/{len(pdfs)}] claudeが応答せず（この書類は見送りに入れない）: {rel}: "
                  f"{str(e)[:80]}", flush=True)
        except OSError as e:
            # ★ファイルを読めなかっただけ。**バックエンド異常として数えない**（2026-08-29）。
            #   Dropbox(CloudStorage) の**未ダウンロード（オンラインのみ）**のファイルを開くと
            #   `[Errno 11] Resource deadlock avoided` が出る。書類の中身の問題ではないので、
            #   見送りリストにも入れない（ダウンロードされれば次の晩に読める）。
            #   2026-08-28 の晩は、これを「claudeがこけた」と誤って数えたせいで**3件で撤退**し、
            #   7,840件中2件しか進まなかった。
            unreadable += 1
            print(f"  [{i}/{len(pdfs)}] 読めない（Dropbox未ダウンロードの可能性・再挑戦する）: "
                  f"{rel}: {type(e).__name__}: {e}", flush=True)
        except Exception as e:
            # 書類側の問題。見送りに記録して次へ進む。**バックエンド異常として数えない**
            failed += 1
            doc_streak += 1
            _record_skip(skips, p, mtime, f"{type(e).__name__}: {e}")
            print(f"  [{i}/{len(pdfs)}] FAIL {rel}: {type(e).__name__}: {e}", flush=True)

        done = ocr_ok + empty + failed        # 実際に手を動かした件数
        if done and done % 25 == 0:
            set_state("ocr_progress", f"{i}/{len(pdfs)} (OCR {ocr_ok})")
            _save_skiplist(skips)             # 途中で落ちても記録を残す
        if streak >= ABORT_AFTER_BACKEND_FAILS:
            stopped = (f"claude が連続 {streak} 回こけた（定額枠切れ・環境異常の可能性）。"
                       "この晩は諦める。★書類側の問題ではないので見送りには入れていない")
            break
        if doc_streak >= ABORT_AFTER_DOC_FAILS:
            stopped = (f"書類側の失敗が連続 {doc_streak} 件（環境がおかしい可能性）。この晩は諦める。"
                       "★1件ずつの失敗では止めない。まとめて壊れているときだけここへ来る")
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
    print(f"節約モードで後日に回した {postponed} 件") if postponed else None
    print(f"OCR取込 {ocr_ok} / 既取込スキップ {text_skip} / 認識なし {empty} / "
          f"失敗 {failed} / 読めない {unreadable} / 見送り済み飛ばし {known_skip} / "
          f"追加チャンク {chunks}", flush=True)
    if unreadable:
        print(f"※「読めない {unreadable} 件」は Dropbox が未ダウンロードの可能性。"
              "見送りには入れていないので、次の晩に再挑戦する", flush=True)
    print(f"索引合計: {knowledge.stats()}", flush=True)


if __name__ == "__main__":
    main()
