# -*- coding: utf-8 -*-
"""クリアフォルダ1冊分をまとめてスキャンしたPDFを、書類1件ずつに切り分けるモジュール。

「📄 PDFを整理」タブから使う。**全文をPDF化した後**の整理が対象で、
中に何件の書類が入っていて、それぞれが何ページ目から何ページ目までなのか、
種類・日付・正式なタイトルは何かを AI に判定させる。
（倉庫でスマホ撮影した写真は「📥 ファイルを登録」側の担当。ここでは扱わない）

判定結果はそのまま**中身の目録**になるので、分割PDFを取り出すのと同時に
そのファイル1冊分の台帳登録にも流用できる（これがこのアプリに載せている理由）。

claude CLI の呼び出しは ai_reader と共有する（同じ経路を2つ持たないため）。
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import unicodedata

import ai_reader
import db

try:
    import fitz  # PyMuPDF
except ImportError:  # 呼び出し側で分かるように、使う瞬間まで落とさない
    fitz = None

TEXT_MIN_CHARS_PER_PAGE = 20   # 1ページあたりこれ未満ばかりならスキャン画像とみなす
TEXT_WINDOW = 30               # 一度にAIへ渡すページ数（テキスト経路）
VISION_WINDOW = 8              # 同（画像経路。1ページが高コストなので少なく刻む）
RENDER_DPI = 150
MAX_IMAGE_EDGE = 2200
DIGEST_CHARS = 700             # 各ページ冒頭の何文字をAIに渡すか

UNCLASSIFIED = "その他"

VISION_TIMEOUT = 900
TEXT_TIMEOUT = 300


class SplitError(RuntimeError):
    pass


def available() -> bool:
    return fitz is not None and ai_reader.claude_available()


# ---------------------------------------------------------------- PDFの下ごしらえ

def _open(pdf_bytes: bytes):
    if fitz is None:
        raise SplitError("PyMuPDF が入っていません（pip install pymupdf）")
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise SplitError(f"PDFとして開けませんでした: {type(e).__name__}") from e


def page_count(pdf_bytes: bytes) -> int:
    with _open(pdf_bytes) as doc:
        return doc.page_count


def _page_texts(pdf_bytes: bytes) -> list:
    with _open(pdf_bytes) as doc:
        return [(doc[i].get_text() or "").strip() for i in range(doc.page_count)]


def _has_text_layer(texts: list) -> bool:
    """テキスト層が実用になるか。半分以上のページに十分な文字があれば True。"""
    if not texts:
        return False
    good = sum(1 for t in texts if len(t) >= TEXT_MIN_CHARS_PER_PAGE)
    return good >= max(1, len(texts) // 2)


def _digest(texts: list, offset: int) -> str:
    """ページ番号つきのダイジェスト。全文だと長すぎるので各ページ冒頭だけ渡す。

    書類の境目は先頭（表題・日付・宛名）に出るので、冒頭だけで境界判定は足りる。
    """
    parts = []
    for i, t in enumerate(texts, start=offset):
        body = " ".join((t or "").split())
        if len(body) > DIGEST_CHARS:
            body = body[:DIGEST_CHARS] + "…"
        parts.append(f"--- ページ {i} ---\n{body or '(このページにテキストなし)'}")
    return "\n\n".join(parts)


def _render(pdf_bytes: bytes, first: int, last: int, out_dir: str) -> list:
    """1始まり両端含むページ範囲を PNG 化する。ファイル名にページ番号を入れる。"""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    with _open(pdf_bytes) as doc:
        for idx in range(first - 1, min(last, doc.page_count)):
            page = doc[idx]
            scale = RENDER_DPI / 72.0
            longest = max(page.rect.width, page.rect.height) * scale
            if longest > MAX_IMAGE_EDGE:
                scale *= MAX_IMAGE_EDGE / longest
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            dest = os.path.join(out_dir, f"p{idx + 1:04d}.png")
            pix.save(dest)
            written.append(dest)
    return written


def extract_range(pdf_bytes: bytes, start_page: int, end_page: int) -> bytes:
    """1始まり両端含むページ範囲を、新しいPDFのバイト列として取り出す。"""
    with _open(pdf_bytes) as src:
        last = src.page_count
        s = max(1, min(start_page, last))
        e = max(s, min(end_page, last))
        out = fitz.open()
        try:
            out.insert_pdf(src, from_page=s - 1, to_page=e - 1)
            return out.tobytes(garbage=4, deflate=True)
        finally:
            out.close()


# ---------------------------------------------------------------- プロンプト

def _system_prompt() -> str:
    types = " / ".join(db.DEFAULT_DOC_TYPES)
    return f"""あなたは日本の不動産会社で書類整理を担当する事務です。
