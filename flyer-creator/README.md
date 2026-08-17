# チラシクリエーター（port 8529）

旧称: 加東 貸家チラシメーカー / フォルダ名 kato-flyer（2026-08-15 改称）

加東市の貸家（秋津11・秋津9・秋津2・上三草）について、
**屋外看板のホルダーに入れるA4チラシ**と、**看板QRの飛び先になる物件サイト**を、
同じデータから出す。

```bash
./run.sh          # http://127.0.0.1:8529
```

- `flyer.py` … A4（300dpi）を1枚描く。看板と同じ橙×濃紺
- `build_site.py` … 物件サイトを `site/` に書き出す（スマホ縦持ち前提）
- `properties.py` … 物件データと素材の場所
- `maisoku.py` … 案件フォルダの `賃貸資料.xls` から写真・間取り図を取り出す（`data/maisoku/`）
- `contact.py` … 問い合わせページと受け口の `send.php`（会社サイトの mailform とは別系統）
- `publish.py` … `site/` をサーバーへ上げる（差分のみ。`--all` で全部）
- `data/overrides.json` … アプリ上で編集した内容（gitignore対象の想定）

紙とWebが同じ `properties.py` を読むので、片方を直せば両方に反映される。

## ⚠️ 写真の扱い（事故が起きかけた箇所）

**サイトに載せる写真は、必ず人が選んだものだけにすること。**

2026-08-08、`build_site.build()` が「案件フォルダから先頭10枚を自動選択」していたため、
`加東市秋津2/賃貸資料2/` に同居していた**入居申込者の運転免許証（顔写真・氏名・生年月日・
本籍・免許証番号）と記入済みの賃貸保証委託申込書**が、公開サイトの生成物に入った。
公開前に気づいて破棄したので流出はしていない。

対策として以下を入れてある。**戻さないこと。**

1. `properties.list_photos()` は **Dropboxの撮影フォルダだけ**を見る。
   Googleドライブの案件フォルダは写真ソースにしない（間取り図だけ `list_madori()` で拾う）
2. `DENY`（身分証・免許・申込・契約・保証・謄本…）に当たる名前は候補から外す
3. `build_site.build()` は**明示的に選ばれた写真がない物件を飛ばす**。自動選択はしない

## 公開について

まだ公開していない。公開するなら `shinsei99/project` の `gh-pages` に `kato/` として置く
（`https://shinsei99.github.io/project/kato/`）。

**公開前に必ず `site/img/` の中身を一覧で目視すること。** リポジトリは公開されている。

## 関連

- 看板ラフ・カラー比較 … `~/Downloads/看板サンプル/`（元は `~/design-assets/rough/`）
- 撮影写真 … `~/Library/CloudStorage/Dropbox-個人/写真フォルダ/`（CR2はsipsで自動変換）

## 運用メモ（ルート CLAUDE.md から移動・2026-08-17）

> 元の見出し: 「チラシクリエーター（flyer-creator）補足 ※ツール・port 8529」
> **他PCと共有される情報。** ここを直せば2台で同じ内容になる。

- 旧称「加東 貸家チラシメーカー」・旧フォルダ名 `kato-flyer`（**2026-08-15 に改称**）。加東市秋津の貸家の客付け一式（A4チラシ＋物件サイト＋看板の元データ）。紙とWebが同じ `properties.py` を読むので、片方を直せば両方に反映される。
- **紙面の型10種・配色9種は `../agent-platform`（マルチプロダクション）のエンジンを借りている。コピーしていない。** 呼び方は **agent-platform の `.venv/bin/python` を別プロセスで動かす**方式（`engine.py`）。理由: エンジンは `import tools` で16アイテム（numpy・moviepy・playwright…）を読むため、こちらの `.venv` に同じものを入れると両方が壊れやすい。**flyer-creator 側に playwright は不要**。agent-platform が無いPCでは「これまでの型」（PIL版）だけで動く。
  - **★型・レイアウト・下帯・配色を直すときは `agent-platform/core/{layouts,blocks,previews}.py` を直す（flyer-creator 側に型の実体は無い）。1箇所直せばマルチプロダクションとチラシクリエーターの両方に反映される＝共通。** flyer-creator の `engine.py` はその型を呼ぶ橋渡し（`build_content` で `flyer.Flyer`→content へ翻訳・renderは `layouts.build()` 経由）だけ。型を直したら `agent-platform/.cache/previews/*.png` を消して見本を作り直す。逆に「チラシだけ変えたい」変更も、共通なのでマルチにも出る点に注意。
- **配色の既定 橙 `#f07c1e` × 濃紺 `#1b2340` は変えないこと。** 現地写真に重ねて検証した色（木立にも壁にも負けず工事看板にも見えない）。エンジンの `sunset`（`#e2701a`）で代用しない。
- **写真の安全装置3段構え（絶対に外さない）**: ①写真ソースは Dropbox 撮影フォルダのみ ②`DENY`（身分証・免許・申込・契約…）を候補から除外 ③人が選んだ写真がない物件は書き出さない。案件フォルダに**入居申込者の身分証と申込書が同居**しており、以前サイトの生成物に入りかけた（公開前に破棄・流出なし）。
- 集計の閲覧キーは `.stats_key`（gitignore）。`stats.php?k=…` で見る。**ソースにも文書にも書かない**。
- gitに入れるのは**コードと文書だけ**。`.venv` / `data/`（賃貸資料74MB・型サンプル）/ `site/`（生成物）は除外。旧免許番号(1)第58258号が焼き込まれた `assets/spm_logo_white.png` も配らない（使うのは `spm_logo_white_name.png`）。
- 物件サイトは **https://daikyocorp.co.jp/slowlife/** に公開済み（募集中4件＋賃貸中11件）。FTP接続情報は `theta-viewer/server/ftp-config.json`（gitignore）。
