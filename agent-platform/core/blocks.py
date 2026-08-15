"""紙面の部品（ブロック）ライブラリ

なぜ部品方式にしたか:
  - LLMにHTMLを全部書かせる … 柔軟だが**1枚に230秒**かかり、毎回どこかが崩れる
  - 固定テンプレートを増やす … 速くて崩れないが、**型に無いものは作れない**
    （成果物のパターンは無限にあるので、テンプレを増やし続けることになる）
  → **部品は固定、組み合わせは自由**。LLMは「どの部品を、どの順で、中身は何か」だけを
    JSONで決める。CSSは書かせない。速く、崩れず、それでいて何でも組める。

部品を足すときは、ここに関数を1つ足して BLOCKS に登録し、
`describe_for_prompt()` に説明を書く。それだけで全部隊が使えるようになる。
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from .config import ROOT

MAX_PHOTOS = 12


def _esc(text: Any) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _img_uri(path) -> str:
    """画像をdata URIに。相対パスはブラウザが読めないため必ず埋め込む。"""
    path = Path(path)
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
            ".svg": "image/svg+xml"}.get(path.suffix.lower(), "image/png")
    return "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode("ascii"))


# --- 部品 -------------------------------------------------------------------

def header_band(title: str = "", sub: str = "", **_) -> str:
    """色帯の見出し。掲示物・チラシの一番上に置く。"""
    length = len(str(title))
    size = 54 if length <= 10 else (42 if length <= 16 else 32)
    sub_html = '<div class="hb-sub">%s</div>' % _esc(sub) if sub else ""
    return ('<div class="band"><h1 style="font-size:%dpt">%s</h1>%s</div>'
            % (size, _esc(title), sub_html))


def catch(text: str = "", note: str = "", **_) -> str:
    """一番言いたい一言。紙面で最も大きい文字。"""
    length = len(str(text))
    size = 40 if length <= 14 else (32 if length <= 22 else 26)
    note_html = '<div class="catch-note">%s</div>' % _esc(note) if note else ""
    return ('<div class="catch" style="font-size:%dpt">%s</div>%s'
            % (size, _esc(text), note_html))


def price(main: str = "", unit: str = "", note: str = "", **_) -> str:
    """価格・賃料を大きく見せる。"""
    return ('<div class="price"><span class="p-main">%s</span>'
            '<span class="p-unit">%s</span>%s</div>'
            % (_esc(main), _esc(unit),
               '<div class="p-note">%s</div>' % _esc(note) if note else ""))


def _luminance(color: str) -> float:
    """色の明るさ（0〜1）。文字が読めるかの判定に使う。"""
    text = str(color).lstrip("#")
    if len(text) != 6:
        return 0.5
    parts = []
    for i in (0, 2, 4):
        value = int(text[i:i + 2], 16) / 255.0
        parts.append(value / 12.92 if value <= 0.03928
                     else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def _contrast(front: str, back: str) -> float:
    a, b = _luminance(front), _luminance(back)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def readable_on(color: str, background: str, target: float = 4.5) -> str:
    """濃い面の上でも読める色にする。

    帯（濃色）の上に同系の濃い色で文字を置くと、色は合っているのに読めない
    （緑の帯に緑の賃料を出して読みにくいと指摘された）。

    白を混ぜて明るくすると読めるようになるが、**色がくすんで賃料の力が落ちる**。
    そこで色相と鮮やかさは保ったまま、**明度だけを上げる**。
    それでも足りなければ最後に白へ寄せる。
    """
    import colorsys

    text = str(color).lstrip("#")
    if len(text) != 6:
        return color
    r, g, b = (int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    for step in range(0, 21):
        value = min(light + step * 0.04, 0.97)
        red, green, blue = colorsys.hls_to_rgb(hue, value, sat)
        blend = "#%02x%02x%02x" % (int(red * 255), int(green * 255), int(blue * 255))
        if _contrast(blend, background) >= target:
            return blend
    return "#ffffff"


def _trim_margins(path: str) -> str:
    """図面・地図の**外周の白い余白だけ**を切り落とす。

    間取り図は図の周りに大きく白が入っていることが多い。そのまま置くと
    紙面では図が小さく見え、逆に枠に合わせて切ると**図面そのものが欠ける**。
    余白を先に落としてから contain で置けば、切らずに大きく見せられる。

    白でない画素の外接矩形を取るだけ。**図の中身には触らない**。
    元ファイルは書き換えず、切った版をキャッシュに置く。
    """
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return path
    src = Path(path)
    try:
        stamp = "%s-%d" % (src.name, int(src.stat().st_mtime))
    except OSError:
        return path
    cache = ROOT / ".cache" / "trim"
    out = cache / (hashlib.md5(stamp.encode("utf-8")).hexdigest() + ".png")
    if out.exists():
        return str(out)
    try:
        img = Image.open(src).convert("RGB")
        # 完全な白でなくスキャンのくすみもあるため、しきい値を少し下げて判定する
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg).convert("L").point(
            lambda v: 255 if v > 12 else 0)
        box = diff.getbbox()
        if not box:
            return path
        w, h = img.size
        pad = max(2, int(min(w, h) * 0.01))
        box = (max(0, box[0] - pad), max(0, box[1] - pad),
               min(w, box[2] + pad), min(h, box[3] + pad))
        # ほとんど余白が無いなら触らない（無駄なファイルを作らない）
        if (box[2] - box[0]) * (box[3] - box[1]) > w * h * 0.97:
            return path
        cache.mkdir(parents=True, exist_ok=True)
        img.crop(box).save(out)
        return str(out)
    except Exception:
        return path


def photo_hero(path: str = "", caption: str = "", height: int = 90,
               fit: str = "cover", **_) -> str:
    """主役の写真を1枚大きく。height はmm。

    fit="cover"（既定）… 枠いっぱいに広げ、はみ出した分は切る。写真向き。
    fit="contain"      … **切らずに全体を入れる**。間取り図・地図・図面はこちら。
                         切ると部屋や方位が欠けて、資料として成立しなくなる。
    """
    if not path or not Path(path).exists():
        return ""
    cap = '<div class="cap">%s</div>' % _esc(caption) if caption else ""
    if str(fit) == "contain":
        # 図面は周りの余白を落としてから置く。余白ごと入れると図が小さくなる
        # 高さを固定すると上下に白い帯が出る。**高さは図の縦横比に任せ、
        # 指定値は上限として効かせる**。こうすると枠が図にぴったり沿う。
        return ('<div class="hero contain">'
                '<img src="%s" style="max-height:%dmm;height:auto">%s</div>'
                % (_img_uri(_trim_margins(path)), int(height), cap))
    return ('<div class="hero"><img src="%s" style="height:%dmm">%s</div>'
            % (_img_uri(path), int(height), cap))


def photo_grid(paths: List[str] = (), cols: int = 3, captions: List[str] = (),
               height: int = 38, **_) -> str:
    """写真を並べる。物件チラシは点数がそのまま反響に効くので余らせない。"""
    items = []
    for i, path in enumerate(list(paths)[:MAX_PHOTOS]):
        if not path or not Path(path).exists():
            continue
        cap = ""
        if i < len(captions) and captions[i]:
            cap = '<div class="cap">%s</div>' % _esc(captions[i])
        items.append('<div class="cell"><img src="%s" style="height:%dmm">%s</div>'
                     % (_img_uri(path), int(height), cap))
    if not items:
        return ""
    return ('<div class="grid" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
            % (max(int(cols), 1), "".join(items)))


def spec_table(rows: List[Any] = (), **_) -> str:
    """条件表。文章に混ぜず表にする。rows は [[項目, 内容], ...]。"""
    lines = []
    for row in rows:
        if isinstance(row, dict):
            label, value = row.get("label", ""), row.get("value", "")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            label, value = row[0], row[1]
        else:
            continue
        lines.append("<tr><th>%s</th><td>%s</td></tr>" % (_esc(label), _esc(value)))
    return '<table class="spec">%s</table>' % "".join(lines) if lines else ""


def bullets(items: List[str] = (), title: str = "", **_) -> str:
    head = '<div class="b-title">%s</div>' % _esc(title) if title else ""
    body = "".join("<li>%s</li>" % _esc(x) for x in items if str(x).strip())
    return '%s<ul class="bul">%s</ul>' % (head, body) if body else ""


def steps(items: List[str] = (), caption: str = "", **_) -> str:
    """段階図（①→②→③）。文章より伝わり、後から示す根拠にもなる。"""
    items = [x for x in items if str(x).strip()][:4]
    if len(items) < 2:
        return ""
    cells = "".join(
        '<div class="step"><span class="n">%d</span><div class="t">%s</div></div>'
        % (i, _esc(x).replace("／", "<br>"))
        for i, x in enumerate(items, start=1))
    cap = '<div class="s-cap">%s</div>' % _esc(caption) if caption else ""
    return '<div class="flow">%s<div class="steps">%s</div></div>' % (cap, cells)


def pictograms(names: List[str] = (), size: int = 200, **_) -> str:
    """禁止マークなどの記号。掲示物向け。"""
    try:
        import tools

        return tools.pictograms.svg_group(list(names), size=int(size), color="#c1272d")
    except Exception:
        return ""


def contact(lines: List[str] = (), title: str = "お問い合わせ", **_) -> str:
    body = "<br>".join(_esc(x) for x in lines if str(x).strip())
    if not body:
        return ""
    return ('<div class="contact"><div class="c-title">%s</div>'
            '<div class="c-body">%s</div></div>' % (_esc(title), body))


def blanks(labels: List[str] = (), **_) -> str:
    """手書きの記入欄。日付・担当など、その場で変わるものは印刷しない。"""
    labels = [x for x in labels if str(x).strip()][:4]
    if not labels:
        return ""
    cells = "　".join('%s <span class="blank"></span>' % _esc(x) for x in labels)
    return '<div class="blanks">%s</div>' % cells


def note(text: str = "", **_) -> str:
    return '<div class="note">%s</div>' % _esc(text) if text else ""


def spacer(size: int = 6, **_) -> str:
    return '<div style="height:%dmm"></div>' % int(size)


def hero_band(kicker: str = "", catch: str = "", **_) -> str:
    """紙面の頭。**幅いっぱいの色帯に、小さいタイトル1行＋大きいタイトル1行**。

    2行に折り返すと帯が重くなり、下の写真に使える面積が減る。
    大きいタイトルは必ず1行に収める（長ければ級数を落とす）。
    """
    if not catch and not kicker:
        return ""
    # 「／」で区切られていても1行に繋ぐ
    text = "　".join(x.strip() for x in str(catch).split("／") if x.strip())
    # A4の本文幅は約186mm≒527pt。1行に収まる級数を文字数から決める
    chars = max(len(text), 1)
    size = max(15, min(34, int(500 / chars)))
    kick = '<div class="hbd-kicker">%s</div>' % _esc(kicker) if kicker else ""
    body = ('<div class="hbd-catch" style="font-size:%dpt">%s</div>' % (size, _esc(text))
            if text else "")
    return '<div class="heroband full-bleed">%s%s</div>' % (kick, body)


def title_price_bar(title: str = "", sub: str = "", price: str = "",
                    unit: str = "円 / 月", **_) -> str:
    """**帯の中に、左＝物件名／右＝価格**。実物のチラシの定番。

    価格を独立した囲みにするより、帯に載せる方が紙面が締まる。
    """
    if not (title or price):
        return ""
    left = ('<div class="tpb-left"><div class="tpb-title">%s</div>%s</div>'
            % (_esc(title),
               '<div class="tpb-sub">%s</div>' % _esc(sub) if sub else ""))
    right = ""
    if price:
        size = 40 if len(str(price)) <= 7 else 32
        right = ('<div class="tpb-right"><span class="tpb-price" style="font-size:%dpt">'
                 '%s</span><span class="tpb-unit">%s</span></div>'
                 % (size, _esc(price), _esc(unit)))
    return '<div class="tpbar full-bleed">%s%s</div>' % (left, right)


def photo_row(paths: List[str] = (), height: int = 46, gap: int = 2, **_) -> str:
    """写真を**隙間なく横一列**に、幅いっぱいで並べる。

    余白を空けて小さく並べると弱い。ぴったり並べると1枚の絵のように見える。
    """
    cells = [p for p in list(paths)[:4] if p and Path(p).exists()]
    if not cells:
        return ""
    return ('<div class="photorow full-bleed" style="grid-template-columns:repeat(%d,1fr);'
            'gap:%dpx">%s</div>'
            % (len(cells), int(gap),
               "".join('<img src="%s" style="height:%dmm">' % (_img_uri(p), int(height))
                       for p in cells)))


def contact_bar(label: str = "ご見学・お問い合わせ", tel: str = "", company: str = "",
                address: str = "", note: str = "", qr: str = "",
                qr_label: str = "物件ページはこちら", license_no: str = "",
                trade: str = "", **_) -> str:
    """最下部の連絡先帯。**電話番号を特大**にする。

    連絡先を小さく置くと問い合わせは来ない。紙面で2番目に大きい文字にする。

    qr にURL等を渡すと、**帯の右端にQRコード**を出す（空なら出さない）。
    紙から先へ誘導する導線。作れなかった場合はQRだけ落として帯は出す
    （QRのために紙面全部を失わないため）。
    """
    if not (tel or company):
        return ""
    box = ""
    if qr:
        try:
            from tools import qr as qr_tool

            path = qr_tool.make(qr_tool.normalize_url(qr))
        except Exception:
            path = None
        if path:
            box = ('<div class="cbar-qr"><img src="%s">'
                   '<div class="cbar-qr-cap">%s</div></div>'
                   % (_img_uri(path), _esc(qr_label)))
    return ('<div class="contactbar full-bleed"><div class="cbar-inner">'
            '<div class="cbar-main">'
            '<div class="cbar-label">%s</div>'
            '<div class="cbar-tel">☎ %s</div>'
            '<div class="cbar-com">%s</div>'
            '<div class="cbar-addr">%s</div>%s%s</div>%s</div></div>'
            % (_esc(label), _esc(tel), _esc(company), _esc(address),
               '<div class="cbar-note">%s</div>' % _esc(note) if note else "",
               _license_line(license_no, trade), box))


def _license_line(license_no: str = "", trade: str = "") -> str:
    """免許番号と取引態様。

    **不動産の広告では免許番号の表示が要る**（宅建業法）。無いと配布できない。
    実際に、取引態様だけ書いて免許番号が抜けた紙面が出て、最終確認で止まった。
    値が無ければ何も出さない（架空の番号を作らないため）。
    """
    parts = []
    if trade:
        parts.append("取引態様：%s" % _esc(trade))
    if license_no:
        parts.append("免許番号：%s" % _esc(license_no))
    if not parts:
        return ""
    return '<div class="cbar-license">%s</div>' % "　／　".join(parts)


def headline_bar(catch: str = "", name: str = "", access: str = "",
                 dark: bool = True, **_) -> str:
    """上部の帯。左に大きなキャッチ、右に物件名と交通。

    日本の物件チラシの定番の頭。キャッチで足を止めさせ、物件名で何の話か示す。
    """
    right = ""
    if name or access:
        right = ('<div class="hlb-right">%s%s</div>'
                 % ('<div class="hlb-name">%s</div>' % _esc(name) if name else "",
                    '<div class="hlb-access">%s</div>' % _esc(access) if access else ""))
    size = 30 if len(str(catch)) <= 16 else (24 if len(str(catch)) <= 24 else 19)
    return ('<div class="hlbar %s"><div class="hlb-catch" style="font-size:%dpt">%s</div>'
            '%s</div>' % ("hlb-dark" if dark else "hlb-accent", size, _esc(catch), right))


def spec_highlight(items: List[Any] = (), **_) -> str:
    """間取り・面積・価格を**特大で横一列**に。チラシで一番目立たせる部分。

    items=[{"label":"間取り","value":"3LDK","unit":"","small":"62.73㎡"},
           {"label":"賃料","value":"5.9","unit":"万円"}]
    """
    cells = []
    for item in list(items)[:3]:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", ""))
        size = 44 if len(value) <= 5 else (34 if len(value) <= 8 else 26)
        cells.append(
            '<div class="sh-cell">'
            '<span class="sh-label">%s</span>'
            '<span class="sh-value" style="font-size:%dpt">%s</span>'
            '<span class="sh-unit">%s</span>%s</div>'
            % (_esc(item.get("label", "")), size, _esc(value),
               _esc(item.get("unit", "")),
               '<div class="sh-small">%s</div>' % _esc(item["small"])
               if item.get("small") else ""))
    return '<div class="spechigh">%s</div>' % "".join(cells) if cells else ""


def spec_list(rows: List[Any] = (), cols: int = 1, **_) -> str:
    """◆付きの概要リスト。表組みより密に入り、チラシらしくなる。"""
    lines = []
    for row in rows:
        if isinstance(row, dict):
            label, value = row.get("label", ""), row.get("value", "")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            label, value = row[0], row[1]
        else:
            continue
        lines.append('<li><span class="sl-label">◆ %s</span>'
                     '<span class="sl-value">%s</span></li>' % (_esc(label), _esc(value)))
    if not lines:
        return ""
    return ('<ul class="speclist" style="column-count:%d">%s</ul>'
            % (max(int(cols), 1), "".join(lines)))


def company_bar(name: str = "", lines: List[str] = (), tel: str = "", fax: str = "",
                license_no: str = "", trade: str = "", **_) -> str:
    """最下部の会社情報の帯。横一列に、社名・連絡先・免許番号・取引態様。"""
    if not any([name, tel, license_no, lines]):
        return ""
    left = '<div class="cb-name">%s</div>' % _esc(name) if name else ""
    if lines:
        left += ('<div class="cb-sub">%s</div>'
                 % "　".join(_esc(x) for x in lines if str(x).strip()))
    if license_no:
        left += '<div class="cb-sub">%s</div>' % _esc(license_no)
    middle = ""
    if tel or fax:
        middle = ('<div class="cb-tel">%s%s</div>'
                  % ("TEL %s" % _esc(tel) if tel else "",
                     "<br>FAX %s" % _esc(fax) if fax else ""))
    right = ('<div class="cb-trade"><div class="cb-trade-l">取引態様</div>'
             '<div class="cb-trade-v">%s</div></div>' % _esc(trade)) if trade else ""
    return ('<div class="combar"><div class="cb-left">%s</div>%s%s</div>'
            % (left, middle, right))


def columns(left: List[Any] = (), right: List[Any] = (), ratio: str = "1fr 1fr",
            **_) -> str:
    """左右に分けて、それぞれに部品を積む。比率を指定できる（例 "1fr 2fr"）。"""
    def build(items):
        out = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            func = BLOCKS.get(str(item.get("block", "")))
            if func:
                try:
                    out.append(func(**{k: v for k, v in item.items() if k != "block"}))
                except Exception:
                    continue
        return "".join(out)

    return ('<div class="cols2" style="grid-template-columns:%s">'
            '<div>%s</div><div>%s</div></div>'
            % (_esc(ratio), build(left), build(right)))


def full_photo(path: str = "", title: str = "", sub: str = "", height: int = 120,
               align: str = "bottom", **_) -> str:
    """**全面写真に文字を重ねる。** PRチラシで一番強い見せ方。

    小さい写真を等間隔に並べた紙面は、それだけで安っぽく見える。
    一番良い1枚を大きく敷いて、その上にキャッチを載せると印象が変わる。
    """
    if not path or not Path(path).exists():
        return catch(text=title, note=sub)
    overlay = ""
    if title or sub:
        overlay = ('<div class="fp-text"><div class="fp-title">%s</div>%s</div>'
                   % (_esc(title),
                      '<div class="fp-sub">%s</div>' % _esc(sub) if sub else ""))
    return ('<div class="fullphoto fp-%s" style="height:%dmm">'
            '<img src="%s">%s</div>'
            % (_esc(align), int(height), _img_uri(path), overlay))


def lifestyle(items: List[Any] = (), title: str = "", **_) -> str:
    """暮らしのシーンを提案する。写真＋短い一言を横に並べる。

    「3LDK・ロフト付き」ではなく「ロフトは趣味の部屋に」と書くための部品。
    条件の羅列を、住んだあとの情景に変換する。
    """
    cells = []
    for item in list(items)[:4]:
        if not isinstance(item, dict):
            continue
        path = item.get("path") or ""
        image = ('<img src="%s">' % _img_uri(path)
                 if path and Path(path).exists() else "")
        cells.append('<div class="ls-cell">%s<div class="ls-t">%s</div>'
                     '<div class="ls-n">%s</div></div>'
                     % (image, _esc(item.get("title", "")), _esc(item.get("text", ""))))
    if not cells:
        return ""
    head = '<div class="b-title">%s</div>' % _esc(title) if title else ""
    return ('%s<div class="lifestyle" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
            % (head, len(cells), "".join(cells)))


def big_catch(text: str = "", sub: str = "", **_) -> str:
    """特大のキャッチ。紙面の主張を1行で立てる。"""
    if not text:
        return ""
    length = len(str(text))
    size = 46 if length <= 12 else (36 if length <= 20 else 28)
    return ('<div class="bigcatch" style="font-size:%dpt">%s</div>%s'
            % (size, _esc(text),
               '<div class="bc-sub">%s</div>' % _esc(sub) if sub else ""))


def cta(text: str = "", lines: List[str] = (), note: str = "", **_) -> str:
    """行動を促す枠。連絡先を書くだけでは人は動かない。"""
    body = "<br>".join(_esc(x) for x in lines if str(x).strip())
    return ('<div class="cta"><div class="cta-t">%s</div>'
            '<div class="cta-b">%s</div>%s</div>'
            % (_esc(text or "まずはお気軽にお問い合わせください"), body,
               '<div class="cta-n">%s</div>' % _esc(note) if note else ""))


def hero_pair(left_photo: str = "", right_photo: str = "", left_caption: str = "外観",
              right_caption: str = "間取り", height: int = 72,
              left_fit: str = "cover", right_fit: str = "contain", **_) -> str:
    """写真を2枚、左右に大きく並べる。**マイソクの核心**。

    不動産チラシは「外観」と「間取り図」を大きく並べるのが定番で、
    これが小さいと物件チラシに見えない（小さい写真を並べただけの紙面になる）。
    片方しか無ければ、あるほうを幅いっぱいに使う。
    """
    cells = []
    # 右は既定で間取り図。**図面は切らない**（切ると1階しか映らない等が起きる。実際に踏んだ）
    for path, cap, fit in ((left_photo, left_caption, left_fit),
                           (right_photo, right_caption, right_fit)):
        if path and Path(path).exists():
            if str(fit) == "contain":
                cells.append('<div class="hp-cell contain">'
                             '<img src="%s" style="height:%dmm">'
                             '<div class="cap">%s</div></div>'
                             % (_img_uri(_trim_margins(path)), int(height), _esc(cap)))
            else:
                cells.append('<div class="hp-cell"><img src="%s" style="height:%dmm">'
                             '<div class="cap">%s</div></div>'
                             % (_img_uri(path), int(height), _esc(cap)))
    if not cells:
        return ""
    if len(cells) == 1:
        return '<div class="hero">%s</div>' % cells[0]
    return '<div class="hpair">%s</div>' % "".join(cells)


def point_row(items: List[Any] = (), **_) -> str:
    """推しポイントを横に並べる。**番号は振らない**。

    工程用の steps（①→②→③）で代用すると、順番の意味が無いのに番号と矢印が付き、
    読み手に「順にやること」と誤解させる（実際にそう見えて指摘された）。
    順序のないものは順序のない見せ方にする。
    """
    cells = []
    for item in list(items)[:3]:
        if isinstance(item, dict):
            title, text = item.get("title", ""), item.get("text", "")
        else:
            parts = str(item).split("｜")
            title, text = parts[0], (parts[1] if len(parts) > 1 else "")
        if not (title or text):
            continue
        cells.append('<div class="pt-cell"><div class="pt-title">%s</div>'
                     '<div class="pt-text">%s</div></div>'
                     % (_esc(title), _esc(text)))
    if not cells:
        return ""
    return '<div class="pointrow">%s</div>' % "".join(cells)


def price_box(rent: str = "", unit: str = "万円", label: str = "賃料",
              details: List[Any] = (), **_) -> str:
    """賃料を囲みで大きく＋その周りに管理費・敷礼を small で。マイソクの定番。"""
    if not rent:
        return ""
    chips = ""
    if details:
        parts = []
        for row in details:
            if isinstance(row, dict):
                parts.append("%s %s" % (row.get("label", ""), row.get("value", "")))
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                parts.append("%s %s" % (row[0], row[1]))
            else:
                parts.append(str(row))
        chips = ('<div class="pb-details">%s</div>'
                 % "　／　".join(_esc(x) for x in parts))
    return ('<div class="pricebox"><span class="pb-label">%s</span>'
            '<span class="pb-main">%s</span><span class="pb-unit">%s</span>%s</div>'
            % (_esc(label), _esc(rent), _esc(unit), chips))


def spec_two_col(rows: List[Any] = (), **_) -> str:
    """物件概要を2列で密に並べる。項目が多いマイソク向け。"""
    cleaned = []
    for row in rows:
        if isinstance(row, dict):
            cleaned.append((row.get("label", ""), row.get("value", "")))
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            cleaned.append((row[0], row[1]))
    if not cleaned:
        return ""
    half = (len(cleaned) + 1) // 2
    def build(items):
        return "".join("<tr><th>%s</th><td>%s</td></tr>" % (_esc(a), _esc(b))
                       for a, b in items)
    return ('<div class="spec2"><table class="spec">%s</table>'
            '<table class="spec">%s</table></div>'
            % (build(cleaned[:half]), build(cleaned[half:])))


def map_note(path: str = "", text: str = "", height: int = 42, **_) -> str:
    """地図。画像があれば載せ、無ければ所在地の文章だけ。"""
    if path and Path(path).exists():
        return ('<div class="mapb"><img src="%s" style="height:%dmm">%s</div>'
                % (_img_uri(path), int(height),
                   '<div class="cap">%s</div>' % _esc(text) if text else ""))
    return '<div class="note">%s</div>' % _esc(text) if text else ""


def icon_row(items: List[Any] = (), accent: str = "", cols: int = 6, **_) -> str:
    """物件の特色を**アイコン付き**で並べる。

    文字だけのタグ（badge_row）は読み飛ばされる。絵が付くと目に留まり、
    離れていても何の設備か分かる。マイソク・チラシで実際に使われている形。

    アイコンが見つからない項目は**文字だけ**で出す。無理に似た絵を当てない
    （「浴室乾燥機」に「浴室」の絵を出すと、書いていない設備を語ることになる）。
    """
    words = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not words:
        return ""
    try:
        from tools import feature_icons

        found = {x["label"]: x["path"] for x in feature_icons.match_all(words)}
    except Exception:
        found = {}
    cells = []
    for word in words[:12]:
        path = found.get(word)
        if path and accent:
            try:
                from tools import feature_icons

                path = feature_icons.recolor(path, accent)
            except Exception:
                pass
        img = ('<img src="%s">' % _img_uri(path)) if path and Path(path).exists() else ""
        cells.append('<div class="ficon">%s<div class="ficon-t">%s</div></div>'
                     % (img, _esc(word)))
    return ('<div class="iconrow" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
            % (max(int(cols or 6), 2), "".join(cells)))


def badge_row(items: List[str] = (), style: str = "outline", **_) -> str:
    """条件バッジを並べる。

    style="outline"（白地に枠線・既定）は紙面が軽くなり、写真の邪魔をしない。
    style="fill"（色で塗る）は強いが、多用すると重くなる。
    """
    items = [str(x).strip() for x in items if str(x).strip()][:8]
    if not items:
        return ""
    css = "badge-fill" if str(style) == "fill" else "badge-outline"
    return ('<div class="badges">%s</div>'
            % "".join('<span class="badge %s">%s</span>' % (css, _esc(x))
                      for x in items))


def ribbon(text: str = "", **_) -> str:
    """「新着」「即入居可」などの帯。紙面の角に置く強い一言。"""
    return '<div class="ribbon">%s</div>' % _esc(text) if text else ""


def photo_split(path: str = "", title: str = "", items: List[str] = (),
                reverse: bool = False, height: int = 52, **_) -> str:
    """写真とテキストを左右に並べる。設備や周辺環境の説明に向く。"""
    if not path or not Path(path).exists():
        return bullets(items=items, title=title)
    body = "".join("<li>%s</li>" % _esc(x) for x in items if str(x).strip())
    text = ('<div class="sp-text">%s<ul class="bul">%s</ul></div>'
            % ('<div class="b-title">%s</div>' % _esc(title) if title else "", body))
    image = ('<div class="sp-img"><img src="%s" style="height:%dmm"></div>'
             % (_img_uri(path), int(height)))
    order = [text, image] if reverse else [image, text]
    return '<div class="split">%s</div>' % "".join(order)


def illust_point(path: str = "", text: str = "", note: str = "",
                 height: int = 30, **_) -> str:
    """イラスト＋一言。フリー素材（いらすとや等）を活かす部品。

    素材が無ければ文字だけで成立するので、素材の有無で紙面が壊れない。
    """
    image = ('<img src="%s" style="height:%dmm">' % (_img_uri(path), int(height))
             if path and Path(path).exists() else "")
    return ('<div class="ipoint">%s<div class="ip-text"><b>%s</b>%s</div></div>'
            % (image, _esc(text),
               '<div class="ip-note">%s</div>' % _esc(note) if note else ""))


def timeline(items: List[str] = (), caption: str = "", **_) -> str:
    """入居までの流れなど、縦に並べる手順。steps より項目が多いとき。"""
    items = [str(x).strip() for x in items if str(x).strip()][:6]
    if len(items) < 2:
        return ""
    rows = "".join('<li><span class="tl-n">%d</span>%s</li>' % (i, _esc(x))
                   for i, x in enumerate(items, start=1))
    cap = '<div class="s-cap">%s</div>' % _esc(caption) if caption else ""
    return '<div class="flow">%s<ul class="timeline">%s</ul></div>' % (cap, rows)


def voice(text: str = "", who: str = "", **_) -> str:
    """お客様の声。**実際に聞いた声だけ**。作り話は書かないこと。"""
    if not text:
        return ""
    return ('<div class="voice">「%s」<div class="v-who">%s</div></div>'
            % (_esc(text), _esc(who)))


def two_column(left: List[Any] = (), right: List[Any] = (), **_) -> str:
    """2段組み。条件表と写真を横に並べたいときなど。"""
    def build(items):
        out = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            func = BLOCKS.get(str(item.get("block", "")))
            if func:
                try:
                    out.append(func(**{k: v for k, v in item.items() if k != "block"}))
                except Exception:
                    continue
        return "".join(out)

    return '<div class="cols"><div>%s</div><div>%s</div></div>' % (build(left), build(right))


BLOCKS = {
    "hero_band": hero_band, "title_price_bar": title_price_bar,
    "photo_row": photo_row, "contact_bar": contact_bar,
    "headline_bar": headline_bar, "spec_highlight": spec_highlight,
    "spec_list": spec_list, "company_bar": company_bar, "columns": columns,
    "full_photo": full_photo, "lifestyle": lifestyle, "big_catch": big_catch,
    "cta": cta,
    "hero_pair": hero_pair, "price_box": price_box, "point_row": point_row, "spec_two_col": spec_two_col,
    "map_note": map_note,
    "badge_row": badge_row, "icon_row": icon_row, "ribbon": ribbon, "photo_split": photo_split,
    "illust_point": illust_point, "timeline": timeline, "voice": voice,
    "two_column": two_column,
    "header_band": header_band, "catch": catch, "price": price,
    "photo_hero": photo_hero, "photo_grid": photo_grid, "spec_table": spec_table,
    "bullets": bullets, "steps": steps, "pictograms": pictograms,
    "contact": contact, "blanks": blanks, "note": note, "spacer": spacer,
}


def describe_for_prompt() -> str:
    """LLMに渡す部品の説明。ここに書いたものだけ使わせる。"""
    return """使える部品（この中から選んで並べます。CSSは書かないでください）:
