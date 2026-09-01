# -*- coding: utf-8 -*-
"""OCR済みの本から ISBN を拾い、openBD で正式書名・出版社・出版年月・著者を引く。

- ISBN は**裏表紙**（バーコード横）にあることが多い。奥付にも載る。前後の数ページを見る
- OCR は数字を誤読するので、**チェックディジットで検算**してから使う
- ISBN-10 の本（古い本）は ISBN-13 に直してから引く
"""
import json, os, re, sys, time, urllib.request

# ★置き場は個人Dropboxの CLAUDE/ の下（CLAUDE.md 3-c）。2026-09-01 にオーナー指示で移した。
#   ingest_all.py / replace_all.py と同じ環境変数で差し替えられる。
BOOKS = os.environ.get(
    "BOOKSHELF_BOOKS_DIR",
    os.path.expanduser("~/Library/CloudStorage/Dropbox-個人/CLAUDE/書籍"))
S = os.path.dirname(os.path.abspath(__file__))


def ok13(s):
    if len(s) != 13 or not s.isdigit() or not s.startswith(("978", "979")):
        return False
    t = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s[:12]))
    return (10 - t % 10) % 10 == int(s[12])


def ok10(s):
    if len(s) != 10 or not re.fullmatch(r"\d{9}[\dXx]", s):
        return False
    t = sum((10 - i) * (10 if c in "Xx" else int(c)) for i, c in enumerate(s))
    return t % 11 == 0


def to13(s10):
    core = "978" + s10[:9]
    t = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
    return core + str((10 - t % 10) % 10)


def find_isbn(text):
    """テキストから妥当な ISBN を全部拾う（検算に通ったものだけ）"""
    out = []
    flat = re.sub(r"[-‐−ー\s]", "", text)
    for m in re.findall(r"97[89]\d{10}", flat):
        if ok13(m) and m not in out:
            out.append(m)
    if not out:                      # 13桁が無ければ 10桁を探す
        for m in re.findall(r"(?<!\d)\d{9}[\dXx](?!\d)", flat):
            if ok10(m):
                c = to13(m)
                if c not in out:
                    out.append(c)
    return out


def openbd(isbns):
    if not isbns:
        return {}
    url = "https://api.openbd.jp/v1/get?isbn=" + ",".join(isbns)
    try:
        data = json.load(urllib.request.urlopen(url, timeout=20))
    except Exception as e:
        print("openBD 失敗:", e); return {}
    got = {}
    for d in data:
        if not d:
            continue
        s = d.get("summary", {})
        if s.get("isbn"):
            got[s["isbn"]] = s
    return got


if __name__ == "__main__":
    import fitz
    titles = {}
    for line in open(os.path.join(S, "final_titles.tsv"), encoding="utf-8"):
        if "\t" in line:
            a, b = line.rstrip("\n").split("\t", 1)
            titles[b] = a
    done = [t for t in titles if os.path.exists(os.path.join(BOOKS, t + ".pdf"))]
    print(f"OCR済み {len(done)}冊を調べる\n")
    found, none = {}, []
    for t in sorted(done):
        p = os.path.join(BOOKS, t + ".pdf")
        try:
            d = fitz.open(p)
            n = d.page_count
            look = list(range(max(0, n - 6), n)) + list(range(0, min(4, n)))
            txt = "\n".join(d[i].get_text() for i in look)
            d.close()
        except Exception as e:
            none.append((t, f"読めず {e}")); continue
        c = find_isbn(txt)
        if c:
            found[t] = c
        else:
            none.append((t, "ISBNが見つからない"))
    all_isbn = sorted({i for v in found.values() for i in v})
    meta = openbd(all_isbn)
    print(f"■ ISBNが取れた {len(found)}冊 / うち openBD に載っていた {len(meta)}件\n")
    rows = []
    for t in sorted(found):
        hit = next((meta[i] for i in found[t] if i in meta), None)
        if hit:
            rows.append((t, hit))
            print(f"○ {t}")
            print(f"    正式書名: {hit.get('title')}")
            print(f"    {hit.get('publisher')} / {hit.get('pubdate')} / {hit.get('author')}")
        else:
            print(f"△ {t}  … ISBN {found[t]} は openBD に無し")
    print(f"\n■ ISBNが取れなかった {len(none)}冊")
    for t, why in none:
        print(f"  × {t}  … {why}")
    json.dump({t: {"isbn": h.get("isbn"), "title": h.get("title"),
                   "publisher": h.get("publisher"), "pubdate": h.get("pubdate"),
                   "author": h.get("author")} for t, h in rows},
              open(os.path.join(S, "bookmeta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
