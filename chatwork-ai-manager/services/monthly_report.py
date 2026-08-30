"""業務月報の自動作成（TASK-20260825-001 → TASK-20260826-002 で入力源をLINEへ変更）。

日報（社員ごと・毎日・実務の記録）とは役割も起点も別物:
  - 起点: オーナーがLINEで直接AI業務マネージャーへ送った内容（テキスト・画像・会議資料）。
    「月報開始」〜「月報終了」の間に送った内容だけが今回の月報の材料になる
    （セッション・材料の管理は services/monthly_report_line.py）。
  - 内容: 月次会議（社長挨拶→各担当の業務報告→今後の改善点・現状の問題点の3部構成）の記録。
    社長挨拶は月報に含めず、**各担当の業務報告**（鷲見のみ先頭固定・それ以降（塚本・松本・森・
    吉浦・大鹿）は会議によって順番が変わるため送られた順に従う。欠席者は省略）と
    **今後の改善点・現状の問題点**の2セクションで出力する。
  - 出力（Excel）は日報と**同じ保存フォルダ**（daily_report_save_dir）に保管し、
    社内向けにChatworkの対象ルーム（target_room_id）へアップする（出力先は従来どおり）。

★2026-08-26 オーナー指示: 入力源をChatwork（鷲見の資料アップロード検知）からLINEへ変更した。
  **Chatworkの資料アップロードでは今後いっさい月報を作らない**（services/scheduler.py の
  tick() からもChatwork検知の呼び出しを外した。旧 pending_triggers 等の関連コードは削除済み）。
"""
import datetime
import json
import os

from db.connection import get_conn, query, query_one
from services import settings
from services.claude_client import run_json

# --- 出力先（Excelのアップ先Chatworkルーム）------------------------------------
def target_room_id():
    """月報の出力（Excel）をアップロードするChatworkルーム（入力経路とは無関係）。"""
    rid = settings.get_setting("monthly_report_room_id", "") or \
        settings.get_setting("daily_report_room_id", "") or \
        settings.get_setting("manager_room_id", "")
    if rid:
        return int(rid)
    row = query_one("SELECT room_id FROM rooms WHERE monitored=1 AND type='group' "
                    "ORDER BY room_id LIMIT 1")
    return row["room_id"] if row else None


# --- プロンプト --------------------------------------------------------------
_PROMPT = """あなたは不動産会社「大京商事」のAI業務マネージャーです。
オーナーがLINEで直接入力・送信した**会議資料・会議内容**（{date}（{wd}曜日）に受け付けたもの）から、
会社としての月報を書いてください。

# 会議の構成（月報はこれに合わせる）
実際の会議は次の3部構成です。
1. 社長挨拶 → 月報には**含めない**（読み取れても書かない）
2. 各担当の業務報告（**鷲見が1番目で固定**。それ以降の塚本・松本・森・吉浦・大鹿は
   会議によって順番が変わるため、送られた順（または実際の発言順）に従う。欠席者は報告なし）
3. 今後の改善点や現状の問題点

# 絶対に守ること
- **送られた材料に書かれていないことは書かない。** 想像で内容を作らない。
- 推測せざるを得ないことは文末に「（推測）」と付ける。
- 日報（社員ごとの日々の実務記録）とは役割が違います。月報は**会議で共有された内容**を
  まとめる位置づけです。
- 社長挨拶の内容（冒頭の挨拶・訓示など）は読み取れても本文に含めない。
- 添付資料のうち抽出に失敗しているものがあれば、内容を想像で埋めず、
  「〇〇（ファイル名）は内容を読み取れませんでした」とだけ書く。
- 材料が実質的に空だった場合は、無理に本文を作らず
  「材料の内容を読み取れず、月報を作成できませんでした」とだけ書く。

# オーナーがLINEで送った材料
{material}

# 出力
次のJSONだけを返してください（前後に説明文を付けない）。

{{
  "summary": "1行要約（40字以内）",
  "body_md": "月報本文（Markdown）"
}}

body_md は**次の2つの大見出し（##）だけ**を、この順で書いてください。見出しを増やさない。
各行は「・」ではなく `- ` で始める箇条書き。

## 各担当の業務報告

この下に、材料の中で実際に業務報告がある担当だけ、小見出し（###・担当者名のみ）を作り、
その人の報告内容を箇条書きでまとめる。**順番のルール:** 鷲見の報告があれば必ず1番目に置く。
それ以降（塚本・松本・森・吉浦・大鹿）は固定順にせず、材料に書かれた順のまま並べる。
順番が材料から読み取れない担当者は、材料内での記載位置をそのまま使う。
欠席等でその担当の報告が材料に無い場合は、その人の小見出しごと**丸ごと省略する**
（「特になし」と書かない・無理に埋めない）。6名とも報告が無ければ、この見出しの下に
「今回の材料からは各担当の業務報告を読み取れませんでした」と1行だけ書く。

## 今後の改善点や現状の問題点

会議で挙がった改善点・問題点を箇条書きでまとめる。該当が無ければ「特になし」と1行だけ書く。
"""


