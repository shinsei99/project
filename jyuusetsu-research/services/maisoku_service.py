"""マイソク（物件概要書）PDF から、住所などの物件情報を読み取る。

**なぜここに置くか（2026-08-21 オーナー判断）**
`maisoku-converter`(8505) にもマイソクのAI解析があるが、あちらの役割は
「他社マイソク → 自社フォーマットのExcelに作り替える」で、賃料・間取り・設備まで
広く取る。こちらの役割は「重説・契約書の住所欄を埋める」だけなので、
**取る項目も後段の使い道も別物**。したがって同じ解析器を共有するのではなく、
**解析のやり方（PDF→画像→向き補正→AIに読ませる）だけを応用**している。

ただし**仕組みの重複は作らない**。claude CLI の場所解決・向き補正・JSON の取り出しは
直下の共有モジュール `registry_parser.py` の関数をそのまま使う
（`CLAUDE_BIN` をハードコードして Intel Mac で黙って動かなくなる事故が
2026-08-21 に起きているため、CLIの呼び出しは1か所に寄せる）。

**読み取った住所は「候補」であって確定ではない。**
マイソクの住所は地番表記のことがあり、号まで書かれていないことも多い。
画面では編集できる欄に出し、日本郵便のデータで町名を確認してから使う。
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
from typing import Dict, Optional

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import registry_parser as RP          # 共有: claude CLI・向き補正・JSON取り出し
except Exception:                          # 共有モジュールが無くてもアプリは止めない
    RP = None

RENDER_DPI = 150
THUMB_MAX = 900
MAX_PAGES = 2          # マイソクは1枚もの。裏面があっても2ページまで見れば足りる
TIMEOUT = 180

_SCHEMA = """
次の JSON だけを出力してください（説明文やコードフェンスは不要）。
読み取れない項目は空文字にしてください。**推測で埋めないこと。**

{
  "所在地":   "物件の所在地。マイソクに書かれている表記のまま（例: 大阪市都島区中野町1-4-18）",
  "建物名":   "マンション名・建物名。無ければ空文字",
  "部屋番号": "号室。無ければ空文字",
  "交通":     "最寄駅と徒歩分（例: 京橋駅 徒歩5分）",
  "種目":     "例: 中古戸建 / 売地 / 分譲マンション / 賃貸マンション",
  "表記種別": "所在地が『住居表示』か『地番』か判断できれば住居表示/地番、分からなければ空文字"
}
"""


def available() -> bool:
    """解析できる状態か（共有モジュールと claude CLI があるか）。"""
    return RP is not None and bool(getattr(RP, "CLAUDE_BIN", ""))


def parse_maisoku(pdf_file) -> Dict[str, str]:
    """マイソクPDFを読み、住所などを返す。失敗しても例外を投げず空の辞書を返す。

    戻り値のキーは `_SCHEMA` のとおり。**呼び出し側は「候補」として扱うこと。**
    """
    empty = {k: "" for k in
             ("所在地", "建物名", "部屋番号", "交通", "種目", "表記種別")}
    if not available() or pdf_file is None:
        return empty

    diag: Dict[str, object] = {}
    note = RP._note_fn(diag)
    try:
        raw = RP._read_pdf_bytes(pdf_file)
    except Exception:
        return empty

    try:
        import fitz            # PyMuPDF
        from PIL import Image
    except ImportError:
        return _parse_pdf_direct(raw, diag, note) or empty

    with tempfile.TemporaryDirectory(prefix="maisoku_") as td:
        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception:
            return _parse_pdf_direct(raw, diag, note) or empty

        pages = []
        for i, page in enumerate(doc):
            if i >= MAX_PAGES:
                break
            pix = page.get_pixmap(dpi=RENDER_DPI)
            from io import BytesIO
            im = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
            # 向き補正（マイソクは横向きスキャンが多い）。共有モジュールの判定を使う
            th = im.copy()
            th.thumbnail((THUMB_MAX, THUMB_MAX))
            thumb = "thumb_{}.png".format(i + 1)
            th.save(os.path.join(td, thumb))
            ang = RP._detect_angle(thumb, td, note)
            up = im.rotate(-ang, expand=True) if ang else im
            fn = "page_{}.png".format(i + 1)
            up.save(os.path.join(td, fn))
            pages.append(fn)
        doc.close()

        if not pages:
            return _parse_pdf_direct(raw, diag, note) or empty

        files_block = "\n".join("- {}".format(f) for f in pages)
        prompt = (
            "次の画像は不動産の「マイソク（物件概要書）」です（向きは正立済み）。"
            "Read ツールで開いて読み取り、重要事項説明書の住所欄に転記するための情報を"
            "JSON で抽出してください。\n\n"
            "【画像ファイル（順番に全て開くこと）】\n{}\n\n".format(files_block)
            + _SCHEMA
            + "\n\n必ず全ての画像を Read ツールで開いてから、JSON のみを出力してください:"
        )
        got = RP._run_claude(
            prompt, diag, note,
            extra_args=["--tools", "Read", "--add-dir", td],
            cwd=td, timeout=TIMEOUT,
        )
    out = dict(empty)
    if isinstance(got, dict):
        for k in out:
            v = got.get(k)
            if v:
                out[k] = str(v).strip()
    return out


def _parse_pdf_direct(raw: bytes, diag: dict, note) -> Optional[dict]:
    """フォールバック: PDF をそのまま claude に読ませる（画像化できないPC用）。"""
    with tempfile.TemporaryDirectory(prefix="maisoku_") as td:
        fname = "maisoku.pdf"
        with open(os.path.join(td, fname), "wb") as f:
            f.write(raw)
        prompt = (
            "ファイル {} は不動産の「マイソク（物件概要書）」のPDFです。"
            "Read ツールで開いて読み取り、JSON で抽出してください。\n\n".format(fname)
            + _SCHEMA
            + "\n\n必ず {} を Read ツールで開いてから、JSON のみを出力してください:".format(fname)
        )
        return RP._run_claude(
            prompt, diag, note,
            extra_args=["--tools", "Read", "--add-dir", td],
            cwd=td, timeout=TIMEOUT,
        )
