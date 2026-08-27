"""「いま何番目にどの写真を見せたか」を覚えておく（2026-08-27）。

**なぜ要るのか**（実際に起きた事故）:
  AIが写真を複数枚まとめて送るとき「①②③…」と番号を振るが、その対応をどこにも
  残していなかった。次の発言では毎回DBを引き直すため、間にタイトルを直すと
  **同じ番号が別の写真を指す**。2026-08-27 に、オーナーが「③がもと美モータープール」と
  答えたのに、実際には別の写真（SHELLOのトランクルームのシャッター）へその名前を
  付けてしまい、以後の会話が全部ずれた。

仕組み:
  - 送信ツールが送るたびに `record()` を呼ぶ。同じ相手への連続送信は
    `BATCH_GAP_SEC` 以内なら同じ「ひと組」とみなして番号を1,2,3…と振り足す。
  - `recent()` が「直近のひと組」を順番どおり返す。これをそのまま
    プロンプトの文脈に入れるので、AIはツールを呼ばずに「③」を解決できる。
  - 保存先は `processing_state`（既存テーブル）。新しいテーブルは作らない。
"""
from __future__ import annotations

import json
import time

from services.settings import get_state, set_state

KEY_PREFIX = "image_sendlog:"
BATCH_GAP_SEC = 20 * 60      # これ以上あいたら「別のひと組」として番号を1から振り直す
MAX_KEEP = 20                # 1組で覚えておく最大枚数


def _key(target: str) -> str:
    return KEY_PREFIX + (target or "unknown")


def _load(target: str) -> dict:
    try:
        return json.loads(get_state(_key(target)) or "{}") or {}
    except Exception:
        return {}


def record(target: str, room_id, file_id, title=None, now=None, line_message_id=None) -> int:
    """1枚送ったことを記録し、そのひと組の中での番号（1始まり）を返す。"""
    now = now or time.time()
    data = _load(target)
    items = data.get("items") or []
    if not items or (now - float(data.get("last_at") or 0)) > BATCH_GAP_SEC:
        items = []                       # 間があいた＝新しいひと組
    items.append({
        "n": len(items) + 1,
        "room_id": str(room_id) if room_id is not None else None,
        "file_id": str(file_id) if file_id is not None else None,
        "title": title,
        "at": int(now),
        "line_message_id": str(line_message_id) if line_message_id else None,
    })
    items = items[-MAX_KEEP:]
    set_state(_key(target), json.dumps({"last_at": now, "items": items}, ensure_ascii=False))
    return items[-1]["n"]


def recent(target: str, now=None) -> list[dict]:
    """直近のひと組を順番どおり返す（間があいていれば空）。"""
    data = _load(target)
    items = data.get("items") or []
    if not items:
        return []
    if (now or time.time()) - float(data.get("last_at") or 0) > BATCH_GAP_SEC:
        return []
    return items


def context_text(target: str) -> str:
    """プロンプトに差し込む用の1ブロック。番号→写真の対応をそのまま書く。"""
    items = recent(target)
    if not items:
        return "（直近に写真は送っていません）"
    lines = ["★直近にこの相手へ送った写真（利用者が「①」「3番目」等と言ったらこの対応で解決する）:"]
    for it in items:
        lines.append("  %s) room_id=%s file_id=%s  タイトル=%s"
                     % (it["n"], it["room_id"], it["file_id"], it.get("title") or "（なし）"))
    lines.append("  ※利用者が番号を言わず「この写真」とだけ言った場合は、"
                 "**勝手に決めずに番号を聞き返すこと**（間違えると別の写真の名前を壊す）")
    return "\n".join(lines)


def resolve(target: str, ordinal: int):
    """番号から (room_id, file_id) を引く。見つからなければ None。"""
    for it in recent(target):
        if int(it["n"]) == int(ordinal):
            return it["room_id"], it["file_id"]
    return None


def by_line_message_id(target: str, message_id: str):
    """LINEの引用（quotedMessageId）から、その写真の (room_id, file_id, title) を引く。

    利用者がLINEの「リプライ」で写真を引用して「◯◯です」と言うのが一番自然なので、
    番号を言われなくてもここで確実に特定できる。直近のひと組に限らず全部の記録から探す
    （少し前に送った写真に返信されることがあるため）。
    """
    if not message_id:
        return None
    data = _load(target)
    for it in reversed(data.get("items") or []):
        if it.get("line_message_id") and str(it["line_message_id"]) == str(message_id):
            return it["room_id"], it["file_id"], it.get("title")
    return None
