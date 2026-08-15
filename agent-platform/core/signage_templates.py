"""掲示物の型（貼り紙・案内表示）

なぜ型を分けるか:
  掲示物はひとくくりに見えて、実は**目的が3つに割れている**。
    禁止（やめさせる）／お知らせ（日時を伝える）／お願い（協力を仰ぐ）／案内（誘導する）
  目的が違えば、強さも配色も並びも変わる。禁止の様式でお願いを書くと威圧的になり、
  お願いの様式で禁止を書くと誰も守らない。1つの型で全部やろうとすると必ずどちらかが崩れる。

作りの方針:
  紙面は**固定**（LLMにレイアウトを触らせない）。差し替えるのは文言だけ。
  掲示物は様式がほぼ決まっており、崩れないことの価値が創意より大きい。

配色:
  禁止=赤 / 注意・工事=橙 / お願い=紺 / 案内=緑。
  日本の掲示物の慣習に合わせてある（赤は「してはいけない」の色）。
"""
from __future__ import annotations

from typing import Any, Dict, List

# 共通のCSS土台。型ごとに違うのは「並び」と「色」だけにする
BASE_CSS = """
{fontface}
@page{{margin:0}} *{{box-sizing:border-box}}
body{{margin:0;width:{pw}mm;height:{ph}mm;font-family:{fontstack};color:#15181d;
 background:#fff;display:flex;flex-direction:column;position:relative}}

/* --- 紙面の作り ---------------------------------------------------------
   平らな色帯に文字を置いただけだと「印刷物」に見えない。
   実際の掲示物は ①内枠の罫 ②見出し帯の下の細いライン ③地の薄い色
   ④締めの濃い帯 で構成されている。この4つで紙面が締まる。 */

/* ① 内枠。紙の縁から6mm内側に細い罫を回す。掲示物らしさはここで出る */
body::before{{content:"";position:absolute;top:{frame}mm;left:{frame}mm;
 right:{frame}mm;bottom:{frame}mm;
 border:0.4mm solid {accent};opacity:.28;pointer-events:none;z-index:5}}

/* ② 見出し帯。下に濃い細ラインを重ねて、帯の縁を立てる */
/* 帯は縮ませない。紙が低いとき（A4横など）flexが帯を潰し、見出しが帯からはみ出て
   切れる（チラシでも同じ事故があった）。高さは中身に決めさせる */
.band, .foot{{flex:0 0 auto}}
.band{{position:relative;background:{accent};color:#fff;
 padding:{bandpad}mm {sidepad}mm {bandpad2}mm;text-align:center;overflow:hidden}}
.band::after{{content:"";position:absolute;left:0;right:0;bottom:0;height:2.2mm;
 background:rgba(0,0,0,.28)}}
/* 帯の右上に薄い斜めの面を敷く。無地の帯より奥行きが出る */
.band::before{{content:"";position:absolute;top:-30mm;right:-30mm;width:110mm;
 height:110mm;background:rgba(255,255,255,.07);transform:rotate(35deg)}}
.band h1{{position:relative;margin:0;font-size:{h1}pt;font-weight:900;line-height:1.05;
 letter-spacing:{ls}em;text-indent:{ls}em;word-break:auto-phrase;text-wrap:balance}}
.band .en{{position:relative;margin-top:5mm;font-size:{sub}pt;letter-spacing:.28em;
 opacity:.92;font-weight:700}}
/* 見出しの上に置く小見出し（「重要」「管理者より」など）。枠付きで小さく */
.band .kicker{{position:relative;display:inline-block;font-size:11pt;font-weight:700;
 letter-spacing:.24em;border:0.5mm solid rgba(255,255,255,.75);border-radius:1mm;
 padding:1.4mm 4mm 1.2mm;margin-bottom:5mm}}

.main{{flex:1;display:flex;flex-direction:column;align-items:center;
 justify-content:center;padding:{mainpad}mm {sidepad}mm {mainpad2}mm;position:relative}}
/* 幅の広い紙（A3横など）で、1行が長くなりすぎないよう中身に上限を置く。
   1行が長い掲示物は、離れて読むときに目が戻れない */
.main > *{{max-width:{maxw}mm;width:100%}}
.pict{{display:flex;gap:{pictgap}mm;align-items:center;justify-content:center;
 margin-bottom:{pictmb}mm}}
.pict svg, .pict img{{max-height:{pictoh}mm;width:auto}}

/* ③ 一番言いたい一行。上下に細い罫を入れて、本文と役割を分ける */
.lead{{font-size:{msg}pt;font-weight:900;color:{accent};text-align:center;line-height:1.4;
 word-break:auto-phrase;text-wrap:balance;line-break:strict;
 padding:5mm 0;border-top:0.5mm solid {accent};border-bottom:0.5mm solid {accent}}}
.reason{{margin-top:6mm;font-size:{note}pt;text-align:center;color:#3f464f;line-height:1.9;
 word-break:auto-phrase;line-break:strict}}

/* 対応の流れ。地を薄い色にして、丸番号は白抜きで抜く */
.flow{{margin-top:{pictmb}mm;width:100%;background:#f4f6f9;border-radius:3mm;
 border:0.4mm solid #dde2e8;padding:{flowpad}mm 6mm {flowpad2}mm}}
.flow .cap{{text-align:center;font-size:{capf}pt;font-weight:700;color:{accent};
 letter-spacing:.16em;margin-bottom:5mm}}
.steps{{display:flex;align-items:flex-start;justify-content:space-between}}
.step{{flex:1;text-align:center;position:relative;padding:0 3mm}}
.step .n{{display:inline-block;width:{stepn}mm;height:{stepn}mm;line-height:{stepn}mm;
 border-radius:50%;background:{accent};color:#fff;font-size:{stepnf}pt;font-weight:900}}
.step .t{{margin-top:3mm;font-size:{steptf}pt;font-weight:700;line-height:1.5;
 word-break:auto-phrase}}
.step:not(:last-child):after{{content:"";position:absolute;right:-2mm;top:5mm;
 width:0;height:0;border-left:3.5mm solid #b9bec6;
 border-top:2.4mm solid transparent;border-bottom:2.4mm solid transparent}}

/* ④ 締めの帯。白地に罫線一本だと紙面が終わらない。濃い面で受け止める */
.foot{{background:#1c2530;color:#fff;
 padding:{footpad}mm {sidepad}mm {footpad2}mm;position:relative}}
.foot::before{{content:"";position:absolute;left:0;right:0;top:0;height:1.6mm;
 background:{accent}}}
.owner{{font-size:13pt;line-height:2.2;color:#e8ecf1}}
.owner b{{font-size:15pt;font-weight:900;color:#fff}}
.blank{{display:inline-block;border-bottom:1px solid rgba(255,255,255,.55);min-width:44mm}}
.multi{{margin-top:4mm;font-size:11pt;color:rgba(255,255,255,.65);text-align:center;
 letter-spacing:.06em}}

/* --- 横向きの組み ---------------------------------------------------------
   横長の紙で縦組みをそのまま縮めると、左右が余って中央に細く積まれるだけになる。
   横は**左に見せるもの、右に読ませるもの**と役割で分けると紙面が埋まる。 */
.split{{display:flex;align-items:center;gap:{splitgap}mm;width:100%;max-width:100%}}
.split > .l{{flex:0 0 40%;display:flex;flex-direction:column;align-items:center}}
.split > .r{{flex:1;min-width:0}}
.split .lead{{text-align:left}}
/* 横は囲みの幅が半分になる。級数を落とさないと日付が3行に割れる */
.split .period{{font-size:{periodwide}pt;padding:6mm 5mm}}
.split .reason{{text-align:left;margin-top:4mm}}
/* 横は左半分がまるごと空くので、記号は縦のときより大きく取れる */
.split .pict{{margin-bottom:0}}
.split .l .pict svg, .split .l .pict img{{max-height:{pictowide}mm}}
.split .flow{{margin-top:5mm}}
.main > .split{{max-width:100%}}
/* 横の案内表示は矢印と行き先を横に並べる（縦に積むと文字が小さくなる） */
.split .arrow{{margin-bottom:0}}
.split .dest{{text-align:left;margin-top:0}}
.split .dist{{text-align:left}}

/* お知らせ型: 日時・場所を表で。掲示物で一番読まれるのはここなので、
   見出し列は色ベタ、行は薄いしま模様にして目が滑らないようにする */
.infotable{{width:100%;border-collapse:collapse;margin:8mm 0 4mm;font-size:19pt;
 border:0.5mm solid {accent}}}
.infotable th{{background:{accent};color:#fff;text-align:center;padding:6mm 4mm;
 width:36mm;font-weight:700;white-space:nowrap;border-bottom:1px solid rgba(255,255,255,.35)}}
.infotable td{{padding:6mm;border-bottom:1px solid #dde2e8;font-weight:700;
 line-height:1.45;background:#fff}}
.infotable tr:nth-child(even) td{{background:#f7f9fb}}

/* お願い型: 命令ではなく依頼。角を丸め、左に色の太い罫、番号は振らない */
.cards{{display:flex;flex-direction:column;gap:4mm;width:100%;margin-top:6mm}}
.card{{background:#f5f7fa;border:0.4mm solid #e0e5eb;border-left:3.5mm solid {accent};
 border-radius:2mm;padding:5.5mm 7mm;font-size:18pt;font-weight:700;line-height:1.6}}
.thanks{{margin-top:7mm;font-size:14pt;color:#4a5058;text-align:center;
 letter-spacing:.06em}}

/* 案内型: 矢印と行き先だけ。文字の「→」は細くて遠くから見えないので図形で描く */
.arrow{{text-align:center;margin-bottom:7mm}}
.arrow svg{{width:{arroww}mm;height:{arrowh}mm}}
.dest{{font-size:{dest}pt;font-weight:900;text-align:center;line-height:1.25;
 word-break:auto-phrase;text-wrap:balance;margin-top:4mm}}
.dist{{font-size:19pt;text-align:center;color:#4a5058;margin-top:6mm;
 letter-spacing:.05em}}

/* 休業型: 期間が主役。囲みを二重罫にして「ここだけ見れば足りる」ようにする */
.period{{font-size:40pt;font-weight:900;color:{accent};text-align:center;line-height:1.3;
 border:1.2mm solid {accent};outline:0.4mm solid {accent};outline-offset:1.8mm;
 border-radius:2mm;padding:8mm 9mm;margin-bottom:7mm;background:#fff;
 word-break:auto-phrase;text-wrap:balance}}

/* 料金表・営業時間 */
.pricelist{{width:100%;border-collapse:collapse;font-size:19pt;margin:6mm 0 3mm}}
.pricelist td{{padding:4.5mm 4mm;border-bottom:1px dashed #c8cfd6;font-weight:700}}
.pricelist td:last-child{{text-align:right;color:{accent};font-size:22pt;
 white-space:nowrap}}
.hours{{font-size:20pt;font-weight:900;text-align:center;margin-top:5mm;
 letter-spacing:.06em}}

/* 募集 */
.recruit{{width:100%;border-collapse:collapse;font-size:17pt;margin:5mm 0}}
.recruit th{{width:34mm;text-align:left;padding:4mm 2mm;color:{accent};font-weight:900;
 border-bottom:1px solid #dde2e8;white-space:nowrap}}
.recruit td{{padding:4mm 2mm;border-bottom:1px solid #dde2e8;font-weight:700}}
.apply{{margin-top:6mm;background:{accent};color:#fff;border-radius:2mm;
 padding:6mm 8mm;text-align:center}}
.apply .t{{font-size:13pt;letter-spacing:.18em;opacity:.9}}
.apply .v{{font-size:30pt;font-weight:900;line-height:1.3;margin-top:2mm}}

/* 配布用の文書。掲示物と違い、余白と行間で読ませる。色はほとんど使わない */
.doc{{flex:1;padding:{docpad}mm {docside}mm {docpad2}mm;font-size:{doc}pt;
 line-height:2.0;color:#1b1f26}}
.doc-date{{text-align:right;font-size:11.5pt}}
.doc-to{{margin-top:6mm;font-size:13pt;font-weight:700}}
.doc-from{{text-align:right;margin-top:4mm;font-size:11.5pt;line-height:1.9;
 white-space:pre-line}}
.doc-title{{text-align:center;font-size:17pt;font-weight:900;margin:11mm 0 9mm;
 letter-spacing:.08em}}
.doc-title::after{{content:"";display:block;width:24mm;height:0.6mm;
 background:{accent};margin:3mm auto 0}}
.doc-body{{font-size:12pt;line-height:2.0;white-space:pre-line}}
.doc-kaki{{margin:8mm auto 0;width:86%}}
.doc-kaki .cap{{text-align:center;font-weight:700;letter-spacing:.3em;margin-bottom:4mm}}
.doc-kaki table{{width:100%;border-collapse:collapse;font-size:12.5pt}}
.doc-kaki th{{width:32mm;text-align:left;padding:2.6mm 0;font-weight:700;
 vertical-align:top;white-space:nowrap}}
.doc-kaki td{{padding:2.6mm 0;border-bottom:1px dotted #c3c9d1}}
.doc-end{{text-align:right;margin-top:8mm;font-size:12pt}}
"""

