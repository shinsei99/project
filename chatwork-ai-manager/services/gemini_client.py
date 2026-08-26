"""Gemini API 音声文字起こしクライアント（標準ライブラリのみ・SDK非依存）。

**なぜ Gemini か**: `claude` CLI（このアプリのAIバックエンド）は音声入力に対応していない
（画像は Read ツールで読めるが音声は不可）。Gemini は音声をそのまま添付できるため、
「文字にする」までをここに任せ、要約・TODO抽出等の言語理解は従来どおり
`services/claude_client.py`（Claude）に戻す。この分業なので Tool 1本の役目が小さく保てる。

**新規キー発行はしていない**。brain-dump / madori-tracer / pasha-calo / agent-platform と
同じ全社共有の Gemini APIキーを、このアプリの `.streamlit/secrets.toml` にも登録して使う。

依存を増やさない理由: 本番の `/usr/bin/python3`(3.9) は51本のアプリが共有する環境で、
`google-genai` 等のSDKを入れると依存衝突のリスクがある（CLAUDE.md「ライブラリを追加していない
理由」と同じ判断）。他の外部APIクライアント（chatwork.py / japanpost_api.py / estat_api.py /
google_maps_api.py）もすべて urllib 直叩きなので、それに揃えた。
"""
import base64
import json
import urllib.error
import urllib.request

from services import config

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_DEFAULT_MODEL = "gemini-2.5-flash"

_TRANSCRIBE_PROMPT = (
    "添付された音声を、日本語として自然な文章に文字起こししてください。\n"
    "- 話された内容を忠実に書き起こす（勝手に要約・省略・脚色はしない）。\n"
    "- 「えー」「あのー」などの言い淀みや意味のない相づちは適度に除き、読みやすくする。\n"
    "- 句読点・改行を適切に入れる。話題が変わったら段落を分ける。\n"
    "- 複数人が話している場合は、話者が変わるごとに改行する。\n"
    "- どうしても聞き取れない箇所は「（聞き取れず）」と記す。\n"
    "- 音声が無音・雑音のみで内容が無い場合は、空文字だけを出力してください。\n"
    "文字起こしした本文だけを出力してください。前置き・説明・注釈は一切不要です。"
)


class GeminiError(Exception):
    pass


def transcribe_audio(audio_bytes: bytes, mime_type: str, timeout: int = 120) -> str:
    """音声バイト列を文字起こしする。戻り値は本文のみの文字列（無音なら空文字）。

    失敗（キー未設定・HTTPエラー・応答形式不正）は GeminiError を投げる。呼び出し側で拾うこと。
    """
    api_key = config.get("gemini_api_key")
    if not api_key:
        raise GeminiError("gemini_api_key が未設定です（.streamlit/secrets.toml）")
    model = config.get("gemini_model", _DEFAULT_MODEL)
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type,
                                  "data": base64.b64encode(audio_bytes).decode("ascii")}},
                {"text": _TRANSCRIBE_PROMPT},
            ],
        }],
        "generationConfig": {"temperature": 0.2},
    }
    url = _ENDPOINT.format(model=model) + f"?key={api_key}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        raise GeminiError(f"Gemini API エラー({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise GeminiError(f"Gemini API に接続できませんでした: {e}") from e
    try:
        candidates = data.get("candidates") or []
        if not candidates:
            # 安全フィルタ等でブロックされた場合、candidates が空で返ることがある
            reason = data.get("promptFeedback", {}).get("blockReason")
            if reason:
                raise GeminiError(f"Gemini がブロックしました: {reason}")
            return ""
        parts = candidates[0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise GeminiError(
            f"Gemini API の応答形式が不正です: {json.dumps(data, ensure_ascii=False)[:300]}"
        ) from e
    return text
