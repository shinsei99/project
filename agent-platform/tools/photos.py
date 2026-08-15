"""アイテム: WebページからPR用の写真を集める

物件ページや商品ページから掲載写真を取り込む。
チラシは実写真が主役なので、これが無いと作図カードだけの紙面になる。

**権利の注意（必ず読むこと）**
  他社サイトの掲載写真には撮影者・元付業者・媒体の権利がある。
  **自社が権利を持つ写真（自社物件・自社撮影）以外は、チラシに使ってはいけない。**
  このアイテムは「自社の掲載ページから自社の写真を回収する」用途を想定している。
  取り込んだ写真には出典URLを必ず記録し、人が確認できるようにする。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

NAME = "photos"
LABEL = "Webページから写真を取り込む"
DESCRIPTION = ("物件・商品ページの掲載写真をダウンロードして素材にする。"
               "※自社が権利を持つ写真のみ使用可")

MIN_BYTES = 20 * 1024        # これ未満はアイコン・ロゴとみなす
# **紙面に使えない小さい画像は取り込まない。**
# 254x169 のサムネイルが混ざり、それがメイン写真に選ばれてA4全幅に
# 引き伸ばされた（実効30dpi）。容量では弾けない（20KB以上あった）ので画素で見る。
#
# **判定は長辺で行うこと。** 幅で見ると 427x640 のような**縦長の写真が全部落ちる**
# （実際に1物件の写真10枚が全滅した）。室内写真は縦位置で撮られることが多い。
#
# **基準は緩めにする。** 600にしたら 360x480 の室内写真が全部落ち、
# 紙面がバルコニーとトイレだけになった。小さくてもサブ枠（幅60mm）なら
# 480px で約200dpi 出て十分使える。大きく使えるかどうかは、
# 取り込みではなく**割り当てのとき**に見る（メイン写真は一番大きいものを選ぶ）。
MIN_LONG_SIDE = 400
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def available() -> Tuple[bool, str]:
    try:
        import requests  # noqa: F401
    except Exception:
        return False, "requests 未導入"
    # ページは自分で読む。claude CLI は取れなかったときの予備なので必須ではない
    return True, "ページから写真を集めます（※自社の権利がある写真のみ使用可）"


# 掲載写真ではないもの（ロゴ・アイコン・バナー・地図・SNSボタン）を弾く語
JUNK = ("logo", "icon", "sprite", "banner", "btn", "button", "bnr", "ad_", "/ads/",
        "noimage", "no_image", "dummy", "blank", "spacer", "avatar", "profile",
        "favicon", "map", "footer", "header", "sns", "share", "campaign", "pixel")

# 画像URLらしき文字列（クエリ付きも拾う）
IMG_PATTERN = re.compile(
    r"""https?://[^\s"'<>\\]+?\.(?:jpe?g|png|webp)(?:\?[^\s"'<>\\]*)?""",
    re.IGNORECASE)


