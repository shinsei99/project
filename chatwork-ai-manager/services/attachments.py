"""受信した添付ファイル（Excel・Word・PDF・CSV・テキスト）を読んで本文にする。

**なぜ要るのか**: これまで Chatwork / LINE に貼られたファイルは、本文のテキストしか
見ていなかったので **完全に無視されていた**（`[download:...]` タグが素通り）。
「この見積を見て」と Excel を貼られても中身を知らないまま答えていた。

方針:
- **抽出器は増やさない。** `services/knowledge.py` の `_EXTRACTORS`（社内資料の取込で
  すでに使っているもの）をそのまま借りる。対応形式が増えたら両方に効く。
- 落とすのは一時ディレクトリ。**読み終わったら必ず消す**（個人情報を残さない）。
- 大きいファイルは落とさない・長い本文は切る（定額枠とタイムアウトを守るため）。

制限（意図的）:
- 画像だけは別扱い。OCRが要るので `services/ocr` 系の対象。ここでは名前だけ伝える。
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import urllib.request

from services import config

# 1ファイルの上限。これを超えるものは落とさず、名前とサイズだけ伝える
MAX_BYTES = 20 * 1024 * 1024          # 20MB
# 1ファイルから本文に入れる最大文字数（Excelは1シートでも巨大になりうる）
MAX_CHARS = 8000
# 1メッセージあたりの最大ファイル数
MAX_FILES = 3

# Chatwork のファイル投稿は本文に `[download:123]名前.xlsx (12.3 KB)[/download]` が入る
_DOWNLOAD_RE = re.compile(r"\[download:(\d+)\]([^\[]*?)(?:\s*\([^)]*\))?\[/download\]")


def chatwork_file_refs(body: str) -> list[tuple[int, str]]:
    """本文から (file_id, ファイル名) を取り出す。無ければ空。"""
    out = []
    for m in _DOWNLOAD_RE.finditer(body or ""):
        out.append((int(m.group(1)), (m.group(2) or "").strip()))
    return out[:MAX_FILES]


def _download(url: str, dest: str, headers: dict | None = None) -> int:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        size = 0
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("大きすぎる")
            f.write(chunk)
    return size


def _extract(path: str, name: str) -> str:
    """knowledge.py の抽出器を借りて本文にする。

    抽出器の戻り値は **`[(本文, 出所), ...]`**（出所は Excel なら `Sheet:請求`、
    PDF なら `P3`）。出所は見出しとして残す——「どのシートの話か」が分からないと
    複数シートのExcelで答えがずれるため。
    """
    from services import knowledge
    ext = os.path.splitext(name or path)[1].lower()
    fn = knowledge._EXTRACTORS.get(ext)
    if not fn:
        return ""
    parts = []
    for text, ref in fn(path) or []:
        text = (text or "").strip()
        if not text:
            continue
        parts.append(f"[{ref}]\n{text}" if ref else text)
    return "\n\n".join(parts).strip()


def _describe(name: str, text: str, note: str = "") -> str:
    head = f"----- 添付ファイル: {name} -----"
    if note:
        return f"{head}\n（{note}）"
    if not text:
        return f"{head}\n（このファイル形式は本文を取り出せませんでした）"
    cut = text[:MAX_CHARS]
    tail = f"\n…（長いので先頭 {MAX_CHARS} 文字まで。全 {len(text)} 文字）" if len(text) > MAX_CHARS else ""
    return f"{head}\n{cut}{tail}"


def read_chatwork_files(room_id, refs: list[tuple[int, str]]) -> str:
    """Chatwork のファイルを落として本文にする。失敗しても例外は投げない。"""
    if not refs:
        return ""
    from services.chatwork import ChatworkClient, ChatworkError
    cw = ChatworkClient()
    tmp = tempfile.mkdtemp(prefix="cwai-att-")
    parts = []
    try:
        for file_id, name in refs:
            try:
                info = cw.get_file(room_id, file_id)
                url = info.get("download_url")
                name = name or info.get("filename") or f"file-{file_id}"
                if not url:
                    parts.append(_describe(name, "", "ダウンロードURLを取得できませんでした"))
                    continue
                ext = os.path.splitext(name)[1].lower()
                from services import knowledge
                if ext not in knowledge._EXTRACTORS:
                    parts.append(_describe(name, "", f"未対応の形式（{ext or '拡張子なし'}）"))
                    continue
                dest = os.path.join(tmp, os.path.basename(name) or f"f{file_id}")
                _download(url, dest)
                parts.append(_describe(name, _extract(dest, name)))
            except ValueError:
                parts.append(_describe(name, "", f"{MAX_BYTES // 1024 // 1024}MB を超えるので読みませんでした"))
            except ChatworkError as e:
                parts.append(_describe(name, "", f"取得に失敗: {e}"))
            except Exception as e:                     # 抽出失敗で応答自体を落とさない
                parts.append(_describe(name, "", f"読み取りに失敗: {type(e).__name__}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)         # ★個人情報を残さない
    return "\n\n".join(parts)


def read_line_file(message_id: str, name: str) -> str:
    """LINE のファイルメッセージを落として本文にする。"""
    token = config.get("line_channel_access_token")
    if not token:
        return _describe(name, "", "LINEのアクセストークンが未設定")
    from services import knowledge
    ext = os.path.splitext(name or "")[1].lower()
    if ext not in knowledge._EXTRACTORS:
        return _describe(name, "", f"未対応の形式（{ext or '拡張子なし'}）")
    tmp = tempfile.mkdtemp(prefix="cwai-att-")
    try:
        dest = os.path.join(tmp, os.path.basename(name) or "line-file")
        _download(f"https://api-data.line.me/v2/bot/message/{message_id}/content", dest,
                  headers={"Authorization": f"Bearer {token}"})
        return _describe(name, _extract(dest, name))
    except ValueError:
        return _describe(name, "", f"{MAX_BYTES // 1024 // 1024}MB を超えるので読みませんでした")
    except Exception as e:
        return _describe(name, "", f"読み取りに失敗: {type(e).__name__}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def with_attachments(question: str, attachment_text: str) -> str:
    """質問文に添付の中身を足す。**質問が空でも添付だけで答えられるようにする。**"""
    if not attachment_text:
        return question
    q = (question or "").strip()
    if not q:
        q = "添付されたファイルの内容を要約し、気づいた点があれば挙げてください。"
    return f"{q}\n\n{attachment_text}"
