#!/usr/bin/env python3
"""agent-platform の画面（Streamlit）。

流れ:
  1. 入力      … 作ってほしいことを書いて「作成を始める」を押すだけ
  2. 確認      … 司令塔が、成果物が変わってしまう点だけ聞き返す（無ければ飛ばす）
  3. 実行状況  … 各部隊の進み具合（同時に動いているものも見える）と日本語の進捗ログ
  4. 成果物    … できあがったファイルのプレビューとダウンロード

枚数・音量といった設定は入力画面に置かない。作るものが依頼ごとに変わるため、
司令塔が決めるか、確認で聞く。どうしても固定したいときだけサイドバーの詳細設定を使う。
"""
from __future__ import annotations

import datetime as _dt
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agents import agent_catalog  # noqa: E402
from agents.orchestrator import clarify  # noqa: E402
from core.config import PROVIDER_LABELS, get_settings  # noqa: E402
from core.context import JobContext  # noqa: E402
from core.pipeline import Pipeline  # noqa: E402

st.set_page_config(page_title="マルチプロダクション", page_icon="🏢", layout="wide")

STATE_COLORS = {
    "待機": ("#8A92A6", "#EEF1F6"),
    "実行中": ("#1A5FB4", "#E3EDFB"),
    "完了": ("#1B7A46", "#E4F5EB"),
    "縮退": ("#9A6700", "#FFF5DA"),
    "失敗": ("#B42318", "#FDE7E5"),
    "不要": ("#9AA0AC", "#F5F6F8"),
}
LEVEL_ICON = {"info": "・", "success": "✅", "warn": "⚠️", "error": "❌", "debug": "·"}


class RunState:
    """実行中の状態。バックグラウンドスレッドが書き、画面が読む。"""

    def __init__(self, catalog: List[Dict[str, Any]]):
        self.lock = threading.Lock()
        self.agents = {a["key"]: dict(a, state="待機", elapsed=0.0, message="")
                       for a in catalog}
        self.order = [a["key"] for a in catalog]
        self.logs: List[Dict[str, Any]] = []
        self.total = len(catalog)
        self.finished = False
        self.job_dir: Path = None  # type: ignore
        self.error = ""

    def handle(self, event: Dict[str, Any]) -> None:
        kind = event.get("type")
        with self.lock:
            key = event.get("agent")
            if kind == "pipeline_start":
                self.total = event.get("total", self.total)
                self._log("info", "", event.get("message", ""))
            elif kind == "agents_skipped":
                for dropped in event.get("agents", []):
                    if dropped in self.agents:
                        self.agents[dropped]["state"] = "不要"
                        self.agents[dropped]["message"] = "今回の成果物には不要と判断"
                self._log("info", "", event.get("message", ""))
            elif kind == "wave":
                self._log("info", "", event.get("message", ""))
            elif kind == "agent_start":
                if key in self.agents:
                    self.agents[key]["state"] = "実行中"
                    self.agents[key]["message"] = "処理中です"
            elif kind == "agent_end":
                if key in self.agents:
                    ok, degraded = event.get("ok", True), event.get("degraded", False)
                    self.agents[key]["state"] = "完了" if ok and not degraded else (
                        "縮退" if ok else "失敗")
                    self.agents[key]["elapsed"] = event.get("elapsed", 0.0)
                    self.agents[key]["message"] = event.get("message", "")
                self._log(event.get("level", "success"), key, event.get("message", ""))
            elif kind == "progress":
                if key in self.agents:
                    self.agents[key]["message"] = event.get("message", "")
                self._log("info", key, event.get("message", ""))
            elif kind == "log":
                self._log(event.get("level", "info"), key, event.get("message", ""))
            elif kind == "pipeline_end":
                self._log("success", "", event.get("message", ""))

    def _log(self, level: str, agent_key: str, message: str) -> None:
        if not message:
            return
        name = self.agents.get(agent_key, {}).get("name_ja", "") if agent_key else ""
        self.logs.append({"ts": _dt.datetime.now().strftime("%H:%M:%S"),
                          "level": level, "agent": name, "message": message})

    def snapshot(self):
        with self.lock:
            return [dict(self.agents[k]) for k in self.order], list(self.logs)


def start_job(brief: str, options: Dict[str, Any], files: List[Dict[str, Any]],
              resume_job: str = "", only: List[str] = None) -> RunState:
    """バックグラウンドでパイプラインを走らせ、進捗を RunState に流し込む。

    resume_job を渡すと、保存済みジョブを読み直して**必要な工程だけ**やり直す
    （調査や原稿に何分もかけた後で「写真だけ差し替えたい」ときのため）。
    """
    state = RunState(agent_catalog())
    if resume_job:
        ctx = JobContext.load(resume_job, on_event=state.handle)
        ctx.options.update(options)
        ctx.log("前回の内容を読み込みました。指示に沿って作り直します")
    else:
        ctx = JobContext(brief=brief, options=options, on_event=state.handle)
    state.job_dir = ctx.root

    for item in files or []:
        (ctx.dir("input") / item["name"]).write_bytes(item["data"])
        ctx.log("資料を受け取りました: %s" % item["name"])

    def worker():
        try:
            Pipeline().run(ctx, only=only or None)
        except Exception as exc:  # 想定外でも画面を固まらせない
            state.error = "%s: %s" % (type(exc).__name__, exc)
            state.handle({"type": "log", "level": "error",
                          "message": "処理が中断しました（%s）" % exc})
        finally:
            state.finished = True

    threading.Thread(target=worker, daemon=True).start()
    return state


# --- 画面部品 -----------------------------------------------------------------