- header_band {title, sub}            … 色帯の見出し。紙面の一番上
- catch {text, note}                  … 一番言いたい一言。最も大きい文字
- price {main, unit, note}            … 価格・賃料を大きく（例 main:"5.9", unit:"万円"）
- photo_hero {photo, caption, height} … 主役の写真1枚（photoは番号。height=mm）
- photo_grid {photos, cols, captions, height} … 写真を並べる（photosは番号の配列）
- spec_table {rows}                   … 条件表。rows=[["間取り","3LDK"],...]
- bullets {title, items}              … 箇条書き
- steps {caption, items}              … 段階図①→②→③（「／」で改行）
- pictograms {names}                  … 記号（no_bicycle / no_parking / no_entry など）
- contact {title, lines}              … 連絡先
- blanks {labels}                     … 手書きの記入欄（例 ["掲示日","担当"]）
- note {text}                         … 小さい注記
- hero_band {kicker, catch}           … **紙面の頭の色帯**。kickerは小さい前置き、
    catchは大きな2行（「／」で改行）。例 catch:"大阪から1時間。／ログハウスを、借りる。"
- title_price_bar {title, sub, price, unit} … **帯に左＝物件名／右＝価格**。
    例 title:"加東市秋津 ログハウス 3LDK", sub:"敷金・礼金なし", price:"59,000"
