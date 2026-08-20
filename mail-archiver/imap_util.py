"""IMAP まわりの道具（接続・フォルダ名のデコード・メールの分解）。

はまりどころ（実際に踏んだ／踏みやすい所を残す）:

- **フォルダ名は「IMAP修正UTF-7」**。`INBOX.&U9ZfFVFI-` のような見た目で返ってくる。
  UTF-16BE→base64（`/` を `,` に置換）という独自形式で、Python 標準にデコーダが無いので自前で持つ。
- **UID は UIDVALIDITY とセットでしか意味を持たない。** サーバーがフォルダを作り直すと
  UIDVALIDITY が変わり、同じ UID が別のメールを指す。取得時にも削除時にも必ず突き合わせる。
- `FETCH` の応答は「タプルと閉じ括弧」が混ざった配列で返る。素朴に `data[0][1]` と書くと
  複数通まとめて取ったときに取りこぼす。
"""
from __future__ import annotations

import base64
import email
import email.policy
import imaplib
import re
import unicodedata
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from typing import Any, Dict, List, Optional, Tuple

imaplib._MAXLINE = 10 * 1024 * 1024  # 巨大ヘッダのメールで "got more than 10000 bytes" を避ける


# ------------------------------------------------------------ IMAP修正UTF-7

def imap_utf7_decode(s: str) -> str:
    out: List[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "&":
            out.append(ch)
            i += 1
            continue
        j = s.find("-", i)
        if j == -1:
            out.append(s[i:])
            break
        chunk = s[i + 1:j]
        if chunk == "":
            out.append("&")
        else:
            b64 = chunk.replace(",", "/")
            b64 += "=" * (-len(b64) % 4)
            try:
                out.append(base64.b64decode(b64).decode("utf-16-be"))
            except Exception:
                out.append(s[i:j + 1])
        i = j + 1
    return "".join(out)


def imap_utf7_encode(s: str) -> str:
    out: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            b = "".join(buf).encode("utf-16-be")
            out.append("&" + base64.b64encode(b).decode("ascii").rstrip("=").replace("/", ",") + "-")
            buf.clear()

    for ch in s:
        if ch == "&":
            flush()
            out.append("&-")
        elif 0x20 <= ord(ch) <= 0x7E:
            flush()
            out.append(ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


# ------------------------------------------------------------ 接続

def connect(host: str, port: int, username: str, password: str, use_ssl: bool = True):
    cls = imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4
    conn = cls(host, port)
    conn.login(username, password)
    return conn


_LIST_RE = re.compile(rb'\((?P<flags>[^)]*)\) "(?P<delim>[^"]*)" (?P<name>.*)')


def list_folders(conn) -> List[Dict[str, Any]]:
    """(raw_name, name, flags) の一覧。`\\Noselect` のフォルダは除く。"""
    typ, data = conn.list()
    if typ != "OK":
        raise RuntimeError("LIST に失敗: {}".format(typ))
    folders = []
    for line in data:
        if not line:
            continue
        m = _LIST_RE.match(line if isinstance(line, bytes) else bytes(line))
        if not m:
            continue
        flags = m.group("flags").decode("ascii", "replace")
        if "\\Noselect" in flags:
            continue
        raw = m.group("name").decode("ascii", "replace").strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        # 表示名は NFC に正規化する。サーバーは「ポータル」を NFD（ホ+゚）で持っていることがあり、
        # そのままだと見た目が同じフォルダが2つあるように見える（2026-08-20に実データで確認）
        folders.append({"raw_name": raw,
                        "name": unicodedata.normalize("NFC", imap_utf7_decode(raw)),
                        "flags": flags})
    return folders


def select_folder(conn, raw_name: str, readonly: bool = True) -> Tuple[int, int]:
    """フォルダを開き (メール数, UIDVALIDITY) を返す。UIDVALIDITY が取れなければ例外。"""
    typ, data = conn.select('"{}"'.format(raw_name), readonly=readonly)
    if typ != "OK":
        raise RuntimeError("SELECT に失敗: {} {}".format(raw_name, data))
    n = int(data[0]) if data and data[0] else 0
    typ, resp = conn.response("UIDVALIDITY")
    if typ != "UIDVALIDITY" or not resp or not resp[0]:
        raise RuntimeError("UIDVALIDITY が取得できない: {}".format(raw_name))
    return n, int(resp[0])


def search_uids(conn, criteria: str = "ALL", since_uid: int = 0) -> List[int]:
    if since_uid > 0:
        typ, data = conn.uid("SEARCH", None, "UID", "{}:*".format(since_uid + 1))
    else:
        typ, data = conn.uid("SEARCH", None, criteria)
    if typ != "OK":
        raise RuntimeError("SEARCH に失敗: {}".format(data))
    if not data or not data[0]:
        return []
    uids = [int(x) for x in data[0].split()]
    return [u for u in uids if u > since_uid]


def fetch_raw(conn, uid: int) -> Optional[Tuple[bytes, str]]:
    """1通を丸ごと取る。戻り値 (RFC822バイト列, フラグ文字列)。無ければ None。

    **`RFC822` ではなく `BODY.PEEK[]` を使う。** `RFC822` で取るとサーバー側で `\Seen` が付き、
    「アーカイブしただけなのに未読が既読になる」という実害が出る（読み取り専用で開いていても
    サーバー実装によっては付く）。
    """
    typ, data = conn.uid("FETCH", str(uid), "(FLAGS RFC822.SIZE BODY.PEEK[])")
    if typ != "OK" or not data:
        return None
    raw = None
    flags = ""
    for part in data:
        if isinstance(part, tuple) and part[1]:
            meta = part[0].decode("ascii", "replace") if isinstance(part[0], bytes) else str(part[0])
            m = re.search(r"FLAGS \(([^)]*)\)", meta)
            if m:
                flags = m.group(1)
            raw = part[1]
        elif isinstance(part, bytes):
            m = re.search(r"FLAGS \(([^)]*)\)", part.decode("ascii", "replace"))
            if m:
                flags = m.group(1)
    if raw is None:
        return None
    return raw, flags


def fetch_size(conn, uid: int) -> Optional[int]:
    typ, data = conn.uid("FETCH", str(uid), "(RFC822.SIZE)")
    if typ != "OK" or not data:
        return None
    for part in data:
        blob = part[0] if isinstance(part, tuple) else part
        if isinstance(blob, bytes):
            m = re.search(rb"RFC822\.SIZE (\d+)", blob)
            if m:
                return int(m.group(1))
    return None


def fetch_message_id(conn, uid: int) -> Optional[str]:
    """削除の直前に「本人か」を確かめるため Message-ID だけを取る（本文は読まない＝軽い）。"""
    typ, data = conn.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
    if typ != "OK" or not data:
        return None
    for part in data:
        if isinstance(part, tuple) and part[1]:
            text = part[1].decode("utf-8", "replace")
            m = re.search(r"(?im)^message-id:\s*(.+)$", text)
            if m:
                return m.group(1).strip()
    return None


# ------------------------------------------------------------ メールの分解

def _decode_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _addr_list(msg: Message, field: str) -> str:
    vals = msg.get_all(field, [])
    return ", ".join(_decode_header(v) for v in vals)


def _split_from(value: str) -> Tuple[str, str]:
    m = re.match(r"^\s*(.*?)\s*<([^>]+)>\s*$", value)
    if m:
        return m.group(1).strip().strip('"'), m.group(2).strip()
    return "", value.strip()


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p\s*>", "\n\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _part_text(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return ""
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    for cs in (charset, "utf-8", "cp932", "iso-2022-jp", "euc-jp", "latin-1"):
        try:
            return payload.decode(cs, "strict")
        except Exception:
            continue
    return payload.decode("utf-8", "replace")


def parse_message(raw: bytes) -> Dict[str, Any]:
    """RFC822 バイト列 → 保存する形の dict。添付は (filename, content_type, bytes) で返す。"""
    msg = email.message_from_bytes(raw)
    subject = _decode_header(msg.get("Subject"))
    from_raw = _decode_header(msg.get("From"))
    from_name, from_addr = _split_from(from_raw)

    date_utc = ""
    try:
        dt = email.utils.parsedate_to_datetime(msg.get("Date"))
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            date_utc = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        date_utc = ""

    text_parts: List[str] = []
    html_parts: List[str] = []
    attachments: List[Tuple[str, str, bytes]] = []

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disp = (part.get("Content-Disposition") or "").lower()
        filename = _decode_header(part.get_filename())
        ctype = part.get_content_type()
        if filename or "attachment" in disp:
            try:
                payload = part.get_payload(decode=True) or b""
            except Exception:
                payload = b""
            if payload:
                attachments.append((filename or "noname.bin", ctype, payload))
            continue
        if ctype == "text/plain":
            text_parts.append(_part_text(part))
        elif ctype == "text/html":
            html_parts.append(_part_text(part))

    body = "\n".join(t for t in text_parts if t).strip()
    if not body and html_parts:
        body = _html_to_text("\n".join(html_parts))

    return {
        "message_id": (msg.get("Message-ID") or "").strip() or None,
        "subject": subject,
        "from_name": from_name,
        "from_addr": from_addr,
        "to_addrs": _addr_list(msg, "To"),
        "cc_addrs": _addr_list(msg, "Cc"),
        "date_utc": date_utc,
        "body_text": body,
        "attachments": attachments,
        "size_bytes": len(raw),
    }
