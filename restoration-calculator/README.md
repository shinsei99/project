# 退去時 原状回復費用 自動精算システム

賃貸退去時の「原状回復費用精算」を効率化・透明化する Streamlit アプリ。
リフォーム業者等の **業者見積書（Excel/CSV）** をアップロードすると、工事明細と金額を
自動で読み込み、国土交通省「原状回復をめぐるトラブルとガイドライン」に基づいて
**入居者負担額 / オーナー負担額** を1円単位で按分計算し、契約者提示用の
**退去精算書（Excel）** を自動生成します。

## 特徴

- **スマートExcel解析**: フォーマットが不統一な業者見積でも、「工事名列」「金額列」を
  キーワード＋数値ヒューリスティクスで自動判定。合計行・空欄行は自動除外。
- **部材自動判別**: クロス／CF／クリーニング／畳などを工事名から自動マッピング。
- **ガイドライン準拠の償却計算**: クロス・CF等は6年で直線償却、畳・襖・クリーニングは
  経過年数を考慮しない。経年劣化（通常損耗）は入居者負担0円。
- **有料API不使用**: pandas / openpyxl のみ。完全ローカル動作。

## セットアップ

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 精算書テンプレートを生成（初回のみ）
.venv/bin/python templates/generate_template.py
```

## 起動

```bash
.venv/bin/streamlit run app.py --server.port 8508
```

→ http://localhost:8508

## 使い方

1. 基本情報（賃借人・物件・入居日・退去日・敷金）を入力
2. 業者見積Excelをアップロード →「解析」で明細を自動展開
3. 部材種別・過失の有無（故意過失／経年劣化）を必要に応じて微調整
4. 「按分を計算」→ 負担額・円グラフを確認
5. 「退去精算書(.xlsx)」をダウンロード

## 構成

```
restoration-calculator/
├── app.py                          # Streamlit UI
├── services/
│   ├── excel_parser.py             # 業者見積の自動解析（品名・金額抽出）
│   ├── depreciation_engine.py      # 減価償却・按分計算
│   └── excel_export_service.py     # openpyxl による精算書出力
├── models/
│   └── restoration_data.py         # RestorationData / LineItem データ構造
└── templates/
    ├── generate_template.py        # テンプレート生成スクリプト
    └── seisan_template.xlsx        # 退去精算書テンプレート
```

## 注意

本ツールの計算はガイドラインの一般的な考え方に基づく目安です。実際の精算は
個別の契約条件・特約・物件状況により異なります。最終判断は専門家にご確認ください。
