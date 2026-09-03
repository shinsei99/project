"""Chatworkに投稿されたPDF・Word・Excel等の文書添付をその場で読むTool（TASK-20260903-002）。

画像は chatwork_image_search / chatwork_image_fetch で対応済みだが、鍵預かり書のような
PDF/文書添付を読む常設の手段が無かった。今回オーナーからの依頼で、AIが
chatwork_image_fetch と同じダウンロード手順をその場しのぎで流用してPDFを読んだが、
標準ツールとして無かったため最初は「読めない」と誤って回答してしまった経緯がある
（今後同じPDF添付が来るたびに同じ手順を再現できるよう、常設ツールとして整備する）。

ダウンロード手順は chatwork_image_fetch と同じ（get_file→download_url→取得）。
取得後は kb_read_document と同じ抽出パイプライン（services.knowledge.extract /
テキスト層の無いPDFはOCRフォールバック）に流して中身を返す。

kb_read_document と違う点: ダウンロード先が使い捨ての一時ディレクトリなので、
**恒久的な社内資料索引(knowledge_documents)には登録しない**（索引の filepath が
指す先がすぐ消えてしまう）。Chatworkの添付はその会話に紐づく一回性の文書であり、
共有フォルダの正典資料（kb_search/kb_read_documentの対象）とは性質が違うため。
"""
import os
import shutil
import tempfile

from services import company_scope as CS
from services import knowledge

_MAX_BYTES = 30 * 1024 * 1024  # 30MB（スキャンPDFの複数ページでも十分な余裕）
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".heic", ".heif", ".webp"}


def chatwork_read_attachment(room_id, file_id, max_pages: int = 15):
    """Chatworkの添付ファイル（PDF・Word・Excel等の文書系）を取得し、その場で中身を読む。

    画像（jpg/png等）は対象外（chatwork_image_search / chatwork_image_fetch を使うこと）。
    テキスト層のあるPDF・Office文書はそのまま抽出し、テキスト層の無いスキャンPDFは
    macOS Vision→claude vision の二段構えでOCRする（kb_read_documentと同じ仕組み）。
    """
    if CS.blocks_room(room_id):
        return CS.deny(room_id, "添付ファイルの取得")
    if not room_id or not file_id:
        return {"ok": False, "error": "room_id と file_id が必要です"}

    from services.chatwork import ChatworkClient, ChatworkError

    cw = ChatworkClient()
    try:
        info = cw.get_file(room_id, file_id)
    except ChatworkError as e:
        return {"ok": False, "error": f"ファイル情報の取得に失敗: {e}"}
    if not info:
        return {"ok": False, "error": "対象の添付が見つかりません（file_idが違うか、既に削除済みの可能性）"}

    filename = info.get("filename") or f"file_{file_id}"
    ext = os.path.splitext(filename)[1].lower()
    if ext in _IMAGE_EXT:
        return {"ok": False, "error": "画像ファイルです。chatwork_image_search / "
                "chatwork_image_fetch を使ってください"}
    if ext not in knowledge.SUPPORTED_EXT:
        return {"ok": False, "error": f"未対応の形式です（{ext or '拡張子なし'}）"}

    filesize = info.get("filesize")
    if isinstance(filesize, int) and filesize > _MAX_BYTES:
        return {"ok": False, "error": f"ファイルが大きすぎます（{filesize // 1024 // 1024}MB）"}

    tmp = tempfile.mkdtemp(prefix="cwai-attach-")
    try:
        try:
            data, dl_filename = cw.download_file(room_id, file_id)
        except ChatworkError as e:
            return {"ok": False, "error": f"取得に失敗: {e}"}
        if not data:
            return {"ok": False, "error": "ファイルを取得できませんでした（Chatwork側で削除済みの可能性があります）"}
        if len(data) > _MAX_BYTES:
            return {"ok": False, "error": f"ファイルが大きすぎます（{len(data) // 1024 // 1024}MB）"}
        filename = dl_filename or filename
        path = os.path.join(tmp, filename)
        with open(path, "wb") as f:
            f.write(data)

        try:
            sections = knowledge.extract(path)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        used_ocr = False
        if not sections and ext == ".pdf":
            try:
                sections = knowledge.ocr_pdf(path, max_pages=max_pages)
            except knowledge.OcrSkippedByQuotaSaver as e:
                return {"ok": False, "error": f"節約モード中のため読めませんでした: {e}"}
            except knowledge.OcrUnavailable as e:
                return {"ok": False, "error": f"OCRに失敗しました: {e}"}
            used_ocr = bool(sections)
        if not sections:
            return {"ok": False, "error": "テキストを抽出できませんでした（中身が画像だけ等の可能性）"}

        text = "\n\n".join(
            f"【{filename}" + (f" / {ref}" if ref else "") + f"】\n{body}"
            for body, ref in sections
        )
        return {
            "ok": True,
            "filename": filename,
            "used_ocr": used_ocr,
            "section_count": len(sections),
            "text": text[:20000],
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
