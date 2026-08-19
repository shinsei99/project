"""claude が「詰まっている」かどうかを1か所で持つ（2026-08-19の障害対応・Stage 8）。

## なぜ必要か

claude CLI の OAuth トークンは **全プロセス共通の Keychain** にある。
そのため 2026-08-19 の障害では、トークン更新がハングした結果
**worker も line_webhook も同時に沈み、worker を再起動しても直らなかった**。
「1本詰まったら全員詰まる」という性質なので、詰まりは**プロセスごとではなく
アプリ全体の状態**として持つのが正しい。

## 効き方

- 誰か1人が詰まりを踏む → ここにフラグが立つ
- **以降の依頼は claude を呼ばずに即キューへ回す**（2人目以降は90秒すら待たない）
- worker が定期的に probe して、通ったらフラグを解除 → キューを流す

フラグは `processing_state` に置く（settings は人が画面から触る設定用なので混ぜない）。
"""
import time

from services import settings

STALL_SINCE = "claude_stalled_since"        # 詰まりを検知した時刻（空なら正常）
STALL_REASON = "claude_stalled_reason"      # 何を見て詰まりと判断したか
STALL_NOTIFIED = "claude_stalled_notified"  # 通知済みか（1回だけ送るため）
LAST_PROBE = "claude_last_probe_at"         # 最後に probe した時刻（epoch秒）

PROBE_INTERVAL_SEC = 60     # 復旧確認の間隔。短すぎても枠を食うだけなので1分
PROBE_TIMEOUT_SEC = 45      # probe 自体の上限。正常なら10秒前後で返る


def is_stalled() -> bool:
    return bool(settings.get_state(STALL_SINCE, ""))


def stalled_since() -> str:
    return settings.get_state(STALL_SINCE, "") or ""


def reason() -> str:
    return settings.get_state(STALL_REASON, "") or ""


def mark_stalled(why: str) -> bool:
    """詰まりを記録する。**新たに詰まったときだけ True**（通知を1回に絞るため）。"""
    if is_stalled():
        return False
    settings.set_state(STALL_SINCE, time.strftime("%Y-%m-%d %H:%M:%S"))
    settings.set_state(STALL_REASON, str(why)[:300])
    settings.set_state(STALL_NOTIFIED, "0")
    print(f"[health] claude 詰まりを検知: {why}", flush=True)
    return True


def mark_ok() -> bool:
    """復旧を記録する。**詰まっていた状態から戻ったときだけ True**。"""
    if not is_stalled():
        return False
    since = stalled_since()
    settings.set_state(STALL_SINCE, "")
    settings.set_state(STALL_REASON, "")
    settings.set_state(STALL_NOTIFIED, "0")
    print(f"[health] claude 復旧（{since} から詰まっていた）", flush=True)
    return True


def probe() -> bool:
    """一番軽い呼び出しで生死を見る。True なら claude は応答している。

    ツールもMCPも読ませない最小構成にしてある（詰まりの判定に社内資料は要らない）。
    """
    from services.claude_client import ClaudeError, run_claude
    try:
        env = run_claude("OKとだけ返して。", model="haiku", timeout=PROBE_TIMEOUT_SEC)
        return not env.get("is_error")
    except ClaudeError:
        return False
    except Exception:
        return False


def tick() -> dict:
    """worker のループから呼ぶ。詰まっているときだけ probe して復旧を待つ。

    正常時は**何もしない**（毎周 probe すると定額枠を無駄に食うため）。
    """
    if not is_stalled():
        return {}
    now = time.time()
    try:
        last = float(settings.get_state(LAST_PROBE, "0") or 0)
    except (TypeError, ValueError):
        last = 0.0
    if now - last < PROBE_INTERVAL_SEC:
        return {}
    settings.set_state(LAST_PROBE, str(now))
    if not probe():
        return {"still_stalled": True}
    recovered = mark_ok()
    return {"recovered": recovered}


def note_success() -> bool:
    """claude 呼び出しが通ったときに呼ぶ。詰まりフラグが残っていれば解除する。

    probe を待たずに、実際の仕事が通った時点で復旧と分かるため。
    """
    return mark_ok()
