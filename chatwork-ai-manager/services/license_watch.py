# -*- coding: utf-8 -*-
"""免許・登録の更新時期が来たら TODO を作る（2026-08-30 オーナー指示）。

**なぜ要るか**
  会社の免許は4つあり、いずれも5年に1度しか触らない。カレンダーには載らず、
  前の担当が居なくなると誰も期限を知らない。実際 2026-08-30 に調べたところ、
  **賃貸住宅管理業の登録が満了日を過ぎていた**（更新済みかどうかも社内で分からなかった）。
  「気づいた人が動く」ではなく「**時期が来たら勝手にTODOに出る**」形にする。

**いつ出すか**
  申請できる期間（apply_from）の `notify_days_before_apply` 日前になったら1件作る。
  期限（apply_to）を過ぎても未完了なら、既存タスクがそのまま残って放置検知に乗る。

**重複しない仕組み**
  dedup_key を `license:<key>:<満了日>` にする。何度走っても同じ更新回では1件しか作らない。
  次の更新回は満了日が変わるので、また1件作られる。

**台帳は licenses.json**（アプリ直下・gitに入る）。日付を直したらここを直す。
"""
from __future__ import annotations

import datetime
import json
import os

from services import tasks

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "licenses.json")


def _raw() -> dict:
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def _company_conf(company: str) -> dict:
    """その会社の宛先（ルーム・担当者・資料の置き場）。

    ★2社を1つの台帳で持つので、**免許ごとに会社を見て宛先を切り替える**。
      大京商事 → 全体チャットワーク／吉浦さん／Dropboxの共有フォルダ
      新誠     → 鷲見さん個人チャット／鷲見さん／GoogleDriveの新誠プロパティ
      間違えると、片方の会社の免許の話がもう片方のルームに出てしまう。
    """
    try:
        return (_raw().get("_meta", {}).get("companies", {}) or {}).get(company, {}) or {}
    except Exception:
        return {}


def _load() -> list:
    try:
        return _raw().get("licenses", [])
    except FileNotFoundError:
        print(f"[license_watch] 台帳が無い: {_PATH}", flush=True)
        return []
    except (OSError, ValueError) as e:      # ★黙って「期限なし」に落ちない
        print(f"[license_watch] 台帳を読めない: {type(e).__name__}: {e}", flush=True)
        return []


def _d(s: str):
    return datetime.date.fromisoformat(s) if s else None


def _content(lic: dict, today: datetime.date) -> str:
    to = _d(lic["valid_to"])
    left = (to - today).days
    head = f"【免許の更新／{lic.get('company','')}】{lic['name']}（{lic['number']}）"
    when = (f"有効期間 {lic['valid_from']}〜{lic['valid_to']}"
            f"（残り{left}日）／申請できるのは {lic['apply_from']}〜{lic['apply_to']}")
    lines = [head, when, f"窓口: {lic['office']}", f"根拠: {lic['law']}"]
    if lic.get("prep"):
        lines.append(f"準備: {lic['prep']}")
    if lic.get("materials"):
        lines.append(f"前回の資料: {lic['materials']}")
    if lic.get("urgent_note"):
        lines.append(f"★{lic['urgent_note']}")
    lines.append("手順は業務マニュアル（http://192.168.1.105:8521/業務マニュアル.html#soumu-menkyo）")
    lines.append("★申請期限を過ぎると更新できず、新規申請のやり直しになる。")
    # ★「終わったら資料を残す」を**本文に**書く。
    #   定時の進捗確認がAIに渡すのは content だけで、done_condition は渡していない
    #   （services/scheduler.py の _decide_prompt を確認済み）。
    #   完了条件にだけ書いても、担当者には一度も伝わらない。
    if lic.get("done_condition"):
        lines.append("【終わったらここまで】" + lic["done_condition"])
    return "\n".join(lines)


def due_licenses(today: datetime.date = None) -> list:
    """いまTODOを作るべき免許を返す。"""
    today = today or datetime.date.today()
    out = []
    for lic in _load():
        af, at, vt = _d(lic.get("apply_from")), _d(lic.get("apply_to")), _d(lic.get("valid_to"))
        if not (af and at and vt):
            continue
        notify_from = af - datetime.timedelta(days=int(lic.get("notify_days_before_apply", 30)))
        # 通知開始日を過ぎていて、まだ「満了から1年」以内なら対象。
        # 満了後も出し続けるのは、失効に気づかず放置されるのが一番怖いため。
        if notify_from <= today <= vt + datetime.timedelta(days=365):
            out.append(lic)
    return out


def tick(now: datetime.datetime = None) -> dict:
    """worker のループから呼ぶ。作ったタスクの件数を返す。"""
    today = (now or datetime.datetime.now()).date()
    made, skipped = [], []
    for lic in due_licenses(today):
        key = f"license:{lic['key']}:{lic['valid_to']}"
        if tasks.find_by_dedup_key(key):
            skipped.append(lic["key"])
            continue
        conf = _company_conf(lic.get("company", ""))
        who = conf.get("assignee", {}) or {}
        tid = tasks.create_task({
            "content": _content(lic, today),
            "assignee_account_id": who.get("account_id"),
            "assignee_name": who.get("name"),
            "room_id": conf.get("room_id"),
            "due_date": lic["apply_to"],
            "due_raw": f"申請期限 {lic['apply_to']}",
            "priority": "高",
            "status": "未着手",
            "dedup_key": key,
            "ai_reason": "免許・登録の期限台帳（licenses.json）から自動作成",
            # ★完了の条件に「資料を残すところまで」を入れる。
            #   2026-08-30 に調べたら建設業とマンション管理業の更新書類が1枚も残っておらず、
            #   次の担当が何を出したか分からない状態になっていた。同じことを繰り返さない。
            "done_condition": lic.get("done_condition")
            or "更新申請を提出し、受付の控えを 社内・総務/免許・登録の更新資料/ に保存した",
        })
        made.append({"key": lic["key"], "task_id": tid, "name": lic["name"]})
        print(f"[license_watch] TODO作成 #{tid} {lic['name']}", flush=True)
    return {"job": "license_watch", "made": made, "skipped": skipped}
