# ⚖️ 売買契約・重説・謄本 4点連動クロスチェックシステム

不動産売買実務で最も重い **重要事項説明書（35条）** と **売買契約書（37条）** の入力ページに特化し、手入力起因の齟齬・法律上の矛盾・建築基準法／都市計画法の違反リスクを自動検知するStreamlitアプリ。

システムが自動取得する **🌐行政の正解（国交省API）** と **📄公式ファクト（登記簿謄本）** を基準に、人間が作成した **📝重説** **🛒契約書** との間で **4者間クロスチェック** を行い、エラー箇所を赤字で可視化した **検閲報告書（Excel）** を出力します。

## 検閲ロジック（3レイヤー）

| レイヤー | 内容 |
|---|---|
| ① 入力齟齬 | 地番・家屋番号・地積・床面積の完全一致、所有者名義 vs 売主、契約日 vs 説明日 |
| ② 宅建業法 | 契約不適合責任の通知期間（40条・2年未満制限の禁止）、違約金の20%制限（38条）、反社条項、手付倍返し |
| ③ 建築基準法 | 用途地域・建ぺい率・容積率の行政データ突合、セットバックの敷地算入バグ検算 |

## セットアップ

```bash
cd legal-crosscheck
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python templates/generate_template.py   # Excelテンプレート生成
```

## 起動

```bash
.venv/bin/streamlit run app.py --server.port 8510
# → http://localhost:8510
```

## API キー（任意）

行政データ（用途地域・建ぺい率・容積率）は国交省「不動産情報ライブラリ」APIから取得します。
**未設定でもモックデータで動作します。** 実運用ではキーを設定してください。

- `.streamlit/secrets.toml.example` を `secrets.toml` にコピーしてキーを記入
- または環境変数 `REINFOLIB_API_KEY` を設定

住所→緯度経度は国土地理院API（キー不要）を使用。**有料API（Google Maps / OpenAI等）は不使用。**

## 構成

```
legal-crosscheck/
├── app.py                              # Streamlit UI（赤字アラート画面）
├── models/legal_check_data.py          # LegalCrossCheckData ほかデータ構造
├── services/
│   ├── geo_service.py                  # 国土地理院 住所→緯度経度
│   ├── admin_research_service.py       # 国交省API 用途地域等（モックfallback）
│   ├── registry_parser.py              # 謄本PDF解析（pdfplumber+regex）
│   ├── document_parser.py              # 重説・契約書PDFの正規表現抽出
│   ├── law_validator.py                # 3レイヤー検閲エンジン
│   └── excel_export_service.py         # 報告書Excel出力（🔴行ハイライト）
└── templates/
    ├── generate_template.py            # テンプレート生成スクリプト
    └── law_check_template.xlsx         # 報告書テンプレート（生成物）
```