# 矢印の向き（度）。図形を回して使うので、向きが増えても描き直さなくていい
ARROW_ANGLES = {"right": 0, "downright": 45, "down": 90, "downleft": 135,
                "left": 180, "upleft": 225, "up": 270, "upright": 315}


def arrow_svg(direction: str = "right", color: str = "#1f7a44") -> str:
    """太い矢印を図形で描く。文字の「→」は細くて遠くから見えない。"""
    angle = ARROW_ANGLES.get(str(direction or "").lower(), 0)
    return ('<svg viewBox="0 0 300 100" xmlns="http://www.w3.org/2000/svg">'
            '<g transform="rotate(%d 150 50)">'
            '<path d="M0 34 H185 V6 L300 50 L185 94 V66 H0 Z" fill="%s"/>'
            '</g></svg>' % (angle, color))

# 用紙。掲示物は貼る場所で大きさが変わる（玄関はA4、掲示板はA3、横並びの壁は横）
PAPERS = {
    "A4": {"label": "A4 縦", "w": 210, "h": 297},
    "A4_LANDSCAPE": {"label": "A4 横", "w": 297, "h": 210},
    "A3": {"label": "A3 縦（掲示板向き）", "w": 297, "h": 420},
    "A3_LANDSCAPE": {"label": "A3 横", "w": 420, "h": 297},
}