- photo_row {photos, height, gap}     … 写真を**隙間なく横一列・幅いっぱい**に
- contact_bar {label, tel, company, address, note} … 最下部の連絡先帯。**電話が特大**
- headline_bar {catch, name, access, dark} … 上部の帯。左に大きなキャッチ、右に物件名
- spec_highlight {items}              … 間取り・面積・価格を**特大で横一列**。
    items=[{"label":"間取り","value":"3LDK","small":"62.73㎡"},
           {"label":"賃料","value":"5.9","unit":"万円"}]
- spec_list {rows, cols}              … ◆付きの概要リスト（表より密。cols=2で2段組み）
- company_bar {name, lines, tel, fax, license_no, trade} … 最下部の会社情報の帯
- columns {left, right, ratio}        … 左右分割。各側に部品の配列。
    ratio="1fr 2fr" のように比率指定（左に写真・右に間取り図など）
- full_photo {photo, title, sub, height, align} … **全面写真に文字を重ねる**。
    PRチラシで一番強い。一番良い写真をここに（height=100〜130mm）
- big_catch {text, sub}               … 特大のキャッチ。暮らしの情景を1行で
- lifestyle {title, items}            … 暮らしのシーン提案。
    items=[{"photo":3,"title":"朝の時間","text":"木漏れ日のLDKで"}] を3つ程度