クリアフォルダ1冊分をまとめてスキャンした1つのPDFを渡します。この中には**複数の別々の書類**が
続けて入っていることがあります。どのページからどのページまでが1件の書類かを見分け、
それぞれについて種類・日付・正式なタイトルを答えてください。

これは要約ではなく**書き写し**の作業です。守ること:

- **固有名詞（物件名・会社名・人名・地名）と数字は、書かれている文字を一字一句そのまま写す。**
  似た言葉への置き換えや、もっともらしい名称の推測による補完は誤りです。
- 読み取れない項目は**空文字にする**。部分的な推測で埋めないこと。
- 日付は書類の作成日・契約日を優先し `YYYY-MM-DD` 形式にする。和暦（令和/平成/昭和）は
  西暦に変換する。読み取れなければ空文字にする。
- `title` は表題をそのまま写し、区別に必要なら物件名や相手先を足す（例:
  「不動産売買契約書 グランドメゾン天王寺302 山田太郎」）。ファイル名になるので
  改行・スラッシュ・コロンは含めない。60文字以内。
- `property` はその書類に出てくる物件名・建物名（号室が分かれば含める）。無ければ空文字。
- `doc_type` は次のいずれかちょうど1つ: {types}
  迷ったら「{UNCLASSIFIED}」にする。勝手に新しい種類名を作らない。
- 1件の書類が複数ページに渡る場合はまとめて1件として扱う（ページごとに分けない）。
  契約書の約款・別表・添付図面は、その契約書と同じ1件に含める。
- **ページの取りこぼし・重複をしない。** 渡された範囲のすべてのページが、
  どれか1件の書類にちょうど1回だけ含まれるようにする。
- `continues_from_previous` は、**その範囲の最初の書類が前回の範囲から続いている**
  場合だけ true。それ以外は false。
- `confidence`: すべて明瞭に読み取れたら high、一部あいまいなら medium、
  文字が不鮮明で自信が持てなければ low。
- 出力は下記のJSONのみ。説明文やコードフェンスは付けない。

