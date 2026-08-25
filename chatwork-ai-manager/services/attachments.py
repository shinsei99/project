"""受信した添付ファイル（Excel・Word・PDF・CSV・テキスト）を読んで本文にする。

**なぜ要るのか**: これまで Chatwork / LINE に貼られたファイルは、本文のテキストしか
見ていなかったので **完全に無視されていた**（`[download:...]` タグが素通り）。
「この見積を見て」と Excel を貼られても中身を知らないまま答えていた。

方針:
- **抽出器は増やさない。** `services/knowledge.py` の `_EXTRACTORS`（社内資料の取込で
  すでに使っているもの）をそのまま借りる。対応形式が増えたら両方に効く。
- 落とすのは一時ディレクトリ。**読み終わったら必ず消す**（個人情報を残さない）。
- 大きいファイルは落とさない・長い本文は切る（定額枠とタイムアウトを守るため）。

画像（LINEの写真・スクリーンショット等）は別ルート（`read_line_image`）で扱う。
テキスト抽出器ではなく claude vision（`services/knowledge.ocr_pdf` / `streetview_tools` と
同じ作法: 一時ファイルへ保存 → `--add-dir` + `Read` ツールで見せる）で内容を読む
（TASK-20260825-006）。
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
# LINE画像contentのContent-Typeから拡張子を決める（Readツールが認識できる形式にする）
_IMAGE_EXT_BY_MIME = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/gif": ".gif", "image/webp": ".webp",
}

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


def _download_ctype(url: str, dest: str, headers: dict | None = None) -> str:
    """_download と同じだが、レスポンスの Content-Type も返す（画像の拡張子判定用）。"""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        size = 0
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("大きすぎる")
            f.write(chunk)
    return ctype


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


def _analyze_image(tmp_dir: str, filename: str) -> str | None:
    """claude vision で画像1枚の内容を読む（`knowledge.ocr_pdf` / `streetview_tools` と同じ作法:
    一時ファイルを --add-dir + Read ツールで見せる）。"""
    from services.claude_client import ClaudeError, run_claude
    prompt = (
        f"次の画像ファイル（ディレクトリ {tmp_dir} 内の {filename}）を Read ツールで開いて見てください。"
        "写っている内容を具体的に説明し、書かれている文字（見出し・数値・氏名・日付など）があれば"
        "そのまま書き起こしてください。書類やスクリーンショットならその種類（請求書・契約書・"
        "チャット画面など）も添えてください。判読できない場合は「判読できませんでした」と正直に"
        "書いてください。"
    )
    try:
        env = run_claude(prompt, model="sonnet", timeout=180, add_dir=tmp_dir, allow_read=True)
    except ClaudeError:
        return None
    return (env.get("result") or "").strip() or None


def read_line_image(message_id: str) -> str:
    """LINE の画像メッセージ（写真・スクリーンショット）を claude vision で読む。

    Excel/PDF等と違いテキスト抽出はできないので、`_analyze_image` で「写っている内容」と
    「書かれている文字」を書き起こしてもらい、本文に足せる形にする。
    """
    token = config.get("line_channel_access_token")
    if not token:
        return _describe("画像", "", "LINEのアクセストークンが未設定")
    tmp = tempfile.mkdtemp(prefix="cwai-img-")
    try:
        dest = os.path.join(tmp, "image")
        ctype = _download_ctype(
            f"https://api-data.line.me/v2/bot/message/{message_id}/content", dest,
            headers={"Authorization": f"Bearer {token}"})
        ext = _IMAGE_EXT_BY_MIME.get(ctype, ".jpg")
        img_name = "image" + ext
        os.rename(dest, os.path.join(tmp, img_name))
        text = _analyze_image(tmp, img_name)
        if text is None:
            return _describe("画像", "", "画像認識(claude vision)に失敗しました")
        return _describe("画像", text)
    except ValueError:
        return _describe("画像", "", f"{MAX_BYTES // 1024 // 1024}MB を超えるので読みませんでした")
    except Exception as e:
        return _describe("画像", "", f"読み取りに失敗: {type(e).__name__}")
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