def metrics(paper: str = "A4") -> Dict[str, Any]:
    """用紙に合わせた寸法一式。

    **紙を大きくしただけでは掲示物にならない。** A3にA4と同じ級数で刷ると、
    紙は倍でも文字は同じ大きさのまま＝ただ余白が増えるだけになる。
    高さの比で全体を拡大し、行長は別に上限を置く（横長の紙で1行が長くなりすぎるため）。
    """
    size = PAPERS.get(str(paper).upper(), PAPERS["A4"])
    k = size["h"] / 297.0                      # 高さの比＝級数と余白の倍率
    return {
        "pw": size["w"], "ph": size["h"], "k": k,
        "frame": round(6 * k, 1),
        "bandpad": round(12 * k, 1), "bandpad2": round(9 * k, 1),
        "mainpad": round(9 * k, 1), "mainpad2": round(5 * k, 1),
        "footpad": round(7 * k, 1), "footpad2": round(8 * k, 1),
        "sidepad": round(min(16 * k, size["w"] * 0.09), 1),
        # 行長の上限。紙幅の8割か、A4相当の168mmを拡大した値の小さい方
        "maxw": round(min(size["w"] * 0.82, 168 * k * 1.25), 1),
        "arroww": round(112 * k, 1), "arrowh": round(36 * k, 1),
        "docpad": round(24 * k, 1), "docpad2": round(20 * k, 1),
        "docside": round(22 * k, 1),
        # 中の部品も用紙倍率で伸縮させる。ここを固定のままにすると、紙が低いとき
        # （A4横など）中身が入りきらず、締めの帯が紙からはみ出て切れる
        "splitgap": round(12 * k, 1),
        "flowpad": round(7 * k, 1), "flowpad2": round(6 * k, 1),
        "stepn": round(12 * k, 1), "pictoh": round(46 * k, 1),
        "pictowide": round(min(size["h"] * 0.42, 130 * k), 1),
        "pictgap": round(14 * k, 1), "pictmb": round(8 * k, 1),
    }


