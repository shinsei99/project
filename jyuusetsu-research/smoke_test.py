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

print("smoke test: all assertions passed")
