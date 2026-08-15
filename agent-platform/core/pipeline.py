"""パイプライン実行器。

一列に並べて順番に流すのではなく、次の2つで動く。

1. **必要な部隊だけ動かす**
   司令塔が「今回作るもの（deliverables）」を決め、それに要らない部隊は起動しない。
   チラシ1枚なら音声・動画・SNSの部隊は最初から出番なし。

2. **依存関係が無い部隊は同時に動かす**
   各部隊が `depends_on` を宣言しており、前提が揃ったものから並列で走る。
   例: レビューと法務は同時、画像・音声・SNSも同時。

流れ（依存グラフ）:

    司令塔
      └→ リサーチャー ─→ 企画構成 ─┬→ 高速チェック ─┐
                                     └→ 法務監査 ────┴→ 司令塔(中間調整)
                                                          ├→ 画像生成 ─┬→ パワポ
                                                          ├→ 音声合成 ─┴→ 動画
                                                          └→ SNS告知
                                                                        └→ 検品/QA
"""
from __future__ import annotations

import datetime as _dt
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Dict, List, Optional, Set

from .base_agent import AgentResult
from .config import get_settings
from .context import JobContext
from .io_utils import write_text

# 画面と一覧の表示順（実行順ではない。実行順は依存関係が決める）
PIPELINE_ORDER = [
    "orchestrator",
    "researcher",
    "planner",
    "reviewer",
    "legal",
    "supervisor",
    "poster",
    "image",
    "flyer",
    "ppt",
    "voice",
    "video",
    "publisher",
    "acceptance",
]

# 司令塔が挙げる「作るもの」と、そのために必要な部隊
DELIVERABLE_AGENTS = {
    "signage": {"poster"},
    "flyer": {"image", "flyer"},
    "maisoku": {"image", "flyer"},
    "pptx": {"image", "ppt"},
    "images": {"image"},
    "mp3": {"voice"},
    "audio": {"voice"},
    "mp4": {"image", "voice", "video"},
    "video": {"image", "voice", "video"},
    "sns": {"publisher"},
    "research": {"researcher"},
}

# 同時に走らせる上限。LLMのレート制限とMacの負荷を考えてこれくらい。
MAX_PARALLEL = 4


