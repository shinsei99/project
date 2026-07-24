import streamlit as st
import subprocess
import json
import os
import io
import re
import copy
import zipfile
import html as html_mod
from datetime import date
from lxml import etree

CLAUDE_BIN = "/opt/homebrew/bin/claude"
CLAUDE_TIMEOUT = 120
SENDERS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "senders.json")
TEMPLATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.docx")

DEFAULT_SENDERS = [
    {
        "label": "大京",
        "company": "大京商事株式会社",
        "title": "専務取締役",
        "name": "鷲見　慎一",
        "address": "大阪市都島区東野田町2-3-14",
        "tel": "０６－６３５３－０４１８",
        "fax": "０６－６３５３－０２８０",
    },
    {
        "label": "新誠",
        "company": "新誠プロパティマネジメント㈱",
        "title": "代表取締役",
        "name": "鷲見　慎一",
        "address": "大阪市北区大淀中3-1-15",
        "tel": "０６－６９３５－７２６７",
        "fax": "０６－７６３５－７８１１",
    },
    {
        "label": "京橋",
        "company": "一般社団法人京橋地域活性化機構",
        "title": "理事長",
        "name": "鷲見　慎一",
        "address": "大阪市都島区東野田町3-10-3",
        "tel": "０６－６９３５－７２６７",
        "fax": "０６－７６３５－７８１１",
    },
    {
        "label": "個人",
        "company": "",
        "title": "",
        "name": "鷲見　慎一",
        "address": "大阪市城東区中央1-10-22-901",
        "tel": "090-8530-0184",
        "fax": "０６－７６３５－７８１１",
    },
]

PREAMBLE = (
    "拝啓　時下いよいよご清祥のこととお慶び申し上げます。\n"
    "平素は何かとご高配を賜り有難く厚くお礼申し上げます。\n"
    "さて、掲題につき下記の通り添付申し上げますので\n"
    "ご査収下さいますようお願い申し上げます。　　　　敬具"
)

_FW  = str.maketrans("0123456789", "０１２３４５６７８９")
_W   = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_SPC = '{http://www.w3.org/XML/1998/namespace}space'