def _fetch_html(page_url: str, timeout: int = 20) -> str:
    import requests

    resp = requests.get(page_url, headers={"User-Agent": UA,
                                           "Accept-Language": "ja,en;q=0.8"},
                        timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def _looks_like_photo(url: str) -> bool:
    low = url.lower()
    return not any(word in low for word in JUNK)


def _base_key(url: str) -> str:
    """同じ写真のサムネと原寸をまとめるための鍵。

    多くのサイトは `/foo_100x75.jpg` と `/foo_640x480.jpg` のように、
    同じ名前に寸法だけ足して出し分ける。寸法を落とせば同一写真だと分かる。
    """
    name = url.split("?")[0].split("/")[-1].lower()
    return re.sub(r"[_-]?\d{2,4}x\d{2,4}", "", name)


def extract_from_html(html: str, limit: int = 12) -> List[str]:
    """HTMLから掲載写真のURLを抜き出す。**通信もAIも使わない純粋な処理。**

    遅延読み込み（data-src）やJSON埋め込みも、結局はHTMLの中に
    画像URLの文字列として出てくるので、まとめて拾って選別する方が速くて確実。
    同じ写真のサムネと原寸が両方出るため、**寸法を除いた名前で1枚にまとめ、
    大きい方（URLが長い＝寸法指定が大きいことが多い）を採る**。
    """
    # JSONの中の画像URLは `https:\\/\\/…` と円記号で逃がされている。
    # **先に戻してから探す**（後から戻しても、正規表現が拾えていない）
    html = (html or "").replace("\\/", "/").replace("&amp;", "&")
    found = {}
    for url in _candidate_urls(html):
        if not _looks_like_photo(url):
            continue
        key = _base_key(url)
        current = found.get(key)
        # 同じ写真ならサムネより大きい方を残す
        if current is None or _size_hint(url) > _size_hint(current):
            found[key] = url
    return list(found.values())[:limit]


def _candidate_urls(html: str) -> List[str]:
    """HTMLから画像URLの候補を出す。

    **画像配信の中継URLを素通ししないこと。** 実際の物件サイトでは
      `https://image4.homes.jp/smallimg/image.php?file=<実URLをエンコード>&width=640`
    のように、実体のURLが**クエリの中に隠れている**。中継URLのまま拾うと
    拡張子で判定できず1件も取れない（実際に0枚になった）。
    中に埋まっている実URLを取り出して使うと、原寸で確実に落とせる。
    """
    from urllib.parse import unquote

    urls = list(IMG_PATTERN.findall(html))
    # クエリに埋め込まれた実URL（file=… / url=… / src=…）を掘り出す
    for encoded in re.findall(r"(?:file|url|src|image)=(https?%3A%2F%2F[^&\"'<>\s]+)",
                              html, re.IGNORECASE):
        inner = unquote(encoded)
        if _looks_like_photo(inner):
            urls.append(inner.split("?")[0] if ".jpg?" in inner or ".png?" in inner
                        else inner)
    return urls


def _size_hint(url: str) -> int:
    """URLから読み取れる大きさの手がかり。大きいほど原寸に近い。"""
    numbers = [int(x) for x in re.findall(r"(\d{2,4})x\d{2,4}", url)]
    numbers += [int(x) for x in re.findall(r"[?&](?:w|width)=(\d{2,4})", url)]
    return max(numbers) if numbers else 0


def extract_image_urls(page_url: str, limit: int = 12) -> List[str]:
    """ページを読んで、掲載写真のURLを抜き出す。

    **まずページを自分で読む**（数秒）。これで足りることがほとんどで、
    以前は claude CLI に読ませていたため1回5〜8分かかり、しかも0枚で返っていた。
    自前で取れなかったときだけ、claude CLI に頼る（JSで後から差し込むページ用）。
    """
    try:
        urls = extract_from_html(_fetch_html(page_url), limit=limit)
    except Exception:
        urls = []
    if urls:
        return urls
    return _extract_with_ai(page_url, limit)


def _extract_with_ai(page_url: str, limit: int = 12) -> List[str]:
    """最後の手段。JSで描画されるページなど、HTMLに直接出てこない場合だけ。"""
    from core.config import get_settings
    from core.llm import complete, extract_json

    if not get_settings().claude_bin:
        return []
    prompt = (
        "次のページを WebFetch で開き、**掲載されている物件・商品の写真**の画像URLを"
        "集めてください。\n\n%s\n\n"
        "- ロゴ・アイコン・広告バナー・地図は除く\n"
        "- サムネイルではなく、できるだけ大きい画像のURLを選ぶ\n"
        "- 最大%d件\n\n"
        'JSONだけを返してください: {"images": ["https://...", ...]}' % (page_url, limit))
    result = complete(prompt, role="tools", max_tokens=2000, temperature=0.1,
                      tools={"web": True, "dirs": [], "mcp": False})
    if not result.ok:
        return []
    data = extract_json(result.text) or {}
    urls = data.get("images") if isinstance(data, dict) else None
    if not isinstance(urls, list):
        return []
    seen, cleaned = set(), []
    for url in urls:
        url = str(url).strip()
        if url.startswith("http") and url not in seen:
            seen.add(url)
            cleaned.append(url)
    return cleaned[:limit]


# 画像ファイルの先頭にある目印（マジックナンバー）
MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"RIFF", b"BM")


def _is_image(resp) -> bool:
    kind = str(resp.headers.get("Content-Type", "")).lower()
    if kind and not kind.startswith("image/"):
        return False
    head = resp.content[:12]
    if head.startswith(b"RIFF") and b"WEBP" not in resp.content[:16]:
        return False
    return any(head.startswith(sign) for sign in MAGIC)


def download(urls: List[str], dest_dir, prefix: str = "photo") -> List[Dict[str, Any]]:
    """画像を保存する。小さすぎるもの（アイコン等）は捨てる。"""
    import requests

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, url in enumerate(urls, start=1):
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            resp.raise_for_status()
        except Exception:
            continue
        if len(resp.content) < MIN_BYTES or not _is_image(resp):
            # **中身が画像かを見る。** サーバーが404やエラーページをHTMLで返しても
            # 拡張子は .jpg のままなので、名前だけでは判別できない。
            # 実際にHTMLを web_11.jpg として保存し、画面が落ちた。
            continue
        suffix = ".jpg"
        match = re.search(r"\.(jpe?g|png|webp)", url.lower())
        if match:
            suffix = "." + match.group(1).replace("jpeg", "jpg")
        path = dest_dir / ("%s_%02d%s" % (prefix, i, suffix))
        path.write_bytes(resp.content)
        _apply_exif_rotation(path)
        size = _pixel_size(path)
        if size and max(size) < MIN_LONG_SIDE:
            path.unlink(missing_ok=True)
            continue
        saved.append({"path": str(path), "url": url, "bytes": len(resp.content),
                      "width": size[0] if size else 0,
                      "height": size[1] if size else 0})
    return saved


def _apply_exif_rotation(path) -> None:
    """写真の向きを正す。

    スマホで撮った写真は**画素はそのままで「向き」だけEXIFに書く**ことがある。
    そのまま紙面に置くと横倒し・上下逆で出る。ここで実際に回して保存し直す
    （紙面側で回す仕組みを持たないため、入り口で正すのが確実）。
    """
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as img:
            fixed = ImageOps.exif_transpose(img)
            if fixed is not img and fixed.size != img.size or _has_orientation(img):
                fixed.convert("RGB").save(path, quality=92)
    except Exception:
        return


def _has_orientation(img) -> bool:
    try:
        exif = img.getexif()
        return int(exif.get(274, 1)) not in (0, 1)
    except Exception:
        return False


def _pixel_size(path):
    """画像の画素数。開けなければ None（呼び出し側は捨てない判断をする）。"""
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return None