def render_board(agents: List[Dict[str, Any]]) -> None:
    active = [a for a in agents if a["state"] != "不要"]
    done = sum(1 for a in active if a["state"] in ("完了", "縮退", "失敗"))
    running = [a["name_ja"] for a in active if a["state"] == "実行中"]
    st.progress(min(done / max(len(active), 1), 1.0),
                text="%d工程中 %d工程が完了%s" % (
                    len(active), done,
                    "／いま同時に動いているのは %s" % "・".join(running) if running else ""))
    cols = st.columns(4)
    for i, agent in enumerate(agents):
        fg, bg = STATE_COLORS.get(agent["state"], STATE_COLORS["待機"])
        spinner = "⏳ " if agent["state"] == "実行中" else ""
        with cols[i % 4]:
            st.markdown(
                """<div style="border:1px solid {fg}33;background:{bg};border-radius:10px;
                        padding:10px 12px;margin-bottom:8px;min-height:96px">
                  <div style="font-size:13px;font-weight:700;color:{fg}">{icon} {name}</div>
                  <div style="font-size:11px;color:{fg};margin-top:2px">{spin}{state}{elapsed}</div>
                  <div style="font-size:11px;color:#444;margin-top:6px;line-height:1.35">{msg}</div>
                </div>""".format(
                    fg=fg, bg=bg, icon=agent["icon"], name=agent["name_ja"],
                    spin=spinner, state=agent["state"],
                    elapsed=("・%.1f秒" % agent["elapsed"]) if agent["elapsed"] else "",
                    msg=(agent["message"] or agent["role_ja"])[:80],
                ),
                unsafe_allow_html=True,
            )


def render_logs(logs: List[Dict[str, Any]], show_debug: bool) -> None:
    visible = [entry for entry in logs if show_debug or entry["level"] != "debug"]
    lines = []
    for entry in visible[-300:]:
        who = "［%s］" % entry["agent"] if entry["agent"] else ""
        lines.append("%s %s %s%s" % (entry["ts"], LEVEL_ICON.get(entry["level"], "・"),
                                     who, entry["message"]))
    st.code("\n".join(lines) or "（まだ進捗はありません）", language=None)


def render_acceptance(job_dir) -> None:
    """司令塔の最終確認。依頼どおりにできているかの判定。"""
    import json

    path = Path(job_dir) / "reports" / "acceptance.json"
    if not path.exists():
        return
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return

    labels = {"ok": "✅ 依頼どおりにできています", "needs_fix": "⚠️ 直しが必要です",
              "failed": "❌ そのままでは使えません"}
    verdict = report.get("verdict", "unknown")
    st.subheader("🧭 司令塔の最終確認")
    if verdict == "ok":
        st.success(labels[verdict])
    elif verdict == "failed":
        st.error(labels.get(verdict, verdict))
    else:
        st.warning(labels.get(verdict, "確認しました"))
    if not report.get("saw_images"):
        st.caption("※ 画像を開けない経路で判定したため、見た目は確認できていません")
    for gap in report.get("gaps") or []:
        st.markdown("- %s" % gap)
    if report.get("fix_instructions"):
        st.info("**次に直すなら**: %s" % report["fix_instructions"])


def _preview_strip(template_ids) -> None:
    """型の見本を横に並べる（組み直し画面用）。"""
    from core import previews, layouts

    columns = st.columns(min(len(template_ids), 5) or 1)
    for index, template_id in enumerate(template_ids):
        path = previews.preview_for(template_id)
        if not path:
            continue
        item = layouts.get(template_id) or {}
        with columns[index % len(columns)]:
            st.image(path, caption=item.get("name", template_id),
                     use_container_width=True)


def render_layout_previews(options, brief: str = "") -> None:
    """型の見本を並べる。選択肢の文字と同じ並び・同じ名前で出す。"""
    from core import previews, layouts, signage_templates

    signage = any(str(o).startswith(("禁止", "お知らせ", "お願い", "案内", "防犯",
                                     "休業", "料金表", "募集"))
                  for o in options)
    shown = 0
    columns = st.columns(min(len(options), 4) or 1)
    for index, option in enumerate(options):
        label = str(option).split("｜")[0]
        template_id = (signage_templates.id_from_answer(option) if signage
                       else layouts.id_from_answer(option))
        if not template_id:
            continue
        path = previews.preview_for(template_id)
        if not path:
            continue
        with columns[index % len(columns)]:
            st.image(path, caption=label, use_container_width=True)
        shown += 1
    if not shown:
        st.caption("（見本を用意できませんでした。下の説明で選んでください）")
    else:
        st.caption("見本は当て紙（灰色）で組んだものです。実際は取り込んだ写真が入ります")


def _env_path() -> Path:
    from core.config import ROOT

    return Path(ROOT) / ".env"


def _read_env_value(key: str) -> str:
    """.env から1つ読む。無ければ空。"""
    import os

    path = _env_path()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("%s=" % key):
                return line.split("=", 1)[1].strip()
    return os.getenv(key, "").strip()


def _write_env_value(key: str, value: str) -> bool:
    """.env に1つ書く。**画面から入れられるようにするため**。

    ファイルを開いて編集させるのは、社員に使ってもらうには無理がある。
    """
    import os

    path = _env_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        out, done = [], False
        for line in lines:
            if line.strip().startswith("%s=" % key):
                out.append("%s=%s" % (key, value))
                done = True
            else:
                out.append(line)
        if not done:
            out.append("%s=%s" % (key, value))
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        os.environ[key] = value      # いまの画面にも即反映する
        return True
    except OSError:
        return False