TEMPLATES: List[Dict[str, Any]] = []


def _register(id_: str, name: str, summary: str, best_for: str, accent: str,
              keywords=()):
    def deco(func):
        TEMPLATES.append({"id": id_, "name": name, "summary": summary,
                          "best_for": best_for, "accent": accent,
                          "keywords": tuple(keywords), "build": func})
        return func
    return deco


@_register(
    "sign_ban", "禁止・警告", "極太の見出し＋記号。対応の流れと記入欄まで入る。",
    "駐輪禁止・ゴミの不法投棄・立入禁止など、やめさせたいとき", "#c1272d",
    keywords=("禁止", "厳禁", "立入", "不法", "撤去", "警告", "おやめ"))
def _ban(parts) -> str:
    if parts.get("wide"):
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="pict">{picto}</div></div>
    <div class="r"><div class="lead">{message}</div>{reason}{flow}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="pict">{picto}</div>
  <div class="lead">{message}</div>
  {reason}
  {flow}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_notice", "お知らせ（日時・工事）",
    "日時・場所・内容を表で大きく。いつ何があるかが一目で分かる。",
    "工事・点検・断水・清掃など、日時を確実に伝えたいとき", "#e07a1a",
    keywords=("工事", "点検", "断水", "停電", "清掃", "実施", "お知らせ", "休業"))
