"""同じ物件データから、看板QRの飛び先になる物件サイトを書き出す。

読むのはスマホ（看板のQRを現地で読む）なので、縦持ち前提で組む。
出力は site/ 配下の静的HTMLだけなので、そのまま gh-pages に置ける。
"""
from __future__ import annotations

import html
import shutil
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter

import contact
import flyer
import tracking
from properties import (ADDRESS, COMMON_TEL, COMPANY, LICENSE, PROPERTIES, RENTALS, RENTED,
                        list_madori, list_photos, rented_photo)


def ask_url(bukken: str = "", kind: str = "") -> str:
    """問い合わせページのURL。物件名と用件を渡して、開いた時点で選ばれた状態にする。"""
    q = "&".join(f"{k}={quote(v)}" for k, v in (("p", bukken), ("k", kind)) if v)
    return "contact.html" + (f"?{q}" if q else "")

SITE = Path(__file__).parent / "site"
IMG_LONG = 1600          # 表示用の長辺
THUMB_LONG = 700         # 一覧用

ORG, NAVY = "#f07c1e", "#1b2340"


def export_blurred(src: Path, dest: Path, long_edge: int = 900, radius: int = 2) -> None:
    """賃貸中の物件用。入居中の方がいるので外観が特定できないところまでぼかす。

    CSSのfilterだと解除できてしまうので、書き出すファイル自体をぼかしておく。
    radius は「どんな家かは分かるが、細部までは追えない」ところを狙って 2。
    強くしすぎると加東らしさまで消えて、載せる意味が無くなる。
    """
    if dest.exists():
        return
    im = flyer.load_image(str(src))
    im.thumbnail((long_edge, long_edge), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(radius))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=78, optimize=True)


OG_W, OG_H = 1200, 630          # LINE・SNSのカードで使われる比率


