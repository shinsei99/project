"""受信した添付ファイル（Excel・Word・PDF・CSV・テキスト）を読んで本文にする。

**なぜ要るのか**: これまで Chatwork / LINE に貼られたファイルは、本文のテキストしか
見ていなかったので **完全に無視されていた**（`[download:...]` タグが素通り）。
「この見積を見て」と Excel を貼られても中身を知らないまま答えていた。

方針:
- **抽出器は増やさない。** `services/knowledge.py` の `_EXTRACTORS`（社内資料の取込で
  すでに使っているもの）をそのまま借りる。対応形式が増えたら両方に効く。
- 落とすのは一時ディレクトリ。**読み終わったら必ず消す**（個人情報を残さない）。
- 大きいファイルは落とさない・長い本文は切る（定額枠とタイムアウトを守るため）。

画像（LINEの写真・スクリーンショット・Chatworkの添付画像等）は別ルート
（`read_line_image` / `read_chatwork_image`）で扱う。テキスト抽出器ではなく claude vision
（`services/knowledge.ocr_pdf` / `streetview_tools` と同じ作法: 一時ファイルへ保存 →
`--add-dir` + `Read` ツールで見せる）で内容を読む（LINE: TASK-20260825-006、
Chatwork: TASK-20260827-001）。
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

# 音声添付（ボイスメモ等）の拡張子→Gemini向けMIME（TASK-20260826-004）
_AUDIO_MIME_BY_EXT = {
    ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".mp3": "audio/mpeg",
    ".wav": "audio/wav", ".aac": "audio/aac", ".ogg": "audio/ogg",
    ".oga": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac",
    ".amr": "audio/amr", ".3gp": "audio/3gpp", ".3gpp": "audio/3gpp",
    ".caf": "audio/x-caf",
}
AUDIO_EXTENSIONS = frozenset(_AUDIO_MIME_BY_EXT)

# Chatwork添付画像（写真・スクリーンショット等）の拡張子（TASK-20260827-001）。
# ChatworkのファイルAPIはContent-Typeでなく拡張子で判定する（LINEは逆にContent-Type頼み）
IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff",
})

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


def read_chatwork_files(room_id, refs: list[tuple[int, str]], message_id=None) -> str:
    """Chatwork のファイルを落として本文にする。失敗しても例外は投げない。

    `message_id`（このファイルが添付されたメッセージ）は画像添付の場合のみ使う
    （前後メッセージの文脈からタイトルを付けるため。TASK-20260827-003）。
    """
    if not refs:
        return ""
    from services.chatwork import ChatworkClient, ChatworkError
    cw = ChatworkClient()
    tmp = tempfile.mkdtemp(prefix="cwai-att-")
    parts = []
    try:
        for file_id, name in refs:
            ext0 = os.path.splitext(name)[1].lower()
            if ext0 in _AUDIO_MIME_BY_EXT:
                # 音声は専用ルート（Gemini文字起こし→Claude要約・キャッシュ有）。
                # get_file/downloadも中で行うのでここでは呼ばない（二重取得を避ける）
                parts.append(transcribe_chatwork_audio(room_id, file_id, name))
                continue
            if ext0 in IMAGE_EXTENSIONS:
                # 画像は専用ルート（claude vision・キャッシュ有）。
                # get_file/downloadも中で行うのでここでは呼ばない（二重取得を避ける）
                parts.append(read_chatwork_image(room_id, file_id, name, message_id=message_id))
                continue
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


_AUDIO_SUMMARY_PROMPT = (
    "次はChatworkに投稿された音声ファイル「{name}」の文字起こしです。"
    "内容を3〜5行程度で簡潔に要約してください。"
    "「誰が・何を・いつまでに」といった業務上の要点があれば漏らさず含めてください。"
    "前置きや説明は不要で、要約の本文だけを出力してください。\n\n"
    "----- 文字起こし -----\n{transcript}"
)


def _audio_cache_get(room_id, file_id):
    from db.connection import query
    rows = query("SELECT * FROM audio_transcripts WHERE room_id=? AND file_id=?", (room_id, file_id))
    return rows[0] if rows else None


def _audio_cache_put(room_id, file_id, filename, transcript, summary):
    from db.connection import get_conn
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audio_transcripts (room_id, file_id, filename, transcript, summary) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(room_id, file_id) DO UPDATE SET filename=excluded.filename, "
            "transcript=excluded.transcript, summary=excluded.summary",
            (room_id, file_id, filename, transcript, summary),
        )


def transcribe_chatwork_audio(room_id, file_id: int, name: str) -> str:
    """Chatwork の音声添付（ボイスメモ等）を文字起こし→要約する（TASK-20260826-004）。

    文字起こしは Gemini（claude は音声非対応のため）、要約は既存の Claude 呼び出しで行う。
    結果は `audio_transcripts` にキャッシュし、同じ添付が会話コンテキストへ何度出てきても
    二度と外部へ問い合わせない。失敗しても例外は投げない（QA/TODO抽出を止めないため）。
    """
    cached = _audio_cache_get(room_id, file_id)
    if cached:
        if not cached["transcript"]:
            return _describe(name, "", "音声に内容がありませんでした（無音・雑音のみ）")
        return _describe(name, f"▼文字起こし\n{cached['transcript']}\n\n▼要約\n{cached['summary']}")

    from services.chatwork import ChatworkClient, ChatworkError
    tmp = tempfile.mkdtemp(prefix="cwai-audio-")
    try:
        cw = ChatworkClient()
        info = cw.get_file(room_id, file_id)
        url = info.get("download_url")
        name = name or info.get("filename") or f"audio-{file_id}"
        if not url:
            return _describe(name, "", "ダウンロードURLを取得できませんでした")
        ext = os.path.splitext(name)[1].lower()
        mime = _AUDIO_MIME_BY_EXT.get(ext, "audio/mp4")
        dest = os.path.join(tmp, os.path.basename(name) or f"audio-{file_id}")
        _download(url, dest)
        with open(dest, "rb") as f:
            audio_bytes = f.read()

        from services.gemini_client import GeminiError, transcribe_audio
        try:
            transcript = transcribe_audio(audio_bytes, mime)
        except GeminiError as e:
            return _describe(name, "", f"文字起こしに失敗: {e}")
        if not transcript:
            _audio_cache_put(room_id, file_id, name, "", "")
            return _describe(name, "", "音声に内容がありませんでした（無音・雑音のみ）")

        from services import settings
        from services.claude_client import ClaudeError, run_text
        try:
            summary, _env = run_text(
                _AUDIO_SUMMARY_PROMPT.format(name=name, transcript=transcript),
                model=settings.get_setting("model_audio_summary", "haiku"), timeout=120)
        except ClaudeError:
            summary = "（要約に失敗しました）"
        _audio_cache_put(room_id, file_id, name, transcript, summary)
        return _describe(name, f"▼文字起こし\n{transcript}\n\n▼要約\n{summary}")
    except ValueError:
        return _describe(name, "", f"{MAX_BYTES // 1024 // 1024}MB を超えるので読みませんでした")
    except ChatworkError as e:
        return _describe(name, "", f"取得に失敗: {e}")
    except Exception as e:
        return _describe(name, "", f"読み取りに失敗: {type(e).__name__}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _image_cache_get(room_id, file_id):
    from db.connection import query
    rows = query("SELECT * FROM chatwork_images WHERE room_id=? AND file_id=?", (room_id, file_id))
    return rows[0] if rows else None


def _image_cache_put(room_id, file_id, filename, description, room_name=None,
                      property_name=None, title=None):
    from db.connection import get_conn
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chatwork_images "
            "(room_id, file_id, filename, description, room_name, property_name, title) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(room_id, file_id) DO UPDATE SET filename=excluded.filename, "
            "description=excluded.description, room_name=excluded.room_name, "
            "property_name=excluded.property_name, title=excluded.title",
            (room_id, file_id, filename, description, room_name, property_name, title),
        )


def _room_name(room_id) -> str | None:
    from db.connection import query_one
    row = query_one("SELECT name FROM rooms WHERE room_id=?", (room_id,))
    return row["name"] if row else None


# LINEで受け取った写真を chatwork_images に入れるときの room_id（2026-08-27）。
# Chatworkのroom_idは数値なので、文字列 'line' と衝突しない。
LINE_ROOM_KEY = "line"

# 前後メッセージの文脈として渡す件数・文字数（TASK-20260827-003）
_CONTEXT_MSG_COUNT = 4
_CONTEXT_LINE_MAX = 200
_CONTEXT_TOTAL_MAX = 1000


def _clean_context_line(body: str) -> str:
    """会話コンテキストに渡す1行を整形（[download:..] 等のタグを剥がす）。"""
    text = _DOWNLOAD_RE.sub(lambda m: m.group(2).strip(), body or "")
    text = re.sub(r"\[[^\]]*\]", "", text).strip()
    return text[:_CONTEXT_LINE_MAX]


def _anchor_caption(room_id, message_id) -> str | None:
    """画像を投稿したのと**同一メッセージ**に書かれた本文（キャプション）を取り出す。

    Chatworkは本文とファイルを1メッセージにまとめて投稿できる
    （例:「本庄西駐車場です [download:123]image.jpg[/download]」）。
    従来 `_surrounding_message_context` は前後の別メッセージしか見ておらず、
    **同一メッセージ内のキャプションは完全に無視されていた**（TASK-20260827-009で判明。
    「メッセージ本文に物件名が明記されているのに画像解析側の誤判定でタイトルがずれる」
    事故の根本原因の一つ）。前後の会話より直接的な手がかりのため最優先で扱う。
    """
    if not message_id:
        return None
    from db.connection import query_one
    row = query_one("SELECT body FROM messages WHERE room_id=? AND message_id=?", (room_id, message_id))
    if not row:
        return None
    return _clean_context_line(row["body"]) or None


def _surrounding_message_context(room_id, message_id) -> str | None:
    """画像が投稿されたメッセージの前後（同じ会話）のメッセージ本文を集める（TASK-20260827-003）。

    投稿者が別メッセージで書いた場所名・案件名の説明を vision プロンプトに渡すため。
    `messages` は poll_room で画像メッセージと同時に一括保存済みなので、ここでは
    Chatwork APIを呼ばず自DBを見るだけでよい。
    """
    if not message_id:
        return None
    from db.connection import query, query_one
    anchor = query_one(
        "SELECT send_time FROM messages WHERE room_id=? AND message_id=?",
        (room_id, message_id),
    )
    if not anchor:
        return None
    send_time = anchor["send_time"]
    before = query(
        "SELECT account_name, body FROM messages WHERE room_id=? AND "
        "(send_time<? OR (send_time=? AND message_id<?)) "
        "ORDER BY send_time DESC, message_id DESC LIMIT ?",
        (room_id, send_time, send_time, message_id, _CONTEXT_MSG_COUNT),
    )
    after = query(
        "SELECT account_name, body FROM messages WHERE room_id=? AND "
        "(send_time>? OR (send_time=? AND message_id>?)) "
        "ORDER BY send_time ASC, message_id ASC LIMIT ?",
        (room_id, send_time, send_time, message_id, _CONTEXT_MSG_COUNT),
    )
    lines = []
    for r in reversed(before):
        text = _clean_context_line(r["body"])
        if text:
            lines.append(f"{r['account_name'] or ''}: {text}")
    for r in after:
        text = _clean_context_line(r["body"])
        if text:
            lines.append(f"{r['account_name'] or ''}: {text}")
    if not lines:
        return None
    return "\n".join(lines)[:_CONTEXT_TOTAL_MAX]


# claude visionの回答の末尾に付けさせる `物件名: ○○` 行（TASK-20260827-002・検索用に拾う）
_PROPERTY_LINE_RE = re.compile(r"\n?物件名[:：]\s*(.*?)\s*$")
_UNKNOWN_PROPERTY_NAMES = {"", "不明", "なし", "N/A", "n/a"}

# claude visionの回答の末尾に付けさせる `タイトル: ○○` 行（TASK-20260827-003・検索用に拾う）
_TITLE_LINE_RE = re.compile(r"\n?タイトル[:：]\s*(.*?)\s*$")
_UNKNOWN_TITLES = {"", "不明", "なし", "N/A", "n/a"}


def _split_property_name(text: str) -> tuple[str, str | None]:
    """解析結果の末尾から `物件名: ○○` 行を切り離す。無ければそのまま返す。"""
    m = _PROPERTY_LINE_RE.search(text or "")
    if not m:
        return text, None
    name = m.group(1).strip()
    cleaned = (text[:m.start()]).rstrip()
    if name in _UNKNOWN_PROPERTY_NAMES:
        return cleaned, None
    return cleaned, name


def _split_title(text: str) -> tuple[str, str | None]:
    """解析結果の末尾から `タイトル: ○○` 行を切り離す。無ければそのまま返す。"""
    m = _TITLE_LINE_RE.search(text or "")
    if not m:
        return text, None
    name = m.group(1).strip()
    cleaned = (text[:m.start()]).rstrip()
    if name in _UNKNOWN_TITLES:
        return cleaned, None
    return cleaned, name


def _resolve_master_property_name(context_text, description, property_name, title) -> str | None:
    """vision解析結果・前後の会話文の中に管理物件マスター（properties・108件）の正式名称が
    含まれていれば、それを返す（TASK-20260827-005）。

    見つかれば `gis_property_search` 等の検索結果と表記が一致する正式名称を優先的に使い、
    見つからなければ None を返して呼び出し側が今まで通りの自由記述（vision推定のproperty_name/
    タイトル）にフォールバックする（例:「花園町駅前駐輪場」のようなマスターに無い固有名称）。
    """
    combined = "\n".join(filter(None, [context_text, description, property_name, title]))
    if not combined:
        return None
    from services import gis
    matched = gis.match_property_in_text(combined)
    return matched["name"] if matched else None


def _resolve_master_property_from_caption(caption_text) -> str | None:
    """**画像と同一メッセージのキャプション**にマスター物件名がそのまま出現していないか確認する
    （TASK-20260827-009）。見つかれば画像解析(vision)の推定より優先して採用する。

    前後メッセージ（surrounding）は対象にしない。実データ（room_id=349546270の巡回写真）で
    検証したところ、前後メッセージまで対象に含めると、同じ会話ルーム内で時間的に近いだけの
    無関係な別案件の物件名（例: ランドリー対応の会話）を拾って誤爆することを確認した。
    同一メッセージのキャプションは投稿者本人が直接書いた文字列であり誤爆の余地が無いため、
    決定的な上書きにはここだけを使う（`_resolve_master_property_name` の
    vision解析結果＋前後メッセージを照合する経路は、キャプションが無い/マスターに一致しない
    画像向けの従来通りのフォールバックとして残す）。
    """
    if not caption_text:
        return None
    from services import gis
    matched = gis.match_property_in_text(caption_text)
    return matched["name"] if matched else None


def read_chatwork_image(room_id, file_id: int, name: str, message_id=None) -> str:
    """Chatwork の画像添付（写真・スクリーンショット等）を claude vision で読む（TASK-20260827-001）。

    LINEの `read_line_image` と同じ `_analyze_image` を使う。結果は `chatwork_images` に
    キャッシュし、同じ添付が会話コンテキストへ何度出てきても二度と解析し直さない
    （`transcribe_chatwork_audio` と同じキャッシュの考え方）。失敗しても例外は投げない
    （QA/TODO抽出を止めないため）。

    `message_id` が分かれば、同一メッセージのキャプション（TASK-20260827-009で追加）と、
    その前後に投稿された同じ会話のメッセージ（場所・案件名の説明文等）を vision プロンプトに
    渡し、画像単体では分からない具体的なタイトルを付けさせる（TASK-20260827-003）。
    さらに、それらメッセージ本文の中に管理物件マスターの正式名称がそのまま書かれていれば、
    画像解析(vision)の推定より優先してそれをタイトル・物件名として採用する
    （TASK-20260827-009・巡回写真等でメッセージに物件名が明記されているのに vision 側の
    誤判定でタイトルがずれる事故対策）。
    """
    cached = _image_cache_get(room_id, file_id)
    if cached:
        if not cached["description"]:
            return _describe(name, "", "画像認識(claude vision)に失敗しました")
        return _describe(name, cached["description"])

    from services.chatwork import ChatworkClient, ChatworkError
    tmp = tempfile.mkdtemp(prefix="cwai-img-")
    try:
        cw = ChatworkClient()
        info = cw.get_file(room_id, file_id)
        url = info.get("download_url")
        name = name or info.get("filename") or f"image-{file_id}"
        if not url:
            return _describe(name, "", "ダウンロードURLを取得できませんでした")
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        img_name = "image" + ext
        dest = os.path.join(tmp, img_name)
        _download(url, dest)
        caption_text = _anchor_caption(room_id, message_id)
        surrounding_text = _surrounding_message_context(room_id, message_id)
        context_text = "\n\n".join(filter(None, [
            f"（この画像を投稿したメッセージ本文）\n{caption_text}" if caption_text else None,
            f"（前後のメッセージ）\n{surrounding_text}" if surrounding_text else None,
        ])) or None
        text = _analyze_image(tmp, img_name, ask_property=True, context_text=context_text)
        if text is None:
            return _describe(name, "", "画像認識(claude vision)に失敗しました")
        text, title = _split_title(text)
        description, property_name = _split_property_name(text)
        forced_name = _resolve_master_property_from_caption(caption_text)
        if forced_name:
            property_name, title = forced_name, forced_name
        else:
            property_name = _resolve_master_property_name(
                context_text, description, property_name, title) or property_name
        _image_cache_put(room_id, file_id, name, description, _room_name(room_id),
                          property_name, title)
        return _describe(name, description)
    except ValueError:
        return _describe(name, "", f"{MAX_BYTES // 1024 // 1024}MB を超えるので読みませんでした")
    except ChatworkError as e:
        return _describe(name, "", f"取得に失敗: {e}")
    except Exception as e:
        return _describe(name, "", f"読み取りに失敗: {type(e).__name__}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


def _make_flipped_copy(tmp_dir: str, filename: str) -> str | None:
    """原本を180度回転した複製を作り、そのファイル名を返す（失敗したら None）。

    macOS 標準の `sips` を使う（Pillow を足したくないため）。
    向きが分からない写真を vision に読ませるとき、原本と一緒に見せて選ばせる。
    """
    import subprocess
    src = os.path.join(tmp_dir, filename)
    stem, ext = os.path.splitext(filename)
    out_name = f"{stem}__flipped{ext or '.jpg'}"
    out = os.path.join(tmp_dir, out_name)
    try:
        subprocess.run(["/usr/bin/sips", "--rotate", "180", src, "--out", out],
                       check=True, capture_output=True, timeout=60)
    except Exception:
        return None
    return out_name if os.path.exists(out) else None


def _analyze_image(tmp_dir: str, filename: str, ask_property: bool = False,
                    context_text: str | None = None) -> str | None:
    """claude vision で画像1枚の内容を読む（`knowledge.ocr_pdf` / `streetview_tools` と同じ作法:
    一時ファイルを --add-dir + Read ツールで見せる）。

    `ask_property=True` のとき、末尾に `物件名: ○○` の1行を追加させる
    （Chatwork画像の検索用。TASK-20260827-002・`_split_property_name` で切り離して保存する）。

    `context_text` が渡された場合（画像投稿と同一メッセージのキャプション＋前後に同じ会話で
    投稿されたメッセージ本文。TASK-20260827-009でキャプションを追加）、画像単体では分からない
    場所名・案件名をそこから拾わせ、末尾に `タイトル: ○○` の1行を追加させる
    （TASK-20260827-003・`_split_title` で切り離して保存する）。
    """
    from services.claude_client import ClaudeError, run_claude
    # ★上下反転した複製も一緒に見せる（2026-08-27）。
    #   Chatworkに上がった巡回写真は **EXIFの回転情報が空（sipsで <nil>）なのにピクセルが逆さま**
    #   だった（Chatwork側が回転情報を捨てているとみられる）。実測で12件中6件の説明に
    #   「上下反転」と書かれており、看板の文字が読めず物件名を判定できていなかった。
    #   EXIFが無い以上プログラムからは向きを決められないので、両方を見せて選ばせる。
    flipped = _make_flipped_copy(tmp_dir, filename)
    files_note = (
        f"{filename}（原本）と {flipped}（原本を180度回転したもの）の2つ"
        if flipped else filename
    )
    prompt = (
        f"次の画像ファイル（ディレクトリ {tmp_dir} 内の {files_note}）を Read ツールで開いて見てください。"
        + ("**この2つは同じ写真で、向きだけが違います。天地が正しいほうだけを見て答えてください**"
           "（撮影時に上下逆さまで保存されていることがあるため）。回転の話は説明に書かないでください。"
           if flipped else "")
        + "写っている内容を具体的に説明し、書かれている文字（見出し・数値・氏名・日付など）があれば"
        "そのまま書き起こしてください。書類やスクリーンショットならその種類（請求書・契約書・"
        "チャット画面など）も添えてください。判読できない場合は「判読できませんでした」と正直に"
        "書いてください。"
    )
    if ask_property:
        prompt += (
            "\n\n最後に、写っている建物・部屋が属する物件名（マンション名・ビル名など。"
            "外観の看板・郵便受け・検針票の宛先等から分かる場合のみ）を、"
            "`物件名: ○○` という1行だけで追加してください。分からない・写っていない場合は"
            "`物件名: 不明` としてください。"
        )
        context_block = (
            f"\n\n参考: この画像の投稿メッセージ本文・前後のメッセージ\n{context_text}"
            if context_text else ""
        )
        prompt += (
            "\n\nさらに、この画像に付けるタイトル（例:「花園町駅前駐輪場」のような、"
            "具体的な場所名・案件名など内容が一目で分かる短い名前）を考え、"
            "`タイトル: ○○` という1行を追加してください。上記のメッセージ本文（特に画像と"
            "同じメッセージに書かれた文章）に場所・物件名・案件名が明記されている場合は、"
            "**それを画像から見た印象より必ず優先して**タイトルに使ってください"
            "（画像だけからは分からない情報でも、メッセージに書いてあれば使ってください。"
            "画像の見た目から別の場所のように見えても、メッセージの記載を信用してください）。"
            "手がかりが無ければ、画像から読み取れる内容から分かりやすい短い"
            "タイトルを付けてください。それでも付けられない場合は `タイトル: 不明` として"
            f"ください。{context_block}"
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
        text = _analyze_image(tmp, img_name, ask_property=True)
        if text is None:
            return _describe("画像", "", "画像認識(claude vision)に失敗しました")
        # ★DBへ登録する（2026-08-27）。以前は解析結果を文字列で返すだけで保存しておらず、
        #   「この写真は◯◯です」と言われてもタイトルを付け替える対象が存在しなかった
        #   （Chatwork側は保存しているのにLINE側だけ抜けていた）。room_id は 'line' 固定。
        body, title = _split_title(text)
        body, prop = _split_property_name(body)
        try:
            _image_cache_put(LINE_ROOM_KEY, str(message_id), img_name, body,
                             room_name="LINE", property_name=prop, title=title)
        except Exception:
            pass          # 保存に失敗しても回答は返す
        return _describe("画像", body) + (
            f"\n（この写真は room_id=\"{LINE_ROOM_KEY}\" file_id=\"{message_id}\" として登録済み。"
            "利用者が『この写真は◯◯です』と名前を教えてきたら "
            "chatwork_image_set_title でこの room_id/file_id のタイトルを直すこと）"
        )
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
