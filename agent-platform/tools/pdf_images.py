"""アイテム: PDFから写真・図版を取り出す

なぜ要るか:
  雑誌記事や既存資料をPDFで渡されたとき、**中の写真と図版が一番の素材**になる。
  取り出せないと、部隊は文字カードしか作れず、動画もスライドも文字だけの
  単調なものになる（実際にそうなった。記事に図版2点・写真2点があったのに使えなかった）。

何を残し、何を捨てるか:
  - 小さすぎるもの（ロゴ・飾り罫）は捨てる
  - **同じ画像が複数ページに出るもの**（ヘッダー・囲み飾り）は捨てる
  - 顔写真は捨てない（判断は人に委ねる）が、**取り出した出所（ページ番号）を必ず残す**
    ので、後から人が確認できる
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

NAME = "pdf_images"
LABEL = "PDFから写真・図版を取り出す"
DESCRIPTION = "既存資料・雑誌記事のPDFに入っている写真や図表を素材として取り出す"

MIN_BYTES = 30 * 1024      # これ未満は飾り・ロゴとみなす
MIN_LONG_SIDE = 240        # 図版は小さめでも使うので、写真より緩い


def available() -> Tuple[bool, str]:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False, "pypdf 未導入"
    return True, "PDFから写真・図版を取り出します"


def extract(pdf_path, dest_dir, limit: int = 24) -> List[Dict[str, Any]]:
    """PDFの画像を取り出して保存する。戻り値は保存した画像の情報。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf_path).stem[:20]

    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return []

    seen: Dict[str, int] = {}
    found: List[Dict[str, Any]] = []
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images)
        except Exception:
            continue
        for image in images:
            data = image.data
            if len(data) < MIN_BYTES:
                continue
            key = hashlib.md5(data).hexdigest()
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                continue          # 同じ絵が何度も出る＝飾り
            suffix = Path(image.name).suffix.lower() or ".png"
            if suffix not in (".png", ".jpg", ".jpeg"):
                suffix = ".png"
            path = dest_dir / ("%s_p%02d_%02d%s" % (stem, page_no,
                                                    len(found) + 1, suffix))
            try:
                path.write_bytes(data)
            except OSError:
                continue
            size = _size(path)
            if not size or max(size) < MIN_LONG_SIDE:
                path.unlink(missing_ok=True)
                continue
            found.append({"path": str(path), "page": page_no,
                          "width": size[0], "height": size[1],
                          "bytes": len(data)})
            if len(found) >= limit:
                return found
    return found


def _size(path):
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return None


def extract_all(input_dir, dest_dir, limit: int = 24) -> List[Dict[str, Any]]:
    """フォルダ内の全PDFから取り出す。"""
    out: List[Dict[str, Any]] = []
    for pdf in sorted(Path(input_dir).glob("*.pdf")):
        out += extract(pdf, dest_dir, limit=max(0, limit - len(out)))
        if len(out) >= limit:
            break
    return out
