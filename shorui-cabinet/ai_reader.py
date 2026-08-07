# -*- coding: utf-8 -*-
"""書類の写真・PDFを読んで「何の書類か」を構造化するモジュール。

ローカルの `claude` CLI を呼ぶ（APIキー不要・Claude Codeのサブスク内で動く）。
見積書ジェネレーター／媒介契約書ジェネレーターと同じ方式。

処理の流れ:
  1. PDFにテキスト層があれば、そのテキストを読ませる（速い）
  2. スキャン画像PDF・写真は、ページを画像化 → 向きを自動補正 → ビジョンで読ませる
表紙まわりが分かれば十分なので、読ませるのは先頭2ページまで。
"""

# 実行環境は system python 3.9（他アプリと同じ）。新しい型注釈を書けるようにする。
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile

import pdf_orient

TEXT_MODEL = "sonnet"     # テキストPDFは sonnet で十分な精度が出る
# 画像読み取りは sonnet だと固有名詞を推測で埋めることがあった（実測で2回に1回程度）ため、
# 誤登録を避けて opus を使う。速度より正確さを優先する場面なので割に合う。
VISION_MODEL = "opus"
TEXT_TIMEOUT = 180        # テキストを読ませる場合のタイムアウト（秒）
VISION_TIMEOUT = 600      # 画像を読ませる場合（向き補正込みで時間がかかる）
MAX_PAGES = 2             # 表紙が分かればよいので先頭2ページまで
TEXT_MIN_CHARS = 40       # これ未満ならスキャン画像PDFとみなす
TEXT_MAX_CHARS = 6000     # 長い書類は先頭だけ渡す

SCHEMA = """{
  "doc_type": "（書類の種別。例: 売買契約書 / 賃貸借契約書 / 重要事項説明書 / 管理委託契約書 / 覚書・合意書 / 登記簿謄本 / 図面・間取図 / 測量図・境界 / 確認済証・検査済証 / 見積書・請求書 / 領収書 / 鍵預り証 / 保険証券 / 納税通知・評価証明 / 写真・現況資料 / その他）",
  "title": "（書類の表題。書かれているとおりに）",
  "property_name": "（対象の物件名・建物名。号室まで分かれば含める。無ければ空）",
  "doc_date": "（作成日・契約日。YYYY-MM-DD形式。和暦は西暦に直す。不明なら空）",
  "counterparty": "（相手方・当事者。売主/買主/貸主/借主/業者名など。複数なら「A（売主）／B（買主）」）",
  "summary": "（この書類が何かを40字程度で。あとで探すときの手がかりになる情報を優先）",
  "confidence": "high | medium | low"
}"""

PROMPT_HEAD = """あなたは日本の不動産会社で書類整理を担当する事務です。
提示された書類から、あとで紙を探すための情報を抜き出してください。

これは要約ではなく**書き写し**の作業です。守ること:

- **固有名詞（物件名・会社名・人名・地名）と数字は、書かれている文字を一字一句そのまま写す。**
  似た言葉への置き換え（例「天王寺」を「中央」、「大京商事」を「大和商事」）は誤りです。
  もっともらしい名称を推測で補ってはいけません。
- 一部の文字がはっきり読み取れない項目は、**その項目を空文字にする**（部分的な推測で埋めない）。
- 数字は桁と並びをそのまま写す（82,000 を 28,000 のように入れ替えない）。
- 和暦（令和/平成/昭和）は西暦に変換する。それ以外は変換しない。
- property_name はマンション名・ビル名など、人が探すときに使う呼び名。号室があれば含める。
- confidence: すべて明瞭に読み取れたら high、一部あいまいなら medium、
  文字が不鮮明・表紙が写っていないなど自信が持てなければ low。
- 出力は下記のJSONのみ。説明文やコードフェンスは付けない。

出力するJSON:
"""


def claude_available() -> bool:
    return _claude_bin() is not None


def _claude_bin() -> str | None:
    p = shutil.which("claude")
    if p:
        return p
    cand = os.path.expanduser("~/.local/bin/claude")
    return cand if os.path.exists(cand) else None


