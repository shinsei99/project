"""物件の初期データ。編集内容は data/overrides.json に保存され、こちらより優先される。

写真はDropboxの撮影フォルダ、間取り図はGoogleドライブの案件フォルダから読む。
どちらも同期フォルダなので、Mac側にファイルが降りていないと一覧に出ないことがある。
"""
from __future__ import annotations

from pathlib import Path

DROPBOX = Path("/Users/apple/Library/CloudStorage/Dropbox-個人/写真フォルダ")
GDRIVE = Path(
    "/Users/apple/Library/CloudStorage/GoogleDrive-daikyocorp.s@gmail.com/マイドライブ/取引案件別"
)
# 案件フォルダの 賃貸資料.xls から取り出した素材（maisoku.py で作る）。
# 写真候補にはしない。物件ごとに "madori" で1枚を名指ししたときだけ使う。
MAISOKU = Path(__file__).parent / "data" / "maisoku"

COMMON_TEL = "06-6935-7267"

COMPANY = "新誠プロパティマネジメント株式会社"
ADDRESS = "〒531-0076 大阪市北区大淀中3-1-15"
# 宅建業免許番号。更新のたびに変わるので、ここ1か所だけを直せば紙もWebも揃うようにしてある。
# ロゴ画像（assets/spm_logo_white_name.png）には番号を入れていない。番号入りの
# spm_logo_white.png は(1)第58258号のままなので、広告物には使わないこと。
LICENSE = "大阪府知事(2)第61884号"

PROPERTIES: dict[str, dict] = {
    "秋津11（ログハウス）": {
        "photo_dirs": ["2026.6.6秋津11"],
        "case_dir": "加東市秋津11",
        "kicker": "兵庫県加東市秋津 別荘地",
        "catch": "大阪から約1時間。\n緑に包まれたログハウス。",
        "title": "加東市秋津 ログハウス 3LDK",
        "rent": "59,000",
        "rent_note": "敷金・礼金なし ／ 管理費なし",
        "tags": ["ログハウス", "ウッドデッキ", "眺望良好",
                 "駐車場1台無料", "バイク置場あり", "VR内覧できます"],
        # 自社の theta-viewer（THETA SPACE）。物件ページから二段目として開く。
        "vr_url": "https://daikyocorp.co.jp/vr/#/property/mrh76zhs7317p",
        "body": "木の香りで癒される希少なログハウス物件。ウッドデッキから森が見渡せて、"
                "地階を入れて3層。週末だけの別荘としても、そのまま住むこともできます。",
        "specs": [
            ("間取り", "3LDK"),
            ("専有面積", "62.73㎡"),
            ("建物", "木造ログハウス 2階建（地下1階付）"),
            ("築年", "1984年1月"),
            ("所在地", "兵庫県加東市秋津"),
            ("交通", "中国自動車道 東条IC より車15分"),
            ("駐車場", "1台無料（ハイルーフ可）"),
        ],
    },
    "秋津9": {
        "photo_dirs": ["2024.5.5秋津9"],
        "case_dir": "加東市秋津9",
        # 案件フォルダに間取り図のファイルは無い。賃貸資料.xls の中から取り出したもの。
        "madori": "加東市秋津9/00.jpg",
        "kicker": "兵庫県加東市秋津 別荘地",
        "catch": "大阪から約1時間。\n畳のある静かな家。",
        "title": "加東市秋津戸建てIX",
        "rent": "52,000",
        "rent_note": "敷金・礼金なし ／ 管理費なし",
        "tags": ["リフォーム済", "和室", "駐車場あり", "静かな環境"],
        "body": "敷地約２４０坪、日当たりよく家庭菜園やキャンプにも最適です。"
                "畳が１２畳あり、落ち着いた雰囲気の戸建てです。駐車場１〜２台駐車可能です。",
        "specs": [
            # 間取り図から起こした（和室6帖＋和室6帖＋DK、縁側つき）
            ("間取り", "2DK"),
            ("所在地", "兵庫県加東市秋津"),
            ("交通", "中国自動車道 東条IC より車15分"),
            ("敷地面積", "約240坪"),
            ("駐車場", "1〜2台"),
        ],
    },
    "秋津2": {
        "photo_dirs": ["2024.11.3秋津2", "2021.11.27秋津2"],
        "case_dir": "加東市秋津2",
        "kicker": "兵庫県加東市秋津 別荘地",
        "catch": "大阪から約1時間。\n吹き抜けのある家。",
        "title": "加東市秋津戸建てII",
        "rent": "49,000",
        "rent_note": "敷金・礼金なし ／ 管理費なし",
        "tags": ["吹き抜け", "庭あり", "駐車場あり", "静かな環境", "VR内覧できます"],
        # 自社の theta-viewer（THETA SPACE）
        "vr_url": "https://daikyocorp.co.jp/vr/#/property/mrh1vh3sdnvzz",
        "body": "吹き抜けのある木造の一戸建てです。庭と駐車場があり、"
                "週末だけの別荘としても、そのまま住むこともできます。",
        # ホームズ掲載（bid=1328470000039）の内容に合わせた
        "specs": [
            ("間取り", "2LDK"),
            ("専有面積", "54.66㎡"),
            ("建物", "木造"),
            ("築年", "1980年3月"),
            ("所在地", "兵庫県加東市秋津"),
            ("交通", "中国自動車道 東条IC より車15分"),
            ("駐車場", "あり（庭あり）"),
            ("入居可能時期", "相談（9月以降）"),
        ],
    },
    "上三草": {
        "photo_dirs": ["2025.12.28上三草"],
        "case_dir": "加東市上三草",
        "kicker": "兵庫県加東市上三草 やしろ台",
        "catch": "大阪から約1時間。\n家具付きで、すぐ暮らせる。",
        "title": "加東市上三草戸建て",
        "rent": "62,000",
        "rent_note": "敷金・礼金なし ／ 管理費なし",
        "tags": ["電動シャッター付き車庫・倉庫", "家具付き", "広いLDK"],
        "body": "約１９０平米、広々３LDK。大人数のご家族でもゆったり過ごせます。"
                "一部家具付き。電動シャッター付き車庫・倉庫有り。庭も広々家庭菜園も楽しめます。",
        # 案件フォルダの 賃貸資料.xls（賃貸不動産案内書）から
        "specs": [
            ("間取り", "3LDK"),
            ("建物面積", "190.98㎡"),
            ("建物", "木造"),
            ("築年", "2003年（平成15年）"),
            ("所在地", "兵庫県加東市上三草"),
            ("交通", "中国自動車道 東条IC より車20分"),
            ("駐車場", "電動シャッター付き車庫・倉庫有り"),
            ("設備", "電気・プロパンガス・上水道・浄化槽"),
            ("入居可能時期", "相談"),
        ],
    },
}

