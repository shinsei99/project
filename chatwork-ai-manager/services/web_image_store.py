"""ネットから取得した画像（streetview_lookup等）を一時的に保持する保管庫（TASK-20260819-005）。

なぜ必要か:
  streetview_lookup は tempfile.TemporaryDirectory() で画像を取得しており、claude vision
  での解析が終わると同時に画像ファイルは自動削除される。Chatwork添付やLINE画像pushは
  解析の後に別Toolとして呼ばれるため、その時点ではもう画像が無く送れなかった。
  ここに短命の置き場を作り、image_token で受け渡しできるようにする。

社内資料(file_send.py)とは別物: 送信元フォルダの限定は不要
（すでにWeb上の公開画像であり、共有フォルダの社外秘ファイルではないため）。
TTLで自動掃除するだけの一時置き場なので、長期保管には使わない。
"""
import os
import time
import uuid

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_DIR = os.path.join(APP_DIR, "data", "web_images")
TTL_SECONDS = 6 * 3600   # 6時間（取得直後に送るためのものなので長くは要らない）


def _ensure_dir():
    os.makedirs(STORE_DIR, exist_ok=True)


def _cleanup(max_age: int = TTL_SECONDS):
    now = time.time()
    try:
        for fname in os.listdir(STORE_DIR):
            fpath = os.path.join(STORE_DIR, fname)
            try:
                if now - os.path.getmtime(fpath) > max_age:
                    os.remove(fpath)
            except OSError:
                pass
    except FileNotFoundError:
        pass


def save(src_path: str) -> str:
    """画像ファイルを保管庫へコピーし、送信用の image_token（=保存ファイル名）を返す。"""
    _ensure_dir()
    _cleanup()
    ext = os.path.splitext(src_path)[1] or ".jpg"
    token = uuid.uuid4().hex + ext
    dest = os.path.join(STORE_DIR, token)
    with open(src_path, "rb") as f_in, open(dest, "wb") as f_out:
        f_out.write(f_in.read())
    return token


def path_for(token: str):
    """image_token から実ファイルパスを引く。存在しない/期限切れなら None。"""
    if not token or "/" in token or "\\" in token or ".." in token:
        return None
    path = os.path.join(STORE_DIR, token)
    return path if os.path.isfile(path) else None
