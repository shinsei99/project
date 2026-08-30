"""社内資料を Chatwork へ添付送信する Tool（Stage 9・2026-08-19）。

Claude が「資料を送って」と頼まれたときに使う。
安全確認（送信元フォルダの限定・サイズ上限・記録・通知）は services/file_send.py が持つ。
ここは Claude から呼びやすい形に整えるだけの薄いラッパ。
"""
import os

from services import file_send
from services import company_scope as CS


def chatwork_send_file(room_id, path, message=None, requester=None,
                       requester_account_id=None):
    """共有フォルダのファイルを Chatwork のルームへ添付する。

    送れない場合も **理由を返す**ので、Claude はそれを利用者にそのまま伝えればよい
    （黙って失敗させない）。
    """
    if not room_id:
        return {"ok": False, "error": "room_id が必要です"}
    if not path:
        return {"ok": False, "error": "path（送るファイルの絶対パス）が必要です"}
    # ★別の会社のルームへは送らない／共有フォルダは既定の会社のもの（2026-08-30）
    if CS.blocks_room(room_id):
        return CS.deny(room_id, "ファイルの送信")
    if not CS.is_default_company():
        return CS.deny(what="共有フォルダのファイル")
    return file_send.send(room_id, path, message=message, requester=requester,
                          requester_account_id=requester_account_id)


def find_files(name, limit=20):
    """共有フォルダからファイル名の一部で探す。

    「グランビルド岩城の図面を送って」のように**名前しか分からない**ときに、まずこれで
    実体（絶対パス）を突き止めてから chatwork_send_file に渡す。
    """
    if not CS.is_default_company():
        return CS.deny(what="共有フォルダのファイル")
    return file_send.find_files(name, limit=limit)


def chatwork_can_send_file(path):
    """送れるかどうかだけ先に確かめる（実際には送らない）。

    「送れます／送れません」を答える前の確認や、複数候補から送れるものを選ぶのに使う。
    """
    return file_send.check(path)


def find_sendable_files(paths):
    """複数の候補パスをまとめて判定し、送れるもの・送れないものに仕分ける。

    kb_search や全ファイル一覧で見つけた候補をそのまま渡せるようにするための道具。
    """
    if isinstance(paths, str):
        paths = [paths]
    sendable, blocked = [], []
    for p in (paths or []):
        v = file_send.check(p)
        if v.get("ok"):
            sendable.append({"path": v["path"], "name": v["name"], "size": v["size"]})
        else:
            blocked.append({"path": p, "name": os.path.basename(p or ""),
                            "reason": v.get("reason")})
    return {"sendable": sendable, "blocked": blocked,
            "note": "sendable のものは chatwork_send_file でそのまま送れる。"
                    "blocked は理由を利用者に伝え、パスを案内する"}
