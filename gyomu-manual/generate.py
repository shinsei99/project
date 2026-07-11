# -*- coding: utf-8 -*-
import html, urllib.parse, io, os, json, re, subprocess, unicodedata

def _nfc(s): return unicodedata.normalize("NFC", s)

OUT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ/業務マニュアル.html"

def esc(s): return html.escape(str(s))
def href(path):  # relative path from the html location (folder root)
    return urllib.parse.quote(path)

# ---------- Departments ----------
DEPTS = [
    ("cal",    "全体像",     "📅", "#6366f1", None),
    ("keiri",  "経理・請求", "📊", "#0284c7", "経理・請求"),
    ("kanri",  "物件・管理", "🏢", "#059669", "物件・管理"),
    ("eigyo",  "営業・募集", "📣", "#d97706", "営業・募集"),
    ("setsubi","業者・設備", "🔧", "#7c3aed", "業者・設備"),
    ("soumu",  "社内・総務", "📁", "#db2777", "社内・総務"),
]
DEPT_LABEL = {d[0]: d[1] for d in DEPTS}
DEPT_COLOR = {d[0]: d[3] for d in DEPTS}

def L(label, path, note=""):
    return {"label": label, "path": path, "note": note}

# ---------- Manuals ----------
M = []
def manual(id, dept, title, lead, blocks, links=None, parent=None):
    M.append(dict(id=id, dept=dept, title=title, lead=lead, blocks=blocks, links=links or [], parent=parent))

# ---------- Word文書(.docx/.doc)→本文ブロック（textutilで抽出。閲覧時はファイル不要） ----------
ROOT = os.path.dirname(OUT)

# 各マニュアルページの「⧉ generate.py用に書き出し」でコピーした本文をここに貼ると、
# 原本docxより優先して全員に反映される（docid をキーにした上書き）。例:
#   OVERRIDES["bldg-1-man"] = r"""...本文...."""
OVERRIDES = {}

# 手順書ページ（経理・管理などの①②③型）の「⧉ generate.py用に書き出し」で
# コピーしたHTMLをここに貼ると、そのページ本文が丸ごと差し替わり全員に反映される。例:
#   HTML_OVERRIDES["keiri-nyukin"] = r"""<div ...>...</div>"""
HTML_OVERRIDES = {}

def _text_to_blocks(txt, docid):
    lines = [ln.rstrip() for ln in txt.replace("\r\n","\n").replace("\r","\n").split("\n")]
    paras=[]; cur=[]
    for ln in lines:
        st=ln.strip()
        if st=="":
            if cur: paras.append("\n".join(cur)); cur=[]
        elif re.match(r'^[《【〔■◆●○▼◎]', st) and len(st)<=30:
            # 見出し記号で始まる短い行は独立させて見出し扱い（後続本文と結合させない）
            if cur: paras.append("\n".join(cur)); cur=[]
            paras.append(ln)
        else:
            cur.append(ln)
    if cur: paras.append("\n".join(cur))
    if not paras:
        return [{"type":"note","text":"（本文が空です）"}]
    return [{"type":"doc","paras":paras,"docid":docid}]

def doc_to_blocks(relpath, docid=None):
    if docid and docid in OVERRIDES:
        return _text_to_blocks(OVERRIDES[docid], docid)
    full = os.path.join(ROOT, relpath)
    if not os.path.exists(full):
        return [{"type":"note","text":"（元ファイルが見つかりません：%s）"%relpath}]
    try:
        r = subprocess.run(["textutil","-convert","txt",full,"-stdout"],
                           capture_output=True, timeout=30)
        txt = r.stdout.decode("utf-8","replace")
    except Exception:
        return [{"type":"note","text":"（本文を読み込めませんでした：%s）"%relpath}]
    return _text_to_blocks(txt, docid)

def doc_prose(relpath):
    """docx/docの本文を、他の手順書ページに埋め込める『prose』ブロックとして返す
    （docブロックと違い独自の編集ツールバーを持たず、ページ全体編集にそのまま乗る）。"""
    out=[]
    for blk in doc_to_blocks(relpath):
        if blk.get("type")=="doc":
            out.append({"type":"prose","paras":blk["paras"]})
        else:
            out.append(blk)
    return out

def _para_html(paras):
    ps=[]
    for p in paras:
        head = ("\n" not in p) and (
                 bool(re.match(r'^[\s　]*[《【〔■◆●○▼◎]', p)) or
                 (len(p)<=24 and (p.endswith("について") or p.endswith("マニュアル") or p.endswith("業者"))))
        ps.append('<div class="%s">%s</div>'%("dochead" if head else "docpara", esc(p)))
    return "".join(ps)

# ---- Calendar (全体像) ----
# (日, 対象=正式名称, 業務内容, 部門, フォルダ相対パス)  ※1行=1対象。フォルダは新共有フォルダ直下からの相対パス
_B  = "物件・管理/管理物件/ビル/"
_M  = "物件・管理/管理物件/マンション/"
_P  = "物件・管理/管理物件/駐車場/"
_O  = "物件・管理/管理物件/その他物件/"
_KS = "物件・管理/検針関連/各メーター検針表/"   # 管理業務から取り出した検針集約フォルダ
CAL = [
 ("1日","もと美モータープール","入金確認→未入金は催促→全入金確認後、最終入金状況を梶原様＋英様へ郵送（入金一覧＋通帳コピー）","keiri",_P+"もと美モータープール"),
 ("1日","大京天王寺ビル","大和証券ファシリティの請求書を月初付で投函","keiri",_B+"大京天王寺ビル"),
 ("1日","ワタヤライラックビル","家賃一覧表を作成（入退去をチェック）","keiri",_M+"ワタヤライラック",_M+"ワタヤライラック/ライラック家賃入金一覧表・請求書.xls"),
 ("5日","マンション空室","空室一覧表を更新（目安：毎週金）","eigyo","営業・募集/募集中物件","営業・募集/管理物件等資料及び空室.xlsx"),
 ("5日","緊急サポート24","退会入力（毎月5日頃まとめて）","setsubi","業者・設備/緊急サポート24"),
 ("7日","パールハイム高殿","水道メーター検針依頼のメール（クエスト）","kanri",_M+"パールハイム高殿"),
 ("9日","大京本社ビル","電気・水道メーター検針（毎月）→一覧表作成","kanri",_B+"大京本社ビル",_KS+"★本社・西・メーター表.xls"),
 ("9日","大京西ビル","電気・水道メーター検針（毎月）→一覧表作成","kanri",_B+"大京西ビル",_KS+"★本社・西・メーター表.xls"),
 ("9日","大京ビル（囲碁）","電気・水道メーター検針（毎月）→一覧表作成","kanri",_B+"大京ビル（囲碁）",_KS+"本社・西・囲碁ビルメーター検針表/★電気メーター　囲碁大京ビル.xls"),
 ("9日","サトウビル","水道メーター検針（2ヶ月に1回）→一覧表作成","kanri",_B+"サトウビル",_KS+"サトウビルメーター検針表/水道メーター検針表.xls"),
 ("9日","クリスタル京橋ビル","水道メーター検針（1F親・2F子メーター）→一覧表作成","kanri",_B+"クリスタル京橋ビル（高野博行）",_B+"クリスタル京橋ビル（高野博行）/水道メーター表.xlsx"),
 ("9日","河合京橋ビル","電気・水道メーター検針（服部さんが検針）","kanri",_B+"河合京橋ビル（河合繁子）",_B+"河合京橋ビル（河合繁子）/●水道メーター"),
 ("10日","大京本社ビル","請求書発行（大和証券ファシリティは月初）","keiri",_B+"大京本社ビル"),
 ("10日","大京西ビル","請求書発行","keiri",_B+"大京西ビル"),
 ("10日","大京ビル（囲碁）","請求書発行","keiri",_B+"大京ビル（囲碁）"),
 ("11日","サトウビル","請求書発行","keiri",_B+"サトウビル"),
 ("11日","クリスタル京橋ビル","請求書発行（管理料も）","keiri",_B+"クリスタル京橋ビル（高野博行）",_B+"クリスタル京橋ビル（高野博行）/クリスタル京橋テナント・管理料　請求書.xls"),
 ("11日","河合京橋ビル","請求書発行","keiri",_B+"河合京橋ビル（河合繁子）"),
 ("11日","各管理物件","請求書発行","keiri","物件・管理/管理物件"),
 ("12日","大京西ビル 5F 嶋村様","メールで請求","keiri",_B+"大京西ビル"),
 ("13日","大京本社ビル 5F ミュゼプラチナム","プラットフォーム入力で電子請求","keiri",_B+"大京本社ビル"),
 ("14日","黒田ビル（黒田徳幸／㈱大建）","請求書発行","keiri",_B+"黒田ビル（黒田徳幸）"),
 ("15日","大京本社ビル（大和証券ファシリティ）","請求書発行（投函は月初）","keiri",_B+"大京本社ビル"),
 ("15日","大京天王寺ビル","検針一覧表を作成","keiri",_B+"大京天王寺ビル",_KS+"大京天王寺ビルメーター検針表"),
 ("16日","各請求先","請求書発行（次月初日の日付、月末入金確認後 月初投函）","keiri","経理・請求/発行請求書（ビル別）"),
 ("17日","全請求書","封筒作成（差し込みデータ使用）","keiri","経理・請求"),
 ("21日","自社マンション","解約予定の募集資料作成（即入時）","eigyo",_M+"自社マンション"),
 ("21日","管理マンション","解約予定の募集資料作成（即入時）","eigyo",_M),
 ("24日","管理マンション","服部さんの条件で募集準備","eigyo",_M),
 ("25日","隆生福祉会（ゆめシリーズ）","各管理料の請求書発行（請求日は末日付）","keiri",_O+"隆生福祉会（ゆめ）"),
 ("29日","キャッスルプラザ壱番館","鍵を服部さんに預ける（賃住扱い・既存カードのまま）","kanri",_M+"キャッスルプラザ"),
 ("30日","キャッスルプラザ松屋町","鍵は新交換後持参・旧は返還（賃貸ショップ扱い）","kanri",_M+"キャッスルプラザ"),
 ("随時","空室（募集中物件）","新規募集・レインズ／ハトマーク登録・ボードに条件記入","eigyo","営業・募集/募集中物件"),
]
manual("cal-month","cal","1ヶ月の業務カレンダー",
  "1日から月末まで、どの部門の作業がいつ発生するかを一望できる全体像です。各作業の詳細は担当部門のマニュアルを参照してください。",
  [{"type":"cal","rows":CAL}])