def _item_block(it: dict) -> str:
    if it["kind"] == "text":
        return f"[オーナーの入力]\n{it['text']}"
    label = "画像" if it["kind"] == "image" else "ファイル"
    name = it.get("filename") or label
    body = it["text"] if it.get("ok") else f"（{it.get('error') or '内容を読み取れませんでした'}）"
    return f"[{label}: {name}]\n{body}"


def build_prompt_from_line(mat_items: list) -> str:
    blocks = [_item_block(it) for it in mat_items if (it.get("text") or "").strip() or not it.get("ok")]
    material = "\n\n".join(blocks) if blocks else "（材料がありません）"
    today = datetime.date.today()
    wd = "月火水木金土日"[today.weekday()]
    return _PROMPT.format(date=today.isoformat(), wd=wd, material=material)


# --- 生成・保存 ---------------------------------------------------------------
def model() -> str:
    return settings.get_setting("model_monthly_report", "sonnet")


def generate_from_line(session: dict, mat_items: list, generated_by: str = "line") -> dict:
    """LINEセッションの材料から1本の月報を作って保存する。session["id"] ごとに1本（冪等）。"""
    prompt = build_prompt_from_line(mat_items)
    parsed, env = run_json(prompt, model=model(), timeout=300)

    body = (parsed.get("body_md") or "").strip()
    if not body:
        raise ValueError("AIが本文を返しませんでした。")

    trigger_key = f"line:{session['id']}"
    period = datetime.date.today().strftime("%Y-%m")
    evidence = [it["id"] for it in mat_items]
    files_json = [{"filename": it.get("filename") or it["kind"], "ok": bool(it.get("ok")),
                  "error": it.get("error")} for it in mat_items if it["kind"] in ("file", "image")]
    save(trigger_key, period, target_room_id(), body, parsed.get("summary"),
        evidence, files_json, model(), generated_by)
    _log(trigger_key, prompt, env, parsed)
    return get_by_trigger(trigger_key)


