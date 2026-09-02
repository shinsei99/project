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
  python3 ocr_ingest.py --workers 2        # ★同時に2件処理する（夜間バッチ用・既定は1＝直列）

★ --limit と --max-new は別物（夜間バッチでは --max-new を使う）:
  --limit は「対象リストの先頭N件」を切り出すだけなので、毎晩流すと**同じ先頭N件を
  舐めて終わり**で前に進まない。--max-new は取込済みを飛ばしながら進み、
  **新しく処理できた件数**がNに達したら止まる。
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import time
from concurrent import futures
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
    # ★既定は 1（＝従来どおりの直列）。増やすと claude の呼び出しも同時に増える＝定額枠を
    #   その分だけ速く食う。夜間バッチ以外で上げないこと。
    ap.add_argument("--workers", type=int, default=1,
                    help="同時に処理する件数（既定1＝直列）。夜間バッチは2")
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
    workers = max(1, args.workers)
    par = f" / {workers}並列" if workers > 1 else ""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] PDF {len(pdfs)} 件を確認{budget}{par}", flush=True)

    # ★集計は全スレッドの共有物なので dict に集め、**必ず lock 越しに触る**。
    #   ローカル変数のままだと 2並列で数え落とす（+= はアトミックではない）。
    st = {"ocr_ok": 0, "text_skip": 0, "empty": 0, "failed": 0, "chunks": 0,
          "known_skip": 0, "unreadable": 0,
          "postponed": 0,   # 節約モードで後日に回した数（撤退の理由にしない）
          "locked": 0,      # DBロックで諦めた数（並列にして初めて起きうる。見送りに入れない）
          "streak": 0,      # claude（バックエンド）が連続でこけた回数。これだけが撤退の理由
          "doc_streak": 0,  # 書類側の失敗が連続した回数。桁違いに大きいときだけ異常とみなす
          "stopped": ""}
    lock = threading.Lock()
    stop_ev = threading.Event()

    def _stop(reason: str) -> None:
        # 2並列だと撤退理由が同時に2つ立つことがある。**先に立った方だけ**を残す。
        with lock:
            if not st["stopped"]:
                st["stopped"] = reason
        stop_ev.set()

    def _one(i, p) -> None:
        """PDF 1件を処理する。直列でも並列でもここだけを通す（処理の分岐を2本作らない）。"""
        if stop_ev.is_set():
            return
        if deadline and time.time() > deadline:
            _stop(f"時間切れ（{args.max_minutes:.0f}分）")
            return
        rel = os.path.relpath(p, os.path.abspath(root))
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            return
        with lock:
            if _skip_known(skips, p, mtime):
                st["known_skip"] += 1
                return
        try:
            r = knowledge.ingest_file(p, category=knowledge.category_of(root, p),
                                      ocr_fallback=True, ocr_max_pages=args.max_pages)
            if r.get("unchanged"):
                with lock:
                    st["text_skip"] += 1
                return                        # 取込済み＝進捗に数えない
            if r.get("skipped"):
                # 本当に文字が無い。見送りに記録するが、**中断の判定には数えない**
                with lock:
                    st["empty"] += 1
                    _record_skip(skips, p, mtime, str(r.get("reason") or "テキスト抽出なし"))
                print(f"  [{i}/{len(pdfs)}] 画像認識なし: {rel}", flush=True)
            else:
                with lock:
                    st["ocr_ok"] += 1
                    st["streak"] = 0
                    st["doc_streak"] = 0
                    st["chunks"] += r.get("chunks", 0)
                    skips.pop(p, None)        # 取れたので記録から外す
                tag = "OCR" if str(r.get("mime", "")).endswith("-ocr") else "text"
                print(f"  [{i}/{len(pdfs)}] {tag} {r.get('chunks')}ch: {rel}", flush=True)
        except OcrSkippedByQuotaSaver:
            # ★節約モード中。**撤退の理由にしない**（2026-09-01 に踏んだ）。
            #   claudeが壊れているわけではないので、Visionで読める書類は最後まで処理を続ける。
            with lock:
                st["postponed"] += 1
            print(f"  [{i}/{len(pdfs)}] 後日に回す（節約モード中・Visionでは読めなかった）: {rel}",
                  flush=True)
        except OcrUnavailable as e:
            # claude 側が落ちている。**見送りリストには入れない**（この書類のせいではない）
            with lock:
                st["failed"] += 1
                st["streak"] += 1
            print(f"  [{i}/{len(pdfs)}] claudeが応答せず（この書類は見送りに入れない）: {rel}: "
                  f"{str(e)[:80]}", flush=True)
        except sqlite3.OperationalError as e:
            # ★並列にして初めて起きうる失敗（2026-09-02）。もう一方のスレッドが書いている間に
            #   `database is locked` になることがある。**書類のせいではないので見送りに入れない**。
            #   入れると2回で永久に飛ばされ、2026-08-28 の「枠が戻っても二度とOCRされない」と
            #   同じ型の事故になる。次の晩に再挑戦させる。
            with lock:
                st["locked"] += 1
            print(f"  [{i}/{len(pdfs)}] DBが混み合って書けなかった（見送りに入れない・再挑戦する）: "
                  f"{rel}: {e}", flush=True)
        except OSError as e:
            # ★ファイルを読めなかっただけ。**バックエンド異常として数えない**（2026-08-29）。
            #   Dropbox(CloudStorage) の**未ダウンロード（オンラインのみ）**のファイルを開くと
            #   `[Errno 11] Resource deadlock avoided` が出る。書類の中身の問題ではないので、
            #   見送りリストにも入れない（ダウンロードされれば次の晩に読める）。
            #   2026-08-28 の晩は、これを「claudeがこけた」と誤って数えたせいで**3件で撤退**し、
            #   7,840件中2件しか進まなかった。
            with lock:
                st["unreadable"] += 1
            print(f"  [{i}/{len(pdfs)}] 読めない（Dropbox未ダウンロードの可能性・再挑戦する）: "
                  f"{rel}: {type(e).__name__}: {e}", flush=True)
        except Exception as e:
            # 書類側の問題。見送りに記録して次へ進む。**バックエンド異常として数えない**
            with lock:
                st["failed"] += 1
                st["doc_streak"] += 1
                _record_skip(skips, p, mtime, f"{type(e).__name__}: {e}")
            print(f"  [{i}/{len(pdfs)}] FAIL {rel}: {type(e).__name__}: {e}", flush=True)

        with lock:
            done = st["ocr_ok"] + st["empty"] + st["failed"]   # 実際に手を動かした件数
            ocr_now, streak, doc_streak = st["ocr_ok"], st["streak"], st["doc_streak"]
            snapshot = dict(skips)            # 保存中に他スレッドが触っても壊れないよう複製
        if done and done % 25 == 0:
            set_state("ocr_progress", f"{i}/{len(pdfs)} (OCR {ocr_now})")
            _save_skiplist(snapshot)          # 途中で落ちても記録を残す
        if streak >= ABORT_AFTER_BACKEND_FAILS:
            _stop(f"claude が連続 {streak} 回こけた（定額枠切れ・環境異常の可能性）。"
                  "この晩は諦める。★書類側の問題ではないので見送りには入れていない")
        elif doc_streak >= ABORT_AFTER_DOC_FAILS:
            _stop(f"書類側の失敗が連続 {doc_streak} 件（環境がおかしい可能性）。この晩は諦める。"
                  "★1件ずつの失敗では止めない。まとめて壊れているときだけここへ来る")
        elif args.max_new and done >= args.max_new:
            _stop(f"上限 {args.max_new} 件に到達")

    if workers == 1:
        for i, p in enumerate(pdfs, 1):
            _one(i, p)
            if stop_ev.is_set():
                break
    else:
        # ★全件をいっぺんに submit しない。撤退・時間切れのときに「もう投げた数千件」を
        #   1件ずつ捨てることになり、止まるまでが遅い。**走らせるのは常に workers 件だけ**。
        it = enumerate(pdfs, 1)
        with futures.ThreadPoolExecutor(max_workers=workers) as pool:
            inflight = set()
            while not stop_ev.is_set():
                while len(inflight) < workers:
                    try:
                        i, p = next(it)
                    except StopIteration:
                        break
                    inflight.add(pool.submit(_one, i, p))
                if not inflight:
                    break
                fin, inflight = futures.wait(inflight, return_when=futures.FIRST_COMPLETED)
                for f in fin:
                    try:
                        f.result()
                    except Exception as e:    # noqa: BLE001 … 想定外だけがここへ来る
                        _stop(f"想定外の例外で中断: {type(e).__name__}: {e}")
            for f in inflight:                # 走っている分（最大 workers 件）は待って終える
                try:
                    f.result()
                except Exception:             # noqa: BLE001 … 集計を出すほうを優先する
                    pass

    ocr_ok, text_skip, empty = st["ocr_ok"], st["text_skip"], st["empty"]
    failed, chunks, known_skip = st["failed"], st["chunks"], st["known_skip"]
    unreadable, postponed, locked = st["unreadable"], st["postponed"], st["locked"]
    stopped = st["stopped"]
    _save_skiplist(skips)
    elapsed = time.time() - started
    tail = f" / 中断理由: {stopped}" if stopped else ""
    set_state("ocr_progress",
              f"{'中断' if stopped else '完了'} OCR {ocr_ok} / 認識なし {empty} / 失敗 {failed}")
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 終了 {elapsed/60:.1f}分{tail}", flush=True)
    print(f"節約モードで後日に回した {postponed} 件") if postponed else None
    print(f"OCR取込 {ocr_ok} / 既取込スキップ {text_skip} / 認識なし {empty} / "
          f"失敗 {failed} / 読めない {unreadable} / DBロック {locked} / "
          f"見送り済み飛ばし {known_skip} / 追加チャンク {chunks}", flush=True)
    if locked:
        print(f"※「DBロック {locked} 件」は並列で書き込みがぶつかった分。見送りには入れていないので"
              "次の晩に再挑戦する。毎晩まとまって出るなら --workers を下げること", flush=True)
    if unreadable:
        print(f"※「読めない {unreadable} 件」は Dropbox が未ダウンロードの可能性。"
              "見送りには入れていないので、次の晩に再挑戦する", flush=True)
    print(f"索引合計: {knowledge.stats()}", flush=True)


if __name__ == "__main__":
    main()