# ---- 経理・請求 ----
manual("keiri-nyukin","keiri","入金確認・催促",
  "毎月月初の入金チェックと催促、オーナーへの入金状況報告までの流れ。",
  [{"type":"steps","items":[
     "月初、もとみP（もとみモータープール）の入金状況をチェック（梶原様・英様分／杉田さんが通帳記入）",
     "未入金があれば催促する",
     "全入金を確認後、最終入金状況を梶原様＋英様へ郵送（入金一覧＋通帳のコピーを同封）",
     "天王寺ビル・大和証券ファシリティーの請求書を月初付で投函",
     "ワタヤライラックビルの家賃一覧表を作成（入退去をチェック）",
  ]},
   {"type":"sub","text":"賃料回収マニュアル（未収金の督促手順）"},
   {"type":"note","text":"未入金が続く場合の月末〜翌月の督促・回収フロー。原本「賃料回収マニュアル」を本ページに組み込み。"}]
  + doc_prose("社内・総務/研修・資料/マニュアル/賃料回収マニュアル.doc"),
  [L("入金予定（新規契約）フォルダ","経理・請求/入金予定（新規契約）"),
   L("管理物件台帳.xlsx","物件・管理/管理物件台帳.xlsx"),
   L("賃料回収マニュアル.doc（原本）","社内・総務/研修・資料/マニュアル/賃料回収マニュアル.doc")])

manual("keiri-seikyu","keiri","請求書発行（月次）",
  "物件・テナントごとの月次請求書発行スケジュールと手順。発行先の一覧は『請求書発行リスト』を参照。",
  [{"type":"steps","items":[
     {"t":"本社・西・囲碁ビル：10日頃に発行","sub":["大和証券ファシリティは月初","本社5Fミュゼは電子請求（プラットフォーム入力）／西5F嶋村様はメール"]},
     "サ・クリ京・河合・各管理物件：11日頃（クリスタル京橋は管理料も）",
     "大京天王寺ビル：検針一覧表を作成→請求書は次月初日の日付で（月末入金確認後、月初に投函）",
     "ゆめシリーズ（あまみ／長居／中央保育園／パラティース）：管理料請求（請求日は末日付、20日頃発行）",
     "㈱大建（黒田ビル・14日）、㈱トリニティ（ザ・プラザ）、イワイ㈱（京橋GH・3ヶ月毎）など",
     "全請求書の封筒を作成（HIRAKI-FD 宛名・差し込みデータを使用）",
  ]},
  {"type":"note","text":"電子請求への切替時は『請求書の電子送信に関するお知らせ.docx』を送付。発行漏れ防止に『●請求書等郵送及び投函表.xlsx』でチェック。"}],
  [L("請求書発行リスト（このマニュアル内）","#keiri-list","台帳"),
   L("見積・請求書フォーマット.xls","経理・請求/見積・請求書フォーマット.xls"),
   L("●請求書等郵送及び投函表.xlsx","経理・請求/●請求書等郵送及び投函表.xlsx"),
   L("発行請求書（ビル別）フォルダ","経理・請求/発行請求書（ビル別）")])

manual("keiri-seisan","keiri","精算明細書の作成",
  "退去・新規契約に伴う精算明細書の作成と入金確認。",
  [{"type":"steps","items":[
     "退去・新規契約時、精算明細書（借主宛）を作成",
     "要望があれば契約書雛形を業者にFAX",
     "精算金の入金を確認（振込み）",
  ]}],
  [L("精算明細書(借主宛）ＢＡＲ2☆.xls","経理・請求/精算明細書(借主宛）ＢＡＲ2☆.xls"),
   L("精算明細書一覧.xls","経理・請求/精算明細書一覧.xls")])

# 発行請求書フォルダの実サブフォルダ名を生成時に解決（※3ヵ月毎 等の接尾辞ズレ・タイポを回避）
_IK_BASE = "経理・請求/発行請求書（家賃等、テナント賃料、管理料他）"
try:
    _ik_dirs = sorted(d for d in os.listdir(os.path.join(ROOT,_IK_BASE))
                      if os.path.isdir(os.path.join(ROOT,_IK_BASE,d)))
except Exception:
    _ik_dirs = []
def ik(*hints):
    """base直下から hints のいずれかを含むサブフォルダを探し相対パスを返す。無ければ base（親）を返す。"""
    for h in hints:
        hn=_nfc(h)
        for d in _ik_dirs:
            if hn in _nfc(d):
                return _IK_BASE+"/"+d
    return _IK_BASE

_KL_ROWS = [
     ["大京本社ビル","家賃","毎月","10日頃","ミュゼは電子請求"],
     ["大京本社ビル（大和証券ファシリティー）","家賃","毎月","1日頃",""],
     ["大京西ビル","家賃","毎月","10日頃",""],
     ["大京ビル（宮本むなし）","家賃","毎月","10日頃","5F嶋村様メール"],
     ["サトウビル","家賃","毎月","10日頃",""],
     ["クリスタル京橋ビル","家賃・管理料","毎月","10日頃",""],
     ["河合京橋ビル","家賃・管理料","毎月","10日頃",""],
     ["大京天王寺ビル","家賃","毎月","1日頃",""],
     ["ゆめあまみ／中央保育園／長居公園","管理料","毎月","20日頃","請求日は末日"],
     ["ゆめパラティース","床・ガラス","実施後","20日頃","請求日は末日"],
     ["㈱大建（黒田邸）","管理料","毎月","10日頃",""],
     ["㈱トリニティ（ザ・プラザ）","管理料","毎月","10日頃",""],
     ["イワイ㈱（京橋グリーンハイツ）","管理料","3ヶ月に1回","10日頃",""],
     ["黒田様（黒田邸）","管理料","3ヶ月に1回","10日頃",""],
     ["㈱ミス・パリ（シャトー）","電気保安管理料","1年に1回","毎年6月",""],
     ["片町看板代","賃料","1年","毎年6・7月",""],
]
_KL_LINKS = [
     ik("大京本社","本社"),
     ik("大京本社","本社"),
     ik("大京西","西ビル"),
     ik("囲碁","大京ビル"),
     ik("サトウ"),
     ik("クリスタル"),
     ik("河合"),
     ik("天王寺"),
     ik("ゆめ","隆生"),
     ik("ゆめ","隆生"),
     ik("黒田"),
     ik("トリニティ","プラザ"),
     ik("イワイ","京橋GH"),
     ik("黒田"),
     ik("ミスパリ","ミス・パリ","シャトー"),
     ik("広告板","大京片町"),
]
manual("keiri-list","keiri","【台帳】請求書発行リスト",
  "毎月どの物件に何を・いつ請求するかの一覧。請求先名をクリックすると、その発行請求書フォルダへ直接移動します。",
  [{"type":"table","head":["請求先","内容","頻度","発行時期","備考"],
    "rows":_KL_ROWS,"rowlinks":_KL_LINKS}],
  [L("発行請求書（家賃等、テナント賃料、管理料他）フォルダ",_IK_BASE),
   L("発行請求書（テナント別）フォルダ","経理・請求/発行請求書（テナント別）")])

# ---- 物件・管理 ----
# 検針表フォルダ内の実ファイルを生成時に自動解決（★・全角空白・競合コピー等の表記ズレを回避）
_KSD = "物件・管理/検針関連/各メーター検針表"          # 集約フォルダ
_HW  = _KSD+"/本社・西・囲碁ビルメーター検針表"
_SA  = _KSD+"/サトウビルメーター検針表"
_TN  = _KSD+"/大京天王寺ビルメーター検針表"
_CRB = "物件・管理/管理物件/ビル/クリスタル京橋ビル（高野博行）"
_KWB = "物件・管理/管理物件/ビル/河合京橋ビル（河合繁子）/●水道メーター"
def _R(base, *hints):
    """base直下から hints のいずれかを含むファイル/フォルダを探し相対パスを返す。無ければ base。"""
    d=os.path.join(ROOT, base)
    try: entries=sorted(os.listdir(d))
    except Exception: return base
    for h in hints:
        hn=_nfc(h)
        for e in entries:  # ディレクトリ優先（同名を含むファイルに吸われないように）
            if hn in _nfc(e) and os.path.isdir(os.path.join(d,e)):
                return base+"/"+e
        for e in entries:
            if hn in _nfc(e):
                return base+"/"+e
    return base
def Lr(label, base, *hints):
    return L(label, _R(base, *hints))

# --- 水道メーター検針場所・ルート（塚本担当）: 原本「●水道メーター検針日及びメーター場所・検針方法.xlsx」より ---
_BIL="物件・管理/管理物件/ビル"; _MAN="物件・管理/管理物件/マンション"
_TSK="物件・管理/管理業務/塚本/水道検針及び請求書作成マニュアル"
_KENSHIN_SRC="物件・管理/管理業務/塚本/●水道メーター検針日及びメーター場所・検針方法.xlsx"
def _tsk(hint):
    p=_R(_TSK,hint)
    return [Lr("物件別マニュアル",_TSK,hint)] if p!=_TSK else []
# [物件表示名, フォルダ解決, 検針日, 請求区分, 場所・方法(改行), 塚本マニュアルhint(無=None)]
_KB=[
 ("ワタヤライラックビル", _R(_MAN,"ワタヤ"), "1〜2日頃","漏水確認",
   "親＝EV内近くのPS内（親・共用メーター有）\n子＝各階PS内","ワタヤ"),
 ("カナンハウス", _R(_MAN,"カナン"), "7〜10日頃","漏水確認",
   "親＝駐車場手前の植栽の中\n子(散水)＝ポンプ室内 共用メーター(散水)","カナン"),
 ("三好マンション", _R(_MAN,"三好マンション"), "7〜8日頃","漏水確認",
   "親＝玄関先にあり","三好"),
 ("ソフィア南森町", _R(_MAN,"南森町"), "1〜2日","漏水確認",
   "親＝料理店横辺り","ソフィア南森町"),
 ("ソフィア東野田【吉浦】", _R(_MAN,"東野田"), "7日頃","事務方（作成なし）",
   "親＝ゴミ置場近く\n子＝各戸PS",None),
 ("河合京橋ビル", _R(_BIL,"河合"), "10日頃","事務方（作成なし）",
   "親＝1階保険の窓口・玄関辺りに有\n子＝基本各階トイレ（6階便器下メーター有／4階室内奥・消火器横のPS内／3階無し／2階便器横PS）","河合"),
 ("大京本社ビル(2階)【大鹿】", _R(_BIL,"大京本社"), "10日頃","事務方（作成なし）",
   "子＝2階男子トイレ内\n※検針前に大和証券・次長へ連絡し調整してから伺う（現在：肥後次長 06-6354-1170）",None),
 ("大京囲碁ビル【大鹿】", _R(_BIL,"囲碁"), "10日頃","事務方（作成なし）",
   "親＝ビル横付近(壁)\n電気＝ビル横壁面（高い位置にあるので注意）",None),
 ("サトウビルⅡ【大鹿】", _R(_BIL,"サトウ"), "10日頃","事務方（作成なし）",
   "親＝外部（1ヶ月に1回）\n子＝1階ポンプ室内（1ヶ月に1回）\n電気＝各階階段踊り場壁面・屋上キュービクル内・8階(マッサージ)室内・玄関近く左側の部屋に有（毎月検針）","サトウ"),
 ("角屋マンション", _R(_MAN,"角屋マンション"), "15日頃","作成する",
   "親＝マンション入り口付近\n子＝各戸PS内・1階郵便局(鍵を借りて裏へ)／角屋酒店に領収書を借りてその場で集金","角屋"),
 ("KSKビル", _R(_BIL,"KSK"), "8日頃","作成する",
   "親＝玄関近くの自転車置場の下\n子＝1階トイレドア(南京錠・要鍵)、各戸トイレ内・タンク裏側PS、3階トイレPSは3・4階分のメーター有","KSK"),
 ("弁天町駅前ビル", _R(_BIL,"弁天町"), "8日頃","水道のみ作成",
   "親＝ビル横（後々2・3階が契約になれば子メーター検針になる）\n電気＝ビル横壁面（高い位置・確認しづらい）","弁天町"),
 ("MDXビル", _R(_BIL,"MDX"), "8日頃","作成する",
   "親＝外部(玄関)\n子＝廊下奥PS内\n電灯＝各テナント室内右PS／動力①4階屋上／動力②地下駐車場・壁面","MDX"),
 ("新谷ビル", _R(_BIL,"新谷"), "7〜8日頃","作成する",
   "親＝薬局入口付近","新谷"),
]
_KB_ROWS=[[b[0], b[2], b[3], {"pre":b[4]}, (_tsk(b[5]) if b[5] else [])] for b in _KB]
_KB_LINKS=[b[1] for b in _KB]