def export_og(src: Path, dest: Path, label: str = "") -> None:
    """LINEやSNSに貼られたときに出るカード用の画像。

    URLだけの素っ気ない表示にせず、外観写真が出るようにする。
    label を渡すと下に濃紺の帯を敷いて文字を入れる（一覧用）。
    """
    if dest.exists():
        return
    im = flyer.load_image(str(src))
    scale = max(OG_W / im.width, OG_H / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                   Image.LANCZOS)
    im = im.crop(((im.width - OG_W) // 2, (im.height - OG_H) // 2,
                  (im.width - OG_W) // 2 + OG_W, (im.height - OG_H) // 2 + OG_H))
    if label:
        band = 104
        d = ImageDraw.Draw(im)
        d.rectangle([0, OG_H - band, OG_W, OG_H], fill=(27, 35, 64))
        f = flyer.font("W6", 40)
        d.text((44, OG_H - band + 30), label, font=f, fill=(255, 255, 255))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(dest, "JPEG", quality=84, optimize=True)


def card_features(prop: dict) -> str:
    """一覧カードに出す特徴の1行。間取り・広さ・一番の売りを並べる。

    4件とも交通の行がほぼ同じで、カードだけ見ると値段しか比べられなかったので足した。
    """
    d = dict(prop.get("specs", []))
    parts = []
    if d.get("間取り"):
        parts.append(d["間取り"])
    for k in ("専有面積", "建物面積", "敷地面積"):
        if d.get(k):
            parts.append(f"敷地{d[k]}" if k == "敷地面積" else d[k])
            break
    tags = prop.get("tags") or []
    if tags:
        parts.append(tags[0])
    return " ／ ".join(parts)


def export_icons() -> None:
    """タブと iPhone のホーム画面用のアイコン。SPMのマークを濃紺の四角に載せる。

    小さく表示されるので社名は入れない（潰れて読めなくなる）。マークだけを使う。
    素材はロゴ白版の左端＝マーク部分の切り出し。
    """
    src = Path(__file__).parent / "assets" / "spm_logo_white.png"
    if not src.exists():
        return
    logo = Image.open(src).convert("RGBA")
    mark = logo.crop((0, 0, 162, logo.height))
    mark = mark.crop(mark.getbbox())

    def square(px: int) -> Image.Image:
        im = Image.new("RGBA", (px, px), (27, 35, 64, 255))     # 濃紺
        inner = round(px * 0.72)
        m = mark.copy()
        m.thumbnail((inner, inner), Image.LANCZOS)
        im.alpha_composite(m, ((px - m.width) // 2, (px - m.height) // 2))
        return im

    square(180).convert("RGB").save(SITE / "apple-touch-icon.png")
    square(256).save(SITE / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


def export_image(src: Path, dest: Path, long_edge: int) -> None:
    if dest.exists():
        return
    im = flyer.load_image(str(src))
    im.thumbnail((long_edge, long_edge), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=82, optimize=True)


CSS = f""":root{{--org:{ORG};--navy:{NAVY};--ink:#20232d;--gray:#6b7280;--line:#e2e5ec}}
*{{box-sizing:border-box}}
body{{margin:0;background:#fff;color:var(--ink);line-height:1.75;
 font-family:-apple-system,"Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif}}
a{{color:inherit}}
.bar{{background:var(--navy);color:#fff;padding:8px 14px;font-size:13px;font-weight:700;gap:10px;
 display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:9}}
.bar img{{height:15px;max-width:100%;object-fit:contain;display:block}}
.bar a{{color:var(--org);text-decoration:none}}
/* 連絡先は上帯に置く。以前は下に貼り付く帯だったが、最下部でフッターと二重に見えた。 */
.bar .home{{flex:0 1 auto;min-width:0;white-space:nowrap;overflow:hidden}}
.bar .acts{{flex:0 0 auto;display:flex;align-items:center;gap:9px}}
.bar .acts .tel{{color:var(--org);font-size:15px;font-weight:900;white-space:nowrap}}
.bar .acts .ask{{background:var(--org);color:var(--navy);font-size:12px;font-weight:900;
 padding:6px 11px;border-radius:6px;white-space:nowrap}}
.hero{{background:var(--org);color:var(--navy);padding:20px 18px 22px}}
.hero .k{{font-size:12px;font-weight:800;letter-spacing:.1em;color:#7a3d05}}
.hero h1{{margin:5px 0 0;font-size:25px;font-weight:900;line-height:1.3;letter-spacing:-.02em}}
.hero .catch{{margin:9px 0 0;font-size:14px;font-weight:700;color:#7a3d05;line-height:1.5}}
/* 一覧のキャッチは1行で見せる。狭い画面では折り返さずに字を詰める。 */
.hero h1.one{{white-space:nowrap;font-size:clamp(20px,7.6vw,29px)}}
.gal{{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:0;-webkit-overflow-scrolling:touch;
 scrollbar-width:none}}
.gal::-webkit-scrollbar{{display:none}}
.gal img{{flex:0 0 100%;scroll-snap-align:center;width:100%;aspect-ratio:3/2;object-fit:cover;display:block}}
.galbar{{display:flex;align-items:center;gap:8px;padding:7px 12px 0}}
.galno{{font-size:12px;color:var(--gray);font-weight:700;white-space:nowrap;min-width:44px}}
.thumbs{{display:flex;gap:6px;overflow-x:auto;padding:7px 12px 12px;scrollbar-width:none}}
.thumbs::-webkit-scrollbar{{display:none}}
.thumbs button{{flex:0 0 76px;padding:0;border:2px solid transparent;border-radius:5px;
 overflow:hidden;background:none;cursor:pointer;line-height:0;opacity:.55;transition:opacity .15s}}
.thumbs button.on{{border-color:var(--org);opacity:1}}
.thumbs img{{width:100%;aspect-ratio:3/2;object-fit:cover;display:block}}
.rent{{background:var(--navy);color:#fff;padding:13px 18px;display:flex;
 justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}}
.rent .n{{font-size:11.5px;color:#aab4d6;white-space:nowrap}}
.rent .p small{{font-size:12.5px;color:#fff;font-weight:700;margin-right:7px}}
.rent .p{{font-size:26px;font-weight:900;color:var(--org);white-space:nowrap}}
.rent .p span{{font-size:13px;color:#fff;font-weight:700;margin-left:3px}}
.wrap{{padding:20px 18px 40px;max-width:760px;margin:0 auto}}
.tags{{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:16px}}
.tag{{border:1.5px solid var(--org);color:#96460a;background:#fff6ec;border-radius:99px;
 padding:4px 13px;font-size:12.5px;font-weight:700}}
p.body{{margin:0 0 20px;font-size:15px}}
h2{{font-size:15px;color:var(--navy);border-left:5px solid var(--org);padding-left:9px;margin:26px 0 10px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{border-bottom:1px solid var(--line);padding:9px 4px;text-align:left;vertical-align:top}}
th{{width:33%;color:var(--navy);font-weight:700;white-space:nowrap}}
.madori{{width:100%;border:1px solid var(--line);border-radius:7px;margin-top:6px}}
.vr{{display:block;background:var(--org);color:var(--navy);text-align:center;text-decoration:none;
 font-weight:900;font-size:17px;padding:15px;border-radius:9px;margin:18px 0 4px}}
.vr small{{display:block;font-weight:700;font-size:11.5px;color:#7a3d05;margin-top:2px}}
/* 本文の最後に置く問い合わせへの導線。上帯のボタンだけだと見落とされる。 */
.askbox{{margin:30px 0 6px;border:1.5px solid var(--org);background:#fff6ec;
 border-radius:11px;padding:16px 16px 18px;text-align:center}}
.askbox p{{margin:0 0 12px;font-size:13.5px;font-weight:700;color:#96460a;line-height:1.65}}
.askbox .b{{display:block;background:var(--org);color:var(--navy);text-decoration:none;
 font-weight:900;font-size:17px;padding:15px;border-radius:9px}}
.askbox .b small{{display:block;font-weight:700;font-size:11.5px;color:#7a3d05;margin-top:2px}}
.askbox .t{{display:inline-block;margin-top:12px;font-size:16px;font-weight:900;
 color:var(--navy);text-decoration:none}}
.cards{{display:grid;gap:16px;padding:20px 18px 40px;max-width:760px;margin:0 auto}}
.card{{border:1px solid var(--line);border-radius:11px;overflow:hidden;text-decoration:none;display:block}}
.card img{{width:100%;aspect-ratio:3/2;object-fit:cover;display:block}}
.card .b{{padding:12px 14px}}
.card .b b{{font-size:16px;display:block}}
.card .b .p{{color:var(--org);font-size:22px;font-weight:900;margin-top:3px}}
.card .b .p span{{font-size:12px;color:var(--gray);font-weight:700}}
.card .b .f{{font-size:13px;font-weight:700;color:var(--navy);margin-top:5px}}
.card{{position:relative}}
.badge{{position:absolute;top:10px;left:10px;background:var(--org);color:var(--navy);
 font-size:12px;font-weight:900;padding:4px 11px;border-radius:99px;z-index:2}}
.sec{{padding:4px 18px 0;max-width:760px;margin:0 auto}}
.sec h2{{margin:22px 0 2px}}
.sec p{{margin:0;font-size:13px;color:var(--gray)}}
.rentals{{display:grid;grid-template-columns:1fr 1fr;gap:11px;padding:12px 18px 8px;
 max-width:760px;margin:0 auto}}
.rentals .rs{{border:1px solid var(--line);border-radius:9px;overflow:hidden;display:block;
 text-decoration:none;color:inherit}}
.rentals .rs img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}}
.rentals .rs .t{{padding:8px 10px;font-size:12.5px;font-weight:700;line-height:1.45}}
.rentals .rs .t small{{display:block;color:#96460a;font-size:11px;font-weight:800;margin-top:2px}}
.rented{{display:grid;grid-template-columns:1fr 1fr;gap:11px;padding:12px 18px 34px;
 max-width:760px;margin:0 auto}}
.rented .r{{border:1px solid var(--line);border-radius:9px;overflow:hidden;position:relative}}
.rented .r img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}}
.rented .r a{{display:block;text-decoration:none;color:inherit}}
.rented .r .ph{{position:relative;line-height:0}}
.rented .r .ph::after{{content:"";position:absolute;inset:0;
 background:linear-gradient(rgba(20,26,48,.12),rgba(20,26,48,.30));pointer-events:none}}
.rented .r .t{{padding:8px 10px;font-size:12.5px;font-weight:700;line-height:1.45;
 background:#fff}}
.rented .r .t small{{display:block;color:#96460a;font-size:11px;font-weight:800;margin-top:2px}}
.rented .r .b{{position:absolute;inset:0;z-index:2;
 display:grid;place-items:center;color:#fff;font-size:34px;font-weight:900;
 letter-spacing:.2em;text-shadow:0 2px 14px rgba(0,0,0,.85),0 0 3px rgba(0,0,0,.7)}}
footer{{background:var(--navy);color:#aab4d6;font-size:12px;padding:22px 18px 30px;text-align:center}}
footer img{{height:26px;max-width:92%;object-fit:contain;margin:0 auto 12px;display:block}}
"""

# ロゴ画像は社名まで。免許番号は変わるのでテキストで持つ（properties.LICENSE）。
FOOTER = (f'<footer><img src="logo_white.png" alt="{COMPANY}">'
          f'{ADDRESS}　TEL {COMMON_TEL}／FAX 06-7635-7811　{LICENSE}</footer>')


# サムネイルをタップで本体を送る。横スワイプだけだと何枚あるか分からない、という指摘への対応。
GALJS = """
(function(){
  var gal=document.getElementById('gal'), no=document.getElementById('galno');
  var bs=[].slice.call(document.querySelectorAll('#thumbs button'));
  if(!gal||!bs.length) return;
  function go(i){ gal.scrollTo({left: gal.clientWidth*i, behavior:'smooth'}); }
  bs.forEach(function(b,i){ b.addEventListener('click', function(){ go(i); }); });
  var cur=-1;
  function sync(){
    var i=Math.round(gal.scrollLeft/gal.clientWidth);
    if(i===cur) return;
    cur=i;
    bs.forEach(function(b,j){ b.classList.toggle('on', j===i); });
    if(no) no.textContent=(i+1)+' / '+bs.length;
    var b=bs[i];
    if(b) b.scrollIntoView({inline:'center', block:'nearest', behavior:'smooth'});
  }
  gal.addEventListener('scroll', sync, {passive:true});
  window.addEventListener('resize', function(){ cur=-1; sync(); });
  sync();
})();
"""


def page(prop_name: str, prop: dict, imgs: list[str], madori: str | None,
         thumbs: list[str] | None = None, slug: str = "") -> str:
    e = html.escape
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in prop.get("tags", []))
    specs = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in prop.get("specs", []))
    gal = "".join(f'<img src="{i}" alt="" loading="lazy">' for i in imgs)
    ts = thumbs or imgs
    thumbstrip = "".join(
        f'<button type="button" aria-label="{n + 1}枚目">'
        f'<img src="{t}" alt="" loading="lazy"></button>'
        for n, t in enumerate(ts)
    )
    body = f'<p class="body">{e(prop.get("body", ""))}</p>' if prop.get("body") else ""
    md = (f'<h2>間取り</h2><img class="madori" src="{madori}" alt="間取り図">' if madori else "")
    tel = prop.get("tel", "06-6935-7267")
    vr = (f'<a class="vr" href="{prop["vr_url"]}" target="_blank" rel="noopener">'
          f'🏠 VRで室内を見る<small>スマホをかざして見回せます</small></a>')\
        if prop.get("vr_url") else ""
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">\n<link rel="icon" href="favicon.ico" sizes="any">\n<link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>{e(prop['title'])}｜新誠プロパティマネジメント</title>
<meta name="description" content="{e(prop.get('body','')[:90])}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="加東の貸家｜新誠プロパティマネジメント">
<meta property="og:title" content="{e(prop['title'])}　{e(prop['rent'])}円/月">
<meta property="og:description" content="{e(prop.get('body','') or prop['catch'].replace(chr(10), ''))[:100]}">
<meta property="og:url" content="{tracking.BASE_URL}{quote(slug)}.html">
<meta property="og:image" content="{tracking.BASE_URL}img/{quote(slug)}/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style></head><body>
<div class="bar"><a class="home" href="index.html">← 物件一覧</a><div class="acts"><a class="tel" href="tel:{tel.replace('-', '')}">☎ {e(tel)}</a><a class="ask" href="{ask_url(prop_name, contact.VISIT)}">お問い合わせ</a></div></div>
<div class="hero"><div class="k">{e(prop['kicker'])}</div>
  <h1>{e(prop['title'])}</h1>
  <p class="catch">{e(prop['catch']).replace(chr(10), '')}</p></div>
<div class="gal" id="gal">{gal}</div>
<div class="galbar"><span class="galno" id="galno">1 / {len(imgs)}</span>
  <span style="font-size:11.5px;color:var(--gray)">写真をタップ、または横にスワイプ</span></div>
<div class="thumbs" id="thumbs">{thumbstrip}</div>
<div class="rent"><div class="p"><small>賃料</small>{e(prop['rent'])}<span>円/月</span></div>
  <div class="n">{e(prop['rent_note'])}</div></div>
<div class="wrap">
  <div class="tags">{tags}</div>
  {body}
  {vr}
  <h2>物件の詳細</h2><table>{specs}</table>
  {md}
  <div class="askbox">
    <p>内覧のご希望、詳しい条件や空き状況など、お気軽にお尋ねください。</p>
    <a class="b" href="{ask_url(prop_name, contact.VISIT)}">この物件をお問い合わせ<small>内覧希望・詳細のご相談</small></a>
    <a class="t" href="tel:{tel.replace('-', '')}">☎ {e(tel)}</a>
  </div>
</div>
{FOOTER}
<script>{GALJS}{tracking.TRACK_JS}</script>
</body></html>"""


def index(cards: list[dict], rented: list[dict] | None = None,
          rentals: list[dict] | None = None) -> str:
    e = html.escape
    items = "".join(
        f'<a class="card" href="{c["href"]}"><span class="badge">募集中</span>'
        f'<img src="{c["thumb"]}" alt="" loading="lazy">'
        f'<div class="b"><b>{e(c["title"])}</b>'
        f'<div class="p">{e(c["rent"])}<span> 円/月</span></div>'
        f'<div class="f">{e(c["feat"])}</div></div></a>'
        for c in cards
    )
    rentalhtml = ""
    if rentals:
        rr = "".join(
            f'<a class="rs" href="{x["url"]}" target="_blank" rel="noopener">'
            f'<img src="{x["thumb"]}" alt="" loading="lazy">'
            f'<div class="t">{e(x["title"])}<small>{e(x["note"])} ／ 予約する →</small></div></a>'
            for x in rentals
        )
        rentalhtml = (
            '<div class="sec"><h2>レンタルスペース（貸切キャンプ場）</h2>'
            '<p>1日1組限定の貸切BBQ・キャンプ場です。ご予約はスペースマーケットから。</p></div>'
            f'<div class="rentals">{rr}</div>'
        )
    rl = rented or []
    rentedhtml = ""
    if rl:
        # 賃貸中もタップで問い合わせへ。用件は「空きが出たら連絡してほしい」で入る。
        rr = "".join(
            f'<div class="r"><a href="{ask_url(r["title"], contact.WAIT)}">'
            f'<div class="ph"><img src="{r["thumb"]}" alt="" loading="lazy">'
            f'<span class="b">賃貸中</span></div>'
            f'<div class="t">{e(r["title"])}<small>空いたら知らせる →</small></div>'
            f'</a></div>' for r in rl
        )
        rentedhtml = (
            '<div class="sec"><h2>賃貸中の物件</h2>'
            '<p>現在満室ですが、空きが出たときにご連絡できます。</p></div>'
            f'<div class="rented">{rr}</div>'
        )
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">\n<link rel="icon" href="favicon.ico" sizes="any">\n<link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>加東の貸家｜大阪から車で約1時間、緑と暮らすスローライフ｜新誠プロパティマネジメント</title>
<meta name="description" content="兵庫県加東市の別荘地にある貸家。大阪から車で約1時間、緑に囲まれたスローライフ。リフォーム済み・駐車場あり・月49,000円から。">
<meta property="og:type" content="website">
<meta property="og:site_name" content="加東の貸家｜新誠プロパティマネジメント">
<meta property="og:title" content="加東の貸家｜大阪から車で約1時間、緑と暮らすスローライフ">
<meta property="og:description" content="兵庫県加東市の別荘地にある貸家。月49,000円から。ログハウス・3LDK・家具付きなど4件を募集中。">
<meta property="og:url" content="{tracking.BASE_URL}">
<meta property="og:image" content="{tracking.BASE_URL}og.jpg">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style></head><body>
<div class="bar"><span class="home"><img src="logo_white.png" alt="新誠プロパティマネジメント株式会社"></span><div class="acts"><a class="tel" href="tel:0669357267">☎ 06-6935-7267</a><a class="ask" href="contact.html">お問い合わせ</a></div></div>
<div class="hero"><div class="k">大阪から車で約1時間</div>
  <h1 class="one">緑と暮らすスローライフ</h1></div>
<div class="sec"><h2>募集中の物件</h2><p>物件詳細・内覧のご希望は各ページよりお問い合わせください。</p></div>
<div class="cards">{items}</div>
{rentalhtml}
<div class="wrap" style="padding-top:0"><div class="askbox">
  <p>内覧のご希望、詳しい条件や空き状況など、お気軽にお尋ねください。<br>
  賃貸中の物件も、空きが出たときにご連絡できます。</p>
  <a class="b" href="contact.html">お問い合わせ<small>内覧希望・詳細のご相談</small></a>
  <a class="t" href="tel:0669357267">☎ 06-6935-7267</a>
</div></div>
{rentedhtml}
{FOOTER}
<script>{tracking.TRACK_JS}</script>
</body></html>"""


def build(selection: dict[str, list[str]] | None = None, max_photos: int = 10) -> Path:
    """selection は 物件名 -> 使う写真パスの配列。

    公開物なので、載せる写真は必ず人が選んだものだけにする。
    一度「先頭から自動で10枚」にしていたら、案件フォルダに同居していた
    入居申込者の免許証と申込書がサイトに載りかけた。自動選択には戻さないこと。
    """
    SITE.mkdir(parents=True, exist_ok=True)
    # 社名はロゴで出す（大京ロゴ.ai から抜いたもの）
    # 免許番号が入っていない版を使う（番号はフッターのテキスト側で出す）
    lg = Path(__file__).parent / "assets" / "spm_logo_white_name.png"
    if lg.exists():
        shutil.copy2(lg, SITE / "logo_white.png")
    export_icons()
    cards = []
    vacant = []          # 問い合わせフォームの物件リスト用（PROPERTIES のキー）
    skipped = []
    for name, prop in PROPERTIES.items():
        photos = [Path(p) for p in (selection or {}).get(name, [])]
        if not photos:
            skipped.append(name)
            continue
        slug = prop["case_dir"] or name
        imgs = []
        for i, p in enumerate(photos[:max_photos]):
            rel = f"img/{slug}/{i:02d}.jpg"
            export_image(p, SITE / rel, IMG_LONG)
            imgs.append(rel)
        tlist = []
        for i, p in enumerate(photos[:max_photos]):
            rel = f"img/{slug}/t{i:02d}.jpg"
            export_image(p, SITE / rel, 260)   # サムネイル帯用
            tlist.append(rel)
        thumb = f"img/{slug}/thumb.jpg"
        export_image(photos[0], SITE / thumb, THUMB_LONG)
        # LINE等に貼られたとき用。外観が写っている2枚目を優先する。
        export_og(photos[1] if len(photos) > 1 else photos[0], SITE / f"img/{slug}/og.jpg")

        mds = list_madori(prop)
        md_rel = None
        if mds:
            md_rel = f"img/{slug}/madori.jpg"
            export_image(mds[0], SITE / md_rel, IMG_LONG)

        href = f"{slug}.html"
        (SITE / href).write_text(page(name, prop, imgs, md_rel, tlist, slug), encoding="utf-8")
        cards.append({"href": href, "thumb": thumb, "title": prop["title"],
                      "rent": prop["rent"], "feat": card_features(prop)})
        vacant.append((name, f"{prop['title']}（{prop['rent']}円/月）"))

    rented = []
    for r in RENTED:
        src = rented_photo(r)
        if not src:
            print("賃貸中の写真が見つかりません:", r["title"])
            continue
        # 連番にすると並べ替えたときに同じURLで中身だけ入れ替わり、
        # ブラウザが古い写真を掴んで名前と食い違う。物件名をそのまま使う。
        rel = f"img/rented/{r['title']}.jpg"
        export_blurred(src, SITE / rel)
        rented.append({"thumb": rel, "title": r["title"]})

    # レンタルスペース（貸切キャンプ場）。賃貸ではないのでぼかさない。
    rentals = []
    for x in RENTALS:
        src = rented_photo(x)
        if not src:
            print("レンタルスペースの写真が見つかりません:", x["title"])
            continue
        rel = f"img/rental/{x['title']}.jpg"
        export_image(src, SITE / rel, THUMB_LONG)
        rentals.append({**x, "thumb": rel})

    # 一覧用のカード画像。ログハウスの外観に帯を敷いてサイト名を入れる。
    hero = next((Path(p) for p in (selection or {}).get("秋津11（ログハウス）", [])[1:2]), None)
    if hero and hero.exists():
        export_og(hero, SITE / "og.jpg", "加東の貸家 ｜ 大阪から車で約1時間")

    (SITE / "index.html").write_text(index(cards, rented, rentals), encoding="utf-8")

    # 問い合わせ（slowlife専用。会社サイトの mailform とは別系統）
    (SITE / "contact.html").write_text(
        contact.page_contact(CSS, FOOTER, vacant, [r["title"] for r in rented]), encoding="utf-8")
    (SITE / "thanks.html").write_text(contact.page_thanks(CSS, FOOTER), encoding="utf-8")
    (SITE / "send.php").write_text(contact.SEND_PHP, encoding="utf-8")

    # 流入元の計測（看板ごとにどれだけ来たかを分けて数える）
    (SITE / "hit.php").write_text(tracking.hit_php(tracking.SOURCES), encoding="utf-8")
    (SITE / "stats.php").write_text(
        tracking.stats_php(tracking.SOURCES, tracking.STATS_KEY), encoding="utf-8")
    for folder, src in tracking.REDIRECTS.items():
        (SITE / folder).mkdir(exist_ok=True)
        (SITE / folder / "index.php").write_text(
            tracking.redirect_php(src), encoding="utf-8")

    if skipped:
        print("写真が選ばれていないので飛ばしました:", "、".join(skipped))
    return SITE


if __name__ == "__main__":
    print(
        "写真を選ばずに実行しても中身は空になります。\n"
        "アプリ（run.sh／port 8529）で物件ごとに載せる写真を選んでから書き出してください。"
    )
    build()