- cta {text, lines, note}             … 行動を促す枠（内見予約・お電話）。
    連絡先を書くだけでは人は動かない
- hero_pair {left_photo, right_photo, left_caption, right_caption, height}
    … **写真2枚を左右に大きく**。物件チラシは「外観＋間取り図」をここに置くのが定番
- price_box {label, rent, unit, details} … 賃料を囲みで大きく
- point_row {items:[{title,text}]}   … 推しポイントを3つ横並び（番号なし）
    （details=[["管理費","なし"],["敷金","0円"]] を下に小さく並べる）
- spec_two_col {rows}                 … 物件概要を2列で密に（項目が多いとき）
- map_note {photo, text}              … 地図（写真番号）。無ければ所在地の文章
- badge_row {items}                   … 条件バッジを並べる（例 ["敷金0円","駐車場込み"]）
- ribbon {text}                       … 「新着」「即入居可」などの強い一言の帯
- photo_split {photo, title, items, reverse, height} … 写真とテキストを左右に
- illust_point {photo, text, note}    … イラスト＋一言（フリー素材を活かす）
- timeline {caption, items}           … 縦の手順（入居までの流れなど。5〜6項目向き）
- voice {text, who}                   … お客様の声。**実際に聞いた声だけ**
- two_column {left, right}            … 2段組み。left/rightに部品の配列を入れる
- spacer {size}                       … 余白（mm）"""


# --- 組み立て ---------------------------------------------------------------

BASE_CSS = """
/* チラシ・掲示物は**1枚で完結するもの**。2ページ目ができてはいけない。
   html/body の両方に高さと overflow を効かせ、改ページを起こさせない。 */