class Pipeline:
    def __init__(self, agents: Optional[List[Any]] = None):
        if agents is None:
            from agents import build_default_agents

            agents = build_default_agents()
        self.agents = {a.key: a for a in agents}

    # --- 実行対象を決める ---
    def _select(self, ctx: JobContext, only, skip) -> Set[str]:
        keys = set(self.agents)
        if only:
            keys &= set(only)
        if skip:
            keys -= set(skip)
        return keys

    def _prune_by_plan(self, ctx: JobContext, selected: Set[str]) -> Set[str]:
        """司令塔の計画を見て、今回要らない部隊を外す。

        画面で「作るもの」を明示された場合はそちらが優先（人の指定が最優先）。
        """
        plan = ctx.state.get("plan") or {}

        # 掲示物（貼り紙）は1部隊が通しで作る。分業すると意図が壊れるため
        # （構成ライターのレイアウト指示がそのまま印刷された事故があった）。
        if plan.get("genre") == "signage" and "poster" in selected:
            keep = {"orchestrator", "poster", "legal", "acceptance"} & selected
            dropped = sorted(selected - keep)
            if dropped:
                names = "・".join(self.agents[k].name_ja for k in dropped)
                ctx.log("掲示物なので %s は動かしません（1部隊で作ります）" % names)
                ctx.emit({"type": "agents_skipped", "agents": dropped,
                          "message": "掲示物のため不要な工程を省きました: %s" % names})
            return keep

        # **紙面1枚の依頼は、司令塔が主導して直接作る。**
        # 企画構成ライター→高速チェッカー→中間調整の3工程は、スライド原稿を
        # 書いて検査して直しているだけで、チラシの文言はチラシビルダーが
        # 調査結果から直接書いている。実測で60秒使って紙面に1文字も届いていなかった。
        # 専門部隊は「必要なときだけ呼ぶ」（音声・動画・SNSが要る依頼なら残る）。
        genre = str(plan.get("genre") or "")
        wanted = {str(x).lower().strip() for x in (plan.get("deliverables") or [])}
        if genre in ("promo", "maisoku") and wanted <= {"flyer", "images", "research"}:
            keep = {"orchestrator", "researcher", "flyer", "legal",
                    "acceptance"} & selected
            dropped = sorted(selected - keep)
            if dropped:
                names = "・".join(self.agents[k].name_ja for k in dropped)
                ctx.log("紙面1枚なので %s は動かしません（司令塔が直接作ります）" % names)
                ctx.emit({"type": "agents_skipped", "agents": dropped,
                          "message": "紙面1枚のため不要な工程を省きました: %s" % names})
            return keep

        # スライド1本なら、音声・動画・SNSは動かさない（原稿は要るので残す）
        if genre in ("deck", "report") and wanted <= {"pptx", "images", "research"}:
            keep = {"orchestrator", "researcher", "planner", "reviewer", "legal",
                    "supervisor", "image", "ppt", "acceptance"} & selected
            dropped = sorted(selected - keep)
            if dropped:
                names = "・".join(self.agents[k].name_ja for k in dropped)
                ctx.log("スライドのみなので %s は動かしません" % names)
                ctx.emit({"type": "agents_skipped", "agents": dropped,
                          "message": "不要な工程を省きました: %s" % names})
            return keep

        forced = ctx.options.get("targets")
        deliverables = forced or plan.get("deliverables")
        if not deliverables:
            return selected

        needed = set()
        unknown = []
        for item in deliverables:
            mapped = DELIVERABLE_AGENTS.get(str(item).lower().strip())
            if mapped:
                needed |= mapped
            else:
                unknown.append(str(item))
        if not needed:
            # 司令塔の答えが想定外の語だった場合、全部落として何も作らない事故を防ぐ。
            # 判断できないときは「全部作る」に倒す。
            ctx.log("作るものを判断できなかったため、一通り作ります（%s）"
                    % "・".join(unknown)[:80], level="warn")
            return selected
        # deliverable を持たない部隊（司令塔・構成・チェック・法務・検品）は常に必要
        keep = {k for k, a in self.agents.items() if a.deliverable is None}

        # **調べる先があるならリサーチャーは必ず残す。**
        # 事実は全ての成果物の材料で、これが無いと紙面が「＿＿＿」だらけになる。
        # 実際に、URL付きの物件チラシ依頼で調査が外れ、物件名も賃料も空欄のまま
        # 印刷できないチラシが出た（司令塔の最終確認も「致命的」と判定）。
        import re as _re

        depth = str(plan.get("research_depth") or "").lower()
        if depth in ("urls", "full") or _re.search(r"https?://", ctx.brief or ""):
            keep.add("researcher")
        result = (selected & (needed | keep))

        dropped = sorted(selected - result)
        if dropped:
            names = "・".join(self.agents[k].name_ja for k in dropped)
            ctx.log("今回の成果物には不要なので %s は動かしません" % names, level="info")
            ctx.emit({"type": "agents_skipped", "agents": dropped,
                      "message": "不要な工程を省きました: %s" % names})
        return result

    # --- 実行 ---
    def run(self, ctx: JobContext, only: Optional[List[str]] = None,
            skip: Optional[List[str]] = None, dry_run: bool = False,
            max_parallel: int = MAX_PARALLEL) -> List[AgentResult]:
        st = get_settings()
        selected = self._select(ctx, only, skip)

        ctx.emit({"type": "pipeline_start", "total": len(selected),
                  "agents": [{"key": k, "name_ja": self.agents[k].name_ja,
                              "icon": self.agents[k].icon, "uses": self.agents[k].uses,
                              "role_ja": self.agents[k].role_ja}
                             for k in PIPELINE_ORDER if k in selected],
                  "message": "%d工程で着手します（依存の無いものは同時に進めます）"
                             % len(selected)})

        results: List[AgentResult] = []
        if dry_run:
            for key in [k for k in PIPELINE_ORDER if k in selected]:
                results.append(AgentResult(key=key, name_ja=self.agents[key].name_ja,
                                           summary="（下見実行のため処理はしていません）"))
            ctx.emit({"type": "pipeline_end", "ok": len(results), "total": len(results),
                      "message": "下見実行を終えました"})
            return results

        done: Set[str] = set()
        pending: Set[str] = set(selected)
        stop = False
        running: Dict[Any, str] = {}
        retakes = 0

        # 「全員終わるまで待つ」をやめ、**終わった部隊から順に**依存先を起動する。
        # 揃うのを待つと、速い部隊（7秒）が遅い部隊（100秒）に引きずられるため。
        with ThreadPoolExecutor(max_workers=max(1, max_parallel)) as pool:
            while (pending or running) and not stop:
                def _ready(key: str) -> bool:
                    agent = self.agents[key]
                    for dep in agent.depends_on:
                        if dep in selected and dep not in done:
                            return False
                    for dep in getattr(agent, "depends_if_present", ()):
                        if dep in selected and dep not in done:
                            return False
                    # 最終確認は必ず最後。出来上がった物を見て判定する役なので、
                    # 他が全部終わってからでないと意味がない
                    if key == "acceptance" and (selected - done - {"acceptance"}):
                        return False
                    return True

                ready = sorted(
                    (k for k in pending if _ready(k)),
                    key=lambda k: PIPELINE_ORDER.index(k) if k in PIPELINE_ORDER else 99,
                )
                for key in ready:
                    if len(running) >= max_parallel:
                        break
                    pending.discard(key)
                    running[pool.submit(self.agents[key].run, ctx)] = key

                if not running:
                    ctx.log("依存関係が解決できない工程が残りました: %s"
                            % "・".join(self.agents[k].name_ja for k in sorted(pending)),
                            level="error")
                    break

                if len(running) > 1:
                    ctx.emit({"type": "wave", "agents": list(running.values()),
                              "message": "同時に進めています: %s"
                                         % "・".join(self.agents[k].name_ja
                                                     for k in running.values())})

                finished, _ = wait(list(running), return_when=FIRST_COMPLETED)
                for future in finished:
                    key = running.pop(future)
                    result = future.result()
                    results.append(result)
                    done.add(key)
                    ctx.results = results

                    if key == "orchestrator":
                        pruned = self._prune_by_plan(ctx, selected)
                        pending -= (selected - pruned)
                        selected = pruned

                    # 司令塔が「直しが必要」と判定したら、指摘を渡して作り直す。
                    # 見つけて終わりにすると、不良品がそのまま人の手に渡る。
                    if key == "acceptance" and retakes < st.max_retake:
                        verdict = (result.data or {}).get("verdict")
                        # 司令塔が**自分で直した**なら差し戻さない。
                        # 差し戻すと制作部隊が最初から作り直すので数分かかるうえ、
                        # 同じ紙面が返ってきて指摘が反映されないことがあった。
                        if (result.data or {}).get("repaired"):
                            verdict = "ok"
                        if verdict in ("needs_fix", "failed"):
                            retakes += 1
                            redo = self._retake_targets(selected)
                            if redo:
                                ctx.options["revision"] = _revision_text(result.data)
                                ctx.log("司令塔の指摘を反映して作り直します（%d回目）: %s"
                                        % (retakes, "・".join(self.agents[k].name_ja
                                                             for k in sorted(redo))),
                                        level="warn")
                                ctx.emit({"type": "retake", "agents": sorted(redo),
                                          "message": "指摘を反映して作り直します（%d回目）"
                                                     % retakes})
                                done -= redo | {"acceptance"}
                                pending |= redo | {"acceptance"}

                    if key == "legal" and st.strict_legal and \
                            (result.data or {}).get("critical_count"):
                        ctx.log("法務監査で重大リスクが出たため、ここで処理を止めました",
                                level="error", agent="legal")
                        stop = True

        ctx.state["report_path"] = str(write_report(ctx, results))
        ctx.save()
        ok = sum(1 for r in results if r.ok)
        ctx.emit({"type": "pipeline_end", "ok": ok, "total": len(results),
                  "message": "全工程が終了しました（成功 %d / %d）" % (ok, len(results))})
        return results


    def _retake_targets(self, selected: Set[str]) -> Set[str]:
        """作り直す部隊。成果物を作る部隊だけを対象にする（調査はやり直さない）。"""
        makers = {"poster", "flyer", "ppt", "image", "video", "publisher"}
        return (makers & selected)