# ── Persistence ───────────────────────────────────────────────────────────────
def load_senders() -> list:
    if os.path.exists(SENDERS_FILE):
        try:
            with open(SENDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SENDERS[:]


def save_senders(senders: list):
    with open(SENDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(senders, f, ensure_ascii=False, indent=2)


# ── Date ──────────────────────────────────────────────────────────────────────
def to_reiwa(d: date) -> str:
    y = d.year - 2018
    return f"令和{str(y).translate(_FW)}年{str(d.month).translate(_FW)}月{str(d.day).translate(_FW)}日"


# ── AI Generation ─────────────────────────────────────────────────────────────
def generate_body(recipient: str, memo: str, sender: dict) -> str:
    sender_name = f"{sender.get('title', '')}　{sender.get('name', '')}".strip()
    sender_desc = f"{sender['company']} {sender_name}" if sender.get("company") else sender_name

    prompt = f"""ビジネス文書の専門家として、送付状の「記」以下に書く本文メッセージを作成してください。

■ 送付先: {recipient}
■ 送付者: {sender_desc}
■ 送付の概要・用件: {memo.strip() if memo.strip() else "（詳細未入力）"}

【作成ルール】
- 「お世話になります。」で書き出す
- 何を送付するか、理由・背景を自然な流れで1〜3文にまとめる
- 締めは「よろしくお願いいたします。」など状況に合わせて
- 余計な前置きや署名は一切不要
- 送付状らしい簡潔・丁寧な文体
- 本文のみを出力すること

本文のみを出力してください:"""

    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", "sonnet"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT)
    except FileNotFoundError:
        raise RuntimeError("`claude` コマンドが見つかりません。")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"生成が{CLAUDE_TIMEOUT}秒を超えたため中断しました。")
    if proc.returncode != 0:
        raise RuntimeError(f"claude コマンドが失敗しました\n{proc.stderr.strip()[:300]}")
    result = json.loads(proc.stdout)
    if result.get("is_error"):
        raise RuntimeError(f"Claude がエラーを返しました: {result.get('result')}")
    return result.get("result", "").strip()


# ── Word Document（zip + lxml 直接差し込み）──────────────────────────────────
def _sender_lines(sender: dict) -> list:
    """テンプレート送付者6行分 [会社, 役職+氏名, 住所, ビル(空欄), TEL, FAX]"""
    tn = f"{sender['title']}　　{sender['name']}" if sender.get("title") and sender.get("name") \
         else sender.get("name", "")
    return [
        sender.get("company", ""),
        tn,
        sender.get("address", ""),          # 段落側で右寄せ（jc=right）するため手動インデント不要
        "",
        f"ＴＥＬ　　{sender['tel']}" if sender.get("tel") else "",
        f"ＦＡＸ　　{sender['fax']}" if sender.get("fax") else "",
    ]


def _wt_set(p_elem, text: str):
    """w:p 内の w:t テキストノードだけ書き換える。構造・書式は一切変更しない。"""
    ts = p_elem.findall(f'.//{{{_W}}}t')
    if not ts:
        return
    ts[0].text = text
    ts[0].set(_SPC, 'preserve')
    for t in ts[1:]:
        t.text = ''


def _apply_rpr(p_elem, ref_rpr):
    """段落先頭ランの書式(rPr)を基準書式で上書きする。
    テンプレの本文空段落は書式が不揃い（sz=22/Times New Romanが混在）なため、
    本文各行を必ず基準段落と同一書式に揃えて出力の崩れを防ぐ。"""
    if ref_rpr is None:
        return
    r = p_elem.find(f'{{{_W}}}r')
    if r is None:
        return
    new = copy.deepcopy(ref_rpr)
    existing = r.find(f'{{{_W}}}rPr')
    if existing is not None:
        r.replace(existing, new)
    else:
        r.insert(0, new)


def _dehyphenate(local: str) -> str:
    """ハイフン表記 → OOXML の camelCase（first-line→firstLine, sz-cs→szCs）。"""
    return re.sub(r'-([a-z])', lambda m: m.group(1).upper(), local)


def _sanitize_ooxml(tree):
    """document.xml を Word が受理する正規形に整える。
    このテンプレは変換ツール由来で、OOXML の camelCase 名を全てハイフン表記
    （w:sz-cs / w:first-line 等）で出力しており、そのままだと Word が
    『破損 → 開いて修復』を要求する。要素名・属性名を正規化し、
    w:pPr の子順序も CT_PPr のシーケンス順（ind → jc）に揃える。"""
    for el in tree.iter():
        q = etree.QName(el)
        if q.namespace == _W and '-' in q.localname:
            el.tag = f'{{{_W}}}{_dehyphenate(q.localname)}'
        for an in list(el.attrib):
            qn = etree.QName(an)
            if qn.namespace == _W and '-' in qn.localname:
                el.set(f'{{{_W}}}{_dehyphenate(qn.localname)}', el.attrib.pop(an))
    for pPr in tree.iter(f'{{{_W}}}pPr'):
        jc  = pPr.find(f'{{{_W}}}jc')
        ind = pPr.find(f'{{{_W}}}ind')
        if jc is not None and ind is not None and \
           list(pPr).index(ind) > list(pPr).index(jc):
            pPr.remove(ind)
            pPr.insert(list(pPr).index(jc), ind)


def create_docx(recipient: str, doc_date: date, body: str, sender: dict) -> io.BytesIO:
    """テンプレートを zip のまま複製し、document.xml の w:t だけ差し込んで返す。
    ページ設定・余白・フォント・行間など一切変更しない。"""

    with open(TEMPLATE_FILE, 'rb') as f:
        tmpl = f.read()

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(tmpl), 'r') as zin, \
         zipfile.ZipFile(out, 'w') as zout:

        for item in zin.infolist():
            data = zin.read(item.filename)

            if item.filename == 'word/document.xml':
                tree      = etree.fromstring(data)
                body_elem = tree.find(f'{{{_W}}}body')
                paras     = body_elem.findall(f'{{{_W}}}p')

                _wt_set(paras[0], to_reiwa(doc_date))          # 日付
                _wt_set(paras[1], f"{recipient}　様")           # 宛名
                for i, line in enumerate(_sender_lines(sender)):# 送付者6行
                    _wt_set(paras[2 + i], line)

                body_start = 17
                # 基準書式（本文1行目 p17 の rPr = sz24/Times）を控える
                ref_run = paras[body_start].find(f'.//{{{_W}}}r')
                ref_rpr = ref_run.find(f'{{{_W}}}rPr') if ref_run is not None else None
                ref_rpr = copy.deepcopy(ref_rpr) if ref_rpr is not None else None

                body_lines = [l for l in body.split('\n') if l.strip()]
                for i in range(body_start, len(paras)):         # 本文欄クリア
                    _wt_set(paras[i], '')
                for i, line in enumerate(body_lines):           # 本文差し込み
                    if body_start + i < len(paras):
                        _wt_set(paras[body_start + i], line)
                        _apply_rpr(paras[body_start + i], ref_rpr)  # 書式を基準に統一

                _sanitize_ooxml(tree)  # Word破損防止（無効要素名・子順序を正規化）

                data = etree.tostring(tree, xml_declaration=True,
                                      encoding='UTF-8', standalone=True)
                # lxml は宣言をシングルクォートで出力するが Word はダブルクォートを要求するため修正
                data = data.replace(
                    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>",
                    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                )

            zout.writestr(item, data, compress_type=item.compress_type)

    out.seek(0)
    return out


