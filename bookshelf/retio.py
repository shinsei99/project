# -*- coding: utf-8 -*-
"""RETIO（不動産適正取引推進機構）機関誌から、判例・紛争事例・賃貸実務の記事だけを取る。

**全部は取らない。** 138号×20本≒2,760本あるので、相手のサーバにも負担。
判例と、賃貸管理に効く実務記事だけを選ぶ。1本ずつ間を空けて落とす。
"""
import os, re, sys, time, urllib.parse, urllib.request, html

BASE = "https://www.retio.or.jp"
# ★置き場は `CLAUDE/` の下（CLAUDE.md 3-c）。2026-09-01 にオーナー指示で移した。
#   ingest_all.py と同じ環境変数で差し替えられる。
OUT = os.path.join(
    os.environ.get("BOOKSHELF_PRIM_DIR",
                   os.path.expanduser("~/Library/CloudStorage/Dropbox-個人/CLAUDE/一次資料")),
    "RETIO判例・実務")
# 欲しい記事の見出し（部分一致）
WANT = re.compile(
    r"最近の裁判例|裁判例索引|紛争事例|検討報告|賃貸|サブリース|管理業法|"
    r"原状回復|重要事項|媒介|相続|空き家|滞納|明渡|借地")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=40).read()


def issue_articles(no):
    """その号の記事一覧（(pdf_url, 見出し)）"""
    for path in (f"/official-organ/retio-{no}号/", f"/official-organ/retio{no}/"):
        try:
            t = fetch(BASE + urllib.parse.quote(path)).decode("utf-8", "replace")
        except Exception:
            continue
        out = []
        for m in re.finditer(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', t, re.S):
            label = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip().replace("\n", " ")
            out.append((m.group(1), label))
        if out:
            return out
    return []


if __name__ == "__main__":
    first, last = int(sys.argv[1]), int(sys.argv[2])
    os.makedirs(OUT, exist_ok=True)
    got = skipped = 0
    for no in range(first, last - 1, -1):
        arts = issue_articles(no)
        if not arts:
            print(f"  {no}号: ページを開けず"); continue
        hit = [(u, l) for u, l in arts if WANT.search(l)]
        print(f"■ {no}号: 記事{len(arts)}本 → 取得対象 {len(hit)}本")
        for url, label in hit:
            name = re.sub(r'[/:*?"<>|]', "_", f"RETIO{no:03d}_{label}")[:90] + ".pdf"
            path = os.path.join(OUT, name)
            if os.path.exists(path):
                skipped += 1; continue
            try:
                data = fetch(BASE + url if url.startswith("/") else url)
                open(path, "wb").write(data)
                got += 1
                print(f"    → {label[:44]} ({len(data)//1024}KB)")
            except Exception as e:
                print(f"    ! {label[:34]}: {type(e).__name__}")
            time.sleep(1.2)          # 相手のサーバに優しく
        time.sleep(1.0)
    print(f"\n取得 {got}本 / 既にあった {skipped}本")
