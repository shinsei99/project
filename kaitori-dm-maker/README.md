# 買取DMジェネレーター（kaitori-dm-maker）

所有者台帳から、未活用地・空き家の**買取DM（Word）を差し込み量産**するツール。謄本PDFを読み取って台帳に行を追加することもできる。

- 分類：ツール
- port：8526
- 技術：Streamlit + python-docx + pandas（+ 謄本読取は `baikai-generator` の `registry_parser` を再利用）

## 起動

```bash
cd kaitori-dm-maker
python3 -m pip install -r requirements.txt   # 初回のみ
python3 -m streamlit run app.py --server.port 8526
```

## 機能

- **差出人**：サイドバーで追加・編集・削除（`senders.json` に保存。無い場合はコード内 `DEFAULT_SENDERS` から生成）。DM作成に使う差出人を選択。送付日を指定。文面は固定。
- **台帳更新**
  - 台帳（.xls/.xlsx）をアップロードして読み込み
  - **謄本PDFを複数（5件程度）アップロード → AI読取 → 台帳に行追加**
    - 「1ファイル＝1物件（まとめて追加）」/「全ファイル＝1物件に統合」を選択
    - 市/所在の分離・地目/地積・建物種類/構造/床面積・登記名義人/現住所を自動抽出
  - 更新した台帳を体裁付きxlsxでダウンロード
- **DM生成**：台帳を絞り込み（現住所なし除外・宛先重複集約・個人/法人・抵当権除外）→ 一覧のチェックで送付先を選択（既定は全選択）→ 結合docx（1通1ページ）または名義人ごと個別docx（ZIP）で出力。

## 台帳フォーマット（確定・15列／1物件1行）

`NO / 市 / 所在 / 地番 / 地目 / 地積・㎡ / 建物種類 / 建物構造 / 床面積・㎡ / 登記名義人 / 持分 / 郵便番号 / 現住所 / 電話番号 / 備考`

土地列・建物列を横並びに持ち、更地は建物列が空欄。

## 依存

- 謄本の読み取りはローカルの `claude` CLI を使う（`registry_parser`）。実行パスは `shutil.which("claude")` で自動解決。
- 謄本パーサは同リポジトリ内の `../baikai-generator/services/registry_parser.py` を参照する（相対パス）。

## 備考

- `senders.json`（編集後の差出人）は個人情報を含むため `.gitignore` 済み。メインPCへはコード内 `DEFAULT_SENDERS` が既定として引き継がれ、必要に応じてアプリ上で編集する。
