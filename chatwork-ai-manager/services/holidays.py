"""会社の休業日（年間休暇スケジュール）を読む。

オーナー管理の Excel「年間休暇スケジュール<年>.xlsx」が正典。
1シート＝1か月のカレンダーで、**オレンジ色に塗られたマスがその日の休み**。

読み方（実物を見て確かめた形・2026-08-21）:
  - 日付の数字は B/D/F/H/J/L/N 列（日〜土）にあり、行は 5,7,9,… と1行おき
  - **色はその1つ下の行の同じ列**に塗られている（日付マスが2行1組のため）
  - 色は「テーマ色5（アクセント2＝オレンジ）」。RGBでは入っていない
  - 前月・翌月の日も並ぶので、「1から始まる連続した並び」だけをその月とみなす

元ファイルは Google Drive（CloudStorage）上にあり、**launchd の常時起動プロセスからは
読めないことがある**（`/bin/bash` にフルディスクアクセスが要る）。そこで読めたときに
DB へ写しておき、読めないときは写しを使う。＝ 1年分は一度読めれば以後ずっと効く。
"""
import datetime
import os

from db.connection import get_conn, query
from services import settings

DAY_COLS = ("B", "D", "F", "H", "J", "L", "N")
ORANGE_THEMES = {5}          # テーマ5＝アクセント2（Office既定でオレンジ）
ORANGE_RGBS = {"FFED7D31", "FFFFC000", "FFF79646", "FFFFA500", "FFFF9900", "FFE36C0A"}


def schedule_path() -> str:
    return settings.get_setting("holiday_schedule_path", "") or ""


def _is_orange(cell) -> bool:
    f = cell.fill
    if not f or f.fill_type != "solid":
        return False
    c = f.start_color
    theme = getattr(c, "theme", None)
    if isinstance(theme, int) and theme in ORANGE_THEMES:
        return True
    rgb = getattr(c, "rgb", None)
    return isinstance(rgb, str) and rgb.upper() in ORANGE_RGBS


def _month_days(ws):
    """(日, 列, 行) を「その月の1日〜末日」だけ順に返す。前月・翌月の分は捨てる。"""
    # 曜日の見出し行（日 月 火 …）より上は見ない。
    # ★ここを見ないと、見出し上の「月」の数字（1月シートの H2=1）を「1日」と誤認して
    #   そこから月が始まったことにしてしまう。2026-08-21 に実際に1月が0件になった。
    head = 0
    for r in range(1, ws.max_row + 1):
        if str(ws[f"{DAY_COLS[0]}{r}"].value or "").strip() in ("日", "Sun", "SUN"):
            head = r
            break
    seq = []
    for r in range(head + 1, ws.max_row + 1):
        for col in DAY_COLS:
            v = ws[f"{col}{r}"].value
            if isinstance(v, int) and 1 <= v <= 31:
                seq.append((v, col, r))
    out, started, prev = [], False, None
    for v, col, r in seq:
        if not started:
            if v != 1:
                continue          # 前月の日
            started, prev = True, 0
        if v != prev + 1:
            break                 # 翌月の1に戻った＝ここで終わり
        out.append((v, col, r))
        prev = v
    return out


def parse(path: str = None) -> dict:
    """{'YYYY-MM-DD': '休み'} を返す。ファイルが読めなければ例外。"""
    from openpyxl import load_workbook
    path = path or schedule_path()
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"休暇スケジュールが見つかりません: {path}")
    wb = load_workbook(path)
    found = {}
    for ws in wb.worksheets:
        name = str(ws.title)
        if not name.endswith("月"):
            continue
        month = int(name[:-1])
        year = ws["B2"].value
        if not isinstance(year, int):
            year = _year_from_name(path)
        for day, col, r in _month_days(ws):
            # 色は「日付の1つ下の行」に付く。念のため日付セル自身も見る。
            if _is_orange(ws[f"{col}{r + 1}"]) or _is_orange(ws[f"{col}{r}"]):
                try:
                    found[datetime.date(year, month, day).isoformat()] = "休み"
                except ValueError:
                    pass
    return found


def _year_from_name(path: str) -> int:
    import re
    m = re.search(r"(20\d{2})", os.path.basename(path))
    return int(m.group(1)) if m else datetime.date.today().year


def refresh(path: str = None) -> dict:
    """スケジュールを読み直して DB に写す。"""
    try:
        found = parse(path)
    except Exception as e:
        return {"count": 0, "error": f"{type(e).__name__}: {e}"}
    years = sorted({d[:4] for d in found})
    src = os.path.basename(path or schedule_path())
    with get_conn() as conn:
        for y in years:               # その年ぶんを入れ替える（消えた休みも反映する）
            conn.execute("DELETE FROM holidays WHERE holiday_date LIKE ?", (f"{y}-%",))
        for d, note in sorted(found.items()):
            conn.execute("INSERT OR REPLACE INTO holidays (holiday_date, note, source) "
                         "VALUES (?, ?, ?)", (d, note, src))
    settings.set_state("holidays_synced_at", datetime.datetime.now().isoformat(timespec="seconds"))
    return {"count": len(found), "error": None, "years": years}


def is_holiday(date_str: str) -> bool:
    """休業日か。DB の写しを見る（その年が未取り込みなら一度だけ読みに行く）。"""
    if query("SELECT 1 FROM holidays WHERE holiday_date=?", (date_str,)):
        return True
    year = date_str[:4]
    if not query("SELECT 1 FROM holidays WHERE holiday_date LIKE ? LIMIT 1", (f"{year}-%",)):
        if refresh().get("count"):
            return bool(query("SELECT 1 FROM holidays WHERE holiday_date=?", (date_str,)))
    return False


def list_for_month(year: int, month: int):
    return [r["holiday_date"] for r in query(
        "SELECT holiday_date FROM holidays WHERE holiday_date LIKE ? ORDER BY holiday_date",
        (f"{year}-{month:02d}-%",))]


def count() -> int:
    r = query("SELECT COUNT(*) AS n FROM holidays")
    return r[0]["n"] if r else 0
