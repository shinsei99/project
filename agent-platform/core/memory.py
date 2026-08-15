"""部隊の学習（過去の失敗を次に活かす）

これが無いと何が起きるか:
  司令塔の最終確認が「原付が抜けている」「文字が1文字だけ次行に落ちている」と
  見つけても、**次のジョブでは忘れている**。同じ不良を何度でも作る。
  毎回ゼロから始まるので、使うほど良くなるということが起きない。

やっていること:
  最終確認の結果を `knowledge/lessons.json` に溜め、次から制作部隊に渡す。
  **失敗（避けること）と成功（効いたこと）の両方**を覚える。
  失敗だけだと「やってはいけないこと」しか増えず、良い作り方が伝わらない。
  モデルを学習させるのではなく、**組織の申し送りを蓄える**やり方。
  人が読める `knowledge/lessons.md` も一緒に書くので、中身を確認・編集できる。

肥大化しないよう、型ごとに新しいものから一定数だけ使う。
同じ内容は回数だけ増やして重複させない（何度も起きる不良ほど上に出る）。
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, List

from .config import ROOT

STORE = ROOT / "knowledge" / "lessons.json"
READABLE = ROOT / "knowledge" / "lessons.md"
MAX_PER_GENRE = 40      # 保存する上限
USE_PER_GENRE = 12      # プロンプトに載せる数
_LOCK = threading.Lock()


def _load() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    if not STORE.exists():
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # 旧形式（型 → 失敗の配列）を読めるようにしておく
    fixed = {}
    for genre, value in data.items():
        if isinstance(value, list):
            fixed[genre] = {"failures": value, "successes": []}
        elif isinstance(value, dict):
            fixed[genre] = {"failures": value.get("failures") or [],
                            "successes": value.get("successes") or []}
    return fixed


def _key(text: str) -> str:
    """同じ不良かどうかの判定用。表記ゆれを落として比べる。"""
    normalized = re.sub(r"[「」『』（）()\s、。・:：/／\d]+", "", str(text))
    return normalized[:40]


def _remember(genre: str, kind: str, texts: List[str], note: str = "") -> int:
    """kind = "failures"（避けること）/ "successes"（効いたこと）。"""
    genre = genre or "共通"
    texts = [str(x).strip() for x in (texts or []) if str(x).strip()]
    if not texts:
        return 0

    with _LOCK:
        data = _load()
        bucket = data.setdefault(genre, {"failures": [], "successes": []})[kind]
        index = {_key(item.get("text", "")): item for item in bucket}
        added = 0
        today = _dt.date.today().isoformat()

        for text in texts:
            key = _key(text)
            if key in index:
                # 同じことが再び起きた。回数を増やして重みを付ける
                index[key]["count"] = int(index[key].get("count", 1)) + 1
                index[key]["last_seen"] = today
                continue
            item = {"text": text[:200], "note": note[:200], "count": 1,
                    "first_seen": today, "last_seen": today}
            bucket.append(item)
            index[key] = item
            added += 1

        bucket.sort(key=lambda x: (int(x.get("count", 1)), x.get("last_seen", "")),
                    reverse=True)
        data[genre][kind] = bucket[:MAX_PER_GENRE]

        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_readable(data)
        return added


def record(genre: str, gaps: List[str], fix: str = "") -> int:
    """指摘された不良（避けること）を覚える。"""
    return _remember(genre, "failures", gaps, fix)


def record_success(genre: str, points: List[str], note: str = "") -> int:
    """効いていた点（次も使うこと）を覚える。

    失敗だけ溜めると「やってはいけないこと」ばかりが増え、
    良い作り方が伝わらない。効いた要素も同じ重みで残す。
    """
    return _remember(genre, "successes", points, note)


def lessons_for(genre: str = "", kind: str = "failures",
                limit: int = USE_PER_GENRE) -> List[Dict[str, Any]]:
    """この型の申し送り。よく起きるものを先に。"""
    data = _load()
    items = list((data.get(genre or "共通") or {}).get(kind) or [])
    if genre and genre != "共通":
        items += list((data.get("共通") or {}).get(kind) or [])
    items.sort(key=lambda x: (int(x.get("count", 1)), x.get("last_seen", "")), reverse=True)
    return items[:limit]


def describe_for_prompt(genre: str = "", limit: int = USE_PER_GENRE) -> str:
    """制作部隊のプロンプトに差し込む申し送り（効いたこと・避けること）。"""
    blocks = []
    wins = lessons_for(genre, "successes", limit)
    if wins:
        lines = ["【これまで効いた作り方（今回も使うこと）】"]
        for item in wins:
            times = int(item.get("count", 1))
            lines.append("- %s%s" % (item["text"],
                                     "（%d回有効）" % times if times > 1 else ""))
        blocks.append("\n".join(lines))

    fails = lessons_for(genre, "failures", limit)
    if fails:
        lines = ["【過去に指摘された不良（同じ失敗を繰り返さないこと）】"]
        for item in fails:
            times = int(item.get("count", 1))
            lines.append("- %s%s" % (item["text"],
                                     "（%d回発生）" % times if times > 1 else ""))
            if item.get("note"):
                lines.append("  → 対策: %s" % item["note"])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def stats() -> Dict[str, Dict[str, int]]:
    return {genre: {"効いたこと": len(value.get("successes") or []),
                    "避けること": len(value.get("failures") or [])}
            for genre, value in _load().items()}


def _write_readable(data) -> None:
    """人が読んで直せるように Markdown でも残す。"""
    lines = ["# 部隊の申し送り", "",
             "最終確認の結果を自動で溜めています。制作部隊は次のジョブからこれを読んで作ります。",
             "**間違った学習をしていたら、この一覧から消してください**"
             "（`knowledge/lessons.json` が本体）。", ""]
    titles = [("successes", "✅ 効いた作り方（次も使う）", "効いた点"),
              ("failures", "⚠️ 指摘された不良（繰り返さない）", "不良")]
    for genre, value in sorted(data.items()):
        lines += ["## %s" % genre, ""]
        for kind, heading, column in titles:
            items = value.get(kind) or []
            if not items:
                continue
            lines += ["### %s（%d件）" % (heading, len(items)), "",
                      "| 回数 | %s | 補足 | 最終 |" % column, "|---|---|---|---|"]
            for item in sorted(items, key=lambda x: -int(x.get("count", 1))):
                lines.append("| %d | %s | %s | %s |" % (
                    int(item.get("count", 1)),
                    str(item.get("text", "")).replace("|", "／"),
                    str(item.get("note", "")).replace("|", "／") or "-",
                    item.get("last_seen", "")))
            lines.append("")
    READABLE.parent.mkdir(parents=True, exist_ok=True)
    READABLE.write_text("\n".join(lines), encoding="utf-8")
