"""UI を起動せずパイプライン各段を検証するスモークテスト。"""
import os

from models.property_data import create_property_data, merge
from services import (
    comment_service,
    excel_export_service,
    pdf_export_service,
    registry_service,
)
from utils import parser

BASE = os.path.dirname(os.path.abspath(__file__))

# 1) PropertyData
data = create_property_data()
assert "所在地" in data and data["所在地"] == ""

# 2) マージ（空/不正キーを無視）
merge(data, {"所在地": " 東京都千代田区丸の内1-1-1 ", "用途地域": "商業地域",
             "建ぺい率": "80%", "容積率": "800%", "不明キー": "x", "地番": ""})
assert data["所在地"] == "東京都千代田区丸の内1-1-1"
assert "不明キー" not in data
assert data["地番"] == ""  # 空文字は上書きしない

# 3) 登記簿パーサ（テキスト直接）
land_text = "所　在  千代田区丸の内一丁目\n地　番  1番1\n地　目  宅地\n地　積  123.45㎡\n所有者  山田太郎\n抵当権設定"
land = parser.parse_land(land_text)
assert land["地目"] == "宅地", land
assert land["地積"].startswith("123"), land
assert "抵当権" in land["抵当権"], land
print("land parse:", land)

# 4) registry_service 統合
reg = registry_service.parse_registry(None, None)
assert isinstance(reg, dict)

# 5) コメント生成
merge(data, {"最寄駅": "東京駅（JR山手線）", "駅距離": "約 350m"})
comment = comment_service.generate_comment(data)
assert "商業地域" in comment and len(comment) > 50
print("comment:", comment)

# 6) Excel 出力（テンプレ自動生成含む）
tpl = os.path.join(BASE, "templates", "jyuusetsu_template.xlsx")
out_xlsx = os.path.join(BASE, "reports", "jyuusetsu_draft.xlsx")
excel_export_service.export_excel(data, comment, tpl, out_xlsx)
assert os.path.exists(tpl) and os.path.exists(out_xlsx)
from openpyxl import load_workbook
ws = load_workbook(out_xlsx).active
assert ws["B2"].value == "東京都千代田区丸の内1-1-1", ws["B2"].value
assert ws["B10"].value == "商業地域", ws["B10"].value
print("excel B2/B10/B11:", ws["B2"].value, ws["B10"].value, ws["B11"].value)

# 7) PDF 出力
out_pdf = os.path.join(BASE, "reports", "jyuusetsu_draft.pdf")
pdf_export_service.export_pdf(data, comment, out_pdf)
assert os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 1000
print("pdf bytes:", os.path.getsize(out_pdf))

print("\nALL SMOKE TESTS PASSED")


# 9) 公式書式カタログ（レジストリが無い環境では skip）
from services import format_catalog  # noqa: E402

msg = format_catalog.status_message()
if msg:
    print("[skip] 公式書式カタログ:", msg)
else:
    cats = format_catalog.categories()
    assert cats, "分類が空"
    total = sum(len(format_catalog.formats_in(c)) for c in cats)
    assert total > 0, "書式が0本"
    # 自動入力書式は「重説へ入れると他書式へ波及する」ものが必ずある
    fanout = [f for c in cats for f in format_catalog.formats_in(c) if f.get("fanout_count")]
    assert fanout, "波及する書式が見つからない（レジストリの作りが変わった可能性）"
    print("[ok] 公式書式カタログ: %d分類 / %d本 / 波及型 %d本" % (len(cats), total, len(fanout)))

# 10) クロスチェック（legal-crosscheck から吸収した検閲エンジン）
import io as _io  # noqa: E402
from reportlab.pdfgen import canvas as _canvas  # noqa: E402
from reportlab.pdfbase import pdfmetrics as _pm  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont as _CID  # noqa: E402
from services import crosscheck_service, crosscheck_report_service  # noqa: E402

_pm.registerFont(_CID("HeiseiKakuGo-W5"))


def _mkpdf(lines):
    buf = _io.BytesIO()
    c = _canvas.Canvas(buf)
    c.setFont("HeiseiKakuGo-W5", 11)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.save()
    return buf.getvalue()


_base = {"所在地": "大阪市都島区東野田町二丁目", "地番": "123番4", "地積": "165.28",
         "家屋番号": "123番4", "床面積": "98.55", "所有者": "検証太郎",
         "用途地域": "商業地域", "建ぺい率": "80%", "容積率": "600%"}

# 書類が無ければ「一致」は1件も出ない（比較していないのに緑を出さない）
_none = crosscheck_service.run(_base, None, None)
assert _none.ok_count == 0, "書類が無いのに一致が出ている: %d" % _none.ok_count

