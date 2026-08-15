"""加東の物件ページを書き出す。写真の選択をここに置いてある。

    python3 build_kato.py     → site/ に出力（index.html をブラウザで開く）

写真は必ずここで明示的に選ぶ。自動選択にすると案件フォルダの身分証・申込書が
混ざる（実際に起きかけた）。詳しくは README.md を参照。
"""
import build_site
from properties import DROPBOX as D

# 見せる順。1枚目が一覧のサムネイルとギャラリーの先頭になる。
# ポータルは間取り図が先頭のことが多いが、QRから来た人は「どんな家か」を先に見たいので、
# 一番いいカットを頭に置いている。
SELECTION = {
    "秋津11（ログハウス）": [
        D / "2026.6.6秋津11" / n for n in
        # LDK → 外観 → デッキ → ロフト → 和室 → 水まわり
        ["IMG_6056.JPG", "IMG_6051.JPG", "IMG_6055.JPG", "IMG_6057.JPG", "IMG_6062.JPG",
         "IMG_6060.JPG", "IMG_6063.JPG", "IMG_6059.JPG", "IMG_6058.JPG", "IMG_6061.JPG"]
    ],
    "秋津9": [
        D / "2024.5.5秋津9" / n for n in
        ["和室1.JPG", "外観.JPG", "洋室1.JPG", "和室2.JPG", "和室3.JPG", "和室4.JPG",
         "洗面室.JPG", "浴室.JPG", "駐車場.JPG"]
    ],
    # 秋津2は2回の撮影にまたがる（2024年＝吹き抜け中心／2021年＝水まわり中心）
    "秋津2": [
        D / "2024.11.3秋津2" / "4.JPG",
        D / "2024.11.3秋津2" / "外観.JPG",
        D / "2024.11.3秋津2" / "5.JPG",
        D / "2024.11.3秋津2" / "1.JPG",
        D / "2021.11.27秋津2" / "3.JPG",
        D / "2021.11.27秋津2" / "7.JPG",
        D / "2021.11.27秋津2" / "4.JPG",
        D / "2021.11.27秋津2" / "5.JPG",
        D / "2021.11.27秋津2" / "6.JPG",
        D / "2024.11.3秋津2" / "駐車場.JPG",
    ],
    "上三草": [
        D / "2025.12.28上三草" / n for n in
        ["リビング1.JPG", "外観1.JPG", "キッチン.JPG", "リビング3.JPG", "和室1.JPG",
         "和室2.JPG", "2F洋室1.JPG", "洗面.JPG", "浴室.JPG", "車庫.JPG"]
    ],
}


def main() -> None:
    missing = [str(p) for ps in SELECTION.values() for p in ps if not p.exists()]
    if missing:
        print("見つからない写真があります（同期待ちかも）:")
        for m in missing:
            print("  ", m)
        return
    out = build_site.build({k: [str(p) for p in v] for k, v in SELECTION.items()})
    print("書き出しました:", out)
    print("  open", out / "index.html")


if __name__ == "__main__":
    main()
