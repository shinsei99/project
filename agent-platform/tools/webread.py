"""アイテム: Webページを自分で読んで本文テキストにする

なぜ要るか:
  ページを読む手段が claude CLI の WebFetch しか無かった。**1回に5〜8分**かかり、
  しかも空で返ることがあった（物件チラシの依頼で、条件が全部「＿＿＿」になった）。
  ページの取得は本来1秒で終わる仕事で、AIに任せる必要が無い。

  ここで本文を取ってプロンプトに載せてしまえば、AIは**読む**のではなく
  **拾う**だけで済む。速くなるうえ、取得できたかどうかが確実に分かる。

JSで描画されるページはこの方法では読めない。その場合だけ従来の WebFetch に頼る。
"""
from __future__ import annotations

import re
from typing import List, Optional

NAME = "webread"
LABEL = "Webページを読む"
DESCRIPTION = "ページを取得して本文テキストにする（AIを使わないので数秒）"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 本文に関係のない塊。ここを消さないと、メニューや広告の語ばかりが残る
DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|svg|iframe|template)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL)
TAGS = re.compile(r"<[^>]+>")
SPACES = re.compile(r"[ \t　]+")
BLANK_LINES = re.compile(r"\n{3,}")


def available():
    try:
        import requests  # noqa: F401
    except Exception:
        return False, "requests 未導入"
    return True, "ページを直接読みます（数秒）"


def fetch(url: str, timeout: int = 20) -> Optional[str]:
    import requests

    try:
        resp = requests.get(url, headers={"User-Agent": UA,
                                          "Accept-Language": "ja,en;q=0.8"},
                            timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return None
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def to_text(html: str, limit: int = 20000) -> str:
    """HTMLを読める文章にする。

    表（物件の条件はほぼ表に入っている）が潰れないよう、**行とセルの区切りを
    改行・全角スペースに置き換えてからタグを消す**。いきなりタグを消すと
    「賃料5.9万円管理費3000円敷金なし」のように連結して読めなくなる。
    """
    text = DROP_BLOCKS.sub(" ", html or "")
    text = re.sub(r"</(tr|div|p|li|h[1-6]|table|section)>", "\n", text,
                  flags=re.IGNORECASE)
    text = re.sub(r"</(td|th|dd|dt|span)>", "　", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = TAGS.sub("", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    text = SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = BLANK_LINES.sub("\n\n", text).strip()
    return text[:limit]


def read(url: str, limit: int = 20000) -> Optional[str]:
    html = fetch(url)
    if not html:
        return None
    text = to_text(html, limit=limit)
    # 中身がほとんど無いページはJSで描画されている。読めなかった扱いにする
    return text if len(text) > 400 else None


def read_many(urls: List[str], limit_each: int = 12000) -> str:
    """複数ページを読んで、プロンプトに載せる形にまとめる。

    読めなかったURLも**読めなかったと書く**。黙って落とすと、
    AIが「書いていない＝存在しない」と誤解して事実を作ってしまう。
    """
    parts = []
    for url in urls:
        text = read(url, limit=limit_each)
        if text:
            parts.append("----- ページ: %s -----\n%s" % (url, text))
        else:
            parts.append("----- ページ: %s -----\n（取得できませんでした。"
                         "このページの内容は不明として扱ってください）" % url)
    return "\n\n".join(parts)