manual("kanri-kenshin","kanri","メーター検針（電気・水道）",
  "毎月の電気・水道メーター検針と一覧表作成の物件別ガイド。物件名をクリックすると物件フォルダ、右端の📄で各検針表ファイルを直接開けます。",
  [{"type":"note","text":"基本は毎月9日頃に検針→一覧表を作成し、請求書発行につなげます。検針表は「物件・管理/検針関連/各メーター検針表」に集約（旧・管理業務から移動）。"},
   {"type":"table",
    "head":["物件（正式名）","検針対象","時期","方法・担当・備考","検針表ファイル"],
    "rows":[
      ["大京本社ビル","電気・水道","毎月9日頃","1F・屋上・各階を検針→一覧表作成（5Fミュゼは電子請求）",
        [Lr("本社ビル 電気メーター",_HW,"★電気メーター本社"), Lr("本社・西 メーター表",_KSD,"★本社・西・メーター表")]],
      ["大京西ビル","電気","毎月9日頃","1F・屋上を検針→一覧表作成",
        [Lr("大京西ビル 電気メーター",_HW,"大京西ビル.xls"), Lr("大京西ビル5F",_HW,"大京西ビル5F"), Lr("本社・西 メーター表",_KSD,"★本社・西・メーター表")]],
      ["大京ビル（囲碁ビル）","電気","毎月9日頃","検針→一覧表作成",
        [Lr("囲碁大京ビル 電気メーター",_HW,"囲碁")]],
      ["サトウビル","電気・水道","毎月9日頃（水道は2ヶ月に1回）","検針→一覧表作成",
        [Lr("サトウ 水道メーター検針表",_SA,"水道メーター検針表.xls"), Lr("サトウ 電気メーター・料金表",_SA,"★電気メーター・料金表")]],
      ["大京天王寺ビル","電気・水道","毎月15日頃","検針数値は専務より受領→検針一覧表を作成",
        [Lr("大京天王寺 電気水道メーター（最新）",_TN,"R6.3.30","（R6"), L("天王寺ビル 検針表フォルダ",_TN)]],
      ["クリスタル京橋ビル","水道","毎月9日頃","1F親・2F子メーターを検針→一覧表作成",
        [Lr("クリスタル京橋 水道メーター表",_CRB,"水道メーター表")]],
      ["河合京橋ビル（河合繁子）","電気・水道","毎月9日頃","服部さんが検針",
        [Lr("河合京橋・水道",_KWB,"●河合京橋・水道.xls"), L("河合京橋 ●水道メーター フォルダ",_KWB)]],
      ["パールハイム高殿","水道","毎月7日頃","クエストへ水道メーター検針依頼のメール",
        [L("パールハイム高殿 物件フォルダ","物件・管理/管理物件/マンション/パールハイム高殿")]],
    ],
    "rowlinks":[
      _B+"大京本社ビル", _B+"大京西ビル", _B+"大京ビル（囲碁）", _B+"サトウビル",
      _B+"大京天王寺ビル", _CRB, "物件・管理/管理物件/ビル/河合京橋ビル（河合繁子）",
      "物件・管理/管理物件/マンション/パールハイム高殿",
    ]},
   {"type":"sub","text":"水道メーター検針場所・ルート（塚本担当）"},
   {"type":"note","text":"下表は原本「●水道メーター検針日及びメーター場所・検針方法.xlsx」より。物件名クリックで物件フォルダ、右端で物件別の検針＋請求書作成マニュアルを開けます。◆巡回ルート：KSK → MDXビル → 三好マンション → 弁天町駅前 → カナンハウス。◆注意：MDXビルは月・火・木・金の午前(〜12時)か午後(13時〜)／サトウビルは月曜以外の11時頃(地下1階は16時頃・2階美容室は月曜休)。"},
   {"type":"table",
    "head":["物件（正式名）","検針日","請求書作成","メーター場所・検針方法","検針マニュアル"],
    "rows":_KB_ROWS,"rowlinks":_KB_LINKS}],
  [L("★ 各メーター検針表（集約フォルダ）",_KSD),
   L("● 水道メーター検針日・場所・検針方法（原本xlsx）",_KENSHIN_SRC),
   L("水道検針＆請求書作成マニュアル（物件別フォルダ）",_TSK),
   L("管理業務フォルダ","物件・管理/管理業務")])

manual("kanri-kaiyaku","kanri","解約・立会い",
  "解約通知の受付から立会い・鍵返却・閉栓までの流れ。",
  [{"type":"steps","items":[
     {"t":"解約通知を受付（全部を受付ける）→ 契約書で解約通知の期限・賃料の日割精算の有無を確認","sub":[
        "自社・ソフィア・ライラックは短期違約金等あり（自社は請求書発行）",
        "ベリエール・エレガンス・ソフィアは旧契約書あり"]},
     {"t":"立会い日：日・祝以外の10時〜明るい時間帯。管理者が立会い、鍵を返却してもらう","sub":[
        "立会い：自社＝杉田さん／ソフィア・ライラック・カナンハウス＝服部さん",
        "解約管理台帳・黒板・各立会人のノートに記入し、森下さんに報告"]},
     "電気・ガス（水道は基本なし）の閉栓をしてもらう（個人契約のため）",
  ]}],
  [L("解約受付表.xlsx","物件・管理/解約関連/解約受付表.xlsx"),
   L("解約通知書フォルダ","物件・管理/解約関連/解約通知書"),
   L("解約関連 書式フォルダ","物件・管理/解約関連/書式")])

manual("kanri-kagi","kanri","鍵の管理・鍵交換",
  "鍵交換の依頼、引き上げ、入居時の鍵渡しまで。",
  [{"type":"steps","items":[
     "鍵交換依頼は杉田さん。キャッスル・松屋町は服部さんに鍵引き上げを依頼",
     "入居決定分は鍵を引き上げる（鍵受領書と交換）",
     "キャッスルプラザ：壱番館→賃住／松屋町→賃貸ショップ。壱番館は既存カードのまま／松屋町は新交換後持参・旧は返還",
     "入居日の基本前日ぐらいに鍵渡し（自社→メールBOX№・自転車シール／メゾン・66・ベリエール→メールBOXNo.＋宅配暗証番号）",
  ]}],
  [L("鍵貸出管理簿（原紙）.xlsx","物件・管理/鍵関連/鍵貸出管理簿（原紙）.xlsx"),
   L("鍵管理フォルダ","物件・管理/鍵関連/鍵管理"),
   L("各マンション鍵交換について.docx","社内・総務/研修・資料/マニュアル/各マンション鍵交換について.docx")])

manual("kanri-hoken","kanri","損保（火災保険）業務",
  "火災保険の満期更新・新規加入の手続き。あいおい／AIGの区分に注意。",
  [{"type":"sub","text":"■ 更新（満期）"},
   {"type":"steps","items":[
     "AIGの満期をチェックし、更改申込書をあいおいのオンラインで作成（準備は2ヶ月前をめど）",
     "①お知らせ②満期のご案内③申込書④重説(オンライン)⑤パンフレット⑥返信用封筒 をセットして郵送",
     "元AIGの更新は、代理店変更の用紙を上につける",
   ]},
   {"type":"sub","text":"■ 新規加入"},
   {"type":"steps","items":[
     "新規加入は新規賃貸借契約書にセットして渡す（単身15,000円／2名以上20,000円）",
     "25日以降の当月始期の場合は、サポートセンター（青木さん宛の申込書）をメールする",
   ]},
   {"type":"note","text":"区分：火災→あいおいニッセイ同和損害保険／自動車（一部賠責）→AIG損保。香渡様は本人所有建物＋家財、すべて香渡さんへ郵送（返信用は付ける）。菊本BL（森田オーナー）・高野オーナーは申込書と引換えに現金で即手渡し。"}],
  [L("損保業務フォルダ","物件・管理/損保業務"),
   L("保険証券（自己契約）フォルダ","経理・請求/保険証券（自己契約）")])

manual("kanri-pool","kanri","【台帳】モータープール（駐車場）",
  "各モータープールの月額・保証・解約条件の一覧。",
  [{"type":"table","head":["持ち主／所在","名称","月額(税込)","保証","解約引き","解約連絡","備考"],"rows":[
     ["大京商事","大京","19,800","36,000","18,000＋税","1ヶ月","ﾀｲﾎｳ建設の寮の隣"],
     ["鶴・横堤1-899-1","（軽）","16,500","30,000","15,000＋税","1ヶ月",""],
     ["梶原・英／城・関目","もと美","20,000","2ヶ月","1ヶ月","1ヶ月",""],
     ["角屋商店／鶴・横堤","横堤","26,400","48,000","24,000＋税","1ヶ月","シャッター・郵便局近く"],
     ["尾本／大東・新田西町","大東","19,950","38,000","19,000＋税","1ヶ月","シャッター"],
     ["仲谷／城・野江","エコ","15,500","31,000","0","1ヶ月",""],
     ["三菱重工／北・本庄西","本庄西","25,300","46,000","23,000＋税","1ヶ月",""],
     ["崎陽軒／淀・野中南","十三","17,600","32,000","0","1ヶ月",""],
     ["コインパーク／城・鴫野東","鴫野東","9,000","9,000","0","1ヶ月",""],
     ["コインパーク／此花・梅香","梅香","12,000","12,000","0","1ヶ月",""],
  ]},
  {"type":"note","text":"㈱バイクパーク（東京）管理分の空き問い合わせは、TELで空き確認→折り返し。契約時は㈱バイクパークへTELし客のTEL番号を知らせて契約手配してもらう。"}],
  [L("駐車場予約ﾘｽﾄ.xlsx","経理・請求/駐車場予約ﾘｽﾄ.xlsx")])