def render_photo_swap(job_dir) -> None:
    """**仮に入れた写真を、本物に差し替える。**

    フリー素材は「どこかの街の写真」でしかない。まず形にするには十分だが、
    配る前に本物へ替えたい。ここでアップロードすれば、その場で入れ替えて
    作り直す（部隊は動かさないので数秒で終わる）。
    """
    import json

    job_dir = Path(job_dir)
    path = job_dir / "job.json"
    if not path.exists():
        return
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    state = job.get("state") or {}
    spec = state.get("deck_spec")
    used = _deck_images(spec) if spec else []
    if not used:
        return

    st.subheader("🖼 写真を差し替える")
    st.caption("フリー素材は仮置きです。実際の写真をアップロードすると入れ替わります"
               "（部隊は動かさないので数秒で終わります）")
    credits = state.get("photo_credits") or []
    if credits:
        st.caption("※ 出典表示が必要な写真: %s" % " ／ ".join(credits[:3]))

    columns = st.columns(4)
    for index, image in enumerate(used):
        with columns[index % 4]:
            try:
                st.image(str(job_dir / image) if not Path(image).is_absolute()
                         else image, use_container_width=True)
            except Exception:
                st.caption("（表示できません）")
            new = st.file_uploader("%d枚目を差し替え" % (index + 1),
                                   type=["png", "jpg", "jpeg", "webp"],
                                   key="swap_%d" % index, label_visibility="collapsed")
            if new is not None:
                target = Path(image)
                if not target.is_absolute():
                    target = job_dir / image
                target.write_bytes(new.getvalue())
                st.success("差し替えました。下の「作り直す」を押してください")

    if st.button("この写真でスライドを作り直す", type="primary",
                 use_container_width=True):
        with st.spinner("作り直しています…"):
            try:
                from core import deck_pptx

                out = sorted((job_dir / "slides").glob("*.pptx"))
                name = out[0] if out else (job_dir / "slides" / "deck.pptx")
                deck_pptx.build(spec, name, paper="4:3")
                st.success("作り直しました（%s）" % name.name)
            except Exception as exc:
                st.error("作り直しに失敗しました: %s" % exc)


def _deck_images(spec) -> list:
    """スライドで使っている画像のパスを、重複なく並べる。"""
    found, seen = [], set()
    for item in spec or []:
        if not isinstance(item, dict):
            continue
        candidates = []
        if item.get("image"):
            candidates.append(item["image"])
        candidates += [x for x in (item.get("images") or []) if x]
        for path in candidates:
            if path not in seen:
                seen.add(path)
                found.append(path)
    return found[:12]


def render_revision_panel(job_dir) -> None:
    """直しの入口を1つにまとめる。

    以前は「紙面を組み直す」と「直しを指示する」が別々の見出しで並んでいて、
    どちらを使えばいいのか分からなかった。**やりたいことは同じ「直す」**なので、
    入口を1つにして、速い直し方と、部隊に任せる直し方を並べる。
    """
    st.subheader("✏️ 直す")
    quick, swap, ask = st.tabs(["自分で直す（数秒・崩れない）", "写真を差し替える",
                                "言葉で指示する（部隊が直す）"])
    with quick:
        render_flyer_editor(job_dir)
    with swap:
        render_photo_swap(job_dir)
    with ask:
        render_revise_form(job_dir)


def render_revise_form(job_dir) -> None:
    """文章で指示して、部隊に作り直させる。時間はかかるが中身から変わる。"""
    st.caption("前回の調査や原稿はそのまま使い、指示した部分だけ作り直します"
               "（数分かかります）")
    with st.form("revise_form"):
        revision = st.text_area(
            "どこをどう直しますか",
            height=110,
            placeholder="例）物件写真をもっと大きく、下に4枚並べて／"
                        "キャッチをもっと感情に訴える表現に／"
                        "周辺の生活利便（スーパー・学校）を調べて足して",
        )
        more_photos = st.file_uploader(
            "写真を追加する（複数可）",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="revise_photos",
        )
        scope = st.radio(
            "どこから作り直すか",
            ["成果物だけ（速い）", "原稿から", "調査からぜんぶ"],
            horizontal=True,
            help="写真の差し替えや紙面の調整だけなら「自分で直す」タブの方が速いです",
        )
        do_revise = st.form_submit_button("この指示で作り直す", type="primary",
                                          use_container_width=True)
    if not do_revise:
        return
    if not revision.strip() and not more_photos:
        st.error("直したい内容を書くか、写真を追加してください。")
        return
    scope_agents = {
        "成果物だけ（速い）": ["image", "flyer", "poster", "voice", "video",
                              "publisher", "acceptance"],
        "原稿から": ["planner", "reviewer", "legal", "supervisor", "image", "flyer",
                    "poster", "voice", "video", "publisher", "acceptance"],
        "調査からぜんぶ": None,
    }[scope]
    payload = [{"name": f.name, "data": f.getvalue()} for f in more_photos or []]
    st.session_state["run"] = start_job(
        "", {"revision": revision.strip()}, payload,
        resume_job=Path(job_dir).name, only=scope_agents)
    st.session_state["stage"] = "running"
    st.rerun()


