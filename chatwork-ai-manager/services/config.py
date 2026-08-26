"""設定・シークレット読み込み。

worker（非Streamlit）と app（Streamlit）の両方から使うため、
`.streamlit/secrets.toml` を自前パースしつつ環境変数フォールバックも持つ。
（Python 3.9 に tomllib が無いため、フラットな secrets.toml を最小パーサで読む）
"""
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_PATH = os.path.join(APP_DIR, ".streamlit", "secrets.toml")

_cache = None


def _parse_flat_toml(text: str) -> dict:
    """`key = "value"` / `key = 123` / `key = true` 形式のフラット TOML を読む。

    セクション見出し [xxx] とコメント # は無視（このアプリの secrets はフラット）。
    """
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key, _, raw = line.partition("=")
        key = key.strip()
        raw = raw.strip()
        # 行末コメント除去（引用符内は考慮しない簡易版）
        if raw and raw[0] not in ("'", '"'):
            raw = raw.split("#", 1)[0].strip()
        if len(raw) >= 2 and raw[0] in ("'", '"') and raw[-1] == raw[0]:
            val = raw[1:-1]
        elif raw.lower() in ("true", "false"):
            val = raw.lower() == "true"
        else:
            try:
                val = int(raw)
            except ValueError:
                val = raw
        out[key] = val
    return out


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    data = {}
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                data = _parse_flat_toml(f.read())
        except Exception:
            data = {}
    _cache = data
    return data


# secrets.toml のキー名 -> 環境変数フォールバック
_ENV_MAP = {
    "chatwork_api_token": "CHATWORK_API_TOKEN",
    "dashboard_password": "CWAI_DASHBOARD_PASSWORD",
    "chatwork_webhook_token": "CHATWORK_WEBHOOK_TOKEN",
    "line_channel_secret": "LINE_CHANNEL_SECRET",
    "line_channel_access_token": "LINE_CHANNEL_ACCESS_TOKEN",
    "line_allowed_user_ids": "LINE_ALLOWED_USER_IDS",
    "ngrok_domain": "NGROK_DOMAIN",
    "reinfolib_api_key": "REINFOLIB_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "gemini_model": "GEMINI_MODEL",
}


def get(key: str, default=None):
    data = _load()
    if key in data and data[key] not in ("", None):
        return data[key]
    env_key = _ENV_MAP.get(key, key.upper())
    env_val = os.environ.get(env_key)
    if env_val not in (None, ""):
        return env_val
    return default


def chatwork_token() -> str:
    tok = get("chatwork_api_token")
    if not tok:
        raise RuntimeError(
            "Chatwork API トークンが未設定です。"
            ".streamlit/secrets.toml に chatwork_api_token を設定してください。"
        )
    return str(tok)
