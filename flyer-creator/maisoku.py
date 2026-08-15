"""案件フォルダの `賃貸資料.xls`（旧Excelのマイソク）から写真と間取り図を取り出す。

    .venv/bin/python maisoku.py        → data/maisoku/<案件フォルダ>/ に書き出し
                                          data/maisoku/index.html で一覧を目視できる

生ファイルをそのまま走査しても画像は取れない。二段で分断されているため。

  1. OLE複合ドキュメント … Workbook ストリームが512バイトのセクタに散っている
  2. BIFF レコード … 1レコード8224バイトの上限があるので、画像を含む
     MSODRAWINGGROUP(0x00EB) が CONTINUE(0x003C) に刻まれている

Workbook を組み直し、さらに 0x00EB と後続の 0x003C を連結してから
Escher の BLIP レコードを読む。LibreOffice でのxlsx変換は要らない。

⚠️ ここで取り出したものを build_site が自動で拾うことはしない。案件フォルダ由来の
   素材はまず人が index.html で見て、build_kato.py / properties.py に明示的に
   書いたものだけがサイトに載る（README.md の写真の扱いを参照）。
"""
from __future__ import annotations

import hashlib
import io
import struct
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import olefile
from PIL import Image

BASE = Path(__file__).parent
OUT = BASE / "data" / "maisoku"

MSODRAWINGGROUP, CONTINUE = 0x00EB, 0x003C
DGG_CONTAINER, BSTORE_CONTAINER, BSE = 0xF000, 0xF001, 0xF007
# MSOBLIPTYPE（BSE の recInstance）
JPEG, PNG, DIB, CMYK_JPEG = 5, 6, 7, 9
BLIP_EXT = {JPEG: "jpg", PNG: "png", DIB: "jpg", CMYK_JPEG: "jpg"}

# マイソクの枠。全13ファイルに同じものが入っているので写真として数えない。
TEMPLATE_SHA1 = "f6003b2c8fa7f78919a7e1a7650fc46f7750f24b"


def drawing_group(path: Path) -> bytes:
    """Workbook ストリームから MSODRAWINGGROUP を連結して返す。"""
    with olefile.OleFileIO(str(path)) as ole:
        name = next((s for s in ("Workbook", "Book") if ole.exists(s)), None)
        if not name:
            raise ValueError("Workbook ストリームが無い")
        buf = ole.openstream(name).read()

    out, i, n, prev = bytearray(), 0, len(buf), None
    while i + 4 <= n:
        rec, size = struct.unpack_from("<HH", buf, i)
        if i + 4 + size > n:
            break
        if rec == MSODRAWINGGROUP or (rec == CONTINUE and prev in (MSODRAWINGGROUP, CONTINUE)):
            out += buf[i + 4: i + 4 + size]
        prev = rec
        i += 4 + size
    return bytes(out)


def bse_records(blob: bytes, off: int = 0, end: Optional[int] = None) -> Iterator[Tuple[int, bytes]]:
    """Escher を辿って BSE（画像1枚ぶんの入れ物）を拾う。"""
    end = len(blob) if end is None else end
    while off + 8 <= end:
        ver_inst, rec_type, rec_len = struct.unpack_from("<HHI", blob, off)
        body, stop = off + 8, min(off + 8 + rec_len, end)
        if rec_type == BSE:
            yield ver_inst >> 4, blob[body:stop]
        elif rec_type in (DGG_CONTAINER, BSTORE_CONTAINER) or (ver_inst & 0xF) == 0xF:
            yield from bse_records(blob, body, stop)
        if rec_len == 0:
            break
        off = body + rec_len


def blip_data(kind: int, bse: bytes) -> Optional[bytes]:
    """BSE の中の BLIP から画像の実体だけを取り出す。"""
    if kind not in BLIP_EXT or len(bse) < 44:
        return None
    blip = bse[36:]                       # BSE ヘッダ36バイトの後ろが BLIP
    ver_inst, _, rec_len = struct.unpack_from("<HHI", blip, 0)
    # recInstance の最下位ビットが立っていると UID が2個入る。その後ろに tag が1バイト。
    head = 8 + (32 if (ver_inst >> 4) & 1 else 16) + 1
    data = blip[head: 8 + rec_len] if rec_len else blip[head:]
    return data or None


