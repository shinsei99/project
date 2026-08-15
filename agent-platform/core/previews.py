"""型の見本画像を作る

なぜ要るか:
  ヒアリングで「写真主役｜外観を大きく1枚…」と**文字だけ**で聞かれても、
  出来上がりが想像できない。紙面は見た目を選ぶものなので、見本を並べて選ばせる。

作り方:
  実際の型で1枚描く。ただし写真は**灰色の当て紙**（「外観」「室内」「間取り」と
  書いた画像）にする。実物の写真を使うと、見本に他人の物件が写ってしまう。

  1枚描くのに数秒かかるので、**作ったら残す**（.cache/previews）。
  型を作り替えたときは、そのファイルを消せば次に開いたとき作り直す。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .config import ROOT

CACHE = ROOT / ".cache" / "previews"
PLACEHOLDER = ROOT / ".cache" / "previews" / "_placeholder"

# 見本に流し込む内容。実在の物件に見えないよう、当たり障りのない値にする
SAMPLE = {
    "kicker": "〇〇県〇〇市", "catch": "暮らしが変わる、この一室。",
    "title": "〇〇マンション 3LDK", "sub": "敷金・礼金なし ／ 管理費込み",
    "price": "68,000", "unit": "円 / 月",
    "lead": "駅から徒歩8分。日当たりの良い南向きで、収納も広く取ってあります。",
    "badges": ["南向き", "駐車場あり", "ペット相談可", "宅配ボックス",
               "追焚き", "即入居可"],
    "appeals": [{"title": "駅まで徒歩8分", "text": "通勤も買い物も近い"},
                {"title": "南向きの明るさ", "text": "日中は照明いらず"},
                {"title": "収納が広い", "text": "各室にクローゼット"}],
    "spec_rows": [["間取り", "3LDK"], ["専有面積", "72.50㎡"],
                  ["建物", "鉄筋コンクリート 5階建"], ["築年", "2015年3月"],
                  ["所在地", "〇〇県〇〇市〇〇町1-2-3"], ["交通", "〇〇駅 徒歩8分"],
                  ["駐車場", "空きあり（月5,000円）"], ["ペット", "相談可"],
                  ["備考", "即入居可／更新料なし"]],
    "photos": {"hero": 1, "floorplan": 2, "rooms": [3, 4, 5, 6, 7, 8]},
    "contact": {"label": "ご見学・お問い合わせ", "tel": "00-0000-0000",
                "company": "〇〇不動産株式会社", "address": "〇〇県〇〇市〇〇町1-2-3"},
}

SIGNAGE_SAMPLE = {
    "sign_ban": {"headline": "駐輪禁止", "message": "ここに自転車・バイクを停めないでください",
                 "reason": "非常時の通行と、消防設備の使用のさまたげになります。",
                 "steps": ["警告の札を付けます", "7日間そのままなら", "撤去して保管します",
                           "1か月後に処分します"],
                 "steps_caption": "対応の流れ", "deadline_label": "撤去予定日",
                 "pictograms": ["no_bicycle", "no_motorcycle"]},
    "sign_notice": {"headline": "給水管清掃のお知らせ", "message": "当日は一時的に断水します",
                    "reason": "ご不便をおかけしますが、ご協力をお願いいたします。",
                    "notes": ["日時：9月3日（木）9:00〜15:00", "場所：全戸（共用部含む）",
                              "内容：給水管の高圧洗浄"],
                    "contact": "〇〇不動産株式会社　TEL 00-0000-0000"},
    "sign_request": {"headline": "夜間の音にご配慮を", "message": "22時以降はお静かにお願いします",
                     "notes": ["洗濯機・掃除機は22時までに", "走る音は階下によく響きます",
                               "窓とドアの開閉をお静かに"],
                     "contact": "〇〇不動産株式会社　TEL 00-0000-0000",
                     "pictograms": ["quiet"]},
    "sign_direction": {"headline": "駐車場", "sub": "PARKING", "message": "来客用駐車場はこちら",
                       "reason": "この先 30m 右手", "arrow": "right",
                       "contact": "〇〇不動産株式会社"},
    "sign_security": {"headline": "監視カメラ作動中", "message": "24時間 録画しています",
                      "reason": "共用部を撮影しています。",
                      "notes": ["不審者は警察へ通報します", "映像は警察へ提供します"],
                      "contact": "〇〇不動産株式会社　TEL 00-0000-0000"},
    "sign_holiday": {"headline": "年末年始休業のお知らせ",
                     "message": "12月28日（日）〜 1月4日（日）",
                     "reason": "ご不便をおかけしますが、よろしくお願いいたします。",
                     "notes": ["通常営業：1月5日（月）9:00〜18:00",
                               "緊急のご連絡：000-0000-0000"],
                     "contact": "〇〇不動産株式会社　TEL 00-0000-0000"},
    "sign_price": {"headline": "駐車場 月極料金", "message": "空きあり・即日ご利用いただけます",
                   "notes": ["普通車：11,000円／月", "軽自動車：9,900円／月",
                             "バイク：3,300円／月"],
                   "reason": "受付　平日 9:00〜18:00",
                   "contact": "〇〇不動産株式会社　TEL 00-0000-0000"},
    "sign_recruit": {"headline": "スタッフ募集", "message": "未経験の方も歓迎します",
                     "notes": ["職種：受付・事務", "時給：1,150円〜", "時間：9:00〜18:00",
                               "勤務：週3日〜"],
                     "contact": "00-0000-0000", "company": "〇〇不動産株式会社"},
    "sign_document": {"headline": "年末年始休業のご案内", "date": "2026年12月1日",
                      "to": "入居者各位",
                      "message": "拝啓　時下ますますご清栄のこととお慶び申し上げます。\n"
                                 "　さて、誠に勝手ながら下記の期間を休業とさせていただきます。",
                      "reason": "敬具",
                      "notes": ["休業期間：12月28日〜1月4日", "通常営業：1月5日 9:00〜"],
                      "contact": "〇〇不動産株式会社　〇〇市〇〇町1-2-3　TEL 00-0000-0000"},
}

# 当て紙に書く文字。番号順に割り当てる
PLACEHOLDER_LABELS = ["外観", "間取り図", "居室", "キッチン", "浴室", "洗面",
                      "バルコニー", "収納"]


def _placeholder_photos() -> List[str]:
    """灰色の当て紙。実物の写真を見本に使わないため。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return []
    PLACEHOLDER.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, label in enumerate(PLACEHOLDER_LABELS, start=1):
        path = PLACEHOLDER / ("ph_%02d.png" % index)
        if not path.exists():
            # 間取り図だけ白地。図面は切らずに置かれることを見本でも示すため
            white = label == "間取り図"
            img = Image.new("RGB", (1200, 800), (255, 255, 255) if white
                            else (208, 213, 219))
            draw = ImageDraw.Draw(img)
            if white:
                draw.rectangle((220, 120, 980, 680), outline=(90, 96, 104), width=6)
                draw.line((600, 120, 600, 680), fill=(90, 96, 104), width=5)
                draw.line((220, 430, 600, 430), fill=(90, 96, 104), width=5)
            draw.text((40, 36), label, fill=(90, 96, 104))
            img.save(path)
        paths.append(str(path))
    return paths