def _strip_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?", "", t).rstrip("`").strip()
    # 前後に説明文が付いた場合に備え、最初の { 〜 最後の } を取り出す
    if not t.startswith("{"):
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e > s:
            t = t[s : e + 1]
    return t


def _invoke(prompt: str, note, extra_args=None, cwd=None, timeout: int = TEXT_TIMEOUT,
            model: str = TEXT_MODEL) -> str | None:
    """claude CLI を実行して result テキストを返す。失敗時 None。"""
    binpath = _claude_bin()
    if not binpath:
        note("claude CLI が見つかりません（`which claude` で確認してください）")
        return None
    cmd = [
        binpath, "-p", prompt,
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--model", model,
    ] + (extra_args or [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        note("claude CLI を実行できませんでした")
        return None
    except subprocess.TimeoutExpired:
        note(f"AI読み取りが{timeout}秒でタイムアウトしました")
        return None
    if proc.returncode != 0:
        note(f"claude CLI がエラー終了（code {proc.returncode}）: {(proc.stderr or '')[:200]}")
        return None
    try:
        outer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        note("claude CLI の出力を解釈できませんでした")
        return None
    if outer.get("is_error"):
        note(f"AIがエラーを返しました: {str(outer.get('result'))[:200]}")
        return None
    return outer.get("result", "")


def _parse(text: str, note) -> dict | None:
    try:
        data = json.loads(_strip_fence(text))
    except (json.JSONDecodeError, TypeError):
        note("AI出力をJSONとして解釈できませんでした")
        return None
    if not isinstance(data, dict):
        note("AI出力の形式が想定と異なります")
        return None
    return _normalize(data)


def _normalize(d: dict) -> dict:
    def s(key: str) -> str:
        v = d.get(key, "")
        return v.strip() if isinstance(v, str) else ""

    date = s("doc_date")
    # 2026/8/7 や 2026年8月7日 のような表記も YYYY-MM-DD に寄せる
    m = re.search(r"(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2})", date)
    if m:
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        m2 = re.search(r"(\d{4})\D{1,2}(\d{1,2})", date)
        date = f"{m2.group(1)}-{int(m2.group(2)):02d}-01" if m2 else ""

    conf = s("confidence").lower()
    return {
        "doc_type": s("doc_type"),
        "title": s("title"),
        "property_name": s("property_name"),
        "doc_date": date,
        "counterparty": s("counterparty"),
        "summary": s("summary"),
        "confidence": conf if conf in ("high", "medium", "low") else "medium",
    }


def _pdf_text(pdf_bytes: bytes) -> str:
    """PDFのテキスト層を先頭ページから拾う。fitz が無ければ空。"""
    try:
        import fitz
    except ImportError:
        return ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            parts = [doc[i].get_text() for i in range(min(MAX_PAGES, doc.page_count))]
        return "\n".join(parts).strip()
    except Exception:
        return ""


def read_document(data: bytes, filename: str, note=lambda _m: None) -> dict | None:
    """書類（PDF or 画像）を読んで構造化した dict を返す。失敗時 None。

    note はユーザーに見せる進捗・失敗理由を受け取るコールバック。
    """
    ext = os.path.splitext(filename)[1].lower()

    # --- テキストPDFならテキストを渡す（速い・正確） ---
    if ext == ".pdf":
        text = _pdf_text(data)
        if len(text) >= TEXT_MIN_CHARS:
            note("PDFのテキストを読み取り中…")
            prompt = (
                PROMPT_HEAD + SCHEMA
                + "\n\n--- 書類のテキスト ---\n" + text[:TEXT_MAX_CHARS]
            )
            out = _invoke(prompt, note, timeout=TEXT_TIMEOUT)
            return _parse(out, note) if out is not None else None

    # --- スキャン画像PDF・写真はビジョンで読む ---
    note("画像として読み取り中…（向きの自動補正を含むため少し時間がかかります）")
    with tempfile.TemporaryDirectory() as tmp:
        names: list[str] = []
        if ext == ".pdf":
            try:
                names = pdf_orient.upright_page_images(data, tmp)[:MAX_PAGES]
            except Exception as e:
                note(f"PDFを画像化できませんでした: {type(e).__name__}")
                return None
        else:
            fixed = pdf_orient.ensure_upright_image(data)
            # ensure_upright_image は (bytes, angle) を返す実装と bytes を返す実装がある
            img_bytes = fixed[0] if isinstance(fixed, tuple) else fixed
            name = "page_1.png"
            with open(os.path.join(tmp, name), "wb") as f:
                f.write(img_bytes if img_bytes else data)
            names = [name]

        if not names:
            note("読み取れる画像がありませんでした")
            return None

        listing = "、".join(names)
        prompt = (
            PROMPT_HEAD + SCHEMA
            + f"\n\n画像ファイル {listing} を Read ツールで開いてください。1ページ目が表紙です。"
            "\n手順: まず画像に書かれている文字を最後まで丁寧に目で追い、"
            "固有名詞と数字を正確に確認してから、JSONを組み立ててください。"
            "画像に無い情報は決して足さないでください。"
        )
        out = _invoke(
            prompt, note,
            extra_args=["--tools", "Read", "--add-dir", tmp],
            cwd=tmp, timeout=VISION_TIMEOUT, model=VISION_MODEL,
        )
        return _parse(out, note) if out is not None else None


def make_thumb(data: bytes, filename: str, out_path: str, max_px: int = 520) -> bool:
    """一覧表示用のサムネイルを作る。作れなければ False（登録自体は続行する）。"""
    ext = os.path.splitext(filename)[1].lower()
    try:
        from PIL import Image
        import io

        if ext == ".pdf":
            import fitz

            with fitz.open(stream=data, filetype="pdf") as doc:
                if doc.page_count == 0:
                    return False
                pix = doc[0].get_pixmap(dpi=110)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            img = Image.open(io.BytesIO(data))

        img = img.convert("RGB")
        img.thumbnail((max_px, max_px))
        img.save(out_path, "JPEG", quality=80)
        return True
    except Exception:
        return False
