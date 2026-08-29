# -*- coding: utf-8 -*-
"""国立国会図書館サーチ API で書誌を引く。

**openBD は新刊書店の流通データ**なので、ムック・古い本・専門書は落ちる。
NDL は納本制度で国内出版物をほぼ全部持っているため、そこを拾える。
出版年は openBD の `pubdate`（YYYYMM）と違い `date`（YYYY のことが多い）。
"""
import time, urllib.request, urllib.parse, xml.etree.ElementTree as ET


def lookup(isbn: str) -> dict:
    url = "https://ndlsearch.ndl.go.jp/api/opensearch?" + urllib.parse.urlencode({"isbn": isbn})
    try:
        raw = urllib.request.urlopen(url, timeout=20).read()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    root = ET.fromstring(raw)
    items = root.findall(".//item")
    if not items:
        return {}
    it = items[0]
    out = {"isbn": isbn}
    for tag in it:
        t = tag.tag.split("}")[-1]
        v = (tag.text or "").strip()
        if not v:
            continue
        if t == "title" and "title" not in out:
            out["title"] = v
        elif t == "creator" and "author" not in out:
            out["author"] = v
        elif t == "publisher" and "publisher" not in out:
            out["publisher"] = v
        elif t == "date" and "date" not in out:
            out["date"] = v
        elif t == "volume":
            out["volume"] = v
        elif t == "edition":
            out["edition"] = v
    return out


if __name__ == "__main__":
    import sys
    for isbn in sys.argv[1:]:
        r = lookup(isbn)
        print(isbn, "→", r if r else "（NDLにも無し）")
        time.sleep(0.5)          # 相手のサーバに優しく