def render_flyer_editor(job_dir) -> None:
    """紙面を**型・写真・文言**の3つで作り直す。

    なぜここに置くか:
      出来上がりを見て初めて「この写真じゃない」「もっと写真を並べたい」と分かる。
      作り直しのたびに部隊を動かすのは遅いので、**組み直すだけ**なら数秒で済む
      この画面で完結させる。文言・写真・型のどれを変えても崩れない
      （並べ方は型が持っていて、人が触るのは中身だけだから）。
    """
    import json

    job_dir = Path(job_dir)
    path = job_dir / "job.json"
    if not path.exists():
        return
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    state = job.get("state") or {}
    content = state.get("flyer_content")
    if not content:
        return render_text_editor(job_dir)     # 型を使っていない紙面は従来どおり

    from core import layouts, palettes

    genre = str((state.get("plan") or {}).get("genre") or "promo")
    photos = _flyer_photos(job_dir, state)
    if not photos:
        return
    # **ファイル名だけでは、どの写真か分からない。**
    # 判別済みの部屋名（外観・LDK・和室…）を番号と一緒に出し、
    # 下のサムネイルの番号と突き合わせて選べるようにする
    labels = _photo_labels(job_dir, state)
    names = ["%d  %s" % (i, labels.get(i) or Path(p).name)
             for i, p in enumerate(photos, 1)]
    none_label = "（使わない）"

    st.caption("型・写真・文言を変えて「この内容で作り直す」を押すと、数秒で差し替わります")

    st.markdown("**使える写真**（下の番号で選びます）")
    cols = st.columns(6)
    for i, photo in enumerate(photos):
        with cols[i % 6]:
            try:
                st.image(photo, caption="%d  %s" % (i + 1, labels.get(i + 1, "")),
                         use_container_width=True)
            except Exception:
                continue

    templates = layouts.all_templates(genre)
    ids = [t["id"] for t in templates]
    current = state.get("flyer_template") or layouts.choose(genre, len(photos))
    picked = content.get("photos") or {}

    with st.form("flyer_edit_form"):
        template_id = st.selectbox(
            "型（レイアウト）", ids,
            index=ids.index(current) if current in ids else 0,
            format_func=lambda x: "%s … %s" % (layouts.get(x)["name"],
                                               layouts.get(x)["summary"]))
        st.caption("　".join("%s=%s" % (t["name"], t["best_for"]) for t in templates))
        _preview_strip([t["id"] for t in templates])

        col1, col2 = st.columns(2)
        hero = col1.selectbox("メイン写真", names,
                              index=_index_of(picked.get("hero"), len(photos)))
        plan_choices = [none_label] + names
        floor = col2.selectbox("間取り図・図面", plan_choices,
                               index=_index_of(picked.get("floorplan"),
                                               len(photos), offset=1))
        rooms = st.multiselect("サブ写真（選んだ順に並びます）", names,
                               default=[names[i - 1] for i in (picked.get("rooms") or [])
                                        if 1 <= int(i) <= len(names)])

        st.markdown("**配色**")
        palette_ids = [x["id"] for x in palettes.all_palettes()]
        current_palette = (state.get("flyer_palette")
                           or content.get("palette") or palettes.DEFAULT)
        palette_id = st.selectbox(
            "配色", palette_ids, label_visibility="collapsed",
            index=palette_ids.index(current_palette)
            if current_palette in palette_ids else 0,
            format_func=lambda x: "%s … %s" % (palettes.get(x)["name"],
                                               palettes.get(x)["best_for"]))
        # **色は名前だけでは伝わらない。** 全部の色見本を並べて目で選べるようにする
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:10px 18px;margin:2px 0 10px">'
            + "".join(palettes.swatch_html(x) for x in palette_ids)
            + "</div>", unsafe_allow_html=True)

        st.markdown("**QRコード（下帯の右端）**")
        col5, col6 = st.columns([1, 3])
        qr_on = col5.checkbox("入れる", value=bool(content.get("qr_on")))
        qr = col6.text_input("QRの中身（物件ページのURLなど）",
                             value=content.get("qr", ""),
                             label_visibility="collapsed",
                             placeholder="https://… （空なら会社サイト）")
        qr_label = st.text_input("QRの下に出す文言", value=content.get("qr_label", "")
                                 or "物件ページはこちら")

        st.markdown("**文言**")
        kicker = st.text_input("小さいタイトル", value=content.get("kicker", ""))
        catch = st.text_input("大きいタイトル（キャッチ）", value=content.get("catch", ""))
        title = st.text_input("物件名・見出し", value=content.get("title", ""))
        sub = st.text_input("補足（敷金・礼金など）", value=content.get("sub", ""))
        col3, col4 = st.columns([2, 1])
        price = col3.text_input("金額", value=content.get("price", ""))
        unit = col4.text_input("単位", value=content.get("unit", "円 / 月"))
        lead = st.text_area("説明文", value=content.get("lead", ""), height=80)
        badges = st.text_area("特徴タグ（1行に1つ）",
                              value="\n".join(content.get("badges") or []), height=90)
        specs = st.text_area("条件表（「項目：値」で1行に1つ）",
                             value="\n".join("%s：%s" % (r[0], r[1])
                                             for r in (content.get("spec_rows") or [])
                                             if len(r) >= 2), height=180)
        rebuild = st.form_submit_button("この内容で作り直す", type="primary",
                                        use_container_width=True)

    render_template_registry(job_dir, job, content, current)

    if not rebuild:
        return

    import re

    updated = dict(content)
    updated.update({"palette": palette_id,
                    "qr_on": bool(qr_on), "qr": qr.strip(), "qr_label": qr_label.strip(),
                    "kicker": kicker, "catch": catch, "title": title, "sub": sub,
                    "price": price, "unit": unit, "lead": lead,
                    "badges": [x.strip() for x in badges.splitlines() if x.strip()],
                    "spec_rows": [[p.strip() for p in re.split(r"[：:]", line, 1)]
                                  for line in specs.splitlines()
                                  if re.search(r"[：:]", line)]})
    updated["photos"] = {
        "hero": _number_of(hero), 
        "floorplan": None if floor == none_label else _number_of(floor),
        "rooms": [_number_of(x) for x in rooms],
    }
    with st.spinner("紙面を組み直しています…"):
        try:
            _rebuild_flyer(job_dir, job, layouts.build(template_id, updated), photos,
                           paper=layouts.paper_of(template_id), palette=palette_id)
            job.setdefault("state", {})["flyer_palette"] = palette_id
            job.setdefault("state", {})["flyer_content"] = updated
            job["state"]["flyer_template"] = template_id
            path.write_text(json.dumps(job, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            st.success("組み直しました。上のプレビューが差し替わっています")
            st.rerun()
        except Exception as exc:
            st.error("組み直しに失敗しました: %s" % exc)


def render_template_registry(job_dir, job, content, template_id) -> None:
    """いまの紙面を「型」として登録する。

    なぜ人が押すボタンにするか:
      出来の良し悪しは人にしか決められない。自動で貯めると失敗作まで資産に混ざり、
      次の依頼で候補に出てしまう。**人が良いと決めたものだけ**を残す。
    """
    from core import layouts, user_templates

    saved = user_templates.all_saved()
    with st.expander("🧩 この紙面を型として登録する（次から使い回せます）",
                     expanded=False):
        st.caption("並びと寸法だけを保存します。文言と写真は目印に置き換えるので、"
                   "別の物件でも同じ組みで出せます")
        with st.form("save_template_form"):
            name = st.text_input("型の名前", placeholder="例: 戸建て・写真大きめ")
            summary = st.text_input("どんな型か（一覧に出ます）",
                                    placeholder="例: 外観を全幅で大きく、間取りは右に")
            best_for = st.text_input("どんなときに向くか",
                                     placeholder="例: 写真の見栄えが良い戸建て")
            if st.form_submit_button("この並びを型として登録", type="primary",
                                     use_container_width=True):
                if not name.strip():
                    st.error("型の名前を入れてください")
                else:
                    layout = (job.get("state") or {}).get("flyer_layout") or []
                    genre = str((job.get("state", {}).get("plan") or {}).get("genre")
                                or "promo")
                    spec = user_templates.save(
                        name, layout, content,
                        orientation=("landscape"
                                     if layouts.paper_of(template_id).endswith("LANDSCAPE")
                                     else "portrait"),
                        genre=genre, summary=summary, best_for=best_for)
                    st.success("「%s」を型として登録しました（部品%d個）"
                               % (spec["name"], len(spec["layout"])))
                    st.rerun()

        if saved:
            st.markdown("**登録済みの型**")
            for spec in saved:
                col1, col2 = st.columns([5, 1])
                col1.markdown("- **%s**（%s・写真%d枚〜） … %s"
                              % (spec["name"],
                                 "横" if spec.get("orientation") == "landscape" else "縦",
                                 spec.get("photos_min", 1), spec.get("summary", "")))
                if col2.button("削除", key="del_%s" % spec["id"]):
                    user_templates.delete(spec["id"])
                    st.rerun()


def _photo_labels(job_dir, state) -> Dict[int, str]:
    """写真番号 → 部屋名。ビジュアル制作が判別した結果を使う。"""
    labels = {}
    for item in (state.get("photo_labels") or []):
        try:
            labels[int(item.get("no"))] = str(item.get("label", "")).strip()
        except (TypeError, ValueError):
            continue
    content = state.get("flyer_content") or {}
    for key, value in (content.get("photo_captions") or {}).items():
        try:
            labels.setdefault(int(key), str(value).strip())
        except (TypeError, ValueError):
            continue
    return {k: v for k, v in labels.items() if v}


def _index_of(value, count: int, offset: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return (number - 1 + offset) if 1 <= number <= count else 0


def _number_of(label: str) -> int:
    try:
        return int(str(label).split(":", 1)[0])
    except (TypeError, ValueError):
        return 1


def _flyer_photos(job_dir, state):
    """紙面に使える写真の候補。**使わなかった写真も含めて全部**出す。

    「メインをこっちにしたい」は出来上がりを見てから起きるので、
    採用済みの数枚だけでは足りない。
    """
    paths = [Path(job_dir) / p for p in (state.get("flyer_photos") or [])]
    paths = [p for p in paths if p.exists()]
    seen = {p.name for p in paths}
    for folder, exts in ((Path(job_dir) / "input", (".png", ".jpg", ".jpeg", ".webp")),
                         (Path(job_dir) / "images", (".png",))):
        for extra in sorted(folder.glob("*")):
            if extra.suffix.lower() in exts and extra.name not in seen:
                paths.append(extra)
                seen.add(extra.name)
    # **開けるものだけ返す。** 拡張子が .jpg でも中身がHTMLのことがあり、
    # そのまま画面に出すと Streamlit ごと落ちる（実際に落ちた）
    return [str(p) for p in paths if _is_readable_image(p)]


def _is_readable_image(path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def _rebuild_flyer(job_dir, job, layout, photos, paper: str = "A4",
                   palette: str = "") -> None:
    """紙面を作り直す。**書き出しは core/flyer_build に一本化**している。

    以前はここに書き出し処理を写していたため、用紙が縦に決め打ちのまま残り、
    横の型を選んでも縦で描かれかけた。出口は1つにする。
    """
    from core import flyer_build

    made = flyer_build.render(layout, photos, Path(job_dir) / "slides",
                              stem=_flyer_stem(job_dir), paper=paper, palette=palette)
    job.setdefault("state", {})["flyer_layout"] = layout
    job["state"]["flyer"] = str(made["pdf"].relative_to(Path(job_dir)))


def _flyer_stem(job_dir) -> str:
    existing = sorted((Path(job_dir) / "slides").glob("*.pdf"))
    return existing[0].stem if existing else "flyer"


def render_text_editor(job_dir) -> None:
    """紙面の文字をその場で直して、作り直す。

    PowerPointで直させるとレイアウトが崩れる。**文字だけを直させて組み直す**方が、
    位置や大きさは部品が持っているので崩れようがなく、しかも数秒で終わる。
    """
    import json

    job_dir = Path(job_dir)
    path = job_dir / "job.json"
    if not path.exists():
        return
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    layout = (job.get("state") or {}).get("flyer_layout")
    if not layout:
        return

    from core import blocks

    fields = blocks.editable_fields(layout)
    if not fields:
        return

    st.subheader("✏️ 文字を直す")
    st.caption("打ち変えて「この内容で作り直す」を押すと、数秒で紙面が差し替わります"
               "（レイアウトは崩れません）")

    with st.form("text_edit_form"):
        edits = {}
        current_block = None
        for field in fields:
            if field["index"] != current_block:
                current_block = field["index"]
                st.markdown("**%s**" % blocks.BLOCK_LABELS.get(field["block"],
                                                              field["block"]))
            key = "%d:%s" % (field["index"], field["key"])
            if field["kind"] == "text":
                edits[key] = st.text_input(field["label"], value=field["value"],
                                           key="edit_%s" % key)
            else:
                edits[key] = st.text_area(field["label"], value=field["value"],
                                          key="edit_%s" % key,
                                          height=max(70, 24 * (field["value"].count("\n") + 2)))
        rebuild = st.form_submit_button("この内容で作り直す", type="primary",
                                        use_container_width=True)

    if rebuild:
        with st.spinner("紙面を作り直しています…"):
            try:
                import tools

                updated = blocks.apply_edits(layout, edits)
                photos = sorted(str(p) for p in (job_dir / "input").glob("*")
                                if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
                if not photos:
                    photos = sorted(str(p) for p in (job_dir / "images").glob("*.png"))
                html = blocks.render_page(updated, photos=photos)
                html = tools.flyer.fit_to_page(html, paper="A4")

                target = sorted((job_dir / "slides").glob("*.pdf"))
                stem = target[0].stem if target else "flyer"
                tools.flyer.render(html, job_dir / "slides" / (stem + ".pdf"),
                                   fmt="pdf", paper="A4")
                tools.flyer.render(html, job_dir / "slides" / (stem + ".png"),
                                   fmt="png", paper="A4")
                (job_dir / "slides" / (stem + ".html")).write_text(html, encoding="utf-8")

                job.setdefault("state", {})["flyer_layout"] = updated
                path.write_text(json.dumps(job, ensure_ascii=False, indent=2),
                                encoding="utf-8")
                st.success("作り直しました。上のプレビューが差し替わっています")
                st.rerun()
            except Exception as exc:
                st.error("作り直しに失敗しました: %s" % exc)


def render_needed_assets(job_dir) -> None:
    """司令塔が「あると良い」と言った素材を出す。人が用意すれば次から使われる。"""
    import json

    path = Path(job_dir) / "plan" / "job_plan.json"
    if not path.exists():
        return
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    wanted = [x for x in (plan.get("needed_assets") or []) if isinstance(x, dict)]
    if not wanted:
        return

    st.subheader("🧺 用意すると良い素材")
    st.caption("下のサイトから落として `agent-platform/assets/` に置くと、次回から自動で使われます")
    for item in wanted:
        st.markdown("- **%s** — %s（%s）"
                    % (item.get("what", ""), item.get("why", ""), item.get("where", "")))
    with st.expander("素材サイト一覧"):
        try:
            import tools

            for name, kind, url, note in tools.assets_lib.SOURCES:
                st.markdown("- [%s](%s) … %s ※%s" % (name, url, kind, note))
        except Exception:
            pass


def render_legal_comments(job_dir) -> None:
    """法務・コンプラ監査からのコメントを、成果物とは別枠で見せる。

    成果物そのものに但し書きを書き込むと配布できなくなるので、
    指摘は必ずここに出す。人が読んで判断するためのもの。
    """
    import json

    path = Path(job_dir) / "reports" / "legal.json"
    if not path.exists():
        return
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return

    risks = audit.get("risks") or []
    critical = audit.get("critical_count", 0)
    major = audit.get("major_count", 0)

    st.subheader("⚖️ 法務・コンプラ監査からのコメント")
    if not risks:
        st.success("指摘事項はありません。（最終判断は人が行ってください）")
        return

    if critical:
        st.error("重大 %d件・要注意 %d件・その他 %d件。**配布前に必ず確認してください**"
                 % (critical, major, len(risks) - critical - major))
    elif major:
        st.warning("要注意 %d件・その他 %d件" % (major, len(risks) - major))
    else:
        st.info("軽微な指摘が %d件" % len(risks))
    st.caption("これは法的助言ではありません。指摘は成果物には書き込んでいません。")

    label = {"critical": "🔴 重大", "major": "🟠 要注意", "minor": "🟡 軽微"}
    order = {"critical": 0, "major": 1, "minor": 2}
    for risk in sorted(risks, key=lambda r: order.get(r.get("severity"), 3)):
        head = "%s  %s" % (label.get(risk.get("severity"), "・"), risk.get("message", "")[:60])
        with st.expander(head):
            if risk.get("law"):
                st.markdown("**関係する法令・規約**: %s" % risk["law"])
            if risk.get("target"):
                st.markdown("**箇所**: %s" % risk["target"])
            if risk.get("message"):
                st.markdown("**指摘**: %s" % risk["message"])
            if risk.get("fix"):
                st.markdown("**直し方**: %s" % risk["fix"])


def open_in_finder(path) -> bool:
    """Finderで開く。アプリはこのMac上で動いているので open コマンドが使える。"""
    import subprocess

    try:
        subprocess.run(["open", str(path)], check=True, timeout=10)
        return True
    except Exception:
        return False


def _open_folder_once(job_dir) -> None:
    """成果物のフォルダを1回だけ開く。"""
    import subprocess

    opened = st.session_state.setdefault("_opened_folders", set())
    key = str(job_dir)
    if key in opened:
        return
    opened.add(key)
    try:
        subprocess.Popen(["open", key])
    except Exception:
        pass


def render_open_buttons(job_dir) -> None:
    """出力フォルダと主な成果物を、その場で開けるようにする。"""
    job_dir = Path(job_dir)
    main = None
    for pattern in ("slides/*.pdf", "video/*.mp4", "slides/*.png"):
        found = sorted(job_dir.glob(pattern))
        if found:
            main = found[0]
            break

    col1, col2 = st.columns(2)
    if col1.button("📂 出力フォルダを開く", use_container_width=True):
        if open_in_finder(job_dir):
            st.toast("Finderで開きました")
        else:
            st.warning("開けませんでした。パス: %s" % job_dir)
    if main is not None:
        if col2.button("📄 成果物を開く（%s）" % main.name, use_container_width=True):
            if open_in_finder(main):
                st.toast("開きました")
            else:
                st.warning("開けませんでした。パス: %s" % main)
    st.code(str(job_dir), language=None)


def render_reports(job_dir) -> None:
    """調査・原稿・監査の記録。**画面の一番下に置く。**

    毎回読むものではないので、完成品より前に出すと邪魔になる。
    後から根拠をたどりたいときだけ開く。
    """
    job_dir = Path(job_dir)
    docs = (sorted(job_dir.glob("reports/*.md")) + sorted(job_dir.glob("research/*.md"))
            + sorted(job_dir.glob("plan/*.md")) + sorted(job_dir.glob("social/*.md")))
    if not docs:
        return
    st.subheader("📄 レポート・原稿")
    st.caption("調査の出典、原稿、法務の記録です。根拠をたどりたいときに開いてください")
    for path in docs:
        with st.expander(path.name):
            st.markdown(path.read_text(encoding="utf-8"))
            st.download_button("ダウンロード", path.read_bytes(), file_name=path.name,
                               key="dlmd_%s" % path)


def render_artifacts(job_dir) -> None:
    if not job_dir or not Path(job_dir).exists():
        st.info("まだ成果物はありません。")
        return
    job_dir = Path(job_dir)

    # **できた紙面を一番上に大きく出す。** 受け取る人が見たいのはこれ。
    flyers = sorted(job_dir.glob("slides/*.png"))
    if flyers:
        st.subheader("📄 できあがった紙面")
        for path in flyers:
            st.image(str(path), use_container_width=True)
            pdf = path.with_suffix(".pdf")
            col1, col2 = st.columns(2)
            if pdf.exists():
                col1.download_button("PDFをダウンロード（印刷用）", pdf.read_bytes(),
                                     file_name=pdf.name, key="dlpdf_%s" % pdf,
                                     use_container_width=True, type="primary")
            col2.download_button("画像をダウンロード", path.read_bytes(),
                                 file_name=path.name, key="dlpng_%s" % path,
                                 use_container_width=True)

    for pattern, label in (("video/*.mp4", "🎬 解説動画"),
                           ("audio/*.mp3", "🔊 ナレーション"),
                           ("audio/*.wav", "🔊 ナレーション（無音代用）")):
        files = sorted(job_dir.glob(pattern))
        if not files:
            continue
        st.subheader(label)
        for path in files:
            col1, col2 = st.columns([3, 1])
            col1.write("`%s`（%.1fKB）" % (path.relative_to(job_dir),
                                          path.stat().st_size / 1024))
            col2.download_button("ダウンロード", path.read_bytes(), file_name=path.name,
                                 key="dl_%s" % path, use_container_width=True)
            if path.suffix == ".mp4":
                st.video(str(path))
            elif path.suffix == ".mp3":
                st.audio(str(path))

    # 制作の途中で使った素材。**完成品と紛らわしいので畳んでおく。**
    # 紙面の依頼なのに「生成した画像」として物件写真が1枚出ていて、
    # できあがりと取り違える作りになっていた。
    materials = sorted(job_dir.glob("images/*.png")) + \
        [p for p in sorted(job_dir.glob("input/*"))
         if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    if materials:
        with st.expander("🧰 制作に使った素材（%d点）" % len(materials)):
            st.caption("紙面に使った写真・作図です。完成品は上の「できあがった紙面」です")
            cols = st.columns(5)
            for i, path in enumerate(materials):
                try:
                    cols[i % 5].image(str(path), caption=path.name,
                                      use_container_width=True)
                except Exception:
                    continue




# --- 本体 ---------------------------------------------------------------------

st.title("マルチプロダクション")
st.caption("作ってほしいことを書くだけ。司令塔が必要な部隊だけを選び、同時に走らせて仕上げます")

settings = get_settings()
st.session_state.setdefault("stage", "input")

with st.sidebar:
    st.header("接続状況")
    for provider, ok in settings.availability_report().items():
        st.write("%s %s" % ("✅" if ok else "－", PROVIDER_LABELS[provider]))
    with st.expander("使えるアイテム"):
        try:
            import tools as tool_pack

            for item in tool_pack.catalog():
                st.write("%s %s" % ("✅" if item["available"] else "－", item["label"]))
        except Exception as exc:
            st.caption("取得できませんでした（%s）" % exc)
    with st.expander("🖼 素材の設定（フリー写真）", expanded=False):
        st.caption("キーが無くても写真は入ります（Openverse・鍵不要）。"
                   "Pexelsのキーを入れると写真の質が上がります。**無料・登録のみ**")
        st.markdown("[Pexelsのキーを取る（無料）](https://www.pexels.com/api/)")
        current = _read_env_value("PEXELS_API_KEY")
        entered = st.text_input("Pexels APIキー", value=current, type="password",
                                placeholder="貼り付けると保存されます")
        if entered != current:
            if _write_env_value("PEXELS_API_KEY", entered.strip()):
                st.success("保存しました。次の実行から使われます")
            else:
                st.error("保存できませんでした（.env を確認してください）")

    st.divider()
    show_debug = st.checkbox("技術ログも表示する", value=False,
                             help="ライブラリの内部出力やエラー詳細。ふだんは不要です")
    from core import company

    with st.expander("🏢 発行者情報（一度登録すれば全部の成果物に入ります）",
                     expanded=not company.is_set()):
        st.caption("チラシ・掲示物・送付書の連絡先や免許番号に使われます。"
                   "未登録の場合、部隊は連絡先を作らず記入欄にします")
        saved = company.load()
        with st.form("company_form"):
            values = {}
            for key, label, hint in company.FIELDS:
                values[key] = st.text_input(label, value=saved.get(key, ""),
                                            placeholder=hint)
            if st.form_submit_button("保存する", use_container_width=True):
                company.save(values)
                st.success("保存しました")
    st.divider()
    if st.session_state["stage"] != "input":
        if st.button("新しい依頼を作る", use_container_width=True):
            for key in ("stage", "run", "pending"):
                st.session_state.pop(key, None)
            st.rerun()

tab_input, tab_progress, tab_output = st.tabs(["📝 入力", "📡 実行状況", "📦 成果物"])
run: RunState = st.session_state.get("run")  # type: ignore[assignment]


def _base_options() -> Dict[str, Any]:
    # 枚数・音量は成果物ごとに変わるので設定に持たない。
    # 依頼文か、司令塔の確認で決める。
    # QRは「入れるかどうか」が依頼のたびに変わるので、ここで持つ
    return dict(st.session_state.get("qr") or {})


with tab_input:
    stage = st.session_state["stage"]

    if stage == "input":
        with st.form("job_form"):
            brief = st.text_area(
                "作ってほしいことを書いてください",
                height=160,
                placeholder="例1）中古マンション買取再販事業の社内提案。市場と競合を調べて、"
                            "提案資料と解説動画、SNSの告知文まで一式作って。\n"
                            "例2）加東の貸家4棟の入居者募集チラシを1枚作りたい。",
            )
            files = st.file_uploader(
                "参考資料（任意・複数可）",
                type=["txt", "md", "csv", "json", "png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                help="テキストは調査に、画像はそのまま素材として使います",
            )
            qr_col1, qr_col2 = st.columns([1, 3])
            qr_on = qr_col1.checkbox("QRを入れる", value=False,
                                     help="チラシの下帯の右端に出ます。物件ページや"
                                          "会社サイトへ誘導する導線です")
            qr_url = qr_col2.text_input("QRの中身", label_visibility="collapsed",
                                        placeholder="https://…（空なら発行者情報のサイト）")
            submitted = st.form_submit_button("▶ 作成を始める", type="primary",
                                              use_container_width=True)
        if submitted:
            if not brief.strip():
                st.error("作ってほしい内容を入力してください。")
            else:
                payload = [{"name": f.name, "data": f.getvalue()} for f in files or []]
                st.session_state["qr"] = {"qr_on": bool(qr_on), "qr": qr_url.strip()}
                with st.spinner("司令塔が依頼を読んでいます…"):
                    asked = clarify(brief.strip(), [f["name"] for f in payload])
                st.session_state["pending"] = {"brief": brief.strip(), "files": payload,
                                               "clarify": asked}
                if asked.get("questions"):
                    st.session_state["stage"] = "clarify"
                else:
                    st.session_state["run"] = start_job(brief.strip(), _base_options(),
                                                        payload)
                    st.session_state["stage"] = "running"
                st.rerun()

    elif stage == "clarify":
        pending = st.session_state["pending"]
        asked = pending["clarify"]
        st.info("制作に入る前に、司令塔から確認です。答えによって成果物が変わる点だけ聞いています。")
        with st.form("clarify_form"):
            answers = []
            OTHER = "その他（下の欄に書く）"
            for q in asked["questions"]:
                st.markdown("**%s**" % q.get("question", ""))
                if q.get("why"):
                    st.caption("なぜ聞くか: %s" % q["why"])
                if str(q.get("id")) == "layout":
                    # 紙面は見た目を選ぶもの。**文字だけで聞かれても想像できない**ので
                    # 見本を並べる（初回だけ描いて、以降は残したものを出す）
                    render_layout_previews(q.get("options") or [],
                                           pending.get("brief", ""))
                options = list(q.get("options") or []) + [OTHER]
                choice = st.radio("選択", options, key="ans_%s" % q["id"],
                                  label_visibility="collapsed")
                # フォームの中では選択してもその場で再描画されないため、
                # 記入欄は条件分岐せず**常に出す**（出さないと「その他」を選んでも書けない）
                free = st.text_input(
                    "自由に書く（ここに書くと、上の選択より優先されます）",
                    key="free_%s" % q["id"],
                    placeholder="例: 具体的な条件、固有名詞、外せない要素など")
                answers.append({"question": q.get("question", ""),
                                "answer": free.strip() or ("" if choice == OTHER else choice)})
                st.divider()
            col1, col2 = st.columns(2)
            go = col1.form_submit_button("この内容で進める", type="primary",
                                         use_container_width=True)
            auto = col2.form_submit_button("おまかせで進める", use_container_width=True)
        if asked.get("assumption"):
            st.caption("「おまかせ」の場合の前提: %s" % asked["assumption"])
        if go or auto:
            options = _base_options()
            if go:
                options["answers"] = [a for a in answers if a["answer"]]
            st.session_state["run"] = start_job(pending["brief"], options,
                                                pending["files"])
            st.session_state["stage"] = "running"
            st.rerun()

    else:
        st.success("実行中です。「📡 実行状況」タブで進み具合を確認してください。")
        st.caption("依頼: %s" % st.session_state.get("pending", {}).get("brief", "")[:200])

with tab_progress:
    if not run:
        st.info("「📝 入力」タブから実行してください。ここに各部隊の進み具合が出ます。")
    else:
        board = st.empty()
        logbox = st.empty()
        # 実行中は0.7秒ごとに描き直す。Streamlitはこのループ中ずっと画面を占有するため、
        # 一定時間で抜けて再実行し、他タブの操作を受け付ける。
        deadline = time.time() + 45
        while True:
            agents, logs = run.snapshot()
            with board.container():
                render_board(agents)
            with logbox.container():
                render_logs(logs, show_debug)
            if run.finished:
                break
            if time.time() > deadline:
                st.rerun()
            time.sleep(0.7)
        if run.error:
            st.error("処理が中断しました: %s" % run.error)
        else:
            st.success("すべての工程が終わりました。「📦 成果物」タブから受け取れます。")
            # 終わったら**成果物のフォルダを自動で開く**。
            # 場所を見て手で辿るのは毎回の手間なので、1回だけ開く
            # （画面は0.7秒ごとに描き直されるため、開いたことを覚えておかないと
            #   フォルダが何十枚も開く）
            _open_folder_once(run.job_dir)

with tab_output:
    if not run:
        st.info("まだ実行していません。")
    else:
        render_open_buttons(run.job_dir)
        render_artifacts(run.job_dir)
        if run.finished:
            # 並び順は「見る → 直す → 確かめる → 記録」。
            # 受け取った人がまず見たいのは完成品、次にやりたいのは直しなので、
            # レポート類はすべての後ろに置く
            st.divider()
            render_revision_panel(run.job_dir)
            st.divider()
            render_acceptance(run.job_dir)
            st.divider()
            render_legal_comments(run.job_dir)
            st.divider()
            render_needed_assets(run.job_dir)
            st.divider()
            render_reports(run.job_dir)