# ---- 営業・募集 ----
manual("eigyo-moushikomi","eigyo","入居申込〜審査〜契約〜鍵渡し",
  "申込受付から審査・契約書類作成・鍵渡しまでの一連の流れ。慣れるまでは服部さんに相談。",
  [{"type":"steps","items":[
     "入居申込書を受付（オンライン入力で作成）",
     "審査：保証会社へ申込書＋借主の身分証明書を送付（FAX）",
     "自社以外は保証会社OK後にオーナーへ申込書をFAX（自社以外その他は服部さん担当）",
     "承認がおりたら業者に連絡",
     {"t":"契約書類を作成","sub":[
        "契約書・保証会社申込書・火災保険新規申込書",
        "①案内②ハイパー家財申込書③重説④パンフレット"]},
     "緊急サポート24に加入（対象：メゾン・66・26・トーヨー・パールハイム）",
     "家賃の口座振替依頼書を契約書（自社）と一緒に渡す（メゾン・66・26・トーヨー→三菱UFJ／ベリエール・エレガンス→りそな）",
     "鍵交換依頼 → 精算金入金確認 → 契約書類受付チェック → オーナー㊞手配",
     "入居日の前日ぐらいに鍵渡し（メールBOX№・宅配暗証番号・自転車シール等）",
     "完成契約書を返却（オーナー印未の場合は後日取りに来てもらう）",
  ]}],
  [L("賃貸書式フォルダ（各種申込書・送付状）","営業・募集/賃貸書式"),
   L("マンション入居申込書(個人用).xlsx","営業・募集/賃貸書式/マンション入居申込書(個人用).xlsx"),
   L("賃貸借保証委託契約申込書(個人用).pdf","営業・募集/賃貸書式/賃貸借保証委託契約申込書(個人用).pdf"),
   L("連絡先通知書.xlsx","営業・募集/賃貸書式/連絡先通知書.xlsx"),
   L("各マンションビル等契約の流れ.docx","社内・総務/研修・資料/マニュアル/各マンションビル等契約の流れ.docx")])

manual("eigyo-boshu","eigyo","空室募集・レインズ／ハトマーク登録",
  "空室が出たときの募集資料作成と各サイトへの登録。",
  [{"type":"steps","items":[
     "マンション空室一覧表を随時更新（目安：毎週金曜）",
     "解約予定が即入になったら募集資料を作成（21〜22日頃）",
     "条件を決める（慣れるまで服部さんに依頼）→ ボードに条件を記入",
     "レインズ登録（図面登録／月末は休）・ハトマーク登録（毎週金曜チェック）・黒板に記載",
     "間取りプレミアムで図面を作成",
  ]}],
  [L("募集中物件フォルダ","営業・募集/募集中物件"),
   L("物件資料フォルダ","営業・募集/物件資料"),
   L("物件(間取りプレミアム用）フォルダ","営業・募集/物件(間取りプレミアム用）"),
   L("◎最新マンション空室情報.xls","営業・募集/◎最新マンション空室情報（23.10）.xls")])

manual("eigyo-yachin","eigyo","【台帳】自社マンション家賃推移",
  "自社マンションのタイプ別・現行家賃の目安（坪単価付き）。",
  [{"type":"table","head":["棟","号数","タイプ","㎡","共益費","現行家賃","坪＠(家＋共)"],"rows":[
     ["メゾン","304/305/610","1DK","22.39","7,000","36,000","約6,352"],
     ["メゾン","207","1DK","32.93","7,000","45,000","約5,422"],
     ["メゾン","501","1LDK","31.80","7,000","50,000","約5,619"],
     ["66","501","1DK","30.50","7,000","47,000","約5,857"],
     ["66","603","1DK","21.30","7,000","35,000","約6,211"],
     ["26","107","1DK","34.20","7,000","47,000","約4,932"],
     ["26","207","1DK","34.20","7,000","45,000","約5,029"],
     ["26","105","1K","20.40","7,000","29,000","約5,835"],
  ]},
  {"type":"note","text":"ト-ヨーコーポ／コーポ・ラ・ベリエール／エレガンス放出／パールハイム高殿など㎡が違う物件は、部屋タイプ・リフォーム金額・向き・階数で変わるため服部さんに相談の上決定。"}],
  [])

# ---- 業者・設備 ----
manual("setsubi-support24","setsubi","緊急サポート24（加入・退会・利用対応）",
  "アクトコール／JBRの緊急サポート24の加入・退会入力と利用時対応。",
  [{"type":"steps","items":[
     {"t":"加入はその都度入力（入居日をみて）。対象：メゾン・66・26・トーヨー・パール","sub":[
        "入居は随時入力（後日、承認要入力）","退去はまとめて月初に入力"]},
     "退会入力は毎月5日頃",
     "入居者が利用した場合はメールが来る → 対応する",
  ]}],
  [L("緊急サポート24フォルダ（案内文・チラシ）","業者・設備/緊急サポート24")])

# --- 消防設備点検スケジュール（参考:「消防設備点検表（ユタカ商会）.xlsx」＋報告書の実施実績） ---
_YT_REP="業者・設備/報告書/報告書_ゆたか商会・㈱ワコーテック"
_YT_SRC="業者・設備/消防設備点検表（ユタカ商会）.xlsx"
_YUME="物件・管理/管理物件/その他物件/隆生福祉会（ゆめ）"
# [ビル名, 点検回数, 実施時期の目安, 備考, リンク先]
_YT=[
 ("サトウビル","年1回","10月頃","", _R(_YT_REP,"サトウ")),
 ("H・Kビル","年1回","11月頃","", _R(_YT_REP,"H・K")),
 ("大京ビル（囲碁ビル）","年1回","11〜12月頃","", _R(_YT_REP,"大京ビル")),
 ("第一・第二トーヨーコーポ","第一=3年1回／第二=年1回","11月頃","", _R(_YT_REP,"トーヨーコーポ")),
 ("クリスタル京橋ビル","年1回","12月頃","", _R(_YT_REP,"クリスタル京橋")),
 ("コーポ・ラ・ベリエール","3年1回","12月頃","", _R(_YT_REP,"コーポ・ラ・ベリエール")),
 ("エレガンス放出","3年1回","12月頃","", _R(_YT_REP,"エレガンス放出")),
 ("湯浅ビル","年1回","12月頃","", _R(_YT_REP,"湯浅")),
 ("河合京橋ビル","年1回","12月頃（報告は翌1月のことあり）","", _R(_YT_REP,"河合京橋")),
 ("鶴見会館（鶴見公民館）","年1回","7月頃","", _R(_YT_REP,"鶴見公民館")),
 ("パールハイム高殿","年1回","5月頃","", _R(_YT_REP,"パールハイム")),
 ("ソフィア南森町","3年1回","—","", _R(_MAN,"南森町")),
 ("カナンハウス","3年1回","—","", _R(_MAN,"カナン")),
 ("弁天町駅前ビル","年1回","—","", _R(_BIL,"弁天町")),
 ("KSKビル","年1回","—","消火器・誘導灯のみ", _R(_BIL,"KSK")),
 ("角屋マンション","3年1回","—","消火器・誘導灯のみ", _R(_MAN,"角屋マンション")),
 ("角屋ビル","—","—","消火器のみ", _R(_MAN,"角屋マンション")),
 ("ゆめあまみ","年2回","3月・9月","", _R(_YUME,"ゆめあまみ")),
 ("ゆめ長居公園","年2回","6月・12月","", _R(_YUME,"長居公園")),
 ("ゆめ中央保育園","年2回","3月・9月","", _R(_YUME,"中央保育園")),
]
_YT_ROWS=[[r[0],r[1],r[2],r[3]] for r in _YT]
_YT_LINKS=[r[4] for r in _YT]

manual("setsubi-shoubou","setsubi","消防設備点検",
  "各ビル・マンションの消防設備点検と報告書の保管。",
  [{"type":"steps","items":[
     "各ビル・マンションの消防点検を実施（→物件別の消防点検マニュアル参照）",
     "点検報告書は 業者・設備/報告書 に保管",
  ]},
   {"type":"sub","text":"各ビルの点検スケジュール（実施業者＝ゆたか商会 ほか）"},
   {"type":"note","text":"参考：「消防設備点検表（ユタカ商会）.xlsx」の点検回数・備考＋各報告書の実施実績。物件名クリックでゆたか商会の報告書フォルダ（無い物件は物件フォルダ）へ移動します。「次回報告期限」の最新は原本xlsxで確認してください。天王寺ビル・本社ビル・西ビルは別業者（ニッタン㈱／東洋ビルメンテナンス㈱）です。"},
   {"type":"table",
    "head":["ビル名","点検回数","実施時期の目安","備考"],
    "rows":_YT_ROWS,"rowlinks":_YT_LINKS}],
  [L("● 消防設備点検表（ユタカ商会）原本xlsx",_YT_SRC),
   L("報告書_ゆたか商会・㈱ワコーテック（フォルダ）",_YT_REP),
   L("報告書フォルダ（全業者）","業者・設備/報告書"),
   L("各ビル・マンション等消防点検マニュアル.docx","社内・総務/研修・資料/マニュアル/各ビル・マンション等消防点検マニュアル.docx")])

manual("setsubi-shuzen","setsubi","修繕・メンテ依頼",
  "定期メンテと修繕の外注先・手数料ルール。見積は基本10%オンで発行。",
  [{"type":"steps","items":[
     "ゆめ長居公園：空室リフォーム受け → ベルポへ見積依頼 → 見積書発行（10%オン）→ 実施後に請求書を即発行",
     "ミスパリ（電気設備点検）：関電エネルギーソリューション、2ヶ月に1回 → 報告書をシェイプアップハウス（井ノ上氏）に郵送",
     "ゆめ中央保育園：ガスヒートポンプ（エアコン）点検満了 → ビケンテクノ（大野さん）見積 → 10%オンしてお伺い",
  ]}],
  [L("業者一覧.xlsx","業者・設備/業者一覧.xlsx"),
   L("（契約書雛形）工事請負契約書.doc","業者・設備/（契約書雛形）工事請負契約書.doc")])

manual("setsubi-gyosha","setsubi","【台帳】取引業者一覧",
  "仲介・取引のある不動産会社の一覧。",
  [{"type":"cols","items":["アーバン不動産","アスカオフィスサービス","アパマンショップ","エイブル","オフィスコガ（吉岡氏）","関西不動産（鈴木氏）","クラスモ","三幸エステート","誠和ハウジング","タイセイシュアサービス","宅都プロパティ","賃貸住宅サービス（上野店長）","賃貸ショップ","ディーモハウス","日住サービス","ピッタットハウス","ベストレント","ホームメイト","三鬼商事","ミニミニ","ユニゾン","ライフエステート","リブマックス","レンティブ大成","ワントップハウス"]}],
  [L("業者一覧.xlsx","業者・設備/業者一覧.xlsx")])