PHOTO_EXT = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG", ".cr2", ".CR2")

# 案件フォルダには入居申込者の身分証や申込書のスキャンが同居している。
# 実際に自動選択でサイトへ載りかけたので、名前に以下を含むものは候補から必ず外す。
DENY = (
    "身分証", "免許", "申込", "契約", "保証", "謄本", "名簿", "請求", "領収",
    "住民", "印鑑", "通知", "評価", "公図", "測量", "台帳", "重説", "重要事項",
    "本人", "誓約", "委託", "納税", "課税", "口座", "通帳",
)


def _allowed(p: Path) -> bool:
    return not any(k in str(p) for k in DENY)


def list_photos(prop: dict) -> list[Path]:
    """写真候補は Dropbox の撮影フォルダだけから拾う。

    案件フォルダ（Googleドライブ）は個人情報のスキャンが混ざるので写真ソースにしない。
    そこから取るのは list_madori の間取り図だけ。
    """
    out: list[Path] = []
    for name in prop.get("photo_dirs", []):
        d = DROPBOX / name
        if d.is_dir():
            out += [p for p in sorted(d.iterdir()) if p.suffix in PHOTO_EXT and _allowed(p)]
    out.sort(key=lambda p: (p.suffix.lower() in (".cr2",), p.name))
    return out


