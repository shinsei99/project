"""NFCタグに書き込むNDEFメッセージの組み立てと、容量の計算。

なぜアプリ側ではなくここに置くか
    書き込むのはネイティブアプリだが、**収まるかどうかの判定はサーバー側でやりたい**。
    管理画面で鍵を登録した時点で「この内容はNTAG213に入りません」と出せれば、
    60本書いた後に気づく事故を防げる。アプリはここが出したバイト列をそのまま書く。

タグの容量（ユーザーメモリ・実測値ではなくNXPの仕様値）
    NTAG213  144バイト   ← 今回購入したもの
    NTAG215  504バイト
    NTAG216  888バイト

書き込む内容（2レコード）
    1. URLレコード   http://192.168.1.105:8534/t/<token>
       … iPhoneのバックグラウンドタグ読み取りが Safari を開くのはこれ。**必須**
    2. テキストレコード  物件名|鍵の名称|鍵番号|ボックス-位置
       … WiFiが無くても内容が読めるようにするための控え。**入らなければ削る**

キーリングに物件名を印字済みのため、タグに書いても漏れる情報は増えない
（2026-08-17に確認）。
"""

from __future__ import annotations

from typing import Optional

# NXP の仕様値（ユーザーメモリ）
TAG_CAPACITY = {
    "NTAG213": 144,
    "NTAG215": 504,
    "NTAG216": 888,
}
DEFAULT_TAG = "NTAG213"

# NDEF の URI Identifier Code。先頭の定型部分を1バイトに縮められる。
# 'http://' が 7バイト → 1バイトになるので、必ず使う。
URI_PREFIXES = [
    (0x01, "http://www."), (0x02, "https://www."),
    (0x03, "http://"),     (0x04, "https://"),
]

SEP = "|"          # 項目の区切り。日本語に出てこず1バイトで済む文字を選ぶ


def _record(tnf_flags: int, type_bytes: bytes, payload: bytes) -> bytes:
    """NDEFレコード1本を組み立てる。

    payload が255バイト以下なら SR（Short Record）が使え、長さ欄が1バイトで済む。
    鍵の情報はどう転んでも255を超えないので、常にSRになる。
    """
    short = len(payload) < 256
    header = tnf_flags | (0x10 if short else 0)
    out = bytes([header, len(type_bytes)])
    out += bytes([len(payload)]) if short else len(payload).to_bytes(4, "big")
    return out + type_bytes + payload


def uri_record(url: str, first: bool = True, last: bool = False) -> bytes:
    """URLレコード。先頭の 'http://' 等は1バイトのコードに畳む。"""
    code, rest = 0x00, url
    for c, prefix in URI_PREFIXES:
        if url.startswith(prefix):
            code, rest = c, url[len(prefix):]
            break
    flags = 0x01                       # TNF=1（Well Known）
    if first:
        flags |= 0x80                  # MB（メッセージの先頭）
    if last:
        flags |= 0x40                  # ME（メッセージの末尾）
    return _record(flags, b"U", bytes([code]) + rest.encode("utf-8"))


def text_record(text: str, lang: str = "ja", first: bool = False, last: bool = True) -> bytes:
    """テキストレコード。日本語はUTF-8で1文字3バイトになる点に注意。"""
    payload = bytes([len(lang)]) + lang.encode("ascii") + text.encode("utf-8")
    flags = 0x01
    if first:
        flags |= 0x80
    if last:
        flags |= 0x40
    return _record(flags, b"T", payload)


def _tlv(message: bytes) -> bytes:
    """NDEFメッセージをタグに置くときの包み（TLV）。

    255バイト未満なら長さ欄は1バイト、それ以上は3バイトになる。
    終端の 0xFE まで含めて、これがタグのユーザーメモリを実際に消費する量。
    """
    if len(message) < 255:
        return bytes([0x03, len(message)]) + message + bytes([0xFE])
    return bytes([0x03, 0xFF]) + len(message).to_bytes(2, "big") + message + bytes([0xFE])


def info_text(property_name: Optional[str], name: str, item_numbers: Optional[str],
              box_code: Optional[str], box_position: Optional[str]) -> str:
    """タグに載せる控えのテキスト。空の項目は詰めて短くする。"""
    box = _box(box_code, box_position)
    parts = [p for p in (property_name, name, item_numbers, box) if p]
    return SEP.join(parts)


def _box(code: Optional[str], position: Optional[str]) -> str:
    """ボックス未設定のとき『-03』にならないようにする。"""
    code, position = (code or "").strip(), (position or "").strip()
    if code and position:
        return f"{code}-{position}"
    return code or (f"位置{position}" if position else "")


def build(url: str, text: Optional[str] = None) -> bytes:
    """タグに書き込むバイト列（TLV込み）を返す。"""
    if text:
        msg = uri_record(url, first=True, last=False) + text_record(text, last=True)
    else:
        msg = uri_record(url, first=True, last=True)
    return _tlv(msg)


