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

DBの行は消さず検索側でグルーピングする（TASK-20260827-004）。同一room_id・同一filenameで
撮影時刻が近い（既定30分以内）行は「同じ被写体の重複投稿」とみなし、代表1件だけを返す
（実例: room_id=349546270 の IMG_0254.jpeg が file_id違いで05:34と05:42の2回投稿されていた
駐輪場写真）。DB行自体は残すので、chatwork_image_fetch はどちらのfile_idでも従来通り引ける。

ただし、ChatworkのiPhoneカメラ写真は同日中すべて同じfilename（例: image_2026_8_27.jpeg）に
なるため、filenameだけでは同一被写体かどうか分からない。TASK-20260827-008で判明した実例:
1時間の間に投稿された「もと美モータープール／エコパーキング京橋東×2／もと美モータープール／
本庄西駐車場」計5枚が全て同一filenameかつ相互に30分以内だったため1グループに連鎖統合され、
後から明示キャプション付きで投稿された「本庄西駐車場」が、キャプション無しでAIが
「4か所のいずれか」と曖昧命名した1枚目の代表titleに隠れてしまった。
そのため時間窓だけでなく、property_name/titleが両方の行に明示されていて食い違う場合は
別被写体と確定して統合しない（`_is_same_subject`）。どちらも空でラベルで判別できない場合のみ
description（vision解析結果）の類似度で判定する。
"""
import difflib

from db.connection import execute, query, query_one
from services import web_image_store
from services import company_scope as CS

_DEDUP_WINDOW_SECONDS = 30 * 60
_DESC_SIMILARITY_THRESHOLD = 0.5


def _row(r):
    return {
        "room_id": r["room_id"],
        "file_id": r["file_id"],
        "filename": r["filename"],
        "room_name": r["room_name"],
        "property_name": r["property_name"],
        "title": r["title"],
        "description": (r["description"] or "")[:200],
        "posted_at": r["created_at"],
    }


def _parse_ts(s):
    import datetime

    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _conflicts(a_val, b_val):
    """両方に値があって食い違うか（=別被写体の確たる証拠か）。"""
    a_val = (a_val or "").strip()
    b_val = (b_val or "").strip()
    return bool(a_val) and bool(b_val) and a_val != b_val


def _desc_similarity(a, b):
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return None
    return difflib.SequenceMatcher(None, a, b).ratio()


def _is_same_subject(candidate, cluster_members):
    """candidateをこのクラスタ（同一被写体の連続投稿）へ統合してよいか判定する。

    property_name/titleのどちらかがクラスタ内の既存行と食い違えば別被写体と確定し、
    統合しない（曖昧タイトルの写真が後続の明示キャプション写真を隠す事故を防ぐ）。
    双方ラベルが無く判別できない場合のみdescriptionの類似度にフォールバックする。
    """
    for m in cluster_members:
        if _conflicts(candidate["property_name"], m["property_name"]):
            return False
        if _conflicts(candidate["title"], m["title"]):
            return False
    if not (candidate["property_name"] or candidate["title"]):
        unlabeled = [m for m in cluster_members if not (m["property_name"] or m["title"])]
        for m in unlabeled:
            similarity = _desc_similarity(candidate["description"], m["description"])
            if similarity is not None and similarity < _DESC_SIMILARITY_THRESHOLD:
                return False
    return True


def _dedup_rows(rows):
    """同一room_id・同一filenameで投稿時刻が近く、かつ同一被写体と判別できる行をまとめる。

    代表選びの優先順位: title有り > property_name有り > 投稿が最も早いもの。
    重複としてまとめられた件数は duplicate_count として代表側に付与する。
    """
    groups = {}
    order = []
    for r in rows:
        key = (r["room_id"], r["filename"])
        groups.setdefault(key, []).append(r)
        if key not in order:
            order.append(key)

    representatives = []
    for key in order:
        members = sorted(groups[key], key=lambda r: r["created_at"] or "")
        clusters = []
        for r in members:
            ts = _parse_ts(r["created_at"])
            placed = False
            for cluster in clusters:
                last_ts = _parse_ts(cluster[-1]["created_at"])
                within_window = ts and last_ts and (ts - last_ts).total_seconds() <= _DEDUP_WINDOW_SECONDS
                if within_window and _is_same_subject(r, cluster):
                    cluster.append(r)
                    placed = True
                    break
            if not placed:
                clusters.append([r])
        for cluster in clusters:
            best = sorted(
                cluster,
                key=lambda r: (
                    0 if r["title"] else 1,
                    0 if r["property_name"] else 1,
                    r["created_at"] or "",
                ),
            )[0]
            row = _row(best)
            row["duplicate_count"] = len(cluster)
            if len(cluster) > 1:
                row["duplicate_file_ids"] = [r["file_id"] for r in cluster if r["file_id"] != best["file_id"]]
            representatives.append((best["created_at"] or "", row))

    representatives.sort(key=lambda t: t[0], reverse=True)
    return [row for _, row in representatives]


def chatwork_image_search(keyword=None, room_id=None, limit=10):
    """過去にChatworkへ投稿され解析済みの画像を検索する（image本体はまだ取得しない）。

    keyword は title（投稿前後の会話文脈から付けたタイトル。TASK-20260827-003）/
    property_name（画像から読み取れた物件名）/ room_name / filename / description を対象にする。
    同一被写体の重複投稿は代表1件にまとめて返す（duplicate_count>1で分かる）。
    """
    if not keyword and not room_id:
        return {"ok": False, "error": "keyword か room_id のどちらかが必要です"}
    sql = "SELECT * FROM chatwork_images WHERE 1=1"
    params = []
    if keyword:
        kw = f"%{keyword}%"
        or_terms = [
            "title LIKE ?", "property_name LIKE ?", "room_name LIKE ?",
            "filename LIKE ?", "description LIKE ?",
        ]
        kw_params = [kw, kw, kw, kw, kw]
        # keywordが管理物件マスター（properties・108件）の物件名/住所に解決できる場合、
        # その正式名称でも検索する（TASK-20260827-005・表記ゆれ対策。例:
        # 画像は正式名称「クリスタルコート66」で保存されているが、キーワードが
        # 住所や表記違いでも正式名称に解決できれば拾えるようにする）
        from services import gis
        matched = gis.find_property(keyword)
        if matched and matched["name"] not in keyword:
            or_terms.append("property_name LIKE ?")
            kw_params.append(f"%{matched['name']}%")
        sql += " AND (" + " OR ".join(or_terms) + ")"
        params += kw_params
    if room_id:
        sql += " AND room_id=?"
        params.append(room_id)
    sql += " ORDER BY created_at DESC LIMIT 500"
    rows = query(sql, tuple(params))
    deduped = _dedup_rows(rows)[:limit]
    # ★他の会社のルームの画像は出さない（2026-08-30 オーナー指示）
    _ng = CS.other_rooms()
    if _ng:
        rows = [r for r in rows if (r.get('room_id') if isinstance(r, dict) else r['room_id']) not in _ng]
    return {"ok": True, "count": len(deduped), "images": deduped}


def chatwork_image_set_title(room_id, file_id, title):
    """画像のタイトルを手動で設定/更新する（vision解析の自動タイトル付けを補う用途）。

    投稿前後の会話から物件名・案件名が判明しているのに title が空のままの画像を、
    後から埋めるためのTool（TASK-20260827-004）。既存の行にしか設定できない
    （row自体はread_chatwork_imageの解析成功時にしか作られないため）。
    """
    if CS.blocks_room(room_id):
        return CS.deny(room_id, "画像の題名変更")
    if not room_id or not file_id:
        return {"ok": False, "error": "room_id と file_id が必要です"}
    if not title or not str(title).strip():
        return {"ok": False, "error": "title が空です"}
    existing = query_one(
        "SELECT room_id, file_id, filename, title FROM chatwork_images WHERE room_id=? AND file_id=?",
        (room_id, file_id),
    )
    if not existing:
        return {"ok": False, "error": f"該当画像が見つかりません（room_id={room_id}, file_id={file_id}）"}
    execute(
        "UPDATE chatwork_images SET title=? WHERE room_id=? AND file_id=?",
        (str(title).strip(), room_id, file_id),
    )
    return {
        "ok": True,
        "room_id": room_id,
        "file_id": file_id,
        "filename": existing["filename"],
        "old_title": existing["title"],
        "new_title": str(title).strip(),
    }


def chatwork_image_fetch(room_id, file_id):
    """chatwork_image_search でヒットした画像を再ダウンロードし、送信用の image_token を発行する。

    実際の送信は image_token を chatwork_send_web_image / line_send_web_image に渡して行う。
    """
    if CS.blocks_room(room_id):
        return CS.deny(room_id, "画像の取得")
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
    # どの image_token がどの写真かを覚えておく（送信時に番号を記録するため。2026-08-27）
    try:
        web_image_store.remember_source(token, room_id=room_id, file_id=file_id,
                                        title=_title_of(room_id, file_id))
    except Exception:
        pass
    return {
        "ok": True,
        "image_token": token,
        "hint": "この image_token を chatwork_send_web_image / line_send_web_image に渡すと実際に送れます",
    }


def _title_of(room_id, file_id):
    from db.connection import query_one
    r = query_one("SELECT title FROM chatwork_images WHERE room_id=? AND file_id=?",
                  (str(room_id), str(file_id)))
    return r["title"] if r else None


def chatwork_image_delete(room_id, file_id):
    """Chatworkへ間違えて投稿された画像を削除する（TASK-20260828-001）。

    調査結果（developer.chatwork.com で確認済み）: Chatwork API v2 には
    **ファイル単体を削除するエンドポイントが存在しない**（/rooms/{id}/files は
    GET/POSTのみ）。ファイルは投稿時に生成されるメッセージ（GET /files/{file_id} の
    `message_id`）に紐付いており、消せるのはメッセージ削除API
    (DELETE /rooms/{id}/messages/{message_id}) だけ。しかもこのAPIは
    **トークン所有アカウント（このAI自身）が投稿したメッセージしか削除できない**
    （他人のメッセージは403 "You can only edit the message you sent."。
    room管理者による例外もドキュメント上ない）。

    そのため実際の動作は2通りに分かれる:
      1. 投稿者がAI自身（chatwork_send_web_image等で誤って送った画像）→ 本当に削除できる。
      2. 投稿者が社員本人（「間違えて投稿された写真」の主用途）→ API側では削除不可。
         かわりに、投稿者名とmessage_idを返して人に手動削除を案内できるようにし、
         このBotの検索キャッシュ(chatwork_images)からは取り除く
         （以後 chatwork_image_search / 再送信の対象には出なくなる。
         Chatwork本体の画面からは消えないので、その旨を利用者に必ず伝えること）。
    """
    if CS.blocks_room(room_id):
        return CS.deny(room_id, "画像の削除")
    if not room_id or not file_id:
        return {"ok": False, "error": "room_id と file_id が必要です"}
    from services.chatwork import ChatworkClient, ChatworkError

    existing = query_one(
        "SELECT room_id, file_id, filename, title FROM chatwork_images WHERE room_id=? AND file_id=?",
        (room_id, file_id),
    )
    cw = ChatworkClient()
    try:
        info = cw.get_file(room_id, file_id)
    except ChatworkError as e:
        if e.status == 404:
            if existing:
                execute("DELETE FROM chatwork_images WHERE room_id=? AND file_id=?", (room_id, file_id))
            return {"ok": True, "deleted": True,
                    "note": "Chatwork側では既に削除済みでした（このBotのキャッシュも削除しました）"}
        return {"ok": False, "error": f"ファイル情報の取得に失敗: {e}"}
    if not info or not info.get("message_id"):
        return {"ok": False, "error": "対象の画像が見つかりません（file_idが違うか、既に削除済みの可能性）"}

    message_id = info.get("message_id")
    uploader = info.get("account") or {}
    uploader_id = uploader.get("account_id")
    uploader_name = uploader.get("name")

    my_account_id = _my_account_id()
    if my_account_id is not None and str(uploader_id) == str(my_account_id):
        try:
            cw.delete_message(room_id, message_id)
        except ChatworkError as e:
            return {"ok": False, "error": f"削除に失敗: {e}"}
        if existing:
            execute("DELETE FROM chatwork_images WHERE room_id=? AND file_id=?", (room_id, file_id))
        return {"ok": True, "deleted": True,
                "note": "Chatwork上のメッセージごと削除しました（このBot自身が投稿した画像でした）"}

    # 他人（社員）が投稿した画像 → Chatwork APIでは削除できない
    if existing:
        execute("DELETE FROM chatwork_images WHERE room_id=? AND file_id=?", (room_id, file_id))
    return {
        "ok": False,
        "deleted": False,
        "chatwork_still_visible": True,
        "uploader": uploader_name,
        "uploader_account_id": uploader_id,
        "message_id": message_id,
        "filename": info.get("filename"),
        "reason": "Chatwork APIには他人が投稿したファイルを削除する手段がありません"
                  "（削除できるのは投稿者本人のメッセージのみ。room管理者権限でもAPI越しには不可）。",
        "hint": f"投稿者「{uploader_name}」さん本人に、Chatworkアプリ上でこのメッセージ"
                f"（room_id={room_id}, message_id={message_id}）を手動削除してもらうよう案内してください。"
                "このBotの検索対象からは除外済みです（chatwork_image_search・再送信では以後出てきません）",
    }


def _my_account_id():
    from services.sync import get_ai_account_id
    from services.chatwork import ChatworkClient, ChatworkError
    try:
        return get_ai_account_id(ChatworkClient())
    except ChatworkError:
        return None