def list_madori(prop: dict) -> list[Path]:
    """間取り図だけは案件フォルダから拾う。ファイル名に「間取」を含むものに限定する。

    案件フォルダに間取り図のファイルが無くても、賃貸資料.xls の中に入っていることがある。
    その場合は maisoku.py で取り出したものを "madori" で名指しする。
    """
    named = prop.get("madori")
    if named:
        p = MAISOKU / named
        return [p] if p.exists() else []

    case = GDRIVE / prop.get("case_dir", "")
    if not case.is_dir():
        return []
    return [
        p for p in sorted(case.rglob("*"))
        if p.suffix in PHOTO_EXT and "間取" in p.name and _allowed(p)
    ]

# 賃貸中の物件。実績として一覧の下に並べる。
# 賃料・間取りは確定情報が手元に無いので出さない（写真と所在だけにする）。
RENTED = [
    # 所有物件台帳（マイ Mac mini/Desktop/ルーティーン/所有物件台帳.xlsx）の
    # 「利用状況＝賃貸中」かつ 加東・三木・三田 の11件。名称は台帳の識別名称。
    # 写真は全て外観。並びは 加東秋津 → 加東黒谷 → 三木 → 三田。
    # base: "db"=Dropbox写真フォルダ / "gd"=Googleドライブ取引案件別
    {"title": "グリーンログ加東",  "base": "gd", "dir": "加東市秋津1",       "photo": "写真2/DSC07534.jpg"},
    {"title": "グリーンログTWIN",  "base": "db", "dir": "2023.3.5秋津4",     "photo": "IMG_4308.JPG"},
    {"title": "グリーンログ秋津",  "base": "db", "dir": "2022.2.8秋津7",     "photo": "外観1.JPG"},
    {"title": "カナディアンログ秋津", "base": "db", "dir": "2022.5.22加東秋津5", "photo": "外観.JPG"},
    # 秋津戸建て６の外観は撮影フォルダに無かったのでカメラアップロードから案件フォルダへコピー済み。
    {"title": "秋津戸建てVI",      "base": "gd", "dir": "加東市秋津6",       "photo": "外観.JPG"},
    {"title": "秋津戸建てX",    "base": "gd", "dir": "加東市秋津10",      "photo": "外観.JPG"},
    {"title": "黒谷戸建て",        "base": "gd", "dir": "加東市黒谷",        "photo": "外観.JPG"},
    {"title": "吉川町戸建て",      "base": "db", "dir": "2021.8.31三木吉川",  "photo": "11.JPG"},
    {"title": "西相野戸建て",      "base": "gd", "dir": "三田西相野",         "photo": "写真2/外観1.JPG"},
    {"title": "大川瀬戸建て",      "base": "db", "dir": "2024.10.14大川瀬3",  "photo": "1.JPG"},
    {"title": "グリーンログ大川瀬", "base": "gd", "dir": "三田大川瀬",        "photo": "写真/DSC09653.jpg"},
    # キャンプサイト（賃貸資料.xls は種目=土地・賃料39,000円・敷地210㎡）。
    # 建物の外観ではなくサイト全体が写った1枚を選んでいる。
    {"title": "グリーンガーデン大川瀬", "base": "gd", "dir": "三田大川瀬2",       "photo": "写真/1.JPG"},
]


# レンタルスペース（貸切キャンプ場）。予約はスペースマーケットの掲載ページへ飛ばす。
# 賃貸ではないので賃料は出さず、ぼかしもかけない（募集用の写真をそのまま使う）。
RENTALS = [
    {"title": "グリーンガーデン加東",
     "note": "ログハウス付き ／ 1日1組限定",
     "url": "https://www.spacemarket.com/spaces/greengarden-kato/?promotion_link=true",
     "base": "db", "dir": "2022.4.30加東キャンプ", "photo": "BBQエリア1.JPG"},
    {"title": "グリーンガーデン秋津",
     "note": "シャワー完備建物付き ／ 1日1組限定",
     "url": "https://www.spacemarket.com/spaces/greengarden-akitsu/?promotion_link=true",
     "base": "db", "dir": "2024.3.19グリーンガーデン秋津", "photo": "IMG_5244.JPG"},
]


def rented_photo(item: dict) -> Path | None:
    root = GDRIVE if item.get("base") == "gd" else DROPBOX
    q = root / item["dir"] / item["photo"]
    return q if q.exists() else None
