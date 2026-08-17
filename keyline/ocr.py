"""身分証・名刺の読み取り（OCR）。

`claude` CLI のビジョン（Read ツール）を使う。**APIキー不要・追加費用なし。**
既存の `baikai-generator/services/registry_parser.py`（謄本の読み取り）と同じ経路で、
そちらで実用済みの呼び出し方をそのまま踏襲している。

⚠️ 読み取りの瞬間、画像は Anthropic のサーバーへ送られる。
   免許証は氏名・住所・生年月日・免許証番号を含むため、この点は README に明記してある。
   撮った画像は data/id_images/ に置き、**返却から30日で自動削除**する（purge.py）。

★OCRの結果をそのまま台帳に書かないこと。
  必ず人が確認・修正できる画面を挟む。誤読をそのまま「誰に貸したか」の記録にすると、
  鍵が返らないときに追跡できなくなる。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# baikai-generator と同じ場所。which でも解決できるようにしておく
CLAUDE_BIN = shutil.which("claude") or "/opt/homebrew/bin/claude"
MODEL = "sonnet"
TIMEOUT = 120

# 現場のスマホで撮った写真をそのまま送ると数MBになり、読み取りが遅くなる。
# 長辺1600pxあれば免許証・名刺の文字は十分読める。
MAX_EDGE = 1600
JPEG_QUALITY = 85


class OcrUnavailable(Exception):
    """OCRが使えない（claude CLI が無い・タイムアウト等）。手入力に案内する。"""


PROMPT = """添付の画像は日本の{doc}です。写っている情報だけを読み取り、JSONだけを出力してください。

{{
  "name": "氏名（姓名。スペースは詰める）",
  "company": "会社名・屋号（名刺の場合。無ければ空文字）",
  "phone": "電話番号（携帯優先。ハイフンあり。無ければ空文字）",
  "confidence": "high | medium | low"
}}

守ること:
- 読み取れない項目は空文字にする。**推測で埋めないこと。**
- 画像が不鮮明・そもそも{doc}でない場合は confidence を low にする。
- 住所・生年月日・免許証番号は**読み取らないでください**（このシステムでは使いません）。
- JSON以外の文字（説明・コードフェンス）を出力しないこと。

画像ファイル: {filename}
"""

DOC_LABEL = {
    "drivers_license": "運転免許証",
    "business_card": "名刺",
    "other": "身分証明書",
}


def _shrink(src: Path, dst: Path) -> None:
    """長辺 MAX_EDGE に縮めて JPEG で保存。Pillow が無ければそのままコピー。"""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        shutil.copyfile(src, dst)
        return
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)     # スマホ写真の回転情報を実際に反映させる
        im = im.convert("RGB")
        if max(im.size) > MAX_EDGE:
            im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)


def _strip_fence(text: str) -> str:
    """```json ... ``` で囲まれていても中身を取り出す。"""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def read_document(image_path: str | Path, kind: str = "business_card") -> dict:
    """画像から 氏名・会社名・電話 を読む。

    返り値: {"name": str, "company": str, "phone": str, "confidence": str}
    読めなかった項目は空文字。OCRが使えないときは OcrUnavailable を投げる。
    """
    src = Path(image_path)
    if not src.exists():
        raise OcrUnavailable("画像が見つかりませんでした")
    if not os.path.exists(CLAUDE_BIN):
        raise OcrUnavailable("読み取り機能が使えません（claude CLI が見つかりません）")

    # claude には作業ディレクトリごと見せるので、**その貸出の画像1枚だけ**を置いた
    # 一時ディレクトリを作って渡す。data/ をまるごと見せない（他人の身分証を渡さない）。
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        name = "document.jpg"
        _shrink(src, work / name)

        prompt = PROMPT.format(doc=DOC_LABEL.get(kind, "身分証明書"), filename=name)
        cmd = [
            CLAUDE_BIN, "-p", prompt,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            "--model", MODEL,
            "--tools", "Read",
            "--add-dir", str(work),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=TIMEOUT, cwd=str(work))
        except subprocess.TimeoutExpired:
            raise OcrUnavailable("読み取りに時間がかかりすぎました。手入力してください")
        except (FileNotFoundError, OSError):
            raise OcrUnavailable("読み取り機能を起動できませんでした")

        if proc.returncode != 0:
            raise OcrUnavailable("読み取りに失敗しました。手入力してください")

        try:
            outer = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise OcrUnavailable("読み取り結果を解釈できませんでした")
        if outer.get("is_error"):
            raise OcrUnavailable("読み取りに失敗しました。手入力してください")

        try:
            data = json.loads(_strip_fence(outer.get("result", "")))
        except (json.JSONDecodeError, TypeError):
            raise OcrUnavailable("読み取り結果を解釈できませんでした")

    if not isinstance(data, dict):
        raise OcrUnavailable("読み取り結果を解釈できませんでした")

    return {
        "name": str(data.get("name") or "").strip(),
        "company": str(data.get("company") or "").strip(),
        "phone": str(data.get("phone") or "").strip(),
        "confidence": str(data.get("confidence") or "low").strip(),
    }


def is_available() -> bool:
    """OCRが使える環境か。画面で撮影ボタンを出すかどうかの判定に使う。"""
    return os.path.exists(CLAUDE_BIN)


# ---------------------------------------------------------------------------
# 画像の保存と削除
# ---------------------------------------------------------------------------
def save_image(data: bytes, data_dir: Path, ts: str) -> str:
    """アップロードされた画像を data/id_images/YYYY/MM/ に保存し、相対パスを返す。

    年月で切るのは、後から「この月の分を消す」を人手でもやれるようにするため。
    """
    import uuid

    year, month = ts[0:4], ts[5:7]
    rel_dir = Path("id_images") / year / month
    (data_dir / rel_dir).mkdir(parents=True, exist_ok=True)
    rel = rel_dir / f"{uuid.uuid4()}.jpg"

    tmp = data_dir / rel.with_suffix(".orig")
    tmp.write_bytes(data)
    try:
        _shrink(tmp, data_dir / rel)          # 保存も縮小版にする（原寸は要らない）
    finally:
        tmp.unlink(missing_ok=True)
    os.chmod(data_dir / rel, 0o600)
    return str(rel)


def purge_old_images(con, data_dir: Path, days: int = 30) -> int:
    """返却から `days` 日を過ぎた身分証画像を消す。消した件数を返す。

    ファイルを消してから id_image_purged_at を立てる順にしてある。
    逆にすると、途中で落ちたときに「DBは消したことになっているのに実体が残る」
    ——つまり気づかないまま個人情報が残り続ける——という最悪の形になる。
    """
    import db as dbmod

    cutoff = dbmod.ts_plus(days=-days)
    rows = con.execute(
        """SELECT id, id_image_path FROM checkout_logs
            WHERE id_image_path IS NOT NULL AND id_image_purged_at IS NULL
              AND returned_at IS NOT NULL AND returned_at < ?""",
        (cutoff,),
    ).fetchall()

    purged = 0
    for r in rows:
        try:
            (data_dir / r["id_image_path"]).unlink(missing_ok=True)
        except OSError:
            continue          # 消せなかったものは次回に回す（DBを先に更新しない）
        con.execute("UPDATE checkout_logs SET id_image_purged_at = ? WHERE id = ?",
                    (dbmod.now_ts(), r["id"]))
        purged += 1
    return purged