def _cut(text: str, budget: int) -> str:
    """UTF-8で budget バイトに収まるまで後ろを削る。削ったら末尾に … を付ける。

    日本語は1文字3バイトなので、文字数ではなくバイト数で見ないと外れる。
    """
    if len(text.encode("utf-8")) <= budget:
        return text
    ell = "…".encode("utf-8")            # 3バイト
    budget = max(budget - len(ell), 0)
    out = ""
    used = 0
    for ch in text:
        b = len(ch.encode("utf-8"))
        if used + b > budget:
            break
        out += ch
        used += b
    return (out + "…") if out else ""


def plan(url: str, property_name: Optional[str] = None, name: str = "",
         item_numbers: Optional[str] = None, box_code: Optional[str] = None,
         box_position: Optional[str] = None, tag: str = DEFAULT_TAG) -> dict:
    """このタグに何が書けるかを決める。

    ★削る順番が肝。
      鍵番号（10001,10002）とボックス（BOX-01-03）は **ASCIIで1文字1バイト**と安く、
      しかも現場で一番使う情報（どの鍵か・どこに戻すか）なので**必ず残す**。
      削るのは日本語の名前の方（1文字3バイト）。物件名と鍵の名称を、
      残った枠に収まるところまで縮めて「…」を付ける。

      以前は逆に、高い日本語を残して安いASCIIを捨てていた。NTAG213（144B）では
      それだと長い物件名で鍵番号ごと消えてしまう。

    ★URLは必須。入らなければタグを替えるしかない。
    """
    cap = TAG_CAPACITY.get(tag, TAG_CAPACITY[DEFAULT_TAG])
    text = info_text(property_name, name, item_numbers, box_code, box_position)

    full = build(url, text)
    if len(full) <= cap:
        return {"tag": tag, "capacity": cap, "bytes": len(full), "text": text,
                "url_only": False, "truncated": False, "fits": True,
                "payload": full, "free": cap - len(full)}

    # --- 入らない場合 ---
    # まず「鍵番号とボックスだけ」で枠を測り、残りを名前に配分する
    box = _box(box_code, box_position)
    cheap = SEP.join([p for p in (item_numbers, box) if p])
    base = len(build(url, cheap)) if cheap else len(build(url))
    budget = cap - base - (len(SEP.encode()) if cheap else 0)

    names = [p for p in (property_name, name) if p]
    if budget > 0 and names:
        # 物件名と鍵の名称で枠を分け合う。鍵の名称の方が「何の鍵か」を示すので少し厚く配る
        share = budget // len(names)
        cut = [_cut(n, share + (budget % len(names) if i == len(names) - 1 else 0))
               for i, n in enumerate(names)]
        parts = [p for p in cut if p] + ([cheap] if cheap else [])
        trial_text = SEP.join(parts)
        trial = build(url, trial_text)
        if len(trial) <= cap:
            return {"tag": tag, "capacity": cap, "bytes": len(trial), "text": trial_text,
                    "url_only": False, "truncated": True, "fits": True,
                    "payload": trial, "free": cap - len(trial)}

    # 名前がまったく入らない → 鍵番号とボックスだけ
    if cheap:
        trial = build(url, cheap)
        if len(trial) <= cap:
            return {"tag": tag, "capacity": cap, "bytes": len(trial), "text": cheap,
                    "url_only": False, "truncated": True, "fits": True,
                    "payload": trial, "free": cap - len(trial)}

    url_only = build(url)
    return {"tag": tag, "capacity": cap, "bytes": len(url_only), "text": "",
            "url_only": True, "truncated": True, "fits": len(url_only) <= cap,
            "payload": url_only, "free": cap - len(url_only)}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

    print(f"{'内容':<52} {'byte':>5} {'NTAG213':>9}")
    print("-" * 70)
    cases = [
        ("URLのみ", None, "", None, None, None),
        ("標準的な例", "大阪京橋ビル", "1階エントランスキー", "10001,10002", "BOX-01", "03"),
        ("鍵3本セット", "大阪京橋ビル", "機械室キー", "10003x3", "BOX-01", "04"),
        ("長め", "大阪京橋ビル別館", "地下1階機械室入口キー", "10001,10002,10003", "BOX-01", "12"),
        ("かなり長い", "角屋(横堤)モータープール管理棟", "1階事務所エントランス自動ドア", "77001,77002,77003", "BOX-02", "01"),
    ]
    url = "http://192.168.1.105:8534/t/qb767czs8kc2ry43"
    for label, prop, nm, nums, box, pos in cases:
        r = plan(url, prop, nm, nums, box, pos)
        mark = "❌あふれ" if r["truncated"] else "✅"
        detail = f"{r['bytes']:>5}  残{r['free']:>4}B {mark}"
        print(f"{label:<12} {(r['text'] or '（URLのみ）'):<40} {detail}")
