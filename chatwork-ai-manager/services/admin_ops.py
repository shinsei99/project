"""常駐サービスの再起動・稼働確認を、LINE（や管理画面）から行うための係。

**なぜ要るのか**: 常駐4本はメインPCのlaunchdで動いている。今までは不調のとき
Macの前に座って `launchctl kickstart` を叩くしかなかった。外出先から直せるようにする。

★自分自身を殺す問題（この実装の要）
  LINE webhook のプロセスが「自分を再起動しろ」と言われたら、その場で kickstart すると
  **返事をする前に自分が死ぬ**。そこで:
    1. webhook 側は「これから再起動します」と**先に返信**する
    2. 実際の再起動は **切り離した別プロセス**（このファイルを `-m` で起動）にやらせる
    3. 別プロセスが再起動後に生死を確かめ、結果を LINE に push する
  だから webhook 自身を巻き込んで再起動しても、結果は必ず手元に届く。

安全側の決まり:
  - 実行できるのは管理者だけ（`line_admin_user_ids`。未設定なら LINE の許可ユーザー）
  - 触るのは**このアプリの launchd ラベルだけ**。任意のコマンドは実行させない
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 触ってよいラベルはこの4つだけ（任意の launchctl を打たせない）
LABELS = {
    "worker":  ("com.shinsei.chatwork-ai-manager-worker", "worker（Chatwork監視・TODO解析・定時処理）"),
    "admin":   ("com.shinsei.chatwork-ai-manager",        "管理画面（8540）"),
    "line":    ("com.shinsei.chatwork-ai-manager-line",   "LINE webhook（8530）"),
    "ngrok":   ("com.shinsei.chatwork-ai-manager-ngrok",  "ngrok（LINEの公開口）"),
}
# 「再起動」だけ言われたときの既定。**line と ngrok は含めない**
# （LINEの通り道なので、返事が届かなくなる可能性を既定にはしない）
DEFAULT_TARGETS = ["worker", "admin"]
ALL_TARGETS = ["worker", "admin", "line", "ngrok"]

PORTS = {"admin": 8540, "line": 8530}


def _uid() -> int:
    return os.getuid()


def _launchctl(*args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["launchctl", *args], capture_output=True, text=True, timeout=30)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


def _pid(label: str):
    rc, out = _launchctl("print", f"gui/{_uid()}/{label}")
    if rc != 0:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("pid = "):
            try:
                return int(line.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _port_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            return r.status < 500
    except Exception:
        return False


def status_text() -> str:
    """いま動いているかを1画面ぶんの文にする。"""
    lines = ["■ AI業務マネージャーの稼働状況"]
    for key in ALL_TARGETS:
        label, human = LABELS[key]
        pid = _pid(label)
        mark = "🟢" if pid else "🔴"
        extra = ""
        port = PORTS.get(key)
        if port:
            extra = f" / ポート{port} {'応答あり' if _port_ok(port) else '応答なし'}"
        lines.append(f"{mark} {human}: {('pid ' + str(pid)) if pid else '停止'}{extra}")
    return "\n".join(lines)


def parse_command(text: str):
    """LINEの本文から (操作, 対象) を判定する。該当しなければ None。

    ここで拾えなかったものは、いつも通り AI（qa.answer）へ流れる。
    """
    t = (text or "").strip().replace(" ", "").replace("　", "")
    if not t:
        return None
    if t in ("状態", "ステータス", "稼働状況", "状況", "生きてる?", "生きてる？"):
        return ("status", [])
    if "再起動" not in t and "リスタート" not in t:
        return None
    # ★「再起動の手順を教えて」のような **質問** で本当に落とさない。
    #   聞かれているのか命じられているのかは、末尾の「て/して」より
    #   疑問語の有無で見るほうが確実（2026-08-18のテストで誤爆を確認）。
    if any(w in t for w in ("教え", "手順", "方法", "とは", "できる", "できます",
                            "?", "？", "なぜ", "どうやって", "いつ")):
        return None
    if any(w in t for w in ("全部", "ぜんぶ", "すべて", "フル", "まるごと")):
        return ("restart", ALL_TARGETS)
    for key in ("worker", "ワーカー"):
        if key in t.lower():
            return ("restart", ["worker"])
    if "ngrok" in t.lower():
        return ("restart", ["ngrok"])
    if "管理画面" in t:
        return ("restart", ["admin"])
    return ("restart", DEFAULT_TARGETS)


def restart_detached(targets: list[str], line_user_id: str | None = None) -> None:
    """切り離した別プロセスで再起動する（呼び元が死んでも完走する）。"""
    args = [sys.executable or "/usr/bin/python3", "-m", "services.admin_ops",
            "--restart", ",".join(targets)]
    if line_user_id:
        args += ["--notify-line", line_user_id]
    subprocess.Popen(args, cwd=APP_DIR, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def do_restart(targets: list[str]) -> str:
    """実際に再起動して結果の文を返す（別プロセス側で走る）。"""
    results = []
    for key in targets:
        if key not in LABELS:
            continue
        label, human = LABELS[key]
        rc, out = _launchctl("kickstart", "-k", f"gui/{_uid()}/{label}")
        results.append((key, human, rc, out))
    time.sleep(8)                      # 立ち上がりを待つ（workerは起動時にDB移行を走らせる）
    lines = ["■ 再起動しました"]
    for key, human, rc, out in results:
        pid = _pid(LABELS[key][0])
        if rc != 0:
            lines.append(f"❌ {human}: 実行できませんでした（{out[:120]}）")
        elif pid:
            port = PORTS.get(key)
            tail = f" / ポート{port} {'応答あり' if _port_ok(port) else '応答なし'}" if port else ""
            lines.append(f"🟢 {human}: 起動を確認（pid {pid}）{tail}")
        else:
            lines.append(f"🔴 {human}: 起動を確認できませんでした")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="常駐サービスの再起動・稼働確認")
    ap.add_argument("--restart", help="worker,admin,line,ngrok（カンマ区切り）")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--notify-line", help="結果を push する LINE userId")
    a = ap.parse_args()

    if a.status or not a.restart:
        print(status_text())
        return 0

    # 呼び元（LINE webhook 自身かもしれない）が終わるのを待ってから落とす
    time.sleep(2)
    text = do_restart([t.strip() for t in a.restart.split(",") if t.strip()])
    print(text)
    if a.notify_line:
        try:
            sys.path.insert(0, APP_DIR)
            from services import line_client
            line_client.push(a.notify_line, text, label="admin_ops")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
