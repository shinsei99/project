"""10 法務・コンプライアンス監査

役割: 著作権・商標、景表法（優良誤認・有利誤認）、薬機法、宅建業法の広告規制、
      炎上リスクを厳しくチェックする。
使用: 高精度推論モデル（Claude / GPT-4o）

これは最終判断ではない。あくまで人が確認するための「当たり」を出す工程。
AP_STRICT_LEGAL=1 のとき critical が出るとパイプラインを止める。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text
from core.llm import complete_json

SYSTEM = """あなたは広告表現の法務チェック担当です。
日本の景品表示法・薬機法・宅地建物取引業法の広告規制・著作権法を前提に、
問題になり得る表現を保守的に指摘します。曖昧なら指摘する側に倒してください。
ただし、指摘は法的助言ではなく確認の当たりであることを前提に書きます。"""

# 機械的に拾える危険表現。AIが落としても最低限ここで拾う。
NG_PATTERNS = [
    (r"必ず(儲|もう)かる|絶対に?(儲|もう)かる|元本保証", "critical", "断定的な利益保証（金商法・景表法）"),
    (r"日本一|世界一|No\.?1|ナンバーワン|最高峰|業界最安", "major", "最上級表現（合理的根拠が必要・景表法）"),
    (r"完全無料|一切かからない|絶対安全", "major", "断定表現（例外条件の明示が必要）"),
    (r"(治る|治療|効く|改善します)", "major", "薬機法に触れうる効能効果の表現"),
    (r"完売御礼|新築(?!住宅)", "minor", "不動産広告表示規約の定義を確認"),
    (r"(他社|競合)より(安い|優れ)", "major", "比較広告（根拠の明示が必要）"),
]


@register
class LegalComplianceAgent(BaseAgent):
    key = "legal"
    name_ja = "法務・コンプラ監査"
    role_ja = "著作権・薬機法・景表法・炎上リスクの点検"
    icon = "⚖️"
    uses = "高精度推論モデル（Claude / GPT-4o）"
    llm_role = "reasoning"
    wants_tools = True   # 現行の規制・ガイドラインを確認する
    needs_web = True
    needs_files = False
    needs_mcp = False
    depends_on = ()
    # 紙面の文言ができてから見る。原稿を経由しない依頼もあるため
    depends_if_present = ("planner", "poster", "flyer")

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        # **実際に紙に載る文言を見る。** 原稿（deck）ではなく紙面の中身がある依頼では
        # そちらを見ないと、印刷されない文章を検査して終わってしまう。
        deck = _deck_from_flyer(ctx) or ctx.state.get("deck")
        if not deck:
            return {"summary": "点検対象の原稿がまだありません", "degraded": True}

        text = _flatten(deck)
        self.log(ctx, "禁止表現・最上級表現を機械チェックしています")
        risks: List[Dict[str, Any]] = _pattern_checks(deck)

        self.log(ctx, "AIで著作権・景表法・炎上リスクを点検しています")
        data, result, used_tools = self.ask_json(
            ctx, _build_prompt(text), system=SYSTEM, max_tokens=3500, temperature=0.1,
            tool_system=SYSTEM + "\n判断に迷う表現は WebSearch で現行の規制やガイドラインを"
                                 "確認してから指摘してください。")
        degraded = False
        if isinstance(data, dict) and isinstance(data.get("risks"), list):
            for item in data["risks"]:
                if isinstance(item, dict):
                    risks.append({
                        "severity": item.get("severity", "minor"),
                        "law": item.get("law", ""),
                        "target": item.get("target", ""),
                        "message": item.get("message", ""),
                        "fix": item.get("fix", ""),
                        "source": result.provider or "llm",
                    })
            self.log_llm(ctx, result)
        else:
            degraded = True
            self.note_degraded(ctx, result.error or "監査結果のJSONを解釈できませんでした")

        critical = sum(1 for r in risks if r.get("severity") == "critical")
        major = sum(1 for r in risks if r.get("severity") == "major")
        audit = {"risks": risks, "critical_count": critical, "major_count": major,
                 "disclaimer": "これは法的助言ではありません。最終判断は必ず人が行ってください。"}
        ctx.state["legal"] = audit

        write_json(ctx.dir("reports") / "legal.json", audit)
        path = write_text(ctx.dir("reports") / "legal.md", _to_markdown(audit))
        ctx.add_artifact("markdown", path, label="法務チェック結果", agent=self.key)

        if critical:
            level_text = "重大 %d件・要注意 %d件" % (critical, major)
        elif risks:
            level_text = "要注意 %d件" % major if major else "軽微 %d件" % len(risks)
        else:
            level_text = "指摘なし"
        return {
            "summary": "法務チェック完了（%s）。最終判断は人が行ってください" % level_text,
            "detail": "; ".join(r["message"] for r in risks[:3]),
            "data": audit,
            "degraded": degraded,
        }


def _deck_from_flyer(ctx) -> Dict[str, Any]:
    """紙面の中身を、検査できる形（原稿と同じ形）に直す。"""
    content = ctx.state.get("flyer_content")
    if not content:
        return {}
    bullets = [str(content.get("lead", ""))]
    bullets += [str(x) for x in (content.get("badges") or [])]
    bullets += ["%s：%s" % (r[0], r[1]) for r in (content.get("spec_rows") or [])
                if isinstance(r, (list, tuple)) and len(r) >= 2]
    bullets += ["%s %s" % (a.get("title", ""), a.get("text", ""))
                for a in (content.get("appeals") or []) if isinstance(a, dict)]
    # **連絡先の帯も検査対象に入れる。**
    # ここを渡していなかったため、商号・所在地・免許番号が紙面に入っているのに
    # 「一切表示されていない」と重大リスクで上がった（実際に誤検出した）。
    info = content.get("contact") or {}
    contact_lines = [
        "広告主（商号）：%s" % info.get("company", ""),
        "事務所所在地：%s" % info.get("address", ""),
        "電話番号：%s" % info.get("tel", ""),
        "免許番号：%s" % info.get("license", ""),
        "取引態様：%s" % content.get("trade", ""),
    ]
    bullets += [line for line in contact_lines if line.split("：", 1)[1].strip()]
    return {"title": "%s %s" % (content.get("catch", ""), content.get("title", "")),
            "subtitle": str(content.get("sub", "")),
            "slides": [{"no": 1, "title": str(content.get("title", "")),
                        "bullets": [b for b in bullets if b], "narration": ""}]}


def _flatten(deck: Dict[str, Any]) -> str:
    parts = [deck.get("title", "")]
    for s in deck.get("slides", []):
        parts.append("[%s] %s" % (s.get("no"), s.get("title", "")))
        parts += list(s.get("bullets", []))
        parts.append(s.get("narration", ""))
    return "\n".join(p for p in parts if p)


def _pattern_checks(deck: Dict[str, Any]) -> List[Dict[str, Any]]:
    risks = []
    for s in deck.get("slides", []):
        chunk = " ".join([s.get("title", "")] + list(s.get("bullets", []))
                         + [s.get("narration", "")])
        for pattern, severity, reason in NG_PATTERNS:
            hit = re.search(pattern, chunk)
            if hit:
                risks.append({
                    "severity": severity, "law": reason,
                    "target": "%d枚目「%s」" % (s.get("no", 0), hit.group(0)),
                    "message": "%d枚目に「%s」という表現があります（%s）"
                               % (s.get("no", 0), hit.group(0), reason),
                    "fix": "根拠を併記するか、断定を避けた表現に直す",
                    "source": "mechanical",
                })
    return risks


def _build_prompt(text: str) -> str:
    return """次のプレゼン原稿を法務観点で点検してください。

