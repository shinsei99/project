"""QRコードを作る

なぜ segno か:
  紙面に載せるQRは**手元で完結**しないといけない。API（Google Chart等）に
  取りに行く方式は、通信が要る・将来止まる・URLが外部に渡る、の3つが困る。
  segno は純Pythonで依存が無く（BSDライセンス）、オフラインで作れる。

誤り訂正は M（約15%まで復元）。紙面は印刷して配るので、多少かすれても読めるよう
既定より1段上げてある。L だと折り目やインクのかすれで読めなくなる。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from core.config import ROOT

CACHE = ROOT / ".cache" / "qr"


def available() -> bool:
    try:
        import segno  # noqa: F401
    except ImportError:
        return False
    return True


def make(text: str, dark: str = "#000000", scale: int = 8) -> Optional[str]:
    """文字列（URL・電話番号など）からQRのPNGを作り、そのパスを返す。

    同じ内容なら作り直さない（キャッシュ）。作れなければ None を返し、
    呼び出し側は**QRを出さずに紙面を作る**（QRのために紙面全体を失わない）。
    """
    text = str(text or "").strip()
    if not text:
        return None
    try:
        import segno
    except ImportError:
        return None

    key = hashlib.md5(("%s|%s|%d" % (text, dark, scale)).encode("utf-8")).hexdigest()
    out = CACHE / ("%s.png" % key)
    if out.exists():
        return str(out)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        segno.make(text, error="m").save(str(out), scale=int(scale), border=2,
                                         dark=dark, light="#ffffff")
        return str(out)
    except Exception:
        return None


def normalize_url(text: str) -> str:
    """人が打った文字をURLらしく整える。

    「www.example.com」のように打たれることが多い。そのままQRにすると
    スマホで開けないので http を補う。URLでないものはそのまま返す
    （電話番号やメールをQRにしたい場合もあるため）。
    """
    text = str(text or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://", "tel:", "mailto:")):
        return text
    if text.startswith("www.") or ("." in text.split("/")[0] and " " not in text):
        return "https://" + text
    return text