# ---- 社内・総務 ----
manual("soumu-menkyo","soumu","宅建業免許の更新（5年毎）",
  "宅地建物取引業免許の更新手続き。",
  [{"type":"steps","items":[
     "宅地建物取引業免許の更新手続きを法務局で行う（5年毎）",
     "更新資料は『宅建業免許更新資料（5年毎）』フォルダを参照",
  ]}],
  [L("宅建業免許更新資料（5年毎）フォルダ","社内・総務/宅建業免許更新資料（5年毎）"),
   L("大阪宅建協会フォルダ","社内・総務/大阪宅建協会")])

manual("soumu-kigen","soumu","期限管理・引継ぎアラート",
  "定期借家の通知期限や各種満期など、期日管理が必要な項目。",
  [{"type":"note","text":"⚠ 以下の日付は2021年春の引継ぎ時点の内容です。運用時は必ず最新の契約書・満期日で更新してください。"},
   {"type":"steps","items":[
     "定期借家：55ステーション（2021/9/1〜2024/8/31、通知期間 2023/8/31〜2024/2/29）※終了の通知を出すこと",
     "定期借家：エレガンス放出 101号室 田中英男様（2015/7/10〜2025/7/9、通知期間 2024/7/9〜2025/1/9）",
     "本社ビル3階 大和証券 2021/8/31解約／1・2階 2021/9/1より家賃条件変更",
     "火災保険 福井様 令和4年7月2日満期（他 令和5年5月・令和6年12月満期）",
     "年間予定表 自社ビル・ゆめシリーズ（毎年12月に作成／設備点検計画は服部さんに確認）",
   ]}],
  [L("研修・資料フォルダ","社内・総務/研修・資料")])

manual("soumu-idpw","soumu","ID・パスワード／各種サービス",
  "業務で使う主要サービスのログイン情報と用途。",
  [{"type":"table","head":["サービス","ID","パスワード","用途・メモ"],"rows":[
     ["全宅連（ハトサポ）","27100027334000","daikyo63530418","ハトサポ→大阪宅建協会会員→DLで契約書・重説等の最新版"],
     ["ACSYS Client","2014131157","1157","—"],
     ["登記情報提供サービス","（緑ファイル）","（緑ファイル）","全部事項証明書（謄本）取得。ID/PWは後ろのグリーンのファイル"],
     ["レインズ","—","—","会長・専務より依頼で検索・登録"],
     ["間取りプレミアム","—","—","間取り図面作成"],
  ]},
  {"type":"note","text":"すべてのパスワードは『●パスワード一覧.xls』にまとまっています。"}],
  [L("●パスワード一覧.xls","社内・総務/社内書式/●パスワード一覧.xls")])

manual("soumu-roumu","soumu","労務・社内様式",
  "雇用・届出・経費精算などの社内様式。",
  [{"type":"steps","items":[
     "雇用：労働条件通知書兼雇用契約書",
     "届出：退職願／有給等届出書／休業案内",
     "経費：経費精算書テンプレート（適格チェック付）",
  ]}],
  [L("[社内様式（届出書等）]フォルダ","社内・総務/[社内様式（届出書等）]"),
   L("労働条件通知書兼雇用契約書.xlsx","社内・総務/労働条件通知書兼雇用契約書.xlsx"),
   L("経費精算書テンプレート（適格チェック付）.xlsx","社内・総務/経費精算書テンプレート（適格チェック付）.xlsx")])

# 物件別マニュアル索引
BUILDINGS = [
 ("K1","K1マニュアル.docx","K1業者.docx"),("KSK","KSKマニュアル.docx","KSK業者.docx"),
 ("MDX","MDXマニュアル.docx","MDX業者.docx"),("U-RIMZ HOUSE","U-RIMZ　HOUSE　マニュアル.docx",None),
 ("カナンハウス","カナンハウスマニュアル.docx","カナンハウス業者.docx"),
 ("サトウビルⅡ","サトウビルⅡマニュアル.docx",None),
 ("ソフィア東野田","ソフィア東野田マンションマニュアル.docx","ソフィア東野田業者.docx"),
 ("ソフィア南森町","ソフィア南森町マンションマニュアル.docx","ソフィア南森町業者.docx"),
 ("ワタヤライラックビル","ワタヤライラックビルマンションマニュアル.docx","ワタヤライラックビル業者.docx"),
 ("河合京橋","河合京橋マニュアル.docx","河合京橋ビル業者.docx"),
 ("角屋マンション","角屋マンションマニュアル.docx","角屋マンション業者.docx"),
 ("角屋横堤ガレージ","角屋横堤ガレージマニュアル.docx",None),
 ("京橋グリーンハイツ","京橋Gハイツマンションマニュアル.docx","京橋グリーンハイツ業者.docx"),
 ("黒田ビル1棟","黒田ビル１棟マニュアル.docx",None),
 ("三好マンション","三好マンションマニュアル.docx","三好マンション業者.docx"),
 ("新谷ビル","新谷ビルマニュアル.docx",None),("尾本P","尾本Pマニュアル.docx",None),
 ("弁天町駅前","弁天町駅前マニュアル.docx",None),("本庄西P","本庄西Pマニュアル.docx",None),
]
def bpath(fn): return "社内・総務/研修・資料/マニュアル/"+fn

# 物件別マニュアルは独立deptにしておく（ホーム一覧には出さず、索引ページから開く）
BLDG_DEPT = "bldg"
DEPT_LABEL[BLDG_DEPT] = "物件別マニュアル"
DEPT_COLOR[BLDG_DEPT] = "#0891b2"

# ---- 物件別：docx本文をページ化 ----
bldg_cards=[]
for i,(name,man,gyo) in enumerate(BUILDINGS):
    mid="bldg-%d"%(i+1)
    blocks=[]; links=[]
    if man:
        blocks.append({"type":"sub","text":"管理マニュアル"})
        blocks+=doc_to_blocks(bpath(man), mid+"-man")
        links.append(L("元ファイル：%s"%man,bpath(man)))
    if gyo:
        blocks.append({"type":"sub","text":"取引業者"})
        blocks+=doc_to_blocks(bpath(gyo), mid+"-gyo")
        links.append(L("元ファイル：%s"%gyo,bpath(gyo)))
    manual(mid,BLDG_DEPT,name,"物件別の管理内容・取引業者などの詳細。全文をこのページで読めます。",
           blocks,links,parent="soumu-buildings")
    bldg_cards.append({"id":mid,"label":name,"sub":("管理／業者" if gyo else "管理")})

# ---- 共通マニュアル（物件横断）：docx/doc本文をページ化 ----
GENERAL=[
 ("苦情対応マニュアル","苦情対応マニュアル.doc"),
 # 賃料回収マニュアルは「入金確認・催促(keiri-nyukin)」ページに組み込んだため索引の独立ページは廃止
 ("各マンションビル等 契約の流れ","各マンションビル等契約の流れ.docx"),
 ("各マンション 鍵交換について","各マンション鍵交換について.docx"),
 ("各ビル・マンション等 消防点検マニュアル","各ビル・マンション等消防点検マニュアル.docx"),
 ("請求書投函 注意点","請求書投函注意点.docx"),
 ("オートロックNo・メールBOX No","オートロックNoメールBOXNo.docx"),
 ("その他のマニュアル","その他のマニュアル.doc"),
 ("その他マニュアル","その他マニュアル.docx"),
 ("その他マニュアル②","その他マニュアル②.docx"),
 ("その他区分所有物件マニュアル","その他区分所有物件マニュアル.docx"),
]
gen_cards=[]
for i,(label,fn) in enumerate(GENERAL):
    gid="gman-%d"%(i+1)
    manual(gid,BLDG_DEPT,label,"物件横断の共通マニュアル。全文をこのページで読めます。",
           doc_to_blocks(bpath(fn), gid),[L("元ファイル：%s"%fn,bpath(fn))],parent="soumu-buildings")
    gen_cards.append({"id":gid,"label":label})

manual("soumu-buildings","soumu","物件別マニュアル索引",
  "物件ごとの詳細マニュアル（管理内容・業者・鍵など）。カードを選ぶと、ファイルを開かなくてもその場で全文をページとして読めます。",
  [{"type":"sub","text":"物件別マニュアル"},
   {"type":"page_grid","items":bldg_cards},
   {"type":"sub","text":"共通マニュアル（物件横断）"},
   {"type":"page_grid","items":gen_cards}],
  [L("修繕メンテ依頼先一覧.xlsx",bpath("修繕メンテ依頼先一覧.xlsx")),
   L("オーナー連絡先.xlsx",bpath("オーナー連絡先20230415.xlsx")),
   L("物件一覧.xlsx",bpath("物件一覧20220710.xlsx")),
   L("マニュアルフォルダを開く","社内・総務/研修・資料/マニュアル")])