def finalize_line_session(session: dict, client=None, generated_by: str = "line") -> dict:
    """LINEの月報材料受付セッションを締めて、月報の作成・保存・Excel化・Chatworkアップまで行う。

    呼び出し元（line_webhook の「月報終了」／scheduler の放置タイムアウト）が
    戻り値の errors を見て、本人へ結果を伝える。
    """
    from services import monthly_report_export as MEX
    from services import monthly_report_line as MRL

    MRL.close_session(session["id"])  # 先に閉じる（生成が失敗しても二重処理・再試行しない）
    mat = MRL.items(session["id"])
    result = {"session_id": session["id"], "errors": []}
    if not any((it.get("text") or "").strip() for it in mat):
        result["errors"].append("材料が空でした（テキスト・画像・ファイルを1件も受け取れませんでした）。")
        return result

    try:
        row = generate_from_line(session, mat, generated_by=generated_by)
    except Exception as e:
        result["errors"].append(f"generate: {type(e).__name__}: {e}")
        return result
    result["row"] = row

    if client is None:
        from services.chatwork import ChatworkClient
        client = ChatworkClient()

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="monthly_report_")
    xlsx = os.path.join(tmpdir, f"業務月報_{row['report_period']}.xlsx")
    MEX.build_xlsx(row, xlsx)

    save_dir = settings.get_setting("daily_report_save_dir", "") or ""
    if save_dir:
        try:
            os.makedirs(save_dir, exist_ok=True)
            dst = os.path.join(save_dir, os.path.basename(xlsx))
            with open(xlsx, "rb") as f, open(dst, "wb") as g:
                g.write(f.read())
            result["saved"] = dst
        except OSError as e:
            result["errors"].append(f"保管失敗: {type(e).__name__}: {e}")

    if settings.get_setting("monthly_report_upload", "1") == "1":
        rid = target_room_id()
        if not rid:
            result["errors"].append("アップ先ルームが決まらない（monthly_report_room_id 未設定）")
        else:
            msg = (f"{settings.get_setting('ai_prefix', '🤖AI業務マネージャー')}\n"
                   f"📝 業務月報（{MEX.period_label(row['report_period'])}分）を作成しました。\n"
                   "事実と違う点があれば直してください。")
            try:
                fid = client.post_file(rid, xlsx, message=msg)
                result["uploaded"] = {"room_id": rid, "file_id": fid}
            except Exception as e:
                result["errors"].append(f"アップ失敗: {type(e).__name__}: {e}")

    if settings.get_setting("monthly_report_mail", "0") == "1":
        to = (settings.get_setting("monthly_report_mail_to", "").strip()
              or settings.get_setting("daily_report_mail_to", "").strip())
        if not to:
            result["errors"].append("メール送信先が未設定（monthly_report_mail_to）")
        else:
            from services import mailer
            lack = mailer.missing()
            if lack:
                result["errors"].append(
                    "メール未送信: SMTPの設定が足りない（" + " / ".join(lack) + "）")
            else:
                subject = f"業務月報 {MEX.period_label(row['report_period'])}"
                body_mail = f"業務月報送付\n添付：{MEX.sheet_name(row['report_period'])}"
                try:
                    sent = mailer.send([t.strip() for t in to.split(",") if t.strip()],
                                       subject, body_mail, attachments=[xlsx],
                                       sender_name="AI業務マネージャー")
                    result["mailed"] = {"to": sent["to"]}
                except Exception as e:
                    result["errors"].append(f"メール送信失敗: {e}")

    return result


def save(trigger_message_id, period, room_id, body, summary, evidence, files_json,
        model_name, generated_by):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO monthly_reports (trigger_message_id, report_period, room_id, body, "
            "summary, evidence, files, model, generated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(trigger_message_id) DO UPDATE SET "
            "report_period=excluded.report_period, room_id=excluded.room_id, body=excluded.body, "
            "summary=excluded.summary, evidence=excluded.evidence, files=excluded.files, "
            "model=excluded.model, generated_by=excluded.generated_by, updated_at=datetime('now','localtime')",
            (trigger_message_id, period, room_id, body, summary,
             json.dumps(evidence, ensure_ascii=False), json.dumps(files_json, ensure_ascii=False),
             model_name, generated_by))


def _log(trigger_message_id, prompt, env, parsed):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ai_analysis_logs (kind, model, prompt, raw_output, parsed, duration_ms) "
            "VALUES ('monthly_report', ?, ?, ?, ?, ?)",
            (model(), prompt[:20000], str(env.get("result"))[:20000],
             json.dumps({"trigger_message_id": trigger_message_id, **parsed}, ensure_ascii=False)[:20000],
             env.get("_elapsed_ms")))


def get_by_trigger(trigger_message_id: str):
    r = query_one("SELECT * FROM monthly_reports WHERE trigger_message_id=?", (trigger_message_id,))
    return dict(r) if r else None


def list_all(limit: int = 24):
    return [dict(r) for r in query(
        "SELECT * FROM monthly_reports ORDER BY report_period DESC, id DESC LIMIT ?", (limit,))]


def delete(trigger_message_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM monthly_reports WHERE trigger_message_id=?", (trigger_message_id,))
