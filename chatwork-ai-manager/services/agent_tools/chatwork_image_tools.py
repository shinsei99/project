"""過去にChatworkへ投稿された画像を検索し、実物を再送信するTool（TASK-20260827-002）。

`chatwork_images`（TASK-20260827-001でclaude vision解析結果をキャッシュする目的で作った表）は
蓄積されるだけで検索・再送信の手段が無かった。ここでは2段構成にする:

  1. `chatwork_image_search` — キーワード（物件名/ルーム名/ファイル名/解析結果本文）でDBを検索する。
     まだ画像本体はダウンロードしない（検索結果が複数出るのに毎回落とすと無駄なため）。
  2. `chatwork_image_fetch` — ヒットした1件を選び、Chatworkから**再ダウンロード**して
     `web_image_store`（streetview_lookup等が使っているのと同じ一時保管庫）へ保存し、
     image_token を返す。実際にChatwork/LINEへ送るのは既存の
     `chatwork_send_web_image` / `line_send_web_image` をそのまま使う
     （streetview_lookup → 送信 と全く同じ流れに乗せることで、送信経路を増やさない）。

Chatworkはファイルを長期間保持するので、解析時に使った一時ファイルが消えていても
room_id/file_id さえ分かれば何度でも取り直せる（web_image_store 側のTTL=6時間だけ気にすればよい）。
"""
from db.connection import query
from services import web_image_store


def _row(r):
    return {
        "room_id": r["room_id"],
        "file_id": r["file_id"],
        "filename": r["filename"],
        "room_name": r["room_name"],
        "property_name": r["property_name"],
        "description": (r["description"] or "")[:200],
        "posted_at": r["created_at"],
    }


def chatwork_image_search(keyword=None, room_id=None, limit=10):
    """過去にChatworkへ投稿され解析済みの画像を検索する（image本体はまだ取得しない）。"""
    if not keyword and not room_id:
        return {"ok": False, "error": "keyword か room_id のどちらかが必要です"}
    sql = "SELECT * FROM chatwork_images WHERE 1=1"
    params = []
    if keyword:
        kw = f"%{keyword}%"
        sql += " AND (property_name LIKE ? OR room_name LIKE ? OR filename LIKE ? OR description LIKE ?)"
        params += [kw, kw, kw, kw]
    if room_id:
        sql += " AND room_id=?"
        params.append(room_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = query(sql, tuple(params))
    return {"ok": True, "count": len(rows), "images": [_row(r) for r in rows]}


def chatwork_image_fetch(room_id, file_id):
    """chatwork_image_search でヒットした画像を再ダウンロードし、送信用の image_token を発行する。

    実際の送信は image_token を chatwork_send_web_image / line_send_web_image に渡して行う。
    """
    if not room_id or not file_id:
        return {"ok": False, "error": "room_id と file_id が必要です"}
    import os
    import shutil
    import tempfile

    from services.chatwork import ChatworkClient, ChatworkError

    tmp = tempfile.mkdtemp(prefix="cwai-imgfetch-")
    try:
        cw = ChatworkClient()
        try:
            data, filename = cw.download_file(room_id, file_id)
        except ChatworkError as e:
            return {"ok": False, "error": f"取得に失敗: {e}"}
        if not data:
            return {"ok": False, "error": "画像を取得できませんでした（Chatwork側で削除済みの可能性があります）"}
        dest = os.path.join(tmp, filename or f"image-{file_id}.jpg")
        with open(dest, "wb") as f:
            f.write(data)
        token = web_image_store.save(dest)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {
        "ok": True,
        "image_token": token,
        "hint": "この image_token を chatwork_send_web_image / line_send_web_image に渡すと実際に送れます",
    }