# ---------------- RENDER ----------------
def render_blocks(blocks):
    out=[]
    for b in blocks:
        t=b["type"]
        if t=="sub":
            out.append('<h4 class="sub">%s</h4>'%esc(b["text"]))
        elif t=="note":
            out.append('<div class="note">%s</div>'%esc(b["text"]))
        elif t=="steps":
            out.append('<ol class="steps">')
            for it in b["items"]:
                if isinstance(it,dict):
                    sub="".join('<li>%s</li>'%esc(s) for s in it["sub"])
                    out.append('<li><span class="stx">%s</span><ul class="substeps">%s</ul></li>'%(esc(it["t"]),sub))
                else:
                    out.append('<li><span class="stx">%s</span></li>'%esc(it))
            out.append('</ol>')
        elif t=="table":
            th="".join('<th>%s</th>'%esc(h) for h in b["head"])
            rowlinks=b.get("rowlinks")
            rows=[]
            for i,r in enumerate(b["rows"]):
                cells=[]
                for j,c in enumerate(r):
                    if isinstance(c,dict) and "pre" in c:  # 改行保持セル
                        cells.append('<td class="prewrap">%s</td>'%esc(c["pre"]))
                        continue
                    if isinstance(c,(list,tuple)):  # 複数ファイルリンクのセル
                        if c:
                            chips="".join('<a class="calfile" href="%s">📄 %s</a>'%(href(x["path"]),esc(x["label"])) for x in c)
                        else:
                            chips='<span class="lnote">—</span>'
                        cells.append('<td class="filecell">%s</td>'%chips)
                        continue
                    lk = rowlinks[i] if (rowlinks and j==0 and i<len(rowlinks)) else ""
                    if lk:
                        cells.append('<td><a class="ctgtlink" href="%s">%s</a></td>'%(href(lk),esc(c)))
                    else:
                        cells.append('<td>%s</td>'%esc(c))
                rows.append('<tr>'+''.join(cells)+'</tr>')
            out.append('<div class="tablewrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'%(th,"".join(rows)))
        elif t=="cols":
            items="".join('<li>%s</li>'%esc(x) for x in b["items"])
            out.append('<ul class="cols">%s</ul>'%items)
        elif t=="cal":
            rows=[]
            for r in b["rows"]:
                day,tgt,work,dept,folder,fil = (tuple(r)+("","",""))[:6]
                tgt_html = ('<a class="ctgtlink" href="%s">%s</a>'%(href(folder),esc(tgt))) if folder else esc(tgt)
                fil_html = (' <a class="calfile" href="%s">📄 %s</a>'%(href(fil),esc(fil.split("/")[-1]))) if fil else ''
                rows.append('<tr><td class="cday">%s</td><td class="ctgt">%s</td><td>%s%s</td><td><span class="tag" style="--c:%s">%s</span></td></tr>'%(
                    esc(day),tgt_html,esc(work),fil_html,DEPT_COLOR[dept],esc(DEPT_LABEL[dept])))
            out.append(
              '<div class="caltools" id="caltools">'
              '<button class="cbtn" id="caledit">✏️ 編集する</button>'
              '<button class="cbtn primary" id="calsave" hidden>💾 保存</button>'
              '<button class="cbtn" id="caladd" hidden>＋ 行を追加</button>'
              '<button class="cbtn" id="calcancel" hidden>キャンセル</button>'
              '<button class="cbtn ghost" id="calreset" hidden>↺ 初期状態に戻す</button>'
              '<button class="cbtn ghost" id="calexport" hidden>⧉ generate.py用に書き出し</button>'
              '<span class="calmsg" id="calmsg"></span></div>'
              '<div class="note" id="caledithint" hidden>セルを直接クリックして書き換え、部門はプルダウンで変更、行末の <b>✕</b> で行を削除、<b>＋ 行を追加</b>で行を追加できます。<b>保存</b>すると変更はこのブラウザに残ります（他の人の画面には反映されません）。<b>全員に反映</b>したいときは <b>⧉ generate.py用に書き出し</b> でコピーした内容を <code>generate.py</code> の <code>CAL = […]</code> に貼り替え、メインPCで <code>python3 generate.py</code> を実行してください。</div>'
              '<div class="tablewrap"><table class="cal"><thead><tr><th>日</th><th>対象</th><th>業務内容</th><th>部門</th></tr></thead><tbody id="calbody">%s</tbody></table></div>'%"".join(rows))
        elif t=="links_grid":
            cards=[]
            for l in b["links"]:
                cards.append('<a class="bcard" href="%s">%s</a>'%(href(l["path"]),esc(l["label"])))
            out.append('<div class="bgrid">%s</div>'%"".join(cards))
        elif t=="page_grid":
            cards=[]
            for it in b["items"]:
                sub='<span class="bcsub">%s</span>'%esc(it["sub"]) if it.get("sub") else ""
                cards.append('<a class="bcard bpage" href="#%s"><span class="bct">%s</span>%s</a>'%(
                    esc(it["id"]),esc(it["label"]),sub))
            out.append('<div class="bgrid">%s</div>'%"".join(cards))
        elif t=="prose":
            out.append('<div class="doc">%s</div>'%_para_html(b["paras"]))
        elif t=="doc":
            ps=_para_html(b["paras"])
            did=b.get("docid")
            if did:
                out.append(
                  '<div class="doctools" data-doc="%s">'
                  '<button class="cbtn doc-edit">✏️ このマニュアルを編集</button>'
                  '<button class="cbtn primary doc-save" hidden>💾 保存</button>'
                  '<button class="cbtn doc-cancel" hidden>キャンセル</button>'
                  '<button class="cbtn ghost doc-reset" hidden>↺ 元に戻す</button>'
                  '<button class="cbtn ghost doc-export" hidden>⧉ generate.py用に書き出し</button>'
                  '<span class="calmsg doc-msg"></span></div>'%esc(did))
                out.append('<div class="doc" data-doc="%s">%s</div>'%(esc(did),ps))
            else:
                out.append('<div class="doc">%s</div>'%ps)
    return "".join(out)

def render_links(links):
    if not links: return ""
    items=[]
    for l in links:
        p=l["path"]
        h= p if p.startswith("#") else href(p)
        icon="🔗" if p.startswith("#") else ("📁" if "." not in p.split("/")[-1] else "📄")
        note=' <span class="lnote">%s</span>'%esc(l["note"]) if l.get("note") else ""
        items.append('<li><a href="%s">%s %s</a>%s</li>'%(h,icon,esc(l["label"]),note))
    return '<div class="related"><h4>関連ファイル・フォルダ</h4><ul class="links">%s</ul></div>'%"".join(items)

# manual sections
sections=[]
# 手順書ページ（whole-page contenteditable編集の対象）
# … カレンダー(cal)・全文ページ(doc＝独自のテキスト編集あり)・索引(page_grid)は除外
_NOEDIT={"cal","doc","page_grid"}
def page_editable(m):
    return not any(b.get("type") in _NOEDIT for b in m["blocks"])

for m in M:
    c=DEPT_COLOR[m["dept"]]
    mid=m["id"]
    if mid in HTML_OVERRIDES:
        inner=HTML_OVERRIDES[mid]
    else:
        inner=render_blocks(m["blocks"])+render_links(m["links"])
    if page_editable(m):
        toolbar=(
          '<div class="pagetools" data-page="%s">'
          '<button class="cbtn page-edit">✏️ このページを編集</button>'
          '<button class="cbtn primary page-save" hidden>💾 保存</button>'
          '<button class="cbtn page-cancel" hidden>キャンセル</button>'
          '<button class="cbtn ghost page-reset" hidden>↺ 元に戻す</button>'
          '<button class="cbtn ghost page-export" hidden>⧉ generate.py用に書き出し</button>'
          '<span class="calmsg page-msg"></span></div>'%esc(mid))
        body=toolbar+'<div class="mbody" data-page="%s">%s</div>'%(esc(mid),inner)
    else:
        body=inner
    parent=m.get("parent")
    back_href="#"+parent if parent else "#home"
    back_label="← 索引へ戻る" if parent else "← 一覧へ"
    sections.append(
      '<section class="manual" id="%s" data-dept="%s" style="--c:%s">'
      '<div class="mtop"><a class="back" href="%s">%s</a>'
      '<button class="print" onclick="window.print()">🖨 印刷</button></div>'
      '<div class="mhd"><span class="mdept">%s</span><h2>%s</h2><p class="lead">%s</p></div>'
      '%s</section>'%(mid,m["dept"],c,back_href,back_label,esc(DEPT_LABEL[m["dept"]]),esc(m["title"]),esc(m["lead"]),body))

# home: dept groups with cards
home_groups=[]
for key,label,icon,color,folder in DEPTS:
    cards=[]
    for m in M:
        if m["dept"]!=key: continue
        badge=' <span class="taglet">台帳</span>' if m["title"].startswith("【台帳】") else ""
        ttl=m["title"].replace("【台帳】","")
        cards.append('<a class="card" href="#%s"><span class="ct">%s%s</span><span class="cl">%s</span></a>'%(m["id"],esc(ttl),badge,esc(m["lead"])))
    folder_btn=('<a class="folderlink" href="%s">📁 %sフォルダを開く</a>'%(href(folder),esc(label))) if folder else ""
    home_groups.append(
      '<div class="deptgroup" data-dept="%s" style="--c:%s">'
      '<div class="depthd"><span class="dicon">%s</span><h3>%s</h3>%s</div>'
      '<div class="cards">%s</div></div>'%(key,color,icon,esc(label),folder_btn,"".join(cards)))