@page{{margin:0;size:{w} {h}}}
{footfill}
*{{box-sizing:border-box}}
html{{height:{h};overflow:hidden}}
body{{margin:0;width:{w};height:{h};font-family:{font};color:#15181d;background:#fff;
 display:flex;flex-direction:column;overflow:hidden;page-break-after:avoid}}
/* .body に overflow:hidden を付けてはいけない。**縮小する前に切り取られる**ため、
   自動フィットが効かず下が消える（実際に踏んだ）。切り取りは紙面(body)側だけで行う。 */
.body{{flex:1;padding:{pad};display:flex;flex-direction:column;
 justify-content:flex-start}}
/* **flex-shrink を止める。** これが無いと、中身が増えたときに固定高さの写真が
   0まで押し潰されて**写真だけが消える**（実際に外観写真が消えた）。
   しかも潰れたぶん「収まっている」と誤判定され、自動縮小も効かなくなる。 */
.body > *{{flex:0 0 auto}}
/* --- 紙面を最後まで使い切る ------------------------------------------------
   中身を積んでから全体を伸縮させる方式だと、拡大するほど段が狭くなって
   文字の折り返しが増え、どこかで頭打ちになる（実測で95.6%で止まり、
   帯の下に何も無い面が残った）。

   そこで**余った高さは写真が受け取る**。文字・表・帯は伸ばさない
   （級数が変わると読みづらくなり、帯だけ厚くなると間が抜けて見えるため）。
   flex-shrink は 0 のままにする。縮む側を許すと写真が0まで潰れる（実際に潰れた）。 */
