"""紙面の「型」（レイアウトテンプレート）

なぜ型を用意するか:
  同じ物件チラシでも、「写真で見せる」「キャッチで引く」「写真をたくさん載せる」で
  紙面の作りは全く別になる。毎回LLMに部品の並びから考えさせると、
  ①出来が安定しない ②時間がかかる ③良かった並びが次に活きない。

  そこで **並べ方（型）はここに固定**し、LLMには**文言と写真の役割だけ**を書かせる。
  型は司令塔がヒアリングで選ぶ（人が選ぶこともできる）。

  型が増えるほど表現の幅は広がるが、部品と違って型は「完成形」なので、
  1つ増やすたびに必ず実際に描いて目で確かめること。

内容（content）の決まり:
  全ての型が**同じ content を受け取る**。だから型を差し替えても文言を作り直さなくていい。
  {kicker, catch, title, sub, price, unit, lead, badges[], appeals[{title,text}],
   spec_rows[[label,value]], photos{hero,floorplan,rooms[]}, contact{...}}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# 型の一覧。id は保存されるので**変えないこと**（過去の成果物が再現できなくなる）
TEMPLATES: List[Dict[str, Any]] = []


def _register(id_: str, name: str, genres, summary: str, best_for: str,
              photos_min: int, shape: str, orientation: str = "portrait"):
    def deco(func):
        TEMPLATES.append({"id": id_, "name": name, "genres": tuple(genres),
                          "summary": summary, "best_for": best_for,
                          "photos_min": photos_min, "shape": shape,
                          "orientation": orientation, "build": func})
        return func
    return deco


# 用紙。横型は紙そのものが横長になるので、描くときも測るときもこれを渡す
PAPER_BY_ORIENTATION = {"portrait": "A4", "landscape": "A4_LANDSCAPE"}


def _photo(content, key, default=None):
    photos = content.get("photos") or {}
    value = photos.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _captions_for(content, numbers) -> List[str]:
    """写真番号に対応する部屋名。

    **どの部屋か分からない写真は、並べても物件の魅力にならない。**
    「和室・浴室・ロフト・洋室の区別が読み手に伝わらない」と最終確認で止まった。
    ビジュアル制作が判別した名前（photo_captions）をそのまま使う。
    """
    labels = content.get("photo_captions") or {}
    out = []
    for number in numbers or []:
        out.append(str(labels.get(str(number), labels.get(number, ""))).strip())
    return out if any(out) else []


def _rooms(content, count: int, exclude=()) -> List[int]:
    photos = content.get("photos") or {}
    rooms = [int(x) for x in (photos.get("rooms") or []) if str(x).isdigit()]
    rooms = [x for x in rooms if x not in exclude]
    return rooms[:count]


def _contact(content) -> Optional[Dict[str, Any]]:
    info = content.get("contact") or {}
    if not (info.get("tel") or info.get("company")):
        return None
    return {"block": "contact_bar",
            "label": info.get("label") or "ご見学・お問い合わせ",
            "tel": info.get("tel", ""), "company": info.get("company", ""),
            "email": info.get("email", ""), "logo": info.get("logo", ""),
            "address": info.get("address", ""),
            # QRは入れる指定があるときだけ。空ならブロック側が出さない
            "qr": content.get("qr", "") if content.get("qr_on") else "",
            "qr_label": content.get("qr_label") or "物件ページはこちら",
            # 不動産広告は免許番号が必須。登録されていれば必ず載せる
            "license_no": info.get("license", ""),
            "trade": content.get("trade", "")}


REMARK_LABELS = ("備考", "特記", "その他", "注記")


def _spec(content, **kw) -> Optional[Dict[str, Any]]:
    """条件表。**備考は必ず一番下**に置く。

    備考は「更新料」「入居時期」「相談可の条件」など、他の項目に収まらない
    自由記述が入る欄。途中に挟まると読み手が条件を追いにくいので、
    書かれた順にかかわらず末尾へ回す。
    """
    rows = [r for r in (content.get("spec_rows") or []) if r]
    if not rows:
        return None

    def is_remark(row) -> bool:
        label = row.get("label", "") if isinstance(row, dict) else (
            row[0] if isinstance(row, (list, tuple)) and row else "")
        return any(word in str(label) for word in REMARK_LABELS)

    rows = [r for r in rows if not is_remark(r)] + [r for r in rows if is_remark(r)]
    if content.get("remarks") and not any(is_remark(r) for r in rows):
        rows.append(["備考", str(content["remarks"])])
    item = {"block": "spec_table", "rows": rows}
    item.update(kw)
    return item


def _features(content, cols: int = 6) -> Optional[Dict[str, Any]]:
    """設備・特色の並び。

    アイコン用の項目（icons）があればアイコン付きで、無ければ文字のタグで出す。
    アイコンは絵があるぶん目に留まるが、名前がアイコン集に無いものは
    文字だけになるので、両方を扱えるようにしてある。
    """
    icons = [x for x in (content.get("icons") or []) if str(x).strip()]
    badges = [x for x in (content.get("badges") or []) if str(x).strip()]
    blocks_out = []
    if icons:
        try:
            from tools import feature_icons

            icons, extra = feature_icons.split(icons)
        except Exception:
            extra = []
        badges = badges + [x for x in extra if x not in badges]
    if icons:
        # 列は**個数に合わせる**。6列の枠に4個入れると左に寄って間が抜ける
        blocks_out.append({"block": "icon_row", "items": icons,
                           "cols": min(len(icons), cols)})
    if badges:
        blocks_out.append({"block": "badge_row", "items": badges[:8],
                           "style": "outline"})
    return blocks_out or None


def _photo_showcase(content, rooms, big_height: int = 62,
                    small_height: int = 34) -> Optional[Dict[str, Any]]:
    """室内写真の見せ方。**1枚を大きく、残りを小さく**。

    同じ大きさの写真を等間隔に並べると、どれが売りなのか伝わらず、
    紙面が安く見える（「小さい写真を等間隔に並べるとしょぼい」と指摘された）。
    先頭の1枚＝一番見せたいカットを大きく置き、残りを従えるように並べる。
    """
    if not rooms:
        return None
    if len(rooms) <= 2:
        return {"block": "photo_row", "photos": rooms, "height": 50,
                "captions": _captions_for(content, rooms)}
    big, small = rooms[0], rooms[1:4]
    left = [{"block": "photo_hero", "photo": big, "height": big_height,
             "caption": (_captions_for(content, [big]) or [""])[0]}]
    # 右が3枚あると右列の方が背が高くなり、**左の下に穴が空く**（実際に空いた）。
    # 余った写真を左の下に足して、左右の高さをそろえる。
    extra = rooms[4:6]
    if len(small) >= 3 and extra:
        left.append({"block": "photo_grid", "photos": extra,
                     "cols": len(extra), "height": small_height,
                     "captions": _captions_for(content, extra)})
    elif len(small) >= 3:
        # 足す写真が無いなら右を2枚に減らし、1枚あたりを大きくして高さを合わせる
        small = small[:2]
        small_height = int(small_height * 1.55)
    return {"block": "columns", "ratio": "1.6fr 1fr",
            "left": left,
            "right": [{"block": "photo_grid", "photos": small, "cols": 1,
                       "height": small_height,
                       "captions": _captions_for(content, small)}]}


def _clean(layout) -> List[Dict[str, Any]]:
    """並びを整える。**入れ子のリストは展開する**（1か所が複数の部品を返せるように）。"""
    out = []
    for item in layout or []:
        if isinstance(item, list):
            out.extend(x for x in item if isinstance(x, dict) and x)
        elif isinstance(item, dict) and item:
            out.append(item)
    return out


# --- 型 ---------------------------------------------------------------------

@_register(
    "photo_first", "写真主役", ("promo",),
    "外観を大きく1枚。名前と賃料の帯をはさんで室内3枚。下に条件表と間取り図。",
    "写真の見栄えが良い物件。一目で「良さそう」と思わせたいとき",
    photos_min=4,
    shape="帯／大写真／名前・賃料帯／室内3枚／特徴／説明／条件表｜間取り／連絡先")
def _photo_first(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 3, exclude=(hero, plan_no))
    right = ([{"block": "photo_hero", "photo": plan_no, "height": 50,
               "caption": "間取り", "fit": "contain"}] if plan_no else
             [{"block": "spec_highlight", "items": content.get("highlights") or []}])
    return _clean([
        {"block": "hero_band", "kicker": content.get("kicker", ""),
         "catch": content.get("catch", "")},
        # メイン写真は横いっぱい(bleed)＋上帯に密着(gap_top=0)＋中帯との間は詰める(gap_bottom=1)
        {"block": "full_photo", "photo": hero, "height": 122,
         "bleed": True, "gap_top": 0, "gap_bottom": 1} if hero else None,
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        # 中帯の下にも少し余白を入れて、サブ写真とくっつかないようにする
        {"block": "spacer", "size": 2},
        {"block": "photo_row", "photos": rooms, "height": 55,
         "captions": _captions_for(content, rooms)} if rooms else None,
        _features(content),
        {"block": "note", "text": content.get("lead", "")},
        {"block": "columns", "ratio": "1fr 1.05fr",
         "left": _clean([_spec(content)]), "right": right},
        _contact(content),
    ])


@_register(
    "catch_first", "キャッチ主役", ("promo",),
    "大きなキャッチコピーとリード文で引きつけ、写真2枚と推しポイント3つで支える。",
    "写真が少ない・弱いとき。暮らしのイメージや条件の良さで訴えたいとき",
    photos_min=2,
    shape="大キャッチ／リード／写真2枚／推し3点／条件表｜間取り／連絡先")
def _catch_first(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 1, exclude=(hero, plan_no))
    pair = [hero] + rooms
    appeals = [a for a in (content.get("appeals") or []) if isinstance(a, dict)][:3]
    return _clean([
        {"block": "big_catch", "text": content.get("catch", ""),
         "sub": content.get("kicker", "")},
        {"block": "note", "text": content.get("lead", "")},
        {"block": "photo_row", "photos": pair, "height": 74} if pair else None,
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        {"block": "point_row", "items": appeals} if len(appeals) >= 2 else None,
        {"block": "columns", "ratio": "1fr 1fr",
         "left": _clean([_spec(content)]),
         "right": _clean([{"block": "photo_hero", "photo": plan_no, "height": 52,
                           "caption": "間取り", "fit": "contain"} if plan_no else
                          {"block": "badge_row",
                           "items": content.get("badges") or [], "style": "outline"}])},
        _contact(content),
    ])


@_register(
    "gallery", "写真たっぷり", ("promo",),
    "外観1枚のあと、室内・設備を6枚まで並べる。写真の点数で見せる型。",
    "見せたい部屋・設備が多い物件。リフォーム済み・設備が売りのとき",
    photos_min=6,
    shape="帯／大写真／名前・賃料帯／写真6枚／特徴／条件表｜間取り／連絡先")
def _gallery(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 6, exclude=(hero, plan_no))
    return _clean([
        {"block": "hero_band", "kicker": content.get("kicker", ""),
         "catch": content.get("catch", "")},
        {"block": "full_photo", "photo": hero, "height": 90} if hero else None,
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        _photo_showcase(content, rooms),
        _features(content),
        {"block": "columns", "ratio": "1fr 1fr",
         "left": _clean([_spec(content)]),
         "right": _clean([{"block": "photo_hero", "photo": plan_no, "height": 48,
                           "caption": "間取り", "fit": "contain"} if plan_no else
                          {"block": "note", "text": content.get("lead", "")}])},
        _contact(content),
    ])


@_register(
    "split", "左右分割（誌面風）", ("promo",),
    "紙面を左右に割り、左に写真を縦に積み、右にキャッチと条件をまとめる。",
    "縦長の写真が多いとき。落ち着いた誌面の見え方にしたいとき",
    photos_min=3,
    shape="帯／[左:写真3枚｜右:キャッチ・条件・特徴]／連絡先")
def _split(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 3, exclude=(hero, plan_no))
    left = _clean([
        {"block": "photo_hero", "photo": hero, "height": 82} if hero else None,
    ] + [{"block": "photo_hero", "photo": n, "height": 52} for n in rooms])
    right = _clean([
        {"block": "catch", "text": content.get("catch", "")},
        {"block": "note", "text": content.get("lead", "")},
        {"block": "price_box", "rent": content.get("price", ""),
         "unit": content.get("unit", "円 / 月"), "label": "賃料",
         "details": [content.get("sub", "")] if content.get("sub") else []},
        _spec(content),
        {"block": "photo_hero", "photo": plan_no, "height": 46, "caption": "間取り", "fit": "contain"}
        if plan_no else None,
    ])
    return _clean([
        {"block": "hero_band", "kicker": content.get("kicker", ""),
         "catch": content.get("title", "")},
        {"block": "columns", "ratio": "1fr 1fr", "left": left, "right": right},
        _features(content),
        _contact(content),
    ])


@_register(
    "maisoku", "マイソク（業者向け）", ("maisoku",),
    "外観と間取り図を上半分に大きく、下半分は条件を密に並べる。感情訴求はしない。",
    "業者に配る物件概要。情報の網羅と正確さが要るとき",
    photos_min=2,
    shape="見出し帯／[外観｜間取り]／条件表（2列）／写真4枚／連絡先")
def _maisoku(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 4, exclude=(hero, plan_no))
    spec = _spec(content)
    rows = spec["rows"] if spec else []
    return _clean([
        {"block": "headline_bar", "name": content.get("title", ""),
         "catch": content.get("kicker", ""), "access": content.get("sub", "")},
        {"block": "hero_pair", "left_photo": hero, "right_photo": plan_no,
         "height": 92, "left_caption": "外観", "right_caption": "間取り"}
        if hero and plan_no else
        ({"block": "full_photo", "photo": hero, "height": 96} if hero else None),
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        {"block": "spec_two_col", "rows": rows} if rows else None,
        {"block": "photo_row", "photos": rooms, "height": 40} if rooms else None,
        _contact(content),
    ])



# --- 横向き（A4横 297×210mm）の型 -------------------------------------------
#
# 縦型をそのまま横にしても間が持たない。**横は「左右に分ける」のが基本**で、
# 片側に写真、もう片側に情報を置く。全幅の帯（hero_band / title_price_bar /
# photo_row / contact_bar）は横に長く伸びるので、上下の締めに使うと効く。
#
# 注意: 全幅の帯（full-bleed）を columns の中に入れてはいけない。
#       紙面の端まで伸ばす仕組みなので、列の中では位置が壊れる。

@_register(
    "wide_photo_first", "横・写真主役", ("promo",),
    "左に大きな外観、右に条件と間取り。下に室内写真を並べる。",
    "A4横で配る。手に取ってすぐ物件の姿が分かるようにしたいとき",
    photos_min=4, orientation="landscape",
    shape="帯／[左:外観｜右:キャッチ・条件・間取り]／室内3枚／連絡先")
def _wide_photo_first(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 3, exclude=(hero, plan_no))
    right = _clean([
        {"block": "catch", "text": content.get("catch", "")},
        {"block": "note", "text": content.get("lead", "")},
        _spec(content),
        {"block": "photo_hero", "photo": plan_no, "height": 46,
         "caption": "間取り", "fit": "contain"} if plan_no else None,
    ])
    return _clean([
        {"block": "hero_band", "kicker": content.get("kicker", ""),
         "catch": content.get("title", "")},
        {"block": "columns", "ratio": "1.15fr 1fr",
         "left": _clean([{"block": "photo_hero", "photo": hero, "height": 104}
                         if hero else None]),
         "right": right},
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        {"block": "photo_row", "photos": rooms, "height": 44} if rooms else None,
        _contact(content),
    ])


@_register(
    "wide_split", "横・写真面／情報面", ("promo",),
    "紙面を左右で真っ二つ。左は写真だけ、右は文言と条件だけ。",
    "写真の力で見せつつ、条件もきちんと読ませたいとき",
    photos_min=3, orientation="landscape",
    shape="[左:外観＋室内2枚｜右:キャッチ・賃料・条件・間取り]／連絡先")
def _wide_split(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 2, exclude=(hero, plan_no))
    left = _clean([{"block": "photo_hero", "photo": hero, "height": 96} if hero else None,
                   {"block": "photo_grid", "photos": rooms, "cols": 2, "height": 46}
                   if rooms else None])
    right = _clean([
        {"block": "catch", "text": content.get("catch", "")},
        {"block": "note", "text": content.get("lead", "")},
        {"block": "price_box", "rent": content.get("price", ""),
         "unit": content.get("unit", "円 / 月"), "label": "賃料",
         "details": [content.get("sub", "")] if content.get("sub") else []},
        _spec(content),
        {"block": "photo_hero", "photo": plan_no, "height": 44,
         "caption": "間取り", "fit": "contain"} if plan_no else None,
    ])
    return _clean([
        {"block": "hero_band", "kicker": content.get("kicker", ""),
         "catch": content.get("title", "")},
        {"block": "columns", "ratio": "1fr 1fr", "left": left, "right": right},
        _features(content),
        _contact(content),
    ])


@_register(
    "wide_gallery", "横・写真たっぷり", ("promo",),
    "横幅を活かして室内写真を6枚横並びに。下に条件と間取り。",
    "部屋数・設備が多い物件。写真の点数で見せたいとき",
    photos_min=6, orientation="landscape",
    shape="帯／外観／名前・賃料帯／写真6枚／条件表｜間取り／連絡先")
def _wide_gallery(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 6, exclude=(hero, plan_no))
    return _clean([
        {"block": "hero_band", "kicker": content.get("kicker", ""),
         "catch": content.get("catch", "")},
        {"block": "full_photo", "photo": hero, "height": 62} if hero else None,
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        {"block": "photo_row", "photos": rooms[:3], "height": 40} if rooms else None,
        {"block": "columns", "ratio": "1fr 1fr",
         "left": _clean([_spec(content)]),
         "right": _clean([{"block": "photo_hero", "photo": plan_no, "height": 42,
                           "caption": "間取り", "fit": "contain"} if plan_no else
                          {"block": "photo_grid", "photos": rooms[3:], "cols": 3,
                           "height": 34}])},
        _contact(content),
    ])


@_register(
    "wide_catch", "横・キャッチ主役", ("promo",),
    "上半分をキャッチと写真3枚で使い、下半分に推しポイントと条件。",
    "写真が少ない・弱いとき。言葉で引きつけたいとき",
    photos_min=3, orientation="landscape",
    shape="大キャッチ／写真3枚／推し3点／名前・賃料帯／条件表｜間取り／連絡先")
def _wide_catch(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 2, exclude=(hero, plan_no))
    appeals = [a for a in (content.get("appeals") or []) if isinstance(a, dict)][:3]
    return _clean([
        {"block": "big_catch", "text": content.get("catch", ""),
         "sub": content.get("kicker", "")},
        {"block": "photo_row", "photos": [hero] + rooms, "height": 62}
        if hero else None,
        {"block": "point_row", "items": appeals} if len(appeals) >= 2 else None,
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        {"block": "columns", "ratio": "1fr 1fr",
         "left": _clean([_spec(content)]),
         "right": _clean([{"block": "photo_hero", "photo": plan_no, "height": 40,
                           "caption": "間取り", "fit": "contain"} if plan_no else
                          {"block": "note", "text": content.get("lead", "")}])},
        _contact(content),
    ])


@_register(
    "wide_maisoku", "横・マイソク（業者向け）", ("maisoku",),
    "左に外観と室内、右に間取り図を大きく。条件は2列で密に。",
    "業者に配る物件概要をA4横で作るとき",
    photos_min=2, orientation="landscape",
    shape="見出し帯／[左:外観＋室内3枚｜右:間取り＋条件2列]／名前・賃料帯／連絡先")
def _wide_maisoku(content) -> List[Dict[str, Any]]:
    hero = _photo(content, "hero", 1)
    plan_no = _photo(content, "floorplan")
    rooms = _rooms(content, 3, exclude=(hero, plan_no))
    spec = _spec(content)
    left = _clean([{"block": "photo_hero", "photo": hero, "height": 84,
                    "caption": "外観"} if hero else None,
                   {"block": "photo_grid", "photos": rooms, "cols": 3, "height": 32}
                   if rooms else None])
    right = _clean([{"block": "photo_hero", "photo": plan_no, "height": 76,
                     "caption": "間取り", "fit": "contain"} if plan_no else None,
                    {"block": "spec_two_col", "rows": spec["rows"] if spec else []}])
    return _clean([
        {"block": "headline_bar", "name": content.get("title", ""),
         "catch": content.get("kicker", ""), "access": content.get("sub", "")},
        {"block": "columns", "ratio": "1fr 1fr", "left": left, "right": right},
        {"block": "title_price_bar", "title": content.get("title", ""),
         "sub": content.get("sub", ""), "price": content.get("price", ""),
         "unit": content.get("unit", "円 / 月")},
        _contact(content),
    ])


# --- 参照用 -----------------------------------------------------------------

def all_templates(genre: str = "", orientation: str = "") -> List[Dict[str, Any]]:
    """組み込みの型＋**このアプリで登録した型**。

    登録した型を先に出す。人が「これが良かった」と決めたものなので、
    こちらが用意した型より優先して目に入るべき。
    """
    items = list(_saved_templates()) + list(TEMPLATES)
    if orientation:
        items = [t for t in items if t["orientation"] == orientation]
    if genre:
        items = [t for t in items if genre in t["genres"]] or items
    return items or list(TEMPLATES)


def _saved_templates() -> List[Dict[str, Any]]:
    try:
        from core import user_templates

        saved = user_templates.all_saved()
    except Exception:
        return []
    out = []
    for spec in saved:
        item = dict(spec)
        item.setdefault("shape", "登録した紙面の並び")
        item["genres"] = tuple(spec.get("genres") or ("promo",))
        item["build"] = (lambda sid: (lambda content: _build_saved(sid, content)))(
            spec["id"])
        out.append(item)
    return out


def _build_saved(template_id: str, content):
    from core import user_templates

    return user_templates.build(template_id, content)


def paper_of(template_id: str) -> str:
    """その型が使う用紙名。横型は横長の紙で描かないと縦のまま組まれる。"""
    item = get(template_id)
    return PAPER_BY_ORIENTATION.get((item or {}).get("orientation", "portrait"), "A4")


def get(template_id: str) -> Optional[Dict[str, Any]]:
    for item in TEMPLATES:
        if item["id"] == template_id:
            return item
    return None


def build(template_id: str, content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """型に文言を流し込んで、部品の並びにする。

    型が見つからないときは黙って「写真主役」にする。
    紙面が1枚も出ないより、既定の型で出したほうがいい。
    """
    content = content or {}
    item = get(template_id) or get("photo_first")
    layout = item["build"](content)
    # メイン写真の切り取り位置（縦）。指定があれば、主役写真を出す部品に流す
    focus_y = content.get("main_focus_y")
    if focus_y is not None:
        hero = _photo(content, "hero", 1)
        for blk in layout:
            if not isinstance(blk, dict):
                continue
            name = blk.get("block")
            if name in ("full_photo", "photo_hero") and blk.get("photo") == hero:
                blk.setdefault("focus_y", focus_y)
            elif name == "hero_pair" and blk.get("left_photo") == hero:
                blk.setdefault("focus_y", focus_y)
    return layout


def choose(genre: str, photo_count: int, orientation: str = "portrait") -> str:
    """人が選ばなかったときの既定。**縦を既定**とし、写真の枚数で型を決める。

    横は「A4横で」と言われたときだけ。指定が無いのに横にすると、
    印刷やファイリングの前提が変わって使いにくい。
    """
    if orientation == "landscape":
        if genre == "maisoku":
            return "wide_maisoku"
        if photo_count >= 7:
            return "wide_gallery"
        if photo_count <= 3:
            return "wide_catch"
        return "wide_photo_first"
    if genre == "maisoku":
        return "maisoku"
    if photo_count >= 7:
        return "gallery"
    if photo_count <= 2:
        return "catch_first"
    return "photo_first"


def describe_for_prompt(genre: str = "promo", orientation: str = "") -> str:
    lines = ["【紙面の型（どれか1つを選ぶ）】"]
    for item in all_templates(genre, orientation):
        lines.append("- %s（%s）… %s\n    向くとき: %s ／ 写真%d枚以上\n    並び: %s"
                     % (item["id"], item["name"], item["summary"],
                        item["best_for"], item["photos_min"], item["shape"]))
    return "\n".join(lines)


def options_for_question(genre: str, photo_count: int = 0,
                         orientation: str = "portrait") -> List[str]:
    """ヒアリングの選択肢。写真が足りない型は出さない（選んでも崩れるため）。"""
    items = [t for t in all_templates(genre, orientation)
             if not photo_count or photo_count >= t["photos_min"]]
    items = items or all_templates(genre, orientation)
    return ["%s｜%s" % (t["name"], t["summary"]) for t in items]


def id_from_answer(answer: str, genre: str = "promo") -> str:
    """ヒアリングの答え（表示名でも id でも可）から id を取り出す。"""
    text = str(answer or "").strip()
    if not text:
        return ""
    for item in all_templates(genre) + all_templates(genre, "landscape"):
        if text == item["id"] or text.startswith(item["name"]) or item["name"] in text:
            return item["id"]
    return ""
