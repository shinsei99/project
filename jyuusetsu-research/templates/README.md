# templates/ — このフォルダに置くもの（2026-08-23 整理）

**書式の本体はここには無い。** 重説・契約書は Dropbox の
`契約・書類/書類雛形/`（全宅連の公式書式200本）を `services/format_catalog.py` が読む。
書式を増やすときも、このフォルダではなく **Dropbox に置いて `scan_formats.py` を回す**。

いま置いてあるのは、アプリが自前で作る2本だけ。

| ファイル | 用途 | 誰が使うか |
|---|---|---|
| `jyuusetsu_template.xlsx` | 汎用ドラフト（調査結果を項目ごとに並べたExcel） | `app.py` / `smoke_test.py`。起動時に自動生成される |
| `law_check_template.xlsx` | クロスチェック報告書のひな形 | `services/crosscheck_report_service.py`。`generate_crosscheck_template.py` で作る |

どちらも**他社データを含まない**ので、別PCで用意するものは無い。

## 以前ここにあった4本について（2026-08-23 削除）

`rental_building_template.xlsx` / `sale_landbuilding_template.xlsx` /
`sale_mansion_contract_template.xlsx` / `sale_mansion_jyuusetsu_template.xlsx` の4本は、
**白紙ではなく他社の実案件が記入されたファイル**だった（貸主・借主・売主の氏名入り）。

それらを読んでいた `services/format_export_service.py` が
**repo のどこからも import されていない**ことを確認したうえで、ファイルごと削除した。
現在の出力経路（`format_catalog.py` → 公式書式200本）には影響しない。
経緯とセル座標のマッピング例は `../README.md` に残してある。