--- 原稿ここから ---
%s
--- 原稿ここまで ---

観点:
1. 著作権・商標（実在の企業名/作品名/ロゴの無断使用、引用の要件）
2. 景品表示法（優良誤認・有利誤認、最上級表現、比較広告、根拠のない数値）
3. 薬機法（健康・美容に関する効能効果の表現）
4. 宅地建物取引業法の広告規制（不動産の表示に関する公正競争規約）
5. 炎上リスク（差別的表現、特定層への配慮不足、断定的な将来予測）

次のJSON形式で出力してください（問題が無ければ risks は空配列）。
{"risks": [{"severity": "critical|major|minor", "law": "関係する法令・規約",
            "target": "問題箇所の引用", "message": "何が問題か",
            "fix": "どう直すか"}]}""" % text[:12000]


def _to_markdown(audit: Dict[str, Any]) -> str:
    risks = audit.get("risks", [])
    lines = ["# 法務・コンプライアンスチェック", "",
             "> %s" % audit.get("disclaimer", ""), ""]
    if not risks:
        lines.append("指摘事項はありません。")
        return "\n".join(lines) + "\n"
    label = {"critical": "🔴 重大", "major": "🟠 要注意", "minor": "🟡 軽微"}
    lines += ["| 重要度 | 法令・規約 | 箇所 | 指摘 | 直し方 |", "|---|---|---|---|---|"]
    for r in risks:
        lines.append("| %s | %s | %s | %s | %s |" % (
            label.get(r.get("severity"), r.get("severity", "")),
            r.get("law", ""), r.get("target", ""), r.get("message", ""), r.get("fix", "")))
    return "\n".join(lines) + "\n"