# わざと食い違わせた重説・契約書を入れると検出する
_exp = _mkpdf(["重要事項説明書", "地番 123番4", "用途地域 第一種住居地域",
               "建ぺい率 60%", "容積率 600%", "売主 検証太郎"])
_con = _mkpdf(["不動産売買契約書", "地番 123番9", "売主 検証太郎",
               "契約不適合責任の通知期間 引渡しから1年", "違約金 売買代金の30%"])
_cc = crosscheck_service.run(_base, _exp, _con, seller_is_pro=True)
_ng = {r.item for r in _cc.results if r.is_ng}
for _must in ("地番", "用途地域", "指定建ぺい率"):
    assert _must in _ng, "検出できていない: %s（検出=%s）" % (_must, _ng)
assert crosscheck_service.build_admin({}).building_coverage == 0.0, "モックが混入している"
assert len(crosscheck_report_service.build(_cc)) > 3000, "報告書Excelが生成できない"
print("[ok] クロスチェック: %d項目 / 🔴%d件検出 / 報告書OK" % (len(_cc.results), _cc.ng_count))

# ---------------------------------------------------------------------------
# 災害3項目（2026-08-23 実装）。**通信せずに**判定ロジックだけを確かめる。
# 実APIを叩くテストにすると、キーが無いPCや外出先で落ちて意味が薄れる。
from services import checkbox_fill, hazard_service
from services import reinfolib_client as _rc


def _stub(features_by_layer):
    def fake(layer, lat, lon, zoom, api_key=""):
        return features_by_layer.get(layer)
    return fake


def _poly(coords, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [coords]}}


_square = [[135.0, 34.0], [135.1, 34.0], [135.1, 34.1], [135.0, 34.1], [135.0, 34.0]]
_far = [[130.0, 30.0], [130.1, 30.0], [130.1, 30.1], [130.0, 30.1], [130.0, 30.0]]

_orig_fetch, _orig_key = _rc.fetch_features, _rc.get_api_key
_rc.get_api_key = lambda: "dummy"
try:
    # 区域の中 … 浸水深ランク2 = 0.5m以上3.0m未満（公式コードリストで確認済み）
    _rc.fetch_features = _stub({
        "XKT026": [_poly(_square, {"A31a_205": 2, "A31a_202": "淀川"})],
        "XKT029": [_poly(_square, {"A33_001": 1, "A33_002": 2,
                                   "A33_003": "28", "A33_005": "住吉山手Ⅰ"})],
        "XKT028": [_poly(_square, {"A40_003": "1.0～2.0m"})],
    })
    _h = hazard_service.get_hazard_detail(34.05, 135.05)
    assert "0.5m以上3.0m未満" in _h["洪水浸水想定"]["値"], _h
    assert "淀川" in _h["洪水浸水想定"]["値"], _h
    assert _h["土砂災害"]["値"].startswith("土砂災害特別警戒区域"), _h
    assert "急傾斜地の崩壊" in _h["土砂災害"]["値"], _h
    assert "兵庫県" in _h["土砂災害"]["注意"], "兵庫県の利用制限が出ていない"
    assert "1.0～2.0m" in _h["津波"]["値"], _h

    # 区域の外 … 地物はあるが地点は含まれない → 「区域外」と言い切ってよい
    _rc.fetch_features = _stub({
        "XKT026": [_poly(_far, {"A31a_205": 2})],
        "XKT029": [_poly(_far, {"A33_001": 1, "A33_002": 1, "A33_003": "27"})],
        "XKT028": [_poly(_far, {"A40_003": "0.3～1.0m"})],
    })
    _o = hazard_service.get_hazard(34.05, 135.05)
    assert _o["洪水浸水想定"].endswith("区域外（想定最大規模）"), _o
    assert _o["土砂災害"] == "土砂災害警戒区域外", _o
    assert _o["津波"] == "津波浸水想定区域外", _o

    # 取得できない／地物が1件も無い → 空欄（＝判定不可。「区域外」と言わない）
    _rc.fetch_features = _stub({"XKT026": None, "XKT029": [], "XKT028": None})
    _u = hazard_service.get_hazard(34.05, 135.05)
    assert _u == {"洪水浸水想定": "", "土砂災害": "", "津波": ""}, _u
finally:
    _rc.fetch_features, _rc.get_api_key = _orig_fetch, _orig_key

