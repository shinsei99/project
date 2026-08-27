"""PropertyData の項目 → 公式書式の入力欄を、見出しの文言から解決する規則。

200本の公式書式それぞれにセル座標を手で書くのは現実的でないので、
`official_format_service.scan()` が拾った入力欄の見出しに対して
**包含パターン／除外パターン**を当てて対応付ける。

除外が要る理由（実測でつまずいた点）:
  - 「所在」は物件の所在地だけでなく **宅建業者の「主たる事務所所在地」**や
    保証協会の供託所にも出てくる。除外しないと業者住所を物件所在地に書いてしまう
  - 「種類」は建物の種類のほかに **「権利の種類」**（借地権など）がある
  - 「地積」は物件表示のほかに **「地積の確定」**（実測条項）がある
  - 「建蔽率」は指定建蔽率のほかに **「建蔽率の緩和」**の欄がある
  - 「所在」は **「水害ハザードマップにおける建物の所在地」**（＝地図上の位置を示す
    チェック欄）にも出てくる。2026-08-21 に賃貸重説で実際に誤爆し、**物件の所在地が
    ハザード欄に書かれて、本来の所在地はどこにも入らなかった**

予備の見出し（`alt`）が要る理由:
  賃貸重説（建物貸借用）の建物の表示欄は見出しが **「（住居表示）」「（登記簿）」**で、
  「所在」の字が無い。主パターンで当たらなかったときだけ予備を試す
  （売買の書式は「所在」で当たっているので、そちらの対応を変えないため）。

重説に記載欄が無い項目（最寄駅・駅距離・人口・世帯数・路線価・公示地価）は
ここでは扱わない。**あれは調査資料であって重要事項説明書の記載事項ではない**
（2026-08-21 に全宅連の公式書式を実測して確認）。画面に出すだけにする。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# (PropertyData のキー, 見出しに含まれる語, 除外語, 予備の見出し)
# 予備は「主パターンで1つも当たらなかったとき」だけ試す。
# 除外語のうち、物件の「所在」と紛らわしいもの（業者の事務所・供託所・ハザード欄）。
# 所在地と登記所在で同じものを使う（片方だけ直すと、もう片方が業者住所を拾う）
_NOT_PROPERTY_ADDRESS = (
    r"事務所|主たる|供託|保証協会|地方本部|免許|ハザード|水害|高潮|浸水|土砂|津波")

RULES = [
    # ★所在地（住居表示）に予備の「所在」を持たせない（2026-08-27）。
    #   住居表示の欄が無い書式（土地のみの売買など）で予備を許すと、
    #   **②筆目の所在欄**のような空いている「所在」に住居表示が入ってしまう。
    #   欄が無いなら入れない（人が備考へ書く）。
    ("所在地",   r"住居表示",   _NOT_PROPERTY_ADDRESS),
    ("地番",     r"地番",                 r"家屋番号"),
    ("地目",     r"地目",                 None),
    # 「地積測量図」は土地の測量図の作製日欄。地積そのものではない（紙面で確認）。
    # 売買の書式は列見出しが「登記簿面積」なので、予備でそちらも見る
    ("地積",     r"地積",                 r"確定|実測|公簿|差異|清算|測量図",
     r"登記簿面積"),
    # 書式へ入れるのは「記載」側（本体＋車庫なら ①② の連記）。
    # 比較用の素の値は `家屋番号` / `種類` に残してある（law_validator が使う）
    ("家屋番号記載", r"家屋番号",         None),
    ("種類記載", r"種類",                 r"権利の種類|工事|高度地区|免許|保証"),
    # 区分所有の書式は「一棟の建物の表示」にも構造の欄がある。謄本から取るのは
    # **専有部分**の構造なので、一棟のほうは除く（まとまり見出しで判別）
    ("構造",     r"構造",                 r"形状|工事完了|一棟"),
    # 「床面積／新築：」は新築年月の欄（見出しが上に届いてしまうだけ）。
    # 売買の書式は 1階・2階…と階ごとの欄なので、謄本の合計値は「計」の欄へ入れる。
    # 区分所有は「（壁芯）」「（登記簿）」の2欄で、謄本の値は**登記簿のほう**。
    # 一棟の「延床面積」は別物なので除く
    # 「延床面積」は**建物ぜんぶの合計**。区分所有では一棟の合計になってしまうので
    # 素の「床面積」を先に探し（(?<!延) で延床面積を弾く）、無いときだけ延床面積を使う。
    # 売買契約書の建物欄のように延床面積しか無い書式では、そこが正しい行き先になる
    ("床面積",   r"(?<!延)床面積",        r"新築|改築|増築|測量図|一棟",
     r"／計$|（登記簿）|延床面積"),
    # ★登記所在は床面積のあとに決める（2026-08-27）。区分所有では専有部分の
    #   床面積欄の見出しが「（登記簿）」で、先に処理すると**床面積の欄に所在が入る**。
    #   予備の「所在」は、（登記簿）という見出しを持たない売買書式のため。
    ("登記所在", r"登記簿|登記記録",
     # 「登記簿面積」＝地積の欄。ここを除かないと地積の欄に所在が入る（紙面で確認）。
     # 「／□」で終わる見出しは□の右にある選択肢の記入欄（例: 床面積の □登記簿 の隣）
     # 「土地登記簿謄本」は末尾の**添付書類チェックリスト**。物件の所在欄ではない
     _NOT_PROPERTY_ADDRESS
     + r"|構造|種類|床面積|面積|備考|年月|間取|／□|謄本|抄本|証明書|添付|壁芯",
     r"所\s*在"),
    # 公式書式の「登記名義人と□同じ□異なる」は**チェック欄**であって氏名欄ではない。
    # その周りの空欄（異なる→理由 など）へ名前を書くと意味が変わるので当てない
    # （2026-08-27 の紙面確認で、□に所有者名が入って印字が壊れていた）。
    # 真に「名義人 氏名」という欄を持つ書式があればそこだけ拾う
    # 「名称」は建物（マンション）の名前の欄。上の見出しが「登記名義人と」まで
    # 届くせいで当たるが、ここへ所有者名を書くと物件名が人名になる
    ("所有者",   r"名義人",     r"と貸主|と借主|同じ|異なる|理由|住\s*所|名\s*称"),
    # ★抵当権もここに置かない（2026-08-23）。書式の乙区欄は**土地と建物で行が分かれて
    #   いる**のに、この規則は「抵当権」の字に最初に当たったセル＝**建物側の詳細欄**を
    #   拾っていた。土地の謄本しか無くても建物欄に入る（2026-08-21 に発見）。
    #   → `checkbox_fill` が 土地抵当権 / 建物抵当権 をそれぞれの□と詳細欄に入れる。
    ("用途地域", r"用途地域",             r"特別用途|特定用途|準用途"),
    ("建ぺい率", r"指定建蔽率|指定建ぺい率", r"緩和"),
    ("容積率",   r"指定容積率",           r"特例|緩和|道路幅員"),
    ("高度地区", r"高度地区",             r"高度利用"),
    # ★災害3項目（洪水浸水想定・土砂災害・津波）はここに置かない（2026-08-23）。
    #   割り当て先のセルは**中身が `□` のチェックボックス**で、しかも3項目とも
    #   **「外」側の□**を指していた（公式書式25本すべてで実測）。テキストを流し込むと
    #   □が説明文に置き換わって書式が壊れる。`hazard_service` がスタブだった間は
    #   「空文字は書かない」規則で表面化していなかっただけ。
    #   → 土砂災害だけ `checkbox_fill` が「内」の□に■を入れる。
    #     津波は制度が別（浸水想定≠災害警戒区域）、洪水欄は地図添付のチェックなので触らない。
]

_SPACE = re.compile(r"[\s　]")


def normalize(text: str) -> str:
    """見出しの比較用。全角スペースや改行が入っている（例: 「地　　　番」）。"""
    return _SPACE.sub("", text or "")


# 同じ値を**まとまりごとに1回ずつ**書く項目。
# 売買の重説は「（1）土地／所在」と「（2）建物／所在」の2箇所に同じ登記の所在を書く。
# 1セルしか持たないと建物の所在欄が空のまま出る（2026-08-27 の紙面確認で判明）。
REPEAT_BY_SECTION = ("登記所在",)
# 上を書き足してよいまとまり。**不動産の表示の枠だけ**に限る
# （「所在」は業者欄・ハザード欄にもあるので、無制限に広げると誤爆する）
_REPEAT_SECTION_OK = re.compile(r"土\s*地|建\s*物|物\s*件")
_REPEAT_MAX = 3


def resolve(inputs: List[dict], extra: Dict[str, List[str]] = None) -> Dict[str, str]:
    """scan() の inputs から {PropertyData キー: セル} を作る。

    同じ見出しが複数当たる場合（土地が複数筆ある物件表示など）は
    **一番上の行のものを採る**。書式の1件目が主たる物件になっているため。

    `extra` に辞書を渡すと、`REPEAT_BY_SECTION` の項目について
    「別のまとまりにある2箇所目以降のセル」を {項目: [セル,...]} で書き足す。
    """
    out: Dict[str, str] = {}
    used: Dict[str, str] = {}        # セル -> 先に取った項目（衝突を防ぐ）
    picked: Dict[str, dict] = {}     # 項目 -> 採った入力欄（まとまりを見るため）
    rule_by_field = {r[0]: r for r in RULES}
    for rule in RULES:
        field, inc, exc = rule[0], rule[1], rule[2]
        alt = rule[3] if len(rule) > 3 else None
        exc_re = re.compile(exc) if exc else None

        def pick(pattern: str) -> Optional[dict]:
            pat = re.compile(pattern)
            for item in inputs:
                # **中身が「□」のセルには値を書かない。** 色も数式参照も付いていて
                # 入力欄に見えるが、テキストを入れるとチェック欄が消える
                # （2026-08-27 の紙面確認で所有者・床面積が□を潰していた）
                # **すでに文字が入っているセル**も対象にしない。書式の見出しが
                # 入っていることがあり、書くと見出しが消える（2026-08-27）
                if item.get("checkbox") or item.get("has_text"):
                    continue
                label = normalize(item.get("label"))
                if not pat.search(label):
                    continue
                # 除外だけは**属するまとまりの見出しも含めて**見る（`section`）。
                # 「構造」「床面積」は一棟の建物にも専有部分にもあり、見出しの文言が
                # 同じなので、まとまりを見ないと一棟のほうを拾う（2026-08-27）
                if exc_re and exc_re.search(normalize(item.get("section")) + label):
                    continue
                # **1つのセルに2項目を割り当てない。**
                # 割り当てると後の項目が前の値を上書きし、片方が黙って消える
                # （2026-08-21 に賃貸重説の O91 で実際に起きた）
                if item["cell"] in used:
                    continue
                return item
            return None

        best = pick(inc) or (pick(alt) if alt else None)
        if best is not None:
            out[field] = best["cell"]
            used[best["cell"]] = field
            picked[field] = best

    if extra is not None:
        for field in REPEAT_BY_SECTION:
            first = picked.get(field)
            if first is None:
                continue
            rule = rule_by_field[field]
            exc_re = re.compile(rule[2]) if rule[2] else None
            patterns = [rule[1]] + ([rule[3]] if len(rule) > 3 and rule[3] else [])
            seen_sections = {normalize(first.get("section"))}
            cells: List[str] = []
            for pattern in patterns:
                pat = re.compile(pattern)
                for item in inputs:
                    if (item.get("checkbox") or item.get("has_text")
                            or item["cell"] in used):
                        continue
                    section = normalize(item.get("section"))
                    if section in seen_sections or not _REPEAT_SECTION_OK.search(section):
                        continue
                    label = normalize(item.get("label"))
                    if not pat.search(label):
                        continue
                    if exc_re and exc_re.search(section + label):
                        continue
                    seen_sections.add(section)
                    used[item["cell"]] = field
                    cells.append(item["cell"])
                    if len(cells) >= _REPEAT_MAX:
                        break
                if len(cells) >= _REPEAT_MAX:
                    break
            if cells:
                extra[field] = cells
    return out


def coverage(mapping: Dict[str, str]) -> str:
    """対応が取れた項目／取れなかった項目を1行で返す（点検用）。"""
    got = [r[0] for r in RULES if r[0] in mapping]
    miss = [r[0] for r in RULES if r[0] not in mapping]
    return "対応 {}/{}  未対応: {}".format(len(got), len(RULES), "・".join(miss) or "なし")
