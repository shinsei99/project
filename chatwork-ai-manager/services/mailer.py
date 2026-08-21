"""SMTP でメールを送る（添付つき）。業務日報の社内メール送信に使う（2026-08-21 追加）。

**Apple Mail(AppleScript) ではなく SMTP 直**にしている。18:30 の日報は launchd の常駐から
無人で走るので、Mail.app が起動している必要も「自動化」のTCC許可も要らないほうが確実なため。

## 設定（`.streamlit/secrets.toml`。gitignore・このアプリの既存の置き方に合わせている）

    smtp_host = "smtp.daikyocorp.co.jp"
    smtp_port = "587"
    smtp_user = "shin@daikyocorp.co.jp"
    smtp_password = "..."            # ← どちらか。キーチェーンに入れるなら次を使う
    smtp_password_keychain = "chatwork-ai-manager-smtp"
    smtp_from = "shin@daikyocorp.co.jp"   # 省略時は smtp_user

キーチェーンに入れる場合（平文を置きたくないとき。`mail-archiver` と同じやり方）:

    security add-generic-password -s chatwork-ai-manager-smtp -a shin@daikyocorp.co.jp -w

## サーバー側の実測（2026-08-21・DNSとEHLOで確認）

    smtp.daikyocorp.co.jp → 122.28.46.202（Postfix）。MXは mwbgw1/2.ocn.ad.jp（OCN）
    587 = 開いている / **465 と 25 は閉じている**（タイムアウト）
    STARTTLS あり・AUTH PLAIN LOGIN
    SIZE 31457280 ＝ **添付を含めた上限 30MB**

**チャットワーク側と違い、メールは送ったら取り消せない。** 宛先の既定値は設定に持たせ、
コードに埋めない。送信の成否は必ず呼び出し元へ返す（黙って落とさない）。
"""
import mimetypes
import os
import smtplib
import subprocess
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from services import config

TIMEOUT = 30
# EHLO の SIZE から取った上限。超えるなら送らずにエラーにする（サーバーに弾かせない）
MAX_BYTES = 30 * 1024 * 1024


class MailError(RuntimeError):
    pass


def _keychain(service: str, account: str) -> str:
    """キーチェーンからパスワードを読む。無ければ空文字。"""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def settings() -> dict:
    """SMTPの設定を集める（値は返すが、ログには出さないこと）。"""
    host = config.get("smtp_host", "") or ""
    user = config.get("smtp_user", "") or ""
    pw = config.get("smtp_password", "") or ""
    if not pw:
        svc = config.get("smtp_password_keychain", "") or ""
        if svc and user:
            pw = _keychain(svc, user)
    return {
        "host": host,
        "port": int(config.get("smtp_port", "587") or 587),
        "user": user,
        "password": pw,
        "from": (config.get("smtp_from", "") or user),
    }


def is_configured() -> bool:
    s = settings()
    return bool(s["host"] and s["user"] and s["password"])


def missing() -> list:
    """足りない設定の名前を返す（値は返さない）。画面やエラー文で使う。"""
    s = settings()
    out = []
    if not s["host"]:
        out.append("smtp_host")
    if not s["user"]:
        out.append("smtp_user")
    if not s["password"]:
        out.append("smtp_password（または smtp_password_keychain）")
    return out


def send(to, subject, body, attachments=None, sender_name=None):
    """メールを1通送る。

    to: "a@b.jp" または ["a@b.jp", "c@d.jp"]
    attachments: ファイルパスの一覧
    戻り: {"ok": True, "to": [...], "attached": [...]} / 失敗は MailError を投げる
    """
    s = settings()
    lack = missing()
    if lack:
        raise MailError("SMTPの設定が足りません: " + " / ".join(lack)
                        + "（.streamlit/secrets.toml に書く）")

    recipients = [to] if isinstance(to, str) else list(to or [])
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        raise MailError("宛先が空です")

    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, s["from"])) if sender_name else s["from"]
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body)

    attached = []
    for path in (attachments or []):
        if not path or not os.path.exists(path):
            raise MailError(f"添付が見つかりません: {path}")
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))
        attached.append(os.path.basename(path))

    size = len(bytes(msg))
    if size > MAX_BYTES:
        raise MailError(f"メールが大きすぎます（{size/1024/1024:.1f}MB。上限30MB）")

    try:
        with smtplib.SMTP(s["host"], s["port"], timeout=TIMEOUT) as srv:
            srv.ehlo()
            if srv.has_extn("starttls"):
                srv.starttls()
                srv.ehlo()
            srv.login(s["user"], s["password"])
            srv.send_message(msg, from_addr=s["from"], to_addrs=recipients)
    except smtplib.SMTPAuthenticationError as e:
        raise MailError(f"SMTP認証に失敗しました（ユーザー名かパスワードを確認）: {e}")
    except Exception as e:
        raise MailError(f"送信に失敗しました: {type(e).__name__}: {e}")

    return {"ok": True, "to": recipients, "attached": attached, "bytes": size}