def _notice(parts) -> str:
    if parts.get("wide"):
        # 横は「何が起きるか」を左、「いつ・どこで」を右に置く
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="lead">{message}</div>{reason}</div>
    <div class="r">{table}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="lead">{message}</div>
  {table}
  {reason}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_request", "お願い（マナー）",
    "やわらかい色で、お願いしたいことを3点まで。最後にお礼を置く。",
    "騒音・ペット・共用部の使い方など、協力をお願いしたいとき", "#1b4d8f",
    keywords=("お願い", "ご協力", "マナー", "ご遠慮", "騒音", "ペット", "ご配慮"))
def _request(parts) -> str:
    if parts.get("wide"):
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="pict">{picto}</div>
      <div class="thanks">ご理解とご協力を<br>お願いいたします。</div></div>
    <div class="r"><div class="lead">{message}</div>{cards}{reason}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="pict">{picto}</div>
  <div class="lead">{message}</div>
  {cards}
  {reason}
  <div class="thanks">ご理解とご協力をお願いいたします。</div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_direction", "案内・矢印",
    "矢印と行き先だけ。遠くからでも読めるように他を置かない。",
    "駐車場・入口・受付などへ誘導したいとき", "#1f7a44",
    keywords=("こちら", "案内", "入口", "順路", "受付", "矢印", "→"))
def _direction(parts) -> str:
    if parts.get("wide"):
        # 横は矢印と行き先を並べる。縦に積むとどちらも小さくなる
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="arrow">{arrow}</div></div>
    <div class="r"><div class="dest">{message}</div>{dist}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="arrow">{arrow}</div>
  <div class="dest">{message}</div>
  {dist}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_security", "防犯・警戒", "「作動中」を大書きして抑止する。夜でも読める濃色。",
    "監視カメラ作動中・宅配ボックスの盗難注意・特別警戒など", "#1c2530",
    keywords=("防犯", "監視", "カメラ", "盗難", "警戒", "巡回", "不審"))
def _security(parts) -> str:
    """禁止型と分ける理由:
    禁止は「するな」、防犯は「見ているぞ」。狙いが違うので強さの出し方も違う。
    赤で「禁止」と書くより、濃色で「作動中」と書くほうが抑止が効く。
    """
    if parts.get("wide"):
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="pict">{picto}</div></div>
    <div class="r"><div class="lead">{message}</div>{reason}{cards}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="pict">{picto}</div>
  <div class="lead">{message}</div>
  {reason}
  {cards}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_holiday", "休業・営業時間", "休みの期間を特大で。緊急時の連絡先を必ず添える。",
    "年末年始・GW・お盆・臨時休業。営業時間の変更", "#1b4d8f",
    keywords=("休業", "年末年始", "ゴールデンウィーク", "ゴールデンウイーク", "お盆",
              "夏季", "臨時", "営業時間", "休み"))
