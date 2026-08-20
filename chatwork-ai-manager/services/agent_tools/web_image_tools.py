"""ネット取得画像（streetview_lookup等）をChatwork/LINEへ送るTool（TASK-20260819-005）。

streetview_lookup 等が返す image_token を使って、取得した衛星写真・Street View画像を
そのまま利用者へ送る。既存の chatwork_send_file（社内共有フォルダ限定）とは別経路で、
こちらはWebから一時取得した画像専用のため共有フォルダの制限は適用しない
（そもそも社外秘のファイルではないため）。画像は services/web_image_store.py の
一時保管庫（TTLあり）にあるので、時間が経つと image_token が失効する
（その場合は streetview_lookup 等で取り直してから送る）。
"""
import os

from services import config, line_client, web_image_store
from services.chatwork import ChatworkClient, ChatworkError


def chatwork_send_web_image(room_id, image_token, message=None):
    """ネットから取得した画像（streetview_lookupの結果等）をChatworkへ添付送信する。"""
    if not room_id:
        return {"ok": False, "error": "room_id が必要です"}
    if not image_token:
        return {"ok": False, "error": "image_token が必要です（streetview_lookup等の結果から渡す）"}
    path = web_image_store.path_for(image_token)
    if not path:
        return {"ok": False, "error": "画像が見つかりません（一定時間で自動失効します。"
                                       "必要なら取得し直してから送ってください）"}
    body = message or "取得した画像をお送りします。"
    try:
        file_id = ChatworkClient().post_file(room_id, path, message=body,
                                             filename=os.path.basename(path))
    except ChatworkError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "sent": True, "file_id": file_id}


def line_send_web_image(image_token, message=None, user_id=None):
    """ネットから取得した画像（streetview_lookupの結果等）をLINEへ画像メッセージとしてpushする。

    user_id を省略した場合、LINE経由の依頼であれば依頼者本人（環境変数 CWAI_LINE_USER_ID）へ
    自動で送る。Chatwork経由の依頼でLINEへ送りたい場合は user_id を明示すること。
    """
    path = web_image_store.path_for(image_token)
    if not path:
        return {"ok": False, "error": "画像が見つかりません（一定時間で自動失効します。"
                                       "必要なら取得し直してから送ってください）"}
    target = user_id or os.environ.get("CWAI_LINE_USER_ID")
    if not target:
        return {"ok": False, "error": "送り先のLINE userIdが分かりません"
                                       "（LINE経由の依頼以外はuser_idを指定してください）"}
    domain = config.get("ngrok_domain")
    if not domain:
        return {"ok": False, "error": "ngrok_domain が未設定のため画像を公開できません"}
    url = f"https://{domain}/line/web_image/{os.path.basename(path)}"
    ok = line_client.push_image(target, url)
    if not ok:
        return {"ok": False, "error": "LINEへの画像送信に失敗しました"}
    if message:
        line_client.push(target, message, label="web_image")
    return {"ok": True, "sent": True}
