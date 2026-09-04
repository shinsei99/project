#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整理計画 v2 ── 「物件フォルダの直下にあるもの」だけを仕分ける。
   ★1ファイルしか入っていないフォルダを畳むときの例外:
     入居者/ 解約・精算/ の下のテナントの箱は、中が1件でも畳まない。
     「誰の書類か」を表す箱なので、畳むと持ち主が分からなくなる。
   ★フォルダはバラさない。まるごと棚の下へ移す（中身は一切触らない）。
   読むだけ。1件も動かさない。

   {物件名}/契約/            {物件名}/修繕・点検/   {物件名}/図面・写真/
   {物件名}/お知らせ/
   {物件名}/入居者/{テナント}/ {物件名}/解約・精算/{テナント}/
"""
import os, re, sys, unicodedata, collections, datetime
from openpyxl import load_workbook

ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ"
MP   = "物件・管理/管理物件"
RR   = ["★要更新★レントロール一覧（ビル）.xlsx",
        "★要更新★レントロール一覧（マンション）.xlsx",
        "★要更新★レントロール一覧（駐車場他）.xlsx"]
N = lambda s: unicodedata.normalize("NFC", s)

def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = re.sub(r"[\s　・･,，.。\-ー－_/\\'\"()（）\[\]【】]", "", s)
    s = re.sub(r"株式会社|有限会社|合同会社|医療法人|社会福祉法人|一般社団法人|㈱|㈲", "", s)
    for a, b in (("ⅰ","1"),("ⅱ","2"),("ⅲ","3"),("ii","2")): s = s.replace(a, b)
    return s
def names_of(s):
    s = unicodedata.normalize("NFKC", str(s))
    return [norm(x) for x in ([s] + re.findall(r"[(（]([^)）]{2,30})[)）]", s)
                              + [re.sub(r"[(（][^)）]*[)）]", "", s)]) if norm(x)]
def pstem(s):
    n = norm(s)
    for suf in ("ビル","bldg","マンション","駐車場","モータープール","駐輪場"):
        if n.endswith(suf) and len(n) > len(suf)+2: n = n[:-len(suf)]
    return n

# ---------- レントロール ----------
rr = {}
for f in RR:
    p = os.path.join(ROOT, f)
    if not os.path.exists(p): continue
    wb = load_workbook(p, data_only=True, read_only=True)
    for sn in wb.sheetnames:
        data = [[("" if c is None else str(c).strip()) for c in row] for row in wb[sn].iter_rows(values_only=True)]
        ci = si = ri = None
        for row in data[:6]:
            for j, c in enumerate(row):
                if c == "契約者": ci = j
                elif c == "現況": si = j
                elif c in ("号室","号室/フロア","区画No","区画"): ri = j
            if ci is not None: break
        if ci is None: continue
        tbl = {}
        for row in data:
            if len(row) <= ci: continue
            t = row[ci]; rm = row[ri] if (ri is not None and len(row) > ri) else ""
            if not t or t in ("契約者","合計","計","空室","空き","-"): continue
            if si is not None and len(row) > si and row[si] in ("空室","空き","解約","退去"): continue
            for nm in names_of(t): tbl.setdefault(nm, rm or t)
        if tbl: rr[pstem(sn)] = tbl
    wb.close()

# ---------- 棚（上から順に当てる＝優先順位） ----------
SHELVES = [
    ("解約・精算",  r"解約|退去|明渡|原状回復|現状回復|敷金返還|精算|清算"),
    ("入居者",     r"賃借人|入居者|テナント資料"),
    ("お知らせ",   r"お知らせ|おしらせ|通知|案内|貼紙|掲示|連絡先|検針|メーター|水道|ガス|使用量|騒音|ごみ|ゴミ|停電|断水|アンケート|郵便受|ポスト|暗証|解錠"),
    ("図面・写真", r"図面|竣工|平面|間取|配置|測量|公図|写真|マイソク|パース|看板|広告物|サイン|地図|矩計|ターポリン|案内板|\.jpe?g$|\.png$|\.heic$"),
    ("修繕・点検", r"工事|修繕|リフォーム|リホーム|見積|施工|点検|検査|保守|清掃|設備|昇降|エレベータ|ＥＶ|消防|防火|避難|廃棄物|貯水槽|受水槽|給水|排水|空調|請求|領収|報告|作業|統括|訓練|自火報|産業廃棄物|電気"),
    ("契約",      r"契約|重説|重要事項|覚書|合意|更新|定期借家|保証委託|申込|審査|媒介|念書|承諾|民法改正|特殊詐欺|鍵受領|鍵預|登記|謄本|全部事項|評価証明|保険|証券|抵当"),
]
ENTITY = re.compile(r"^\d+番|^\d+号|^[A-Z]?\d{3,4}(号|室|_)|^\d+[FＦ]|^\d+階|^[0-9]{3}_|^\d+[FＦ]【|"
                    r"（\d{4}[.\-/]\d{1,2}|～）|^\d{4}[.\-]\d{2}[.\-]\d{2}_")
KAIYAKU = re.compile(r"解約|退去|明渡|不成立|終了")
SHELFNAME = re.compile(r"^(0[1-9]_)?(契約|修繕・点検|図面・写真|お知らせ|入居者|解約・精算)$")

def shelf_of(name, inner):
    """name=直下の名前、inner=その中のファイル名を連ねたもの"""
    for sh, pat in SHELVES:
        if re.search(pat, name): return sh, "名前"
    for sh, pat in SHELVES:
        if inner and re.search(pat, inner): return sh, "中身のファイル名"
    return "", "★判定できず"

def count(p):
    n = 0
    for c, d, f in os.walk(p): n += sum(1 for x in f if x != ".DS_Store" and not x.startswith("._"))
    return n
def inner_names(p, limit=40):
    out = []
    for c, d, f in os.walk(p):
        for x in f:
            if x == ".DS_Store" or x.startswith("._"): continue
            out.append(N(x))
            if len(out) >= limit: return " ".join(out)
    return " ".join(out)

only = [a for a in sys.argv[1:] if not a.startswith("--")]
JSON = "--json" in sys.argv
rows = []
for kind in sorted(os.listdir(os.path.join(ROOT, MP))):
    kp = os.path.join(ROOT, MP, kind)
    if not os.path.isdir(kp): continue
    for prop in sorted(os.listdir(kp)):
        pp = os.path.join(kp, prop)
        if not os.path.isdir(pp): continue
        if only and N(prop) not in only: continue
        k = pstem(prop)
        cand = [kk for kk in rr if kk and (kk in k or k in kk) and min(len(kk), len(k)) >= 3]
        table = rr[max(cand, key=len)] if cand else None
        for item in sorted(os.listdir(pp)):
            if item in (".DS_Store",) or item.startswith("._"): continue
            ip = os.path.join(pp, item); item = N(item)
            isdir = os.path.isdir(ip)
            if isdir and SHELFNAME.match(item):
                continue                                    # すでに棚
            n = count(ip) if isdir else 1
            # テナントの箱か？
            if isdir and (ENTITY.search(item) or KAIYAKU.search(item) or re.match(r"^賃借人資料", item)):
                if item.startswith("解約済"):      # 既存フォルダは「解約済（物件名）」の名前
                    sh, why, box = "解約・精算", "この箱ごと『解約・精算』にする（中身そのまま）", "＊中身をそのまま"
                elif re.match(r"^賃借人資料", item):
                    sh, why, box = "入居者", "この箱ごと『入居者』にする（中身そのまま）", "＊中身をそのまま"
                elif KAIYAKU.search(item):
                    sh, why, box = "解約・精算", "名前に解約とある", item
                elif table is None:
                    sh, why, box = "", "★レントロールに物件が無い", ""
                else:
                    c2 = names_of(re.sub(r"^[0-9A-Za-zＦF【】\[\]_番号室階\-]+", "", item)) + names_of(item)
                    hit = [t for t in table if t and len(t) >= 3
                           and any(t in c or c.endswith(t) or t.endswith(c) for c in c2)]
                    if hit: sh, why, box = "入居者", f"レントロール {table[max(hit,key=len)]} と一致", item
                    else:   sh, why, box = "解約・精算", "レントロールに載っていない", item
            else:
                sh, why = shelf_of(item, inner_names(ip) if isdir else "")
                box = ""
            new = f"{MP}/{kind}/{prop}/{sh}/" + (f"{box}/" if box else "") + (item if not box else "") \
                  if sh else ""
            if sh and box: new = f"{MP}/{kind}/{prop}/{sh}/{box}"
            elif sh:       new = f"{MP}/{kind}/{prop}/{sh}/{item}"
            rows.append({"物件": N(prop), "種別": N(kind), "種類": "フォルダ" if isdir else "ファイル",
                         "名前": item, "中の件数": n, "行き先": sh or "（動かさない）",
                         "決め手": why,
                         "現在のパス": f"{MP}/{kind}/{prop}/{item}",
                         "移動後のパス": new or f"{MP}/{kind}/{prop}/{item}"})

if JSON:
    import json
    print(json.dumps(rows, ensure_ascii=False))
    sys.exit(0)

tot = sum(r["中の件数"] for r in rows)
print("=" * 74); print("整理計画 v2 ── 直下だけ仕分ける／フォルダはバラさない"); print("=" * 74)
print(f"  直下の項目 {len(rows)}個（中身 合計{tot:,}件）/ {len({r['物件'] for r in rows})}物件\n")
print("  行き先（項目数 / 中の件数）:")
c1 = collections.Counter(r["行き先"] for r in rows)
c2 = collections.Counter()
for r in rows: c2[r["行き先"]] += r["中の件数"]
for k, v in c1.most_common(): print(f"    {k:<14}{v:>5}個{c2[k]:>8,}件")
print("\n  決め手:")
for k, v in collections.Counter(r["決め手"] for r in rows).most_common():
    print(f"    {k:<28}{v:>5}個")

if only:
    print(f"\n=== {only[0]} の内訳 ===")
    for r in sorted(rows, key=lambda x: (x["行き先"], x["名前"])):
        print(f"  {r['行き先']:<12} ← [{r['種類']}] {r['名前'][:44]:<44} {r['中の件数']:>3}件  ({r['決め手']})")
else:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "整理計画v2"
    COLS = list(rows[0].keys()); ws.append(COLS)
    for c in range(1, len(COLS)+1):
        ws.cell(1, c).font = Font(bold=True, color="FFFFFF")
        ws.cell(1, c).fill = PatternFill("solid", fgColor="4472C4")
    for r in sorted(rows, key=lambda x: (x["行き先"] != "（動かさない）", x["物件"], x["行き先"])):
        ws.append([r[c] for c in COLS])
    for i, w in enumerate([26,12,10,46,10,14,28,74,74], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    yel = PatternFill("solid", fgColor="FFF2CC")
    for i in range(2, ws.max_row+1):
        if str(ws.cell(i, 7).value).startswith("★"):
            for c in range(1, len(COLS)+1): ws.cell(i, c).fill = yel
    out = os.path.expanduser(f"~/Desktop/整理計画v2_{datetime.date.today():%Y%m%d}.xlsx")
    wb.save(out); print(f"\n書き出し: {out}  （{len(rows)}行）")