CSS = r"""
:root{--bg:#f6f7f9;--card:#fff;--tx:#1f2430;--mut:#6b7280;--line:#e5e7eb;--accent:#6366f1;--shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04)}
@media(prefers-color-scheme:dark){:root{--bg:#0f1319;--card:#171c26;--tx:#e6e9ef;--mut:#9aa4b2;--line:#262d3a;--shadow:0 1px 3px rgba(0,0,0,.4)}}
:root[data-theme=dark]{--bg:#0f1319;--card:#171c26;--tx:#e6e9ef;--mut:#9aa4b2;--line:#262d3a;--shadow:0 1px 3px rgba(0,0,0,.4)}
:root[data-theme=light]{--bg:#f6f7f9;--card:#fff;--tx:#1f2430;--mut:#6b7280;--line:#e5e7eb;--shadow:0 1px 3px rgba(0,0,0,.06)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,"Hiragino Sans","Hiragino Kaku Gothic ProN",Meiryo,sans-serif;line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:0 20px 80px}
header.top{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.topin{max-width:960px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:14px}
.logo{font-weight:800;font-size:17px;letter-spacing:.02em;white-space:nowrap}
.logo small{display:block;font-weight:500;font-size:11px;color:var(--mut);letter-spacing:.15em}
#search{margin-left:auto;flex:1;max-width:340px;padding:9px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--tx);font-size:14px}
#search:focus{outline:none;border-color:var(--accent)}
.themebtn{border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:9px;padding:8px 10px;cursor:pointer;font-size:15px}
.hero{padding:34px 0 8px}
.hero h1{font-size:26px;margin:0 0 8px;letter-spacing:.01em}
.hero p{color:var(--mut);margin:0;font-size:15px}
.deptgroup{margin-top:30px;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow);overflow:hidden}
.depthd{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--line);border-left:5px solid var(--c)}
.depthd h3{margin:0;font-size:17px}
.dicon{font-size:22px}
.folderlink{margin-left:auto;font-size:12.5px;color:var(--mut);text-decoration:none;border:1px solid var(--line);padding:6px 10px;border-radius:8px;white-space:nowrap}
.folderlink:hover{border-color:var(--c);color:var(--tx)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;padding:16px 20px}
.card{display:flex;flex-direction:column;gap:5px;padding:14px 15px;border:1px solid var(--line);border-radius:12px;text-decoration:none;color:inherit;background:var(--bg);transition:.15s}
.card:hover{border-color:var(--c);transform:translateY(-2px);box-shadow:var(--shadow)}
.ct{font-weight:700;font-size:14.5px}
.cl{font-size:12px;color:var(--mut);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.taglet{font-size:10px;background:var(--c);color:#fff;padding:1px 6px;border-radius:5px;vertical-align:middle;font-weight:700}
.manual{display:none;margin-top:22px;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow);padding:0 26px 30px;border-top:4px solid var(--c)}
.manual:target{display:block}
body.showhome .manual{display:none}
body:not(.showhome) #homehero{display:none}
.mtop{display:flex;align-items:center;gap:10px;padding:16px 0;position:sticky;top:58px;background:var(--card);z-index:5}
.back{text-decoration:none;color:var(--mut);font-size:14px;font-weight:600}
.back:hover{color:var(--tx)}
.print{margin-left:auto;border:1px solid var(--line);background:var(--bg);color:var(--tx);border-radius:8px;padding:7px 12px;cursor:pointer;font-size:13px}
.mhd{padding-bottom:6px;border-bottom:1px solid var(--line);margin-bottom:18px}
.mdept{font-size:12px;font-weight:700;color:var(--c);letter-spacing:.08em}
.mhd h2{margin:4px 0 6px;font-size:22px}
.lead{color:var(--mut);margin:0;font-size:14px}
h4.sub{margin:22px 0 4px;font-size:15px;color:var(--c)}
ol.steps{counter-reset:s;list-style:none;padding:0;margin:6px 0}
ol.steps>li{counter-increment:s;position:relative;padding:12px 12px 12px 46px;border-bottom:1px solid var(--line)}
ol.steps>li:before{content:counter(s);position:absolute;left:10px;top:11px;width:26px;height:26px;background:var(--c);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700}
.stx{font-weight:600}
ul.substeps{margin:6px 0 0;padding-left:18px}
ul.substeps li{color:var(--mut);font-size:13.5px;list-style:disc;margin:2px 0;font-weight:400}
.note{background:color-mix(in srgb,var(--c) 8%,var(--card));border:1px solid color-mix(in srgb,var(--c) 25%,var(--line));border-left:4px solid var(--c);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:13.5px}
.tablewrap{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:520px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line)}
th{background:var(--bg);font-size:12px;color:var(--mut);position:sticky;top:0}
tbody tr:hover{background:var(--bg)}
.cal .cday{font-weight:700;white-space:nowrap;color:var(--c)}
.cal .ctgt{font-size:12px;color:var(--mut)}
.tag{font-size:11px;font-weight:700;color:#fff;background:var(--c);padding:2px 8px;border-radius:6px;white-space:nowrap}
ul.cols{columns:2;-webkit-columns:2;list-style:none;padding:0;margin:8px 0;gap:20px}
ul.cols li{padding:6px 0 6px 18px;position:relative;font-size:13.5px;break-inside:avoid}
ul.cols li:before{content:"•";position:absolute;left:0;color:var(--c)}
.related{margin-top:24px;padding-top:16px;border-top:1px dashed var(--line)}
.related h4{margin:0 0 8px;font-size:13px;color:var(--mut)}
ul.links{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:6px}
ul.links a{text-decoration:none;color:var(--tx);font-size:13px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;display:block;background:var(--bg)}
ul.links a:hover{border-color:var(--c)}
.lnote{color:var(--mut);font-size:11px}
.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin:10px 0}
.bcard{text-decoration:none;color:var(--tx);font-size:13px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;background:var(--bg)}
.bcard:hover{border-color:var(--c)}
.bcard.bpage{display:flex;flex-direction:column;gap:3px;padding:12px 14px;transition:.15s}
.bcard.bpage:hover{transform:translateY(-2px);box-shadow:var(--shadow)}
.bct{font-weight:700;font-size:14px}
.bcsub{font-size:11px;color:var(--mut)}
.pagetools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:2px 0 4px}
.mbody[contenteditable=true]{outline:2px dashed color-mix(in srgb,var(--c) 45%,var(--line));outline-offset:8px;border-radius:8px;background:color-mix(in srgb,var(--c) 4%,var(--card))}
.mbody[contenteditable=true] *{cursor:text}
.doctools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:14px 0 6px}
.doc-edit-area{width:100%;min-height:360px;font:14px/1.85 -apple-system,"Hiragino Sans","Hiragino Kaku Gothic ProN",Meiryo,sans-serif;padding:14px 16px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--tx);white-space:pre-wrap;resize:vertical}
.doc-edit-area:focus{outline:2px solid var(--c);border-color:var(--c)}
.doc-editing{outline:2px dashed color-mix(in srgb,var(--c) 40%,var(--line));outline-offset:6px;border-radius:8px}
.doc{margin:6px 0 2px}
.doc .docpara{white-space:pre-wrap;word-break:break-word;margin:0 0 13px;font-size:14px;line-height:1.85}
.doc .dochead{white-space:pre-wrap;word-break:break-word;margin:22px 0 6px;font-weight:700;font-size:15px;color:var(--c);padding-bottom:4px;border-bottom:1px solid color-mix(in srgb,var(--c) 25%,var(--line))}
.doc .dochead:first-child{margin-top:4px}
.nores{display:none;color:var(--mut);padding:30px;text-align:center}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--mut);font-size:12px;text-align:center}
.caltools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:16px 0 2px}
.cbtn{border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:8px;padding:7px 13px;cursor:pointer;font-size:13px;font-weight:600}
.cbtn:hover{border-color:var(--c)}
.cbtn.primary{background:var(--c);color:#fff;border-color:var(--c)}
.cbtn.ghost{color:var(--mut);font-weight:500}
.calmsg{font-size:12.5px;color:var(--c);font-weight:600}
.ctgtlink{color:var(--c);text-decoration:none;border-bottom:1px dotted color-mix(in srgb,var(--c) 50%,var(--line))}
.ctgtlink:hover{border-bottom-style:solid}
.calfile{display:inline-block;margin-top:3px;font-size:11.5px;color:var(--c);text-decoration:none;border:1px solid color-mix(in srgb,var(--c) 30%,var(--line));border-radius:6px;padding:1px 7px;white-space:nowrap;background:color-mix(in srgb,var(--c) 6%,var(--card))}
.calfile:hover{border-color:var(--c)}
.filecell{white-space:normal;min-width:180px}
.filecell .calfile{display:inline-block;margin:2px 4px 2px 0}
td.prewrap{white-space:pre-wrap;word-break:break-word;min-width:240px;line-height:1.6}
.e-fil{margin-top:5px;width:100%;font-size:11px;padding:3px 6px;border:1px solid var(--line);border-radius:5px;background:var(--card);color:var(--mut)}
.cal .e-day,.cal .e-tgt,.cal .e-work{outline:1px dashed color-mix(in srgb,var(--c) 40%,var(--line));background:color-mix(in srgb,var(--c) 6%,var(--card));border-radius:5px;padding:3px 6px;min-height:1.4em;cursor:text}
.cal .e-day:focus,.cal .e-tgt:focus,.cal .e-work:focus{outline:2px solid var(--c);background:var(--card)}
.e-fol{margin-top:5px;width:100%;font-size:11px;padding:3px 6px;border:1px solid var(--line);border-radius:5px;background:var(--card);color:var(--mut)}
.deptsel{font-size:12px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--tx)}
.delrow{margin-left:6px;border:none;background:transparent;color:#e05252;cursor:pointer;font-size:14px;line-height:1}
.cal tr.editing td{vertical-align:top}
@media(max-width:600px){ul.cols{columns:1}.cards{grid-template-columns:1fr}.hero h1{font-size:22px}}
@media print{header.top,.mtop,.folderlink,footer,.caltools,#caledithint,.doctools,.pagetools{display:none!important}.manual{display:block!important;border:none;box-shadow:none;padding:0}body.showhome .manual{display:block!important}.deptgroup{display:none}}
"""