def dib_to_image(data: bytes) -> Image.Image:
    """BITMAPINFOHEADER だけの DIB に BMP のファイルヘッダを足して開く。"""
    header_size = struct.unpack_from("<I", data, 0)[0]
    bpp = struct.unpack_from("<H", data, 14)[0]
    palette = 0 if bpp > 8 else (1 << bpp) * 4
    offset = 14 + header_size + palette
    return Image.open(io.BytesIO(b"BM" + struct.pack("<IHHI", 14 + len(data), 0, 0, offset) + data))


def extract(src: Path, dst: Path, min_px: int = 400) -> List[Tuple[str, int, int]]:
    """1ファイルぶん取り出して dst に置く。戻り値は (ファイル名, 幅, 高さ)。"""
    dst.mkdir(parents=True, exist_ok=True)
    seen: set = set()
    out: List[Tuple[str, int, int]] = []

    for kind, bse in bse_records(drawing_group(src)):
        data = blip_data(kind, bse)
        if not data:
            continue
        digest = hashlib.sha1(data).hexdigest()
        if digest == TEMPLATE_SHA1 or digest in seen:
            continue
        seen.add(digest)

        try:
            im = dib_to_image(data) if kind == DIB else Image.open(io.BytesIO(data))
            im.load()
        except Exception:
            continue
        if max(im.size) < min_px:         # ロゴ・アイコンの類は落とす
            continue

        name = f"{len(out):02d}.{BLIP_EXT[kind]}"
        if kind == DIB:
            im.convert("RGB").save(dst / name, quality=92)
        else:
            (dst / name).write_bytes(data)
        out.append((name, im.size[0], im.size[1]))
    return out


def write_index(rows: List[Tuple[str, str, int, int]]) -> Path:
    """目視用の一覧。案件フォルダ由来なので、載せる前に必ずここで確認する。"""
    cells = "".join(
        f'<figure><a href="{case}/{name}"><img src="{case}/{name}" loading="lazy"></a>'
        f"<figcaption>{case} / {name}<br>{w}×{h}</figcaption></figure>"
        for case, name, w, h in rows
    )
    html = f"""<!doctype html><meta charset="utf-8"><title>マイソク素材</title>
<style>
body{{font:13px/1.6 -apple-system,sans-serif;margin:24px;background:#fafafa}}
h1{{font-size:18px}} p{{color:#555}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}}
figure{{margin:0;background:#fff;border:1px solid #ddd;border-radius:6px;padding:6px}}
img{{width:100%;height:150px;object-fit:contain;background:#f2f2f2}}
figcaption{{font-size:11px;color:#666;margin-top:4px}}
</style>
<h1>賃貸資料.xls から取り出した素材（{len(rows)}枚）</h1>
<p>案件フォルダ由来。サイトに載せる前にここで目視すること。
使うものは build_kato.py / properties.py に明示的に書く。</p>
<div class="grid">{cells}</div>"""
    path = OUT / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def main() -> None:
    from properties import GDRIVE

    sources = sorted(GDRIVE.glob("*/賃貸資料.xls"))
    if not sources:
        print("賃貸資料.xls が見つかりません（Googleドライブの同期待ちかも）")
        return

    rows: List[Tuple[str, str, int, int]] = []
    for src in sources:
        case = src.parent.name
        try:
            found = extract(src, OUT / case)
        except Exception as e:
            print(f"{case}\tERROR {e}")
            continue
        rows += [(case, name, w, h) for name, w, h in found]
        print(f"{case}\t{len(found)}枚")

    print(f"合計 {len(rows)}枚 → {OUT}")
    print("  open", write_index(rows))


if __name__ == "__main__":
    sys.exit(main())
