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
  "label": "（このファイルの見出し。背表紙や表紙に名前が書いてあればそのまま。無ければ中身から『◯◯マンション 契約関係』のような探しやすい名前を付ける）",
  "properties": ["（関係する物件名・建物名。号室が分かれば含める。複数可。無ければ空配列）"],
  "doc_types": ["（入っている書類の種別。売買契約書 / 賃貸借契約書 / 重要事項説明書 / 管理委託契約書 / 覚書・合意書 / 登記簿謄本 / 図面・間取図 / 測量図・境界 / 確認済証・検査済証 / 見積書・請求書 / 領収書 / 鍵預り証 / 保険証券 / 納税通知・評価証明 / 写真・現況資料 / その他 から該当するものを列挙）"],
  "year_from": "（中身の書類のうち最も古い年。YYYY。分からなければ空）",
  "year_to": "（最も新しい年。YYYY。分からなければ空）",
  "contents": ["（中に入っている書類を1件ずつ。『2024-05-20 賃貸借契約書 グランドメゾン天王寺302 山田太郎』のように、日付・種別・物件・相手先が分かる範囲で1行にまとめる）"],
  "summary": "（このファイルが何かを40字程度で）",
  "confidence": "high | medium | low"
}"""

PROMPT_HEAD = """あなたは日本の不動産会社で書類整理を担当する事務です。
クリアファイル／バインダー／箱に入っている書類を撮った写真を見て、
**その入れ物1つ分の中身の目録**を作ってください。あとで「どのファイルを開けばよいか」を
探すための情報です。

これは要約ではなく**書き写し**の作業です。守ること:

- **固有名詞（物件名・会社名・人名・地名）と数字は、書かれている文字を一字一句そのまま写す。**
  似た言葉への置き換え（例「天王寺」を「中央」、「大京商事」を「大和商事」）は誤りです。
  もっともらしい名称を推測で補ってはいけません。
- 一部の文字がはっきり読み取れない項目は、**その項目を空にする**（部分的な推測で埋めない）。
- 数字は桁と並びをそのまま写す（82,000 を 28,000 のように入れ替えない）。
- 和暦（令和/平成/昭和）は西暦に変換する。それ以外は変換しない。
- **写真に写っていない書類を contents に足さない。** 写真は中身の一部だけのことがあるので、
  見えたものだけを列挙してください。
- 同じ書類が複数ページに渡って写っている場合は、まとめて1件として数える。
- confidence: すべて明瞭に読み取れたら high、一部あいまいなら medium、
  文字が不鮮明・写りが悪いなど自信が持てなければ low。
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

    def lst(key: str) -> list:
        v = d.get(key, [])
        if isinstance(v, str):
            v = [x for x in re.split(r"[,、\n]", v)]
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x).strip()]

    def year(key: str) -> str:
        m = re.search(r"(\d{4})", s(key))
        return m.group(1) if m else ""

    conf = s("confidence").lower()
    return {
        "label": s("label"),
        "properties": lst("properties"),
        "doc_types": lst("doc_types"),
        "year_from": year("year_from"),
        "year_to": year("year_to"),
        "contents": lst("contents"),
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


def read_file_contents(uploads: list, note=lambda _m: None) -> dict | None:
    """ファイル1冊分の写真・PDF（複数可）をまとめて読み、中身の目録を返す。

    uploads は (bytes, filename) のリスト。1冊のクリアファイルの中身を
    数枚パラパラ撮ったもの、という想定。失敗時 None。
    note はユーザーに見せる進捗・失敗理由を受け取るコールバック。
    """
    if not uploads:
        return None

    # --- 全部がテキストPDFなら、テキストをまとめて渡す（速い・正確） ---
    texts = []
    all_text = True
    for data, filename in uploads:
        if os.path.splitext(filename)[1].lower() == ".pdf":
            t = _pdf_text(data)
            if len(t) >= TEXT_MIN_CHARS:
                texts.append(f"--- {filename} ---\n{t}")
                continue
        all_text = False
        break

    if all_text and texts:
        note("PDFのテキストを読み取り中…")
        body = "\n\n".join(texts)[:TEXT_MAX_CHARS]
        prompt = PROMPT_HEAD + SCHEMA + "\n\n--- 中身の書類のテキスト ---\n" + body
        out = _invoke(prompt, note, timeout=TEXT_TIMEOUT)
        return _parse(out, note) if out is not None else None

    # --- 写真・スキャン画像はビジョンで読む ---
    note(f"{len(uploads)}件を画像として読み取り中…（向きの自動補正を含むため時間がかかります）")
    with tempfile.TemporaryDirectory() as tmp:
        names: list = []
        for idx, (data, filename) in enumerate(uploads):
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".pdf":
                try:
                    # 1冊分なのでPDF1件あたりのページ数は絞る
                    pages = pdf_orient.upright_page_images(data, tmp)[:MAX_PAGES]
                    names.extend(pages)
                except Exception as e:
                    note(f"{filename} を画像化できませんでした: {type(e).__name__}")
            else:
                fixed = pdf_orient.ensure_upright_image(data)
                # ensure_upright_image は (bytes, angle) を返す実装と bytes を返す実装がある
                img_bytes = fixed[0] if isinstance(fixed, tuple) else fixed
                name = f"shot_{idx + 1}.png"
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(img_bytes if img_bytes else data)
                names.append(name)

        if not names:
            note("読み取れる画像がありませんでした")
            return None

        listing = "、".join(names)
        prompt = (
            PROMPT_HEAD + SCHEMA
            + f"\n\n画像ファイル {listing} を Read ツールで**すべて**開いてください。"
            "これらは1つのクリアファイル／バインダー／箱の中身を撮ったものです。"
            "\n手順: 各画像の文字を最後まで丁寧に目で追い、固有名詞と数字を正確に確認したうえで、"
            "中身の目録としてJSONを組み立ててください。画像に無い書類は決して足さないでください。"
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