# チェック欄の検出（□ の右に「内」「外」がある実書式の並びを再現）
_rows = {
    276: [(10, "土砂災害警戒区域"), (32, "□"), (34, "外"), (36, "・"), (37, "□"), (39, "内")],
    277: [(10, "土砂災害特別警戒区域"), (32, "□"), (34, "外"), (37, "□"), (39, "内")],
    280: [(10, "津波災害警戒区域"), (32, "□"), (34, "外"), (37, "□"), (39, "内")],
}
_cb = checkbox_fill.detect_hazard(_rows)
assert _cb == {"土砂災害警戒区域_内": "AK276", "土砂災害特別警戒区域_内": "AK277"}, _cb
# 特別警戒区域は警戒区域の中にある（土砂災害防止法9条）ので両方に■
assert checkbox_fill.marks({"土砂災害": "土砂災害特別警戒区域（急傾斜地の崩壊）"}, _cb) == {
    "AK277": "■", "AK276": "■"}
assert checkbox_fill.marks({"土砂災害": "土砂災害警戒区域（土石流）"}, _cb) == {"AK276": "■"}
# 区域外・未取得のときは書式の□をそのまま残す
assert checkbox_fill.marks({"土砂災害": "土砂災害警戒区域外"}, _cb) == {}
assert checkbox_fill.marks({"土砂災害": ""}, _cb) == {}
print("[ok] 災害3項目: 区域内/区域外/判定不可の3状態 ＋ チェック欄の自動■")

# ---------------------------------------------------------------------------
# 抵当権を土地/建物で分ける（2026-08-23）。
# 重説の権利部(乙区)は土地と建物で行が違うのに、1項目にまとめていたため
# **土地の抵当権が建物の欄に入っていた**。その再発防止。
from services import registry_service as _rs

_split = _rs._from_shared({"物件種別": "土地建物",
                           "土地": {"抵当権": "抵当権: A銀行"},
                           "建物": {"抵当権": "根抵当権: B信金"},
                           "抵当権": "有"})
assert _split["土地抵当権"] == "抵当権: A銀行", _split
assert _split["建物抵当権"] == "根抵当権: B信金", _split
# 謄本が土地だけなら、トップレベルの値は土地のものと分かる
_land_only = _rs._from_shared({"物件種別": "土地", "土地": {}, "建物": {},
                               "抵当権": "抵当権: C銀行"})
assert _land_only["土地抵当権"] == "抵当権: C銀行" and _land_only["建物抵当権"] == ""
# 土地建物の謄本で側が分からないときは**どちらにも入れない**（推測で欄を埋めない）
_ambiguous = _rs._from_shared({"物件種別": "土地建物", "土地": {}, "建物": {},
                               "抵当権": "有: D銀行"})
assert _ambiguous["土地抵当権"] == "" and _ambiguous["建物抵当権"] == "", _ambiguous

# 実書式の並び（土地の乙区 → 建物の乙区）を再現して検出を確かめる
_rows_rights = {
    90:  [(2, "土　　地")],
    98:  [(6, "権利部(乙区)"), (9, "所有権以外の権利に関する事項"), (22, "□"), (24, "地上権")],
    99:  [(22, "□"), (24, "抵当権")],
    100: [(22, "□"), (24, "根抵当権")],
    104: [(2, "建　　　　物")],
    112: [(6, "権利部(乙区)"), (9, "所有権以外の権利に関する事項"), (22, "□"), (24, "抵当権")],
    113: [(22, "□"), (24, "根抵当権")],
}
_rb = checkbox_fill.detect_rights(_rows_rights, ["V98", "AH98", "V112", "AH112"])
assert _rb["土地_抵当権"] == "V99" and _rb["土地_根抵当権"] == "V100", _rb
assert _rb["建物_抵当権"] == "V112" and _rb["建物_根抵当権"] == "V113", _rb
assert _rb["土地_詳細"] == "AH98" and _rb["建物_詳細"] == "AH112", _rb

# 土地の抵当権は土地の欄へ。建物が根抵当権なら「抵当権」には■を付けない（別の権利）
_w = checkbox_fill.marks({"土地抵当権": "抵当権: A銀行",
                          "建物抵当権": "根抵当権: B信金"}, _rb)
assert _w == {"V99": "■", "AH98": "抵当権: A銀行",
              "V113": "■", "AH112": "根抵当権: B信金"}, _w
# 値が無い側には何も書かない（書式の□をそのまま残す）
assert checkbox_fill.marks({"土地抵当権": "", "建物抵当権": ""}, _rb) == {}
print("[ok] 抵当権: 土地/建物を別の欄へ ＋ 抵当権と根抵当権の区別")

print("smoke test: all assertions passed")
