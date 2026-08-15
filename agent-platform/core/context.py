"""ジョブ（1回の指示）の文脈。全エージェントがこれを読み書きして連携する。"""
from __future__ import annotations

import datetime as _dt
import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import get_settings
from .io_utils import ensure_dir, write_json

# 出力先のサブフォルダ（成果物の種類ごとに分ける）
SUBDIRS = ("input", "research", "plan", "images", "slides", "audio", "video", "social", "reports")


@dataclass
class Artifact:
    kind: str            # image / pptx / audio / video / markdown / json ...
    path: str            # ジョブフォルダからの相対パス
    label: str = ""
    agent: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


class JobContext:
    """1ジョブ分の入出力・状態・ログをまとめて持つ。

    `state` に各エージェントの成果（構造化データ）を入れ、後続がそれを読む。
    ファイル実体はジョブフォルダ配下に置き、`artifacts` に台帳として記録する。
    """

    def __init__(self, brief: str, job_id: Optional[str] = None,
                 options: Optional[Dict[str, Any]] = None,
                 on_event: Optional[Callable[[Dict[str, Any]], None]] = None):
        st = get_settings()
        self.brief = brief.strip()
        self.job_id = job_id or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.root = ensure_dir(st.output_dir / self.job_id)
        self.options: Dict[str, Any] = dict(options or {})
        self.state: Dict[str, Any] = {}
        self.artifacts: List[Artifact] = []
        self.results: List[Any] = []          # AgentResult の一覧（pipeline が追記）
        self.on_event = on_event
        self.started_at = _dt.datetime.now()
        self._lock = threading.Lock()
        self.log_path = self.root / "run.log"
        for name in SUBDIRS:
            ensure_dir(self.root / name)

    # --- パス ---
    def dir(self, name: str) -> Path:
        return ensure_dir(self.root / name)

    def rel(self, path) -> str:
        p = Path(path)
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    # --- 成果物 ---
    def add_artifact(self, kind: str, path, label: str = "", agent: str = "",
                     **meta) -> Artifact:
        art = Artifact(kind=kind, path=self.rel(path), label=label, agent=agent, meta=meta)
        with self._lock:
            self.artifacts.append(art)
        self.emit({"type": "artifact", "artifact": asdict(art)})
        return art

    def artifacts_of(self, kind: str) -> List[Artifact]:
        return [a for a in self.artifacts if a.kind == kind]

    # --- ログ・イベント ---
    def log(self, message: str, level: str = "info", agent: str = "") -> None:
        self.emit({"type": "log", "level": level, "agent": agent, "message": message})

    def emit(self, event: Dict[str, Any]) -> None:
        event.setdefault("ts", _dt.datetime.now().isoformat(timespec="seconds"))
        with self._lock:
            try:
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            except OSError:
                pass
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                # UI側の不調でパイプラインを落とさない
                pass

    # --- 読み込み（途中で失敗した工程だけやり直すため） ---
    @classmethod
    def load(cls, job_id: str, on_event: Optional[Callable[[Dict[str, Any]], None]] = None):
        """保存済みジョブを復元する。

        調査や構成に何分もかけた後で動画だけ失敗する、ということが実際に起きる。
        そのときにLLM工程をやり直さずに済ませるためのもの。
        """
        st = get_settings()
        path = st.output_dir / job_id / "job.json"
        if not path.exists():
            raise FileNotFoundError("ジョブが見つかりません: %s" % path)
        data = json.loads(path.read_text(encoding="utf-8"))
        ctx = cls(brief=data.get("brief", ""), job_id=job_id,
                  options=data.get("options") or {}, on_event=on_event)
        ctx.state = data.get("state") or {}
        ctx.artifacts = [Artifact(**a) for a in data.get("artifacts") or []]
        return ctx

    # --- 保存 ---
    def save(self) -> Path:
        payload = {
            "job_id": self.job_id,
            "brief": self.brief,
            "options": self.options,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "saved_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "state": _jsonable(self.state),
            "artifacts": [asdict(a) for a in self.artifacts],
            "results": [_jsonable(r) for r in self.results],
        }
        return write_json(self.root / "job.json", payload)


def _jsonable(value: Any) -> Any:
    """dataclass や Path が混ざっていても JSON に落とせる形へ整える。"""
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