def _holiday(parts) -> str:
    """休業の掲示で一番大事なのは**期間**と**緊急時にどこへ掛けるか**。
    「ご迷惑をおかけします」を大きく書いても住民の役には立たない。
    """
    if parts.get("wide"):
        # 横は期間を左に大きく、通常営業・緊急連絡先を右に
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="period">{message}</div></div>
    <div class="r">{table}{reason}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="period">{message}</div>
  {table}
  {reason}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_price", "料金表・営業時間", "品目と金額を右揃えで並べ、営業時間を下に大きく。",
    "駐車場・自転車置場の料金、店舗の料金表や営業時間の掲示", "#1c2530",
    keywords=("料金", "価格", "月額", "営業時間", "利用料", "使用料"))
def _price(parts) -> str:
    """金額は**右端で桁をそろえる**。左揃えだと桁が読み比べられない。"""
    if parts.get("wide"):
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l"><div class="lead">{message}</div>{hours}</div>
    <div class="r">{price}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="lead">{message}</div>
  {price}
  {hours}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_recruit", "募集（スタッフ・入居者）", "条件を項目で整理し、応募先を色帯で大きく。",
    "スタッフ・パート募集、入居者募集の店頭掲示", "#c1272d",
    keywords=("募集", "求人", "パート", "アルバイト", "スタッフ", "採用"))
def _recruit(parts) -> str:
    """募集の掲示は**応募先が一番大事**。条件を読ませても、掛ける先が
    小さければ電話は鳴らない。連絡先を色帯で最後に大きく置く。
    """
    if parts.get("wide"):
        # 横は条件を左、応募先を右に大きく（応募先が主役なので右を広く使う）
        return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="split">
    <div class="l" style="flex:0 0 52%"><div class="lead">{message}</div>{recruit}</div>
    <div class="r">{apply}</div>
  </div>
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)
    return """<div class="band"><h1>{headline}</h1>{en}</div>
<div class="main">
  <div class="lead">{message}</div>
  {recruit}
  {apply}
</div>
<div class="foot"><div class="owner">{foot}</div>{multi}</div>""".format(**parts)


@_register(
    "sign_document", "お知らせ文書（配布用）",
    "拝啓〜記〜以上の体裁。掲示ではなく、投函・郵送する文書。",
    "休業案内・工事案内・請求方法の変更など、住民や取引先に配る紙", "#1b4d8f",
    keywords=("拝啓", "文書", "投函", "郵送", "通知", "ご通知", "案内文"))
def _document(parts) -> str:
    """掲示物と分ける理由:
    貼る紙は「遠くから読ませる」、配る紙は「手元で読ませる」。
    配る紙に極太の見出しを付けると、事務連絡なのに騒がしくなる。
    日本のビジネス文書は日付・宛名・差出人・件名・記書きの順が決まっている。
    """
    return """<div class="doc">
  <div class="doc-date">{date}</div>
  <div class="doc-to">{to}</div>
  <div class="doc-from">{from_}</div>
  <div class="doc-title">{headline}</div>
  <div class="doc-body">{body}</div>
  {kaki}
  <div class="doc-end">以上</div>
</div>""".format(**parts)


def all_templates() -> List[Dict[str, Any]]:
    return list(TEMPLATES)


def get(template_id: str):
    for item in TEMPLATES:
        if item["id"] == template_id:
            return item
    return None


def choose(brief: str, signage=None) -> str:
    """依頼文から型を当てる。迷ったら禁止・警告（一番多い用途）。

    お知らせ・お願い・案内の語が入っていれば、そちらを優先する。
    """
    text = str(brief or "")
    if signage:
        text += " " + " ".join(str(v) for v in signage.values() if isinstance(v, str))
    best, score = "sign_ban", 0
    for item in TEMPLATES:
        hit = sum(1 for word in item["keywords"] if word in text)
        if hit > score:
            best, score = item["id"], hit
    return best


def options_for_question() -> List[str]:
    return ["%s｜%s" % (t["name"], t["summary"]) for t in TEMPLATES]


def id_from_answer(answer: str) -> str:
    text = str(answer or "").strip()
    if not text:
        return ""
    for item in TEMPLATES:
        if text == item["id"] or text.startswith(item["name"]) or item["name"] in text:
            return item["id"]
    return ""


def describe_for_prompt() -> str:
    lines = ["【掲示物の型】"]
    for item in TEMPLATES:
        lines.append("- %s（%s）… %s\n    向くとき: %s"
                     % (item["id"], item["name"], item["summary"], item["best_for"]))
    return "\n".join(lines)