def _revision_text(data: Dict[str, Any]) -> str:
    """司令塔の指摘を、制作部隊への修正指示にまとめる。"""
    gaps = [str(x) for x in (data.get("gaps") or [])]
    lines = ["前回の成果物に、次の不良が見つかりました。必ず直してください。"]
    lines += ["- %s" % g for g in gaps[:6]]
    if data.get("fix_instructions"):
        lines += ["", "直し方: %s" % data["fix_instructions"]]
    return "\n".join(lines)


def write_report(ctx: JobContext, results: List[AgentResult]):
    """人が読む最終レポート（日本語）を reports/report.md に書き出す。"""
    order = {k: i for i, k in enumerate(PIPELINE_ORDER)}
    # 作り直した部隊は複数回出てくる。最後の結果だけ載せる
    latest = {}
    for r in results:
        latest[r.key] = r
    results = sorted(latest.values(), key=lambda r: order.get(r.key, 99))
    lines = [
        "# 実行レポート — %s" % ctx.job_id,
        "",
        "**指示**: %s" % ctx.brief,
        "",
        "**開始**: %s / **終了**: %s" % (
            ctx.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
        "",
        "## 各部隊の結果",
        "",
        "| 部隊 | 状態 | 所要 | 内容 |",
        "|---|---|---|---|",
    ]
    for r in results:
        if not r.ok:
            status = "❌ 失敗"
        elif r.degraded:
            status = "⚠️ 縮退"
        else:
            status = "✅ 完了"
        summary = (r.summary or "").replace("|", "／").replace("\n", " ")
        lines.append("| %s | %s | %.1f秒 | %s |" % (r.name_ja, status, r.elapsed, summary))

    lines += ["", "## 成果物", ""]
    if ctx.artifacts:
        for art in ctx.artifacts:
            label = art.label or art.kind
            lines.append("- **%s** — `%s`" % (label, art.path))
    else:
        lines.append("- （なし）")

    errors = [r for r in results if not r.ok]
    if errors:
        lines += ["", "## 発生したエラー", ""]
        for r in errors:
            lines.append("- **%s**: %s" % (r.name_ja, r.error))

    return write_text(ctx.dir("reports") / "report.md", "\n".join(lines) + "\n")