JS = r"""
const body=document.body;
function route(){
  const h=location.hash.replace('#','');
  if(!h||h==='home'){body.classList.add('showhome');window.scrollTo(0,0);}
  else{body.classList.remove('showhome');const el=document.getElementById(h);if(el){window.scrollTo(0,0);}}
}
window.addEventListener('hashchange',route);route();
// search filter on home
const s=document.getElementById('search');
s.addEventListener('input',()=>{
  const q=s.value.trim().toLowerCase();
  if(q&&location.hash&&location.hash!=='#home'){location.hash='home';}
  let any=false;
  document.querySelectorAll('.deptgroup').forEach(g=>{
    let vis=0;
    g.querySelectorAll('.card').forEach(c=>{
      const m=c.textContent.toLowerCase().includes(q);
      c.style.display=m?'':'none';if(m)vis++;
    });
    g.style.display=(vis||!q)?'':'none';if(vis)any=true;
  });
  document.getElementById('nores').style.display=(q&&!any)?'block':'none';
});
// theme toggle
const tb=document.getElementById('theme');
tb.addEventListener('click',()=>{
  const cur=document.documentElement.getAttribute('data-theme');
  const dark=cur? cur==='dark' : window.matchMedia('(prefers-color-scheme:dark)').matches;
  document.documentElement.setAttribute('data-theme',dark?'light':'dark');
  tb.textContent=dark?'☀️':'🌙';
});
// ---- editable business calendar ----
(function(){
  const DEPTS=window.__DEPTS__||{}, DEF=window.__CAL__||[], KEY='dk_cal_v1';
  const body=document.getElementById('calbody'); if(!body) return;
  const $=id=>document.getElementById(id);
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const encPath=p=>String(p).split('/').map(encodeURIComponent).join('/');
  const firstDept=Object.keys(DEPTS)[0]||'keiri';
  function load(){try{const s=localStorage.getItem(KEY);if(s)return JSON.parse(s);}catch(e){}return DEF.map(r=>r.slice());}
  let data=load(), editing=false;
  function tag(d){const x=DEPTS[d]||DEPTS[firstDept];return '<span class="tag" style="--c:'+x.color+'">'+esc(x.label)+'</span>';}
  function sel(d){let o='';for(const k in DEPTS){o+='<option value="'+k+'"'+(k===d?' selected':'')+'>'+esc(DEPTS[k].label)+'</option>';}return '<select class="deptsel">'+o+'</select>';}
  function tgtCell(name,folder){return folder?('<a class="ctgtlink" href="'+encPath(folder)+'">'+esc(name)+'</a>'):esc(name);}
  function fileChip(f){return f?(' <a class="calfile" href="'+encPath(f)+'">📄 '+esc(f.split('/').pop())+'</a>'):'';}
  function render(){
    body.innerHTML=data.map(function(r){
      if(editing){
        return '<tr class="editing">'+
          '<td><div class="e-day" contenteditable>'+esc(r[0])+'</div></td>'+
          '<td><div class="e-tgt" contenteditable>'+esc(r[1])+'</div><input class="e-fol" value="'+esc(r[4]||'')+'" placeholder="📁 フォルダ相対パス（任意）"></td>'+
          '<td><div class="e-work" contenteditable>'+esc(r[2])+'</div><input class="e-fil" value="'+esc(r[5]||'')+'" placeholder="📄 関連ファイル/サブフォルダ 相対パス（任意）"></td>'+
          '<td class="deptcell">'+sel(r[3])+'<button class="delrow" title="この行を削除">✕</button></td></tr>';
      }
      return '<tr><td class="cday">'+esc(r[0])+'</td><td class="ctgt">'+tgtCell(r[1],r[4]||'')+'</td><td>'+esc(r[2])+fileChip(r[5]||'')+'</td><td>'+tag(r[3])+'</td></tr>';
    }).join('');
  }
  function collect(){
    return [].slice.call(body.querySelectorAll('tr')).map(function(tr){
      const day=tr.querySelector('.e-day'), name=tr.querySelector('.e-tgt'), work=tr.querySelector('.e-work'),
            fol=tr.querySelector('.e-fol'), fil=tr.querySelector('.e-fil'), s=tr.querySelector('.deptsel');
      return [day?day.textContent.trim():'', name?name.textContent.trim():'', work?work.textContent.trim():'',
              s?s.value:firstDept, fol?fol.value.trim():'', fil?fil.value.trim():''];
    });
  }
  function msg(m){const el=$('calmsg');el.textContent=m;if(m)setTimeout(function(){if(el.textContent===m)el.textContent='';},2800);}
  function setMode(e){editing=e;
    ['calsave','caladd','calcancel','calreset','calexport'].forEach(function(i){$(i).hidden=!e;});
    $('caledit').hidden=e; $('caledithint').hidden=!e; render();
  }
  $('caledit').onclick=function(){setMode(true);};
  $('calcancel').onclick=function(){data=load();setMode(false);msg('変更を取り消しました');};
  $('calsave').onclick=function(){data=collect();try{localStorage.setItem(KEY,JSON.stringify(data));}catch(e){}setMode(false);msg('✓ 保存しました（このブラウザ内）');};
  $('caladd').onclick=function(){data=collect();data.push(['','','',firstDept,'','']);render();};
  $('calreset').onclick=function(){if(!confirm('編集内容を破棄して、初期状態（配布時の内容）に戻しますか？'))return;try{localStorage.removeItem(KEY);}catch(e){}data=DEF.map(r=>r.slice());render();msg('初期状態に戻しました');};
  body.addEventListener('click',function(ev){
    if(ev.target.classList.contains('delrow')){
      const rows=[].slice.call(body.querySelectorAll('tr')), i=rows.indexOf(ev.target.closest('tr'));
      data=collect(); data.splice(i,1); render();
    }
  });
  $('calexport').onclick=function(){
    const cur=editing?collect():data;
    const py='CAL = [\n'+cur.map(function(r){return ' ('+[0,1,2,3,4,5].map(function(j){return JSON.stringify(String(r[j]!=null?r[j]:''));}).join(',')+'),';}).join('\n')+'\n]';
    function done(){msg('✓ generate.py用の CAL をコピーしました');}
    function fallback(t){const ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');done();}catch(e){msg('コピーに失敗しました');}ta.remove();}
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(py).then(done,function(){fallback(py);});}else fallback(py);
  };
  // reflect previously-saved edits on load
  try{if(localStorage.getItem(KEY))render();}catch(e){}
})();
// ---- editable manual doc pages (物件別・共通マニュアル) ----
(function(){
  const DKEY='dk_doc_v1_';
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function isHead(p){
    if(/^[\s　]*[《【〔■◆●○▼◎]/.test(p)) return true;
    if(p.indexOf("\n")===-1 && p.length<=24 && (/について$/.test(p)||/マニュアル$/.test(p)||/業者$/.test(p))) return true;
    return false;
  }
  // display:none でも取れるよう textContent で原文を復元（各段落divは原文の改行をそのまま保持）
  function domToSource(d){
    return [].slice.call(d.children).map(function(c){return c.textContent;}).join("\n\n").replace(/\n{3,}/g,"\n\n").trim();
  }
  function renderDoc(d,text){
    const paras=text.replace(/\r\n/g,"\n").split(/\n[ \t　]*\n/);
    d.innerHTML=paras.filter(function(p){return p.trim()!=="";}).map(function(p){
      return '<div class="'+(isHead(p)?'dochead':'docpara')+'">'+esc(p)+'</div>';
    }).join("");
  }
  const DEF={};
  document.querySelectorAll('.doc[data-doc]').forEach(function(d){
    const id=d.getAttribute('data-doc'); DEF[id]=domToSource(d);
    let saved=null; try{saved=localStorage.getItem(DKEY+id);}catch(e){}
    if(saved!=null) renderDoc(d,saved);
  });
  function cur(id){let s=null;try{s=localStorage.getItem(DKEY+id);}catch(e){}return s!=null?s:(DEF[id]||'');}
  document.querySelectorAll('.doctools[data-doc]').forEach(function(bar){
    const id=bar.getAttribute('data-doc');
    const doc=document.querySelector('.doc[data-doc="'+id+'"]'); if(!doc) return;
    const btn=function(n){return bar.querySelector('.doc-'+n);};
    const msgEl=bar.querySelector('.doc-msg');
    function msg(m){msgEl.textContent=m;if(m)setTimeout(function(){if(msgEl.textContent===m)msgEl.textContent='';},2800);}
    function setMode(on){['save','cancel','reset','export'].forEach(function(n){btn(n).hidden=!on;});btn('edit').hidden=on;}
    let ta=null;
    btn('edit').onclick=function(){
      ta=document.createElement('textarea');ta.className='doc-edit-area';ta.value=cur(id);
      doc.innerHTML='';doc.appendChild(ta);doc.classList.add('doc-editing');ta.focus();setMode(true);
    };
    function leave(text){doc.classList.remove('doc-editing');renderDoc(doc,text);ta=null;setMode(false);}
    btn('cancel').onclick=function(){leave(cur(id));msg('変更を取り消しました');};
    btn('save').onclick=function(){const v=ta.value;try{localStorage.setItem(DKEY+id,v);}catch(e){}leave(v);msg('✓ 保存しました（このブラウザ内）');};
    btn('reset').onclick=function(){
      if(!confirm('編集内容を破棄して、配布時の内容に戻しますか？'))return;
      try{localStorage.removeItem(DKEY+id);}catch(e){}leave(DEF[id]||'');msg('配布時の内容に戻しました');
    };
    btn('export').onclick=function(){
      const v=ta?ta.value:cur(id);
      const Q3=String.fromCharCode(34,34,34);
      const py='OVERRIDES["'+id+'"] = r'+Q3+'\n'+v.replace(new RegExp(Q3,'g'),'”””')+'\n'+Q3;
      function done(){msg('✓ generate.py用のコードをコピーしました');}
      function fb(t){const x=document.createElement('textarea');x.value=t;document.body.appendChild(x);x.select();try{document.execCommand('copy');done();}catch(e){msg('コピーに失敗しました');}x.remove();}
      if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(py).then(done,function(){fb(py);});}else fb(py);
    };
  });
})();
// ---- editable structured pages (手順書ページ 本文まるごと編集) ----
(function(){
  const PKEY='dk_page_v2_';
  const Q3=String.fromCharCode(34,34,34);
  const DEF={};
  document.querySelectorAll('.mbody[data-page]').forEach(function(b){
    const id=b.getAttribute('data-page'); DEF[id]=b.innerHTML;
    let saved=null; try{saved=localStorage.getItem(PKEY+id);}catch(e){}
    if(saved!=null) b.innerHTML=saved;
  });
  document.querySelectorAll('.pagetools[data-page]').forEach(function(bar){
    const id=bar.getAttribute('data-page');
    const b=document.querySelector('.mbody[data-page="'+id+'"]'); if(!b) return;
    const btn=function(n){return bar.querySelector('.page-'+n);};
    const msgEl=bar.querySelector('.page-msg');
    function msg(m){msgEl.textContent=m;if(m)setTimeout(function(){if(msgEl.textContent===m)msgEl.textContent='';},2800);}
    function setMode(on){['save','cancel','reset','export'].forEach(function(n){btn(n).hidden=!on;});btn('edit').hidden=on;}
    function stored(){let s=null;try{s=localStorage.getItem(PKEY+id);}catch(e){}return s!=null?s:DEF[id];}
    btn('edit').onclick=function(){b.setAttribute('contenteditable','true');b.focus();setMode(true);msg('テキストを直接書き換えできます');};
    function leave(){b.removeAttribute('contenteditable');setMode(false);}
    btn('cancel').onclick=function(){b.innerHTML=stored();leave();msg('変更を取り消しました');};
    btn('save').onclick=function(){try{localStorage.setItem(PKEY+id,b.innerHTML);}catch(e){}leave();msg('✓ 保存しました（このブラウザ内）');};
    btn('reset').onclick=function(){
      if(!confirm('編集内容を破棄して、配布時の内容に戻しますか？'))return;
      try{localStorage.removeItem(PKEY+id);}catch(e){}b.innerHTML=DEF[id];leave();msg('配布時の内容に戻しました');
    };
    btn('export').onclick=function(){
      const py='HTML_OVERRIDES["'+id+'"] = r'+Q3+'\n'+b.innerHTML.replace(new RegExp(Q3,'g'),'”””')+'\n'+Q3;
      function done(){msg('✓ generate.py用のコードをコピーしました');}
      function fb(t){const x=document.createElement('textarea');x.value=t;document.body.appendChild(x);x.select();try{document.execCommand('copy');done();}catch(e){msg('コピーに失敗しました');}x.remove();}
      if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(py).then(done,function(){fb(py);});}else fb(py);
    };
  });
})();
"""

DEPTS_JSON = json.dumps({d[0]: {"label": d[1], "color": d[3]} for d in DEPTS}, ensure_ascii=False)
CAL_JSON   = json.dumps([list((tuple(r)+("","",""))[:6]) for r in CAL], ensure_ascii=False)

HTML = (
'<!doctype html>\n<html lang="ja">\n<head>\n'
'<meta charset="utf-8">\n'
'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
'<title>大京商事 業務マニュアル</title>\n'
'<style>%s</style>\n</head>\n<body class="showhome">\n'
'<header class="top"><div class="topin">'
'<div class="logo">大京商事 業務マニュアル<small>MANUAL</small></div>'
'<input id="search" placeholder="🔍 マニュアルを検索（例：請求書 / 鍵 / 保険）">'
'<button class="themebtn" id="theme">🌙</button>'
'</div></header>'
'<div class="wrap">'
'<div id="homehero"><div class="hero"><h1>業務マニュアル</h1>'
'<p>部門を選んで、それぞれの業務手順を確認できます。各手順書には共有フォルダの様式・台帳への直接リンク付き。まず「1ヶ月の業務カレンダー」で全体像を掴み、担当業務の詳細へ進んでください。</p></div>'
'%s'
'<div class="nores" id="nores">該当するマニュアルがありません</div></div>'
'%s'
'<footer>大京商事株式会社 — 「1ヵ月の業務の流れ・引き継ぎ.xls」＋全ファイル一覧 をもとに再構成 / 期限・日付は要最新化</footer>'
'</div>'
'<script>window.__DEPTS__=%s;window.__CAL__=%s;</script>\n'
'<script>%s</script>\n</body>\n</html>'
) % (CSS, "".join(home_groups), "".join(sections), DEPTS_JSON, CAL_JSON, JS)

with io.open(OUT,"w",encoding="utf-8") as f:
    f.write(HTML)
print("WROTE:",OUT)
print("manuals:",len(M),"bytes:",len(HTML))