出力するJSON:
{{
  "documents": [
    {{
      "start_page": 1,
      "end_page": 3,
      "doc_type": "売買契約書",
      "title": "不動産売買契約書 グランドメゾン天王寺302",
      "property": "グランドメゾン天王寺 302号室",
      "date": "2021-07-10",
      "continues_from_previous": false,
      "confidence": "high"
    }}
  ]
}}"""


def _user_prompt(first: int, last: int, total: int, pending_title: str, body: str = "") -> str:
    head = (
        f"このPDFは全{total}ページです。今回はそのうち **ページ {first} 〜 {last}** を見てください。\n"
        f"start_page / end_page は、この通し番号（1〜{total}）で答えてください。\n"
    )
    if pending_title:
        head += (
            f"\n直前の範囲は「{pending_title}」という書類の途中で終わっています。"
            "今回の先頭ページがその続きなら、最初の1件の continues_from_previous を true に"
            "してください（続きでなければ false）。\n"
        )
    if body:
        head += "\n--- 各ページのテキスト ---\n" + body
    return head


# ---------------------------------------------------------------- 判定本体

def analyse(pdf_bytes: bytes, split: bool = True, note=lambda _m: None) -> list:
    """PDF1つを判定して、書類ごとのセグメント一覧を返す。

    セグメント: start_page / end_page / doc_type / title / property / date /
                confidence（1始まり・両端を含む）
    """
    total = page_count(pdf_bytes)
    if total == 0:
        raise SplitError("ページが0のPDFです")

    texts = _page_texts(pdf_bytes)
    use_text = _has_text_layer(texts)
    window = total if not split else (TEXT_WINDOW if use_text else VISION_WINDOW)
    note(f"{total}ページ / {'テキスト層あり' if use_text else 'スキャン画像（AIで読み取り）'}")

    system = _system_prompt()
    merged: list = []
    pending: dict | None = None

    tmp_root = tempfile.mkdtemp(prefix="cabsplit_")
    try:
        start = 1
        while start <= total:
            end = min(start + window - 1, total)
            title = pending["title"] if pending else ""

            if use_text:
                body = _digest(texts[start - 1 : end], start)
                prompt = system + "\n\n" + _user_prompt(start, end, total, title, body)
                out = ai_reader._invoke(prompt, note, timeout=TEXT_TIMEOUT,
                                        model=ai_reader.TEXT_MODEL)
            else:
                page_dir = os.path.join(tmp_root, f"w{start}")
                images = _render(pdf_bytes, start, end, page_dir)
                if not images:
                    raise SplitError(f"ページ {start}〜{end} を画像化できませんでした")
                names = "、".join(os.path.basename(p) for p in images)
                prompt = (
                    system + "\n\n" + _user_prompt(start, end, total, title)
                    + f"\n\n画像ファイル {names} を Read ツールで**すべて**開いてください。"
                    "ファイル名の番号がページ番号に対応しています。"
                    "各ページの文字を最後まで丁寧に読み、固有名詞と数字を正確に確認したうえで"
                    "JSONを組み立ててください。"
                )
                out = ai_reader._invoke(
                    prompt, note,
                    extra_args=["--tools", "Read", "--add-dir", page_dir],
                    cwd=page_dir, timeout=VISION_TIMEOUT,
                    model=ai_reader.VISION_MODEL,
                )

            docs = _clean(out, start, end)
            if not docs:
                # 判定できなかった範囲も捨てずに1件として拾う
                docs = [_blank(start, end)]

            for i, d in enumerate(docs):
                if i == 0 and d["continues_from_previous"] and pending:
                    pending["end_page"] = max(pending["end_page"], d["end_page"])
                    if d["confidence"] == "low":
                        pending["confidence"] = "low"
                    continue
                if pending:
                    merged.append(pending)
                pending = d
            start = end + 1
    finally:
        import shutil
        shutil.rmtree(tmp_root, ignore_errors=True)

    if pending:
        merged.append(pending)
    return _fill_gaps(merged, total)


def _blank(start: int, end: int) -> dict:
    return {"start_page": start, "end_page": end, "doc_type": UNCLASSIFIED,
            "title": "", "property": "", "date": "",
            "continues_from_previous": False, "confidence": "low"}


def _clean(out, lo: int, hi: int) -> list:
    """AI出力を検証して、範囲内の妥当なセグメントだけにする。"""
    if not out:
        return []
    import json
    try:
        data = json.loads(ai_reader._strip_fence(out))
    except (json.JSONDecodeError, TypeError):
        return []
    raw = data.get("documents") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []

    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            s = int(item.get("start_page"))
            e = int(item.get("end_page"))
        except (TypeError, ValueError):
            continue
        s, e = max(lo, min(s, hi)), max(lo, min(e, hi))
        if e < s:
            s, e = e, s
        t = str(item.get("doc_type", "")).strip()
        conf = str(item.get("confidence", "")).lower()
        result.append({
            "start_page": s,
            "end_page": e,
            "doc_type": t if t in db.DEFAULT_DOC_TYPES else UNCLASSIFIED,
            "title": str(item.get("title", "")).strip(),
            "property": str(item.get("property", "")).strip(),
            "date": normalise_date(str(item.get("date", ""))),
            "continues_from_previous": bool(item.get("continues_from_previous")),
            "confidence": conf if conf in ("high", "medium", "low") else "medium",
        })
    result.sort(key=lambda d: (d["start_page"], d["end_page"]))
    return result


def _fill_gaps(segs: list, total: int) -> list:
    """重複を削り抜けを埋めて、1〜total を必ず覆う形に整える。

    AIがページを1枚取りこぼしても、そのページが結果から消えないようにする保険。
    """
    result: list = []
    cursor = 1
    for s in sorted(segs, key=lambda d: (d["start_page"], d["end_page"])):
        s["start_page"] = max(s["start_page"], cursor)
        if s["end_page"] < s["start_page"]:
            continue  # 直前の書類に飲み込まれた
        if s["start_page"] > cursor:
            if result:
                result[-1]["end_page"] = s["start_page"] - 1
            else:
                result.append(_blank(cursor, s["start_page"] - 1))
        result.append(s)
        cursor = s["end_page"] + 1
    if cursor <= total:
        if result:
            result[-1]["end_page"] = total
        else:
            result.append(_blank(1, total))
    return result


# ---------------------------------------------------------------- 日付・ファイル名

# 和暦の元号 → その元号の元年の前年（元年を足すと西暦になる）
_ERA_BASE = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911, "明治": 1867}


def _wareki(s: str) -> str:
    """「令和3年7月10日」→「2021-07-10」。AIが和暦のまま返したときの保険。"""
    m = re.search(r"(令和|平成|昭和|大正|明治)\s*(元|\d{1,2})\s*年"
                  r"(?:\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?)?", s)
    if not m:
        return s
    y = _ERA_BASE[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))
    mo, d = m.group(3), m.group(4)
    return f"{y:04d}-{int(mo):02d}-{int(d):02d}" if mo and d else (
        f"{y:04d}-{int(mo):02d}" if mo else str(y))


def normalise_date(v: str) -> str:
    """YYYY-MM-DD に寄せる。不明な部分は 00、全く不明なら空文字。"""
    s = _wareki((v or "").strip())
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{4})\D+(\d{1,2})", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-00"
    m = re.search(r"(\d{4})", s)
    if m:
        return f"{int(m.group(1)):04d}-00-00"
    return ""


_BAD = re.compile(r'[\\/:*?"<>|\r\n\t]')


def safe_component(s: str, limit: int = 60) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = _BAD.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:limit].rstrip() if len(s) > limit else s


def build_name(seg: dict, fallback: str) -> str:
    """YYYY-MM-DD_種類_タイトル.pdf を作る。日付不明はゼロ埋めで先頭に集める。"""
    date = seg.get("date") or "0000-00-00"
    kind = safe_component(seg.get("doc_type", ""), 24) or UNCLASSIFIED
    title = safe_component(seg.get("title", "")) or safe_component(fallback)
    return f"{date}_{kind}_{title}.pdf"


def make_zip(pdf_bytes: bytes, segs: list, fallback: str) -> bytes:
    """判定結果どおりに切り出した分割PDFを、種類別フォルダ入りのZIPにまとめる。"""
    import zipfile

    buf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for seg in segs:
            name = build_name(seg, fallback)
            folder = safe_component(seg.get("doc_type", ""), 24) or UNCLASSIFIED
            path = f"{folder}/{name}"
            n = 2
            while path in used:  # 同名は連番。上書きしない
                stem, ext = os.path.splitext(name)
                path = f"{folder}/{stem}_{n}{ext}"
                n += 1
            used.add(path)
            zf.writestr(path, extract_range(pdf_bytes, seg["start_page"], seg["end_page"]))
    return buf.getvalue()


def to_contents_lines(segs: list) -> list:
    """判定結果を、台帳の「中身の目録」の行にする。"""
    lines = []
    for s in segs:
        bits = [s.get("date") or "", s.get("doc_type") or "", s.get("title") or ""]
        prop = s.get("property") or ""
        if prop and prop not in (s.get("title") or ""):
            bits.append(prop)
        lines.append(" ".join(b for b in bits if b).strip())
    return [ln for ln in lines if ln]
