# -*- coding: utf-8 -*-
"""12種類の覚書がすべて Word として生成できるかを確かめる（2026-08-23 追加）。

    .venv/bin/python smoke_test.py

**なぜ要るか**: 書式が12種類あり、画面から全部を毎回押して確かめるのは現実的でない。
1つの書式で `d['…']` のキー名を変えたときに**他の書式が KeyError で落ちる**のがこのアプリの
壊れ方で、画面上は「生成ボタンを押した人だけが気づく」。ここで12種類を一気に通す。

中身の文言までは見ない（それは目視の仕事）。**落ちずに .docx が出ること**と、
差し込んだ名前・金額が本文に入っていることだけを確かめる。
"""

import io
import sys
import zipfile

import docgen

FAILED = []

# 12種類すべてに渡せる「全部入り」の入力。使わないキーは各書式が無視する
BASE = {
    # 物件表示（_memo_frame は入力 dict をそのまま prop として使うので**トップレベル**に置く）
    "address": "大阪市都島区中野町1-4-18", "name": "テストマンション",
    "area": "25.00㎡", "room": "101号室",
    # 当事者
    "ko_name": "テスト太郎", "otsu_name": "テスト花子", "hei_name": "テスト三郎",
    "ko_sign": "テスト太郎", "otsu_sign": "テスト花子", "hei_sign": "テスト三郎",
    "ko_addr": "大阪市北区大淀中3-1-15", "otsu_addr": "大阪市都島区中野町1-4-18",
    "hei_addr": "大阪市城東区中央2-6-1",
    "era": "令和", "witness": False,
    # 日付
    "orig_date": "令和3年4月1日", "succ_date": "令和8年9月1日",
    "start_date": "令和8年9月1日", "date": "令和8年8月23日",
    "change_date": "令和8年9月1日", "end_date": "令和9年3月31日",
    # 承継の書式が見る連帯保証人（hosho_*）
    "hosho_name": "保証太郎", "hosho_sign": "保証太郎",
    "hosho_addr": "大阪市中央区船場中央1-1-1",
    # 賃料まわり
    "cur_rent": "80,000円", "cur_kyoueki": "5,000円", "cur_suido": "2,000円",
    "cur_total": "87,000円",
    "new_rent": "75,000円", "new_kyoueki": "5,000円", "new_suido": "2,000円",
    "new_total": "82,000円",
    "rent": "75,000円", "reduced_rent": "75,000円", "old_rent": "80,000円",
    # 連帯保証人・承継
    "guarantor_name": "保証太郎", "guarantor_addr": "大阪市中央区船場中央1-1-1",
    "new_guarantor_name": "保証次郎", "new_guarantor_addr": "大阪市西区新町1-1-1",
    "old_rep": "旧代表　一郎", "new_rep": "新代表　二郎",
    "company_name": "テスト商事株式会社", "new_company_name": "テスト商事ホールディングス株式会社",
    # 原状回復・駐車場・同居ほか
    "items": "エアコン設置、間仕切り壁の設置", "work_items": "エアコン設置、間仕切り壁の設置",
    "old_space": "No.5", "new_space": "No.12", "parking_name": "テスト駐車場",
    "resident_name": "同居花子", "relation": "配偶者", "birth": "平成2年1月1日",
    "minor_name": "未成年三郎", "parent_name": "テスト太郎",
    "purpose": "事務所として使用", "permit_content": "看板の設置",
    "title": "覚　　書", "body_text": "本文を自由に入力した場合の確認用の一文。",
}


def check(label, ok, note=""):
    print("  {} {:<40} {}".format("✓" if ok else "✗", label, note))
    if not ok:
        FAILED.append(label)


def is_docx(data: bytes) -> bool:
    """Word として開ける形か（zip の中に document.xml があるか）だけ見る。"""
    if not data or len(data) < 1000:
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def text_of(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("word/document.xml").decode("utf-8", "replace")


def main():
    print("■ 12種類の書式がすべて生成できる")
    produced = {}
    for key, (label, builder) in docgen.DOC_TYPES.items():
        try:
            data = builder(dict(BASE))
        except Exception as e:
            check("{}（{}）".format(key, label), False, "{}: {}".format(type(e).__name__, e))
            continue
        # 同居申請書のように2通返す書式がある
        blobs = list(data) if isinstance(data, (list, tuple)) else [data]
        ok = all(is_docx(b) for b in blobs)
        produced[key] = blobs
        check("{}（{}）".format(key, label), ok,
              "{} 通 / {} bytes".format(len(blobs), sum(len(b) for b in blobs)))

    print("■ 差し込んだ内容が本文に入っている（賃料改定で確認）")
    if produced.get("rent_revision"):
        body = text_of(produced["rent_revision"][0])
        check("賃貸人の名前", "テスト太郎" in body)
        check("賃借人の名前", "テスト花子" in body)
        check("現行賃料", "80,000円" in body)
        check("改定賃料", "75,000円" in body)
        check("物件名", "テストマンション" in body)

    print()
    if FAILED:
        print("✗ {} 件失敗: {}".format(len(FAILED), " / ".join(FAILED)))
        return 1
    print("ALL SMOKE TESTS PASSED（覚書12種類の生成）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