.body > .fullphoto, .body > .hero, .body > .photorow{{flex:1 0 auto}}
.body > .fullphoto img, .body > .hero img{{height:100% !important}}
.body > .photorow img{{height:100% !important}}
.body > .photorow{{align-items:stretch}}
/* 図面だけは伸ばさない。縦横比が変わると図が読めなくなる */
.body > .hero.contain{{flex:0 0 auto}}
.band{{background:{accent};color:#fff;text-align:center;padding:10mm 8mm 8mm}}
.band h1{{margin:0;font-weight:900;line-height:1.1;letter-spacing:.06em;
 word-break:auto-phrase;text-wrap:balance}}
.hb-sub{{margin-top:4mm;font-size:13pt;letter-spacing:.18em;opacity:.94}}
.catch{{font-weight:900;color:{accent};text-align:center;line-height:1.35;margin:4mm 0;
 word-break:auto-phrase;text-wrap:balance}}
.catch-note{{text-align:center;font-size:13pt;color:#5a616b;margin-top:2mm}}
.price{{text-align:center;margin:3mm 0}}
.p-main{{font-size:56pt;font-weight:900;color:{accent};line-height:1}}
.p-unit{{font-size:22pt;font-weight:900;color:{accent};margin-left:2mm}}
.p-note{{font-size:13pt;color:#5a616b;margin-top:2mm}}
.hero{{text-align:center;margin:3mm 0}}
.hero img{{width:100%;object-fit:cover;border-radius:2mm}}
/* 図面・地図は切らずに全体を見せる。切ると資料として成立しない */
.hero.contain img{{object-fit:contain;background:#fff;border-radius:0;width:100%;max-width:100%}}
.grid{{display:grid;gap:3mm;margin:3mm 0}}
.grid .cell img{{width:100%;object-fit:cover;border-radius:1.5mm;display:block}}
.cap{{font-size:10pt;color:#6b727c;margin-top:1mm;text-align:center}}
.spec{{width:100%;border-collapse:collapse;margin:1mm 0;font-size:13pt}}
/* 行の高さは詰める。条件表が縦に伸びると、写真に使える面積が減る */
.spec th{{background:#f2f4f7;text-align:left;padding:0.9mm 3mm;width:30mm;
 font-weight:700;border-bottom:1px solid #dfe3e8;white-space:nowrap;line-height:1.35}}
.spec td{{padding:0.9mm 3mm;border-bottom:1px solid #dfe3e8;line-height:1.25}}
.b-title{{font-size:14pt;font-weight:700;color:{accent};margin:3mm 0 1mm}}
.bul{{margin:0 0 2mm;padding-left:5mm;font-size:13pt;line-height:1.9}}
.flow{{background:#f5f6f8;border-radius:3mm;padding:5mm 4mm 4mm;margin:3mm 0}}
.s-cap{{text-align:center;font-size:12pt;font-weight:700;color:{accent};margin-bottom:3mm;
 letter-spacing:.06em}}
.steps{{display:flex;justify-content:space-between}}
.step{{flex:1;text-align:center;position:relative;padding:0 2mm}}
.step .n{{display:inline-block;width:10mm;height:10mm;line-height:10mm;border-radius:50%;
 background:{accent};color:#fff;font-size:14pt;font-weight:900}}
.step .t{{margin-top:2mm;font-size:12pt;font-weight:700;line-height:1.45}}
.step:not(:last-child):after{{content:"";position:absolute;right:-1.5mm;top:4mm;width:0;height:0;
 border-left:3mm solid #b9bec6;border-top:2mm solid transparent;border-bottom:2mm solid transparent}}
.contact{{border:2px solid {accent};border-radius:2mm;padding:4mm;margin:3mm 0;text-align:center}}
.c-title{{font-size:12pt;font-weight:700;color:{accent};letter-spacing:.08em}}
.c-body{{font-size:15pt;font-weight:700;margin-top:2mm;line-height:1.7}}
.blanks{{font-size:12pt;color:#4a5058;margin:3mm 0;line-height:2.3}}
.blank{{display:inline-block;border-bottom:1px solid #98a0aa;min-width:42mm}}
.note{{font-size:10.5pt;color:#6b727c;line-height:1.7;margin:2mm 0}}
/* 特色アイコン。絵と文字を縦に組み、等幅で並べる */
.iconrow{{display:grid;gap:3mm 2mm;margin:3mm 0;justify-items:center}}
.ficon{{text-align:center;width:100%}}
.ficon img{{width:13mm;height:13mm;object-fit:contain;display:block;margin:0 auto 1.2mm}}
.ficon-t{{font-size:9.5pt;font-weight:700;line-height:1.3;color:#2b313a;
 word-break:auto-phrase}}
.badges{{display:flex;flex-wrap:wrap;gap:2mm;justify-content:center;margin:3mm 0}}
.badge{{background:{accent};color:#fff;border-radius:1.5mm;padding:1.6mm 3.2mm;
 font-size:12pt;font-weight:700}}
.ribbon{{display:inline-block;background:#1f2a37;color:#fff;font-size:12pt;font-weight:700;
 padding:1.6mm 4mm;border-radius:1mm;letter-spacing:.08em}}
.split{{display:flex;gap:4mm;align-items:center;margin:3mm 0}}
.split .sp-img{{flex:0 0 46%}}
.split .sp-img img{{width:100%;object-fit:cover;border-radius:1.5mm;display:block}}
.split .sp-text{{flex:1}}
.ipoint{{display:flex;gap:3mm;align-items:center;margin:2.5mm 0}}
.ipoint img{{flex:0 0 auto}}
.ip-text{{font-size:13.5pt;line-height:1.6}}
.ip-note{{font-size:11pt;color:#6b727c;margin-top:1mm}}
.timeline{{margin:0;padding:0;list-style:none;font-size:12.5pt;line-height:1.9}}
.timeline li{{display:flex;gap:2.5mm;align-items:flex-start;margin-bottom:1.5mm}}
.tl-n{{flex:0 0 auto;width:6.5mm;height:6.5mm;line-height:6.5mm;border-radius:50%;
 background:{accent};color:#fff;font-size:11pt;font-weight:900;text-align:center}}
.voice{{background:#f7f8fa;border-left:3mm solid {accent};padding:3mm 4mm;margin:3mm 0;
 font-size:12.5pt;line-height:1.75}}
.v-who{{font-size:11pt;color:#6b727c;margin-top:1.5mm;text-align:right}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:4mm;margin:2mm 0}}
.hpair{{display:grid;grid-template-columns:1fr 1fr;gap:3mm;margin:3mm 0}}
.hpair .hp-cell img{{width:100%;object-fit:cover;border-radius:1.5mm;display:block}}
.hpair .hp-cell.contain img{{object-fit:contain;background:#fff;border-radius:0}}
.pointrow{{display:grid;grid-template-columns:repeat(3,1fr);gap:0 4mm;margin:3mm 0}}
.pt-cell{{border-top:0.8mm solid {accent};padding:2.5mm 1mm 0}}
.pt-title{{font-size:13pt;font-weight:900;color:{ink};line-height:1.35;
 margin-bottom:1mm;word-break:auto-phrase}}
.pt-text{{font-size:11pt;color:#4a5058;line-height:1.5;word-break:auto-phrase}}
.pricebox{{border:1.2mm solid {accent};border-radius:2mm;padding:4mm 5mm;margin:3mm 0;
 text-align:center;background:#fff8f8;white-space:nowrap}}
.pb-label{{font-size:13pt;font-weight:700;color:{accent};margin-right:3mm;
 vertical-align:middle}}
.pb-main{{font-size:40pt;font-weight:900;color:{accent};line-height:1;
 vertical-align:middle}}
.pb-unit{{font-size:16pt;font-weight:900;color:{accent};margin-left:1mm}}
.pb-details{{white-space:normal}}
.pb-details{{font-size:12pt;color:#4a5058;margin-top:2mm}}
.spec2{{display:grid;grid-template-columns:1fr 1fr;gap:0 4mm;margin:3mm 0}}
.spec2 .spec{{margin:0;font-size:11.5pt}}
.spec2 .spec th{{width:26mm;padding:1.8mm 2.4mm}}
.spec2 .spec td{{padding:1.8mm 2.4mm}}
.mapb{{text-align:center;margin:3mm 0}}
.mapb img{{width:100%;object-fit:cover;border-radius:1.5mm}}
.fullphoto{{position:relative;width:100%;overflow:hidden;border-radius:2mm;margin:3mm 0}}
.fullphoto img{{width:100%;height:100%;object-fit:cover;display:block}}
.fp-text{{position:absolute;left:0;right:0;padding:6mm 8mm;color:#fff}}
.fp-bottom .fp-text{{bottom:0;background:linear-gradient(transparent,rgba(0,0,0,.62))}}
.fp-top .fp-text{{top:0;background:linear-gradient(rgba(0,0,0,.62),transparent)}}
.fp-title{{font-size:26pt;font-weight:900;line-height:1.3;word-break:auto-phrase;
 text-wrap:balance;text-shadow:0 1mm 2mm rgba(0,0,0,.35)}}
.fp-sub{{font-size:13pt;margin-top:2mm;opacity:.95}}
.bigcatch{{font-weight:900;color:{accent};text-align:center;line-height:1.35;margin:4mm 0 1mm;
 word-break:auto-phrase;text-wrap:balance;letter-spacing:.01em}}
.bc-sub{{text-align:center;font-size:13pt;color:#5a616b;margin-bottom:3mm}}
.lifestyle{{display:grid;gap:3mm;margin:3mm 0}}
.ls-cell{{text-align:center}}
.ls-cell img{{width:100%;height:30mm;object-fit:cover;border-radius:1.5mm;display:block}}
.ls-t{{font-size:13pt;font-weight:700;color:{accent};margin-top:2mm}}
.ls-n{{font-size:11.5pt;color:#4a5058;line-height:1.6;margin-top:1mm}}
.cta{{background:{accent};color:#fff;border-radius:2mm;padding:5mm;margin:3mm 0;
 text-align:center}}
.cta-t{{font-size:17pt;font-weight:900;letter-spacing:.04em}}
.cta-b{{font-size:16pt;font-weight:700;margin-top:2mm;line-height:1.6}}
.cta-n{{font-size:11pt;margin-top:2mm;opacity:.92}}
.hlbar{{display:flex;align-items:center;justify-content:space-between;gap:4mm;
 padding:4mm 6mm;margin:0 0 3mm}}
.hlb-dark{{background:#3a3a3a;color:#fff}}
.hlb-accent{{background:{accent};color:#fff}}
.hlb-catch{{font-weight:900;line-height:1.2;word-break:auto-phrase;text-wrap:balance}}
.hlb-right{{text-align:right;flex:0 0 auto}}
.hlb-name{{background:#fff;color:#222;font-size:15pt;font-weight:900;padding:1.4mm 4mm;
 border-radius:1mm;letter-spacing:.04em}}
.hlb-access{{font-size:12pt;margin-top:1.5mm;letter-spacing:.08em}}
.spechigh{{display:flex;align-items:flex-end;justify-content:center;gap:8mm;
 margin:2mm 0 3mm;flex-wrap:wrap}}
.sh-cell{{display:flex;align-items:flex-end;gap:1.5mm}}
.sh-label{{background:{accent};color:#fff;font-size:11pt;font-weight:700;
 padding:1.2mm 2.4mm;border-radius:8mm;margin-bottom:2mm;white-space:nowrap}}
.sh-value{{font-weight:900;color:{accent};line-height:.95;letter-spacing:-.01em}}
.sh-unit{{font-size:14pt;font-weight:900;color:{accent};margin-bottom:1.5mm}}
.sh-small{{font-size:11pt;color:#5a616b;margin-bottom:2mm;margin-left:1mm}}
.speclist{{margin:2mm 0;padding:0;list-style:none;font-size:10.5pt;line-height:1.85;
 column-gap:6mm}}
.speclist li{{break-inside:avoid;display:flex;gap:2mm}}
.sl-label{{flex:0 0 auto;font-weight:700;color:#333a46;white-space:nowrap}}
.sl-value{{color:#15181d}}
.combar{{display:flex;align-items:center;gap:5mm;background:{accent};color:#fff;
 padding:4mm 6mm;margin:3mm -12mm -10mm}}
.cb-left{{flex:1}}
.cb-name{{font-size:15pt;font-weight:900;letter-spacing:.02em}}
.cb-sub{{font-size:9.5pt;opacity:.92;margin-top:1mm}}
.cb-tel{{font-size:15pt;font-weight:900;line-height:1.4;white-space:nowrap}}
.cb-trade{{border:1px solid rgba(255,255,255,.7);border-radius:1mm;padding:1.5mm 3mm;
 text-align:center;flex:0 0 auto}}
.cb-trade-l{{font-size:8.5pt;opacity:.9}}
.cb-trade-v{{font-size:13pt;font-weight:900}}
.cols2{{display:grid;gap:4mm;margin:2mm 0;align-items:start}}
/* full-bleed: 紙面の端まで届かせる。余白の内側に置くと写真も帯も弱く見える */
.full-bleed{{margin-left:-{padx};margin-right:-{padx};width:calc(100% + {padx} + {padx})}}
.heroband{{background:{accent};color:{ink};padding:6mm {padx} 7mm;margin-top:-{pady}}}
.hbd-kicker{{font-size:11.5pt;font-weight:700;opacity:.85;margin-bottom:2mm}}
.hbd-catch{{font-weight:900;line-height:1.25;letter-spacing:.01em;
 white-space:nowrap;overflow:hidden}}
.tpbar{{background:{ink};color:#fff;display:flex;align-items:center;
 justify-content:space-between;gap:5mm;padding:4mm {padx}}}
.tpb-title{{font-size:17pt;font-weight:900;letter-spacing:.01em}}
.tpb-sub{{font-size:10.5pt;opacity:.85;margin-top:1.2mm}}
.tpb-right{{white-space:nowrap}}
.tpb-price{{font-weight:900;color:{onink};line-height:1;letter-spacing:-.01em}}
.tpb-unit{{font-size:13pt;font-weight:700;margin-left:1.5mm}}
.photorow{{display:grid}}
.photorow img{{width:100%;object-fit:cover;display:block}}
.badge-outline{{background:#fff;color:{accent};border:0.5mm solid {accent}}}
.badge-fill{{background:{accent};color:#fff;border:0.5mm solid {accent}}}
/* margin-top:auto を付けてはいけない。flexで残りの余白を食い尽くし、
   紙面が常に溢れ判定になり、しかも自分自身が紙面外へ押し出される（実際に消えた）。 */
/* 帯で終わるなら下の余白は要らない。紙の端まで届かせる */
.contactbar{{background:{ink};color:#fff;padding:6mm {padx} 7mm;
 margin-bottom:-{pady};margin-top:2mm}}
/* QRは帯の右端。左の連絡先が主で、QRは従。QRが無いときは左が全幅を使う */
.cbar-inner{{display:flex;align-items:center;gap:6mm}}
.cbar-main{{flex:1;min-width:0}}
.cbar-qr{{flex:0 0 auto;text-align:center}}
.cbar-qr img{{width:26mm;height:26mm;display:block;background:#fff;padding:1.5mm;
 border-radius:1mm}}
.cbar-qr-cap{{font-size:8.5pt;opacity:.9;margin-top:1.2mm;white-space:nowrap}}
.cbar-label{{font-size:11pt;opacity:.85}}
.cbar-tel{{font-size:34pt;font-weight:900;color:{onink};line-height:1.15;
 letter-spacing:.02em}}
.cbar-com{{font-size:13pt;font-weight:900;margin-top:1.5mm}}
.cbar-addr{{font-size:10pt;opacity:.85;margin-top:1mm}}
.cbar-note{{font-size:9.5pt;opacity:.75;margin-top:1.5mm}}
/* 免許番号は法定表示。小さくてよいが必ず載せる */
.cbar-license{{font-size:9pt;opacity:.8;margin-top:1.8mm;letter-spacing:.02em}}
"""

PAPER_MM = {"A4": ("210mm", "297mm"), "A4_landscape": ("297mm", "210mm"),
            "A3": ("297mm", "420mm")}


def render_page(layout: List[Dict[str, Any]], photos: List[str] = (),
                accent: str = "#c1272d", paper: str = "A4",
                padding: str = "10mm 12mm", ink: str = "#1b2a4a") -> str:
    """部品の並び（layout）からHTMLを組む。

    layout は [{"block": "catch", "text": "…"}, ...] の配列。
    写真は番号（1始まり）で指定させ、ここで実ファイルに解決する。
    知らない部品名は黙って飛ばす（1つの誤りで紙面全部を失わないため）。
    """
    try:
        from tools import fonts_lib

        face = fonts_lib.face_css("Noto Sans JP")
        font = fonts_lib.stack("Noto Sans JP")
    except Exception:
        face, font = "", "'Hiragino Sans','Yu Gothic',sans-serif"

    # 用紙名は大文字・小文字を問わない（"A4_LANDSCAPE" でも "A4_landscape" でも同じ）
    sizes = {k.lower(): v for k, v in PAPER_MM.items()}
    width, height = sizes.get(str(paper).lower(), PAPER_MM["A4"])
    parts = str(padding).split()
    pady, padx = (parts + parts)[:2] if len(parts) >= 2 else (padding, padding)
    # 最後が帯（全幅の色面）なら、下に余白を残さず紙の端まで届かせる
    last = (layout or [])[-1] if layout else None
    footfill = ""
    if isinstance(last, dict) and str(last.get("block")) in (
            "contact_bar", "company_bar", "cta"):
        padding = "%s %s 0mm" % (pady, padx)
        # **紙の地色を帯と同じ色にする。**
        # 自動フィットは文字の折り返しの都合で1〜2mm の誤差が残る。白い紙だと
        # その誤差が帯の下に白い線として出てしまう。地色を合わせれば見えない。
        color = accent if str(last.get("block")) == "cta" else ink
        # **最後の帯を、そのまま紙の下端まで伸ばす。**
        # 自動フィットは文字の折り返しの都合で数mmの誤差が残り、白い紙だと
        # 帯の下に白い線が出る。紙の下端に固定して塗る方法だと、隙間が大きい型で
        # 帯だけが宙に浮いて見えた（左右分割の型で実際にそうなった）。
        # 帯の直下に同じ色を継ぎ足せば、隙間の大小にかかわらず自然につながる。
        # はみ出した分は紙面(body)の overflow:hidden で切れる。
        footfill = (".body > *:last-child{position:relative}"
                    ".body > *:last-child::after{content:\"\";position:absolute;"
                    "left:0;right:0;top:100%%;height:30mm;background:%s}" % color)
    # 濃い帯の上に置く文字は、読める明るさに持ち上げてから使う
    on_ink = readable_on(accent, ink)
    css = BASE_CSS.replace("{accent}", accent).replace("{ink}", ink).format(
        w=width, h=height, font=font, pad=padding, accent=accent, ink=ink,
        padx=padx, pady=pady, footfill=footfill, onink=on_ink)

    banner, body = [], []
    for item in layout or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("block", "")).strip()
        func = BLOCKS.get(name)
        if not func:
            continue
        params = {k: v for k, v in item.items() if k != "block"}
        params = _resolve_photos(params, photos)
        try:
            html = func(**params)
        except Exception:
            continue
        (banner if name == "header_band" else body).append(html)

    return ("<style>%s%s</style>%s<div class=\"body\">%s</div>"
            % (face, css, "".join(banner), "".join(body)))


def _resolve_photos(params: Dict[str, Any], photos: List[str]) -> Dict[str, Any]:
    """写真の番号を実ファイルのパスに置き換える。

    **入れ子の部品（columns の left/right など）も辿ること。**
    これを忘れると、入れ子に置いた写真だけが静かに消える（実際に踏んだ）。
    """
    photos = list(photos or [])

    def pick(value):
        try:
            index = int(value) - 1
        except (TypeError, ValueError):
            return str(value)
        return photos[index] if 0 <= index < len(photos) else ""

    if "photo" in params:
        params["path"] = pick(params.pop("photo"))
    for side in ("left_photo", "right_photo"):
        if side in params:
            params[side] = pick(params[side])
    if "items" in params and isinstance(params.get("items"), list):
        for item in params["items"]:
            if isinstance(item, dict) and "photo" in item:
                item["path"] = pick(item.pop("photo"))
    if "photos" in params:
        params["paths"] = [p for p in (pick(v) for v in params.pop("photos") or []) if p]

    # 入れ子の部品（columns / two_column の left・right）も辿る。
    # これを忘れると、入れ子に置いた写真だけが**静かに消える**（実際に踏んだ）。
    for side in ("left", "right"):
        nested = params.get(side)
        if not isinstance(nested, list):
            continue
        resolved = []
        for child in nested:
            if isinstance(child, dict):
                inner = _resolve_photos(
                    {k: v for k, v in child.items() if k != "block"}, photos)
                inner["block"] = child.get("block")
                resolved.append(inner)
            else:
                resolved.append(child)
        params[side] = resolved
    return params


# --- 人が文字を直せるようにする ---------------------------------------------

# 編集フォームに出す項目（キー → 画面のラベル）
TEXT_FIELDS = {
    "title": "見出し", "sub": "補足", "text": "本文", "catch": "キャッチ",
    "name": "物件名", "access": "交通", "label": "ラベル", "note": "注記",
    "caption": "キャプション", "left_caption": "左の説明", "right_caption": "右の説明",
    "main": "数値", "unit": "単位", "rent": "賃料", "who": "話し手",
    "tel": "電話", "fax": "FAX", "license_no": "免許番号", "trade": "取引態様",
}
LIST_FIELDS = {"items": "項目（1行に1つ）", "lines": "行（1行に1つ）",
               "labels": "記入欄の項目（1行に1つ）", "captions": "写真の説明（1行に1つ）"}
PAIR_FIELDS = {"rows": "項目（「ラベル：値」で1行に1つ）",
               "details": "内訳（「ラベル：値」で1行に1つ）"}


def editable_fields(layout: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """紙面から「人が直せる文字」を拾い出す。

    PowerPointで編集させるとレイアウトが崩れるので、**文字だけを直させて組み直す**。
    位置や大きさは部品が持っているので、崩れようがない。
    """
    fields = []
    for index, item in enumerate(layout or []):
        if not isinstance(item, dict):
            continue
        block = str(item.get("block", ""))
        for key, value in item.items():
            if key == "block":
                continue
            if key in TEXT_FIELDS and isinstance(value, str) and value.strip():
                fields.append({"index": index, "block": block, "key": key,
                               "kind": "text", "label": TEXT_FIELDS[key],
                               "value": value})
            elif key in LIST_FIELDS and isinstance(value, list) and value:
                if all(isinstance(x, str) for x in value):
                    fields.append({"index": index, "block": block, "key": key,
                                   "kind": "list", "label": LIST_FIELDS[key],
                                   "value": "\n".join(value)})
            elif key in PAIR_FIELDS and isinstance(value, list) and value:
                lines = []
                for row in value:
                    if isinstance(row, dict):
                        lines.append("%s：%s" % (row.get("label", ""), row.get("value", "")))
                    elif isinstance(row, (list, tuple)) and len(row) >= 2:
                        lines.append("%s：%s" % (row[0], row[1]))
                if lines:
                    fields.append({"index": index, "block": block, "key": key,
                                   "kind": "pairs", "label": PAIR_FIELDS[key],
                                   "value": "\n".join(lines)})
    return fields


def apply_edits(layout: List[Dict[str, Any]],
                edits: Dict[str, str]) -> List[Dict[str, Any]]:
    """編集フォームの入力を紙面に反映する。キーは "<index>:<key>"。"""
    import copy

    updated = copy.deepcopy(layout or [])
    for key, raw in (edits or {}).items():
        try:
            index_text, field = key.split(":", 1)
            index = int(index_text)
        except (ValueError, AttributeError):
            continue
        if not (0 <= index < len(updated)):
            continue
        item = updated[index]
        if field in TEXT_FIELDS:
            item[field] = raw
        elif field in LIST_FIELDS:
            item[field] = [x.strip() for x in str(raw).splitlines() if x.strip()]
        elif field in PAIR_FIELDS:
            rows = []
            for line in str(raw).splitlines():
                if not line.strip():
                    continue
                for sep in ("：", ":"):
                    if sep in line:
                        label, value = line.split(sep, 1)
                        rows.append([label.strip(), value.strip()])
                        break
                else:
                    rows.append([line.strip(), ""])
            item[field] = rows
    return updated


BLOCK_LABELS = {
    "headline_bar": "上部の帯", "header_band": "見出し帯", "big_catch": "特大キャッチ",
    "catch": "キャッチ", "full_photo": "全面写真", "hero_pair": "写真2枚（大）",
    "spec_highlight": "特大の数値", "price": "価格", "price_box": "価格（囲み）", "point_row": "推しポイント",
    "photo_hero": "主役の写真", "photo_grid": "写真を並べる", "photo_split": "写真＋文章",
    "lifestyle": "暮らしの提案", "spec_table": "条件表", "spec_two_col": "条件表（2列）",
    "spec_list": "概要リスト", "bullets": "箇条書き", "badge_row": "条件バッジ",
    "steps": "段階図", "timeline": "手順", "voice": "お客様の声",
    "contact": "連絡先", "company_bar": "会社情報の帯", "cta": "行動を促す枠",
    "blanks": "記入欄", "note": "注記", "map_note": "地図", "pictograms": "記号",
    "ribbon": "帯ラベル", "illust_point": "イラスト＋一言", "spacer": "余白",
    "columns": "左右分割", "two_column": "2段組み",
}
