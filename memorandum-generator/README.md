# 覚書・合意書ジェネレーター（memorandum-generator）

大京商事「（★必読★）新共有フォルダ/契約・書類/覚書・同居申請等」の約170書類を分析・パターン化し、
フォーム入力から **覚書・合意書・各種申請書の Word(.docx)** を自動生成する Streamlit アプリ。port **8524**。

## 対応書類（12種）

| キー | 書類 |
|---|---|
| rent_revision | 賃料改定（現行→改定・賃料/共益費/水道代） |
| rent_reduction | 家賃値下げ・賃料減額（シンプル） |
| succession | 契約上の地位承継（甲乙丙＋新連帯保証人） |
| rep_change | 代表取締役変更に伴う連帯保証 |
| guarantor_delete | 連帯保証人削除 |
| restoration | 原状回復義務の免除（改装項目） |
| parking_change | 駐車場位置変更 |
| name_change | 名義変更（新設法人へ） |
| freeform | 汎用 覚書／合意書（本文自由入力） |
| cohabitation | 同居申請書＋同居承諾書 |
| minor_consent | 未成年者同意書 |
| use_permit | 使用許可承諾書 |

## 共通骨格

タイトル → 物件表示 → 当事者(甲/乙/丙)と原契約日 → 記 → 本文条項
→「本覚書に定めのない事項は原契約による」→ 作成通数 → 日付欄 → 署名欄(甲乙丙+連帯保証人+立会人=大京商事)

立会人は既定で **大京商事株式会社 代表取締役 鷲見文子**。物件の貸主が大京自身の場合は外す。
日付欄・押印欄は空欄で出力（印刷後に手書き・捺印運用）。

## 起動

```bash
python3 -m pip install -r requirements.txt   # 初回のみ
./起動.command          # ローカル(自分のMac、ブラウザ自動起動)
# または launchd（メインMac常時起動）: run.sh を com.shinsei.memorandum-generator で登録
```

## 構成

- `app.py` … Streamlit UI（書類種別選択＋動的フォーム）
- `docgen.py` … python-docx 文書生成エンジン（全テンプレート）
- `requirements.txt` / `起動.command` / `run.sh`

## 注意

生成物には個人情報を含み得るため、出力 .docx はコミットしない（`.gitignore`）。