def flyer_preview(template_id: str, force: bool = False) -> Optional[str]:
    """チラシの型の見本。作ってあればそれを返す。"""
    out = CACHE / ("%s.png" % template_id)
    if out.exists() and not force:
        return str(out)
    try:
        import tools
        from core import blocks, layouts

        photos = _placeholder_photos()
        layout = layouts.build(template_id, SAMPLE)
        if not layout:
            return None
        paper = layouts.paper_of(template_id)
        html = blocks.render_page(layout, photos=photos, accent="#c1272d",
                                  ink="#1b2a4a", padding="0mm 12mm", paper=paper)
        html = tools.flyer.fit_to_page(html, paper=paper)
        CACHE.mkdir(parents=True, exist_ok=True)
        tools.flyer.render(html, out, fmt="png", paper=paper, png_scale=1)
        _shrink(out)
        return str(out)
    except Exception:
        return None


def signage_preview(template_id: str, force: bool = False) -> Optional[str]:
    out = CACHE / ("%s.png" % template_id)
    if out.exists() and not force:
        return str(out)
    try:
        import tools
        from agents.poster import _build_html

        data = dict(SIGNAGE_SAMPLE.get(template_id) or {})
        if not data:
            return None
        data.setdefault("sub", "")
        for key in ("notes", "steps", "pictograms"):
            data.setdefault(key, [])
        for key in ("reason", "steps_caption", "deadline_label", "contact"):
            data.setdefault(key, "")
        html = _build_html(data, None, template_id, "A4")
        CACHE.mkdir(parents=True, exist_ok=True)
        tools.flyer.render(html, out, fmt="png", paper="A4", png_scale=1)
        _shrink(out)
        return str(out)
    except Exception:
        return None


def _shrink(path, width: int = 420) -> None:
    """見本は一覧に並べるだけなので小さくする（表示が速くなる）。"""
    try:
        from PIL import Image

        with Image.open(path) as img:
            if img.width <= width:
                return
            ratio = width / float(img.width)
            img.resize((width, int(img.height * ratio)), Image.LANCZOS).save(path)
    except Exception:
        pass


def preview_for(template_id: str) -> Optional[str]:
    """型の種類を問わず見本を返す。"""
    if str(template_id).startswith("sign_"):
        return signage_preview(template_id)
    return flyer_preview(template_id)


def clear() -> int:
    """見本を作り直させる（型を直したとき用）。"""
    if not CACHE.exists():
        return 0
    count = 0
    for path in CACHE.glob("*.png"):
        path.unlink()
        count += 1
    return count