# ── Preview HTML ──────────────────────────────────────────────────────────────
def render_preview(recipient: str, doc_date: date, body: str, sender: dict):
    e = html_mod.escape

    s_lines = []
    if sender.get("company"):
        s_lines.append(f"<b>{e(sender['company'])}</b>")
    tn = "　".join(filter(None, [sender.get("title", ""), sender.get("name", "")]))
    if tn:
        s_lines.append(e(tn))
    if sender.get("address"):
        s_lines.append(e(sender["address"]))
    if sender.get("tel"):
        s_lines.append(f"ＴＥＬ　　{e(sender['tel'])}")
    if sender.get("fax"):
        s_lines.append(f"ＦＡＸ　　{e(sender['fax'])}")

    st.markdown(
        f"""
<div style="
    background:white;border:1px solid #ccc;border-radius:6px;
    font-family:'Hiragino Mincho Pro','MS 明朝','Yu Mincho',serif;
    color:#111;box-shadow:0 3px 12px rgba(0,0,0,0.1);
    max-width:680px;margin:0 auto;padding:28px 36px 24px 36px;
    line-height:2;font-size:13px;">
  <div style="text-align:right;margin-bottom:10px;">{e(to_reiwa(doc_date))}</div>
  <div style="margin-bottom:6px;font-size:17px;font-weight:bold;">{e(recipient)}　様</div>
  <div style="margin-bottom:16px;line-height:1.9;text-align:right;">{"<br>".join(s_lines)}</div>
  <div style="text-align:center;font-size:15px;font-weight:bold;letter-spacing:3px;
      border-top:1px solid #555;border-bottom:1px solid #555;
      padding:6px 0;margin-bottom:14px;">書 類　送　付 の 件</div>
  <div style="margin-bottom:14px;text-align:center;">{e(PREAMBLE).replace(chr(10),"<br>")}</div>
  <div style="text-align:center;font-size:14px;font-weight:bold;margin:14px 0 10px;">記</div>
  <div style="margin-bottom:20px;">{e(body).replace(chr(10),"<br>")}</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ── Sidebar: Sender Management ─────────────────────────────────────────────────
def sidebar_senders() -> dict:
    senders = st.session_state.setdefault("senders", load_senders())

    st.markdown("## 📮 送付者を選択")
    labels = [s["label"] for s in senders]
    idx = st.session_state.get("sender_idx", 0)
    if idx >= len(senders):
        idx = 0

    chosen_label = st.radio("送付者", labels, index=idx, key="sender_radio",
                            label_visibility="collapsed")
    chosen_idx = labels.index(chosen_label)
    st.session_state["sender_idx"] = chosen_idx
    sender = senders[chosen_idx]

    st.divider()
    with st.expander("✏️ 送付者を編集・追加", expanded=False):
        mode = st.radio("操作", ["選択中を編集", "新規追加"], horizontal=True, key="edit_mode")
        et = senders[chosen_idx].copy() if mode == "選択中を編集" else \
             {"label": "", "company": "", "title": "", "name": "", "address": "", "tel": "", "fax": ""}

        e_label   = st.text_input("ラベル",   value=et["label"],   key="e_label")
        e_company = st.text_input("会社名",   value=et["company"], key="e_company")
        e_title   = st.text_input("役職",     value=et["title"],   key="e_title")
        e_name    = st.text_input("氏名",     value=et["name"],    key="e_name")
        e_address = st.text_input("住所",     value=et["address"], key="e_address")
        e_tel     = st.text_input("ＴＥＬ",  value=et["tel"],     key="e_tel")
        e_fax     = st.text_input("ＦＡＸ",  value=et["fax"],     key="e_fax")

        new_data = {"label": e_label, "company": e_company, "title": e_title,
                    "name": e_name, "address": e_address, "tel": e_tel, "fax": e_fax}

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存", use_container_width=True):
                if not e_label.strip():
                    st.warning("ラベルを入力してください")
                else:
                    if mode == "新規追加":
                        senders.append(new_data)
                        st.session_state["sender_idx"] = len(senders) - 1
                    else:
                        senders[chosen_idx] = new_data
                    save_senders(senders)
                    st.session_state["senders"] = senders
                    st.success("保存しました")
                    st.rerun()
        with col2:
            if mode == "選択中を編集" and len(senders) > 1:
                if st.button("🗑 削除", use_container_width=True, type="secondary"):
                    senders.pop(chosen_idx)
                    st.session_state["sender_idx"] = 0
                    save_senders(senders)
                    st.session_state["senders"] = senders
                    st.rerun()

    return sender


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="送付書ジェネレーター", page_icon="📮", layout="wide")

    with st.sidebar:
        sender = sidebar_senders()

    st.title("📮 送付書ジェネレーター")
    st.caption("宛名と用件を入力するだけで、AIが送付状を自動生成 → Word（.docx）ダウンロード")
    st.divider()

    left, right = st.columns([1, 1.2], gap="large")

    with left:
        st.subheader("📝 送付内容を入力")
        recipient = st.text_input("① 宛名", placeholder="例：山田　太郎",
                                  help="「様」は自動で付きます。")
        doc_date  = st.date_input("② 日付", value=date.today())
        memo = st.text_area(
            "③ 送付内容・用件メモ",
            placeholder="例：\n・契約書類一式をお送りします\n・先日お話しした見積書を添付します",
            height=150,
            help="箇条書きでもOK。AIが自然な文章に仕上げます。",
        )
        gen_btn = st.button("✨ 送付書を生成する", type="primary", use_container_width=True)

    with right:
        st.subheader("📄 プレビュー・ダウンロード")

        if gen_btn:
            if not recipient.strip():
                st.warning("⚠️ 宛名を入力してください。")
            elif not memo.strip():
                st.warning("⚠️ 送付内容・用件メモを入力してください。")
            else:
                with st.spinner("AIが本文を生成しています..."):
                    try:
                        body = generate_body(recipient.strip(), memo, sender)
                        st.session_state["body"]        = body
                        st.session_state["meta"]        = {"recipient": recipient.strip(),
                                                           "doc_date": doc_date}
                        st.session_state["has_content"] = True
                        st.success("✅ 生成完了！")
                    except Exception as ex:
                        st.error(f"❌ エラーが発生しました: {ex}")

        if st.session_state.get("has_content"):
            meta   = st.session_state["meta"]
            edited = st.text_area("✏️ 本文（記 以下）を確認・編集", height=160, key="body",
                                  help="自由に編集できます。")

            st.markdown("---")
            with st.expander("📋 完成イメージ（プレビュー）", expanded=True):
                render_preview(meta["recipient"], meta["doc_date"], edited, sender)

            st.markdown("---")
            try:
                buf = create_docx(meta["recipient"], meta["doc_date"], edited, sender)
                from datetime import datetime
                fname = f"送付書_{meta['recipient']}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
                st.download_button(
                    label="📥 Word（.docx）をダウンロード",
                    data=buf,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    type="primary",
                )
                st.caption(fname)
            except Exception as ex:
                st.error(f"Word生成エラー: {ex}")

        elif not gen_btn:
            st.info("👈 左側で宛名・用件を入力し、「送付書を生成する」ボタンを押してください。")


if __name__ == "__main__":
    main()
