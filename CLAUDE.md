# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ★★ 作業ルール（PDCA・引き継ぎ）— 起動直後に必ず実行

セッションが切れても後任が同じ状態から続けられるようにするための決まり。
**この節は全アプリ共通で、例外なく守る。**

### 0. 起動したら、挨拶より先に読む

1. `CLAUDE.md`（このファイル）
2. `TODO.md`（リポジトリ直下）… **どのアプリで何が進行中かの索引**。全体像はここだけで掴む
3. 作業対象のアプリが決まったら `<アプリ>/SESSION_LOG.md` と `<アプリ>/TODO.md`

読み終えてから挨拶し、**「前回はどこまで進んでいて、次は何をする状態か」を1〜2行で述べる**。
どのアプリの作業か分からないうちは直下の `TODO.md` までで止めてよい（全アプリのログを
先読みしない）。ファイルが無いアプリは、そのアプリで最初に作業するときに作る。

**もう1台のPCの続きを引き継ぐときは、読む前に `./dev-doctor.py --sync --fetch` を叩く。**
remoteに未取得のコミットがあるか、こちらに未コミットの作業が残っているかが先に分かる
（先に pull すべきか、先に片付けるべきかを間違えない）。

### 1. Plan（計画）／ Do（実行）

着手前に、これからやることを `<アプリ>/TODO.md` に書く（1行でよい）。
書いてからコードを書き、テストする。作業中に増えた課題もその場で追記する。

### 2. Check（評価）

テストが落ちた・エラーが出たときは、**原因と、なぜその直し方で直るのか**まで見る。
現象だけ消して先に進まない。調べて分かった事実（APIの仕様、はまりどころ）は
アプリの `README.md` に残す。同じ調査を次の担当が繰り返さないため。

### 3. Act（改善・記録）

作業の区切り（またはセッションの終わり）に、`<アプリ>/SESSION_LOG.md` の**先頭**へ
新しい日付の節を追記する。**上書きせず必ず追記**。書式は次の3見出しで統一する。

```markdown
## 2026-08-13（メインPC）

### 完了したこと
-

### 発生したエラーと解決策
- 症状 → 原因 → 直し方（原因が分かっていないなら「未特定」と書く）

### 次回への引き継ぎ事項・未解決の課題
-
```

**見出しには日付だけでなく、どのPCで作業したかを必ず書く**（`（メインPC）` / `（サブPC）`）。
2台が同じ日に別々に書くと、**同じ見出しになってgitのマージが衝突する**。実際に
2026-08-17 に「2026-08-17」の節を両PCが書いて衝突した。PC名が入っていれば別の節として並ぶ。

同時に、直下の `TODO.md` のそのアプリの行を現状に合わせて1行で書き換える
（索引なので詳細は書かない。詳細はアプリ側のログにある）。**担当PC列も埋める**
（どちらのPCで続けるかが分かれば、2台で同じ作業を始めてしまう事故が防げる）。

### 3-b. 作業の終わりに `./dev-doctor.py --sync` を叩く（コミット漏れの検知）

「忘れないようにする」ではなく、**忘れたことを機械に見つけさせる**。

```bash
./dev-doctor.py --sync --fetch     # Git・バージョン・機密・自動起動をまとめて点検
```

- 未コミット変更・未追跡ファイル・stash・push漏れ・remoteの未取得を **WARNING** で並べる
- **`.gitignore` の許可行が無くて git に入っていないソース**も検出する。直下 `.gitignore` は
  1行目から `*` で全部無視して `!` で個別許可する方式なので、**新規ファイルは `git add` しても
  黙って無視される**（2026-08-16に整備ツール5本がこれで失われた）
- 直すのは人。このコマンドは勝手に commit・pull・install しない

### 3-c. ★Claude が作るデータの置き場は1か所にまとめる（2026-08-31 オーナー指示）

**アプリが作る大きなデータ・同期したいデータは、個人Dropboxの `CLAUDE/` の下に置く。**

```
~/Library/CloudStorage/Dropbox-個人/CLAUDE/
  ├ mail-archive/          … メールアーカイバ(8535)の原本と添付（46GB）
  ├ company-mail-archive/  … 社内メールアーカイバ(8538)の原本と添付
  ├ 書類取込/               … 書類キャビネット(8528)がスマホから受け取る場所
  └ 社内バックアップ/         … dropbox-backup の退避先（19GB）
```

**なぜまとめるか**: 個人Dropboxの直下にアプリごとのフォルダが増え続けると、
**どれがアプリのもので、どれが人のものか分からなくなる**。1か所に集めれば、
消してよいもの・容量を食っているものの判断がすぐつく。

- **今後 Claude 経由で作るフォルダは、必ずこの下に作る**（直下に作らない）
- パスは**設定（`.env` や環境変数）に持たせ、コードに直書きしない**。
  実際この移動で直したのは 7か所（`.env` 2本・`run.sh`／`sync-daily.sh`・
  `dropbox-backup/backup.sh`・`shorui-cabinet` の2本）だけで済んだ
- **索引DB（SQLite）はここに置かない。** 同期フォルダでSQLiteを開くと壊れる。
  DBは各アプリの `local/` に置く（`mail-archiver/README.md` の「置き場」参照）
- **会社の共有Dropboxには置かない**（個人情報・メール本文が全社員に見える）
- 移動するときは**先に常駐と夜間ジョブを止める**。開いているファイルがあると取りこぼす

### 3-d. ★claudeの定額枠が少ないとき — 節約モード（2026-08-31）

```bash
./ai-quota-saver.sh on      # claudeを使う夜間処理を止める
./ai-quota-saver.sh off     # 元に戻す
./ai-quota-saver.sh         # いまどちらか
```

**印は `~/.ai-quota-saver` の1ファイルだけ。** 夜間ジョブが起動時にこれを見て工程を飛ばす。
**launchd は外さない**（外すと戻し忘れて永久に止まる。印を消せば翌晩から自動で戻る）。

| 止まるもの | 代わりにどうなるか |
|---|---|
| 共有フォルダOCRの **claude 回送** | macOS Vision で読めたものだけ取り込む。読めなかったものは**後日に回す**（見送りリストに入れないので枠が戻れば自動で再挑戦） |
| **英語メールの日本語訳**（8535 / 8538） | その晩は訳さない。翌晩以降に持ち越し |
| **記事の自動執筆**（ai-tools-base） | 書かない。待機に29本の在庫があるので困らない |

| 止まらないもの（業務で使う） |
|---|
| Chatwork・LINE の応答／画面の「AIに探してもらう」／メールの取り込み・**Vision OCR**・ベクトル作成 |

**★見送りリストに入れないことが肝。** 空リストで返すと「この書類には文字が無い」と
見なされ、**枠が戻っても二度とOCRされない**（2026-08-28 に実際に起きた事故と同じ型）。

### 4. PCまたぎの受け渡し — 受け取ったら消す

コードはgit、機密（`.env` / DB / 鍵 / 個人情報を含むデータ）は**個人Dropboxに一時置き場**を作って運ぶ
（`handoff-YYYYMMDD/` のように日付で切る）。**運び終わったら、置き場ごと必ず消す。**

- 消す前に**受け取り側に実体があることを1件ずつ確認する**（`ls` / `du -sh` で見る。件数と容量まで）
- 消すのは受け取りを確認した人。「たぶん入っているはず」で消さない
- 消してよい理由: 機密を同期フォルダに置きっぱなしにしない／容量を食う（実例: ポケカ画像 4.0GB）。
  Dropboxは削除後30日は復元でき、機密は元PCに原本があるので作り直せる
- 一時置き場のパスは**アプリ側ではなく直下の `TODO.md`** に書く（受け取り側が起動時に必ず読むため）

### 5. 完了の定義 — 書いた時点では完了ではない

**成果は「コードを書いたこと」ではなく「動作する機能」。** 次が揃って初めて完了とする。

- [ ] 要件を満たしている（`<アプリ>/TODO.md` に書いた内容と照らす）
- [ ] **検証の最低ラインを実行した**（下の表。`./dev-doctor.py --verify <アプリ>` で回る）
- [ ] **画面を目で見た**（UIを触ったなら `./va.sh shot` / `./va.sh check`。「たぶん直った」で終えない）
- [ ] 既存機能を壊していない（触った周辺を1つ動かす）
- [ ] `<アプリ>/SESSION_LOG.md` に追記し、直下 `TODO.md` の行を更新した
- [ ] `./dev-doctor.py --sync` を叩いて、コミット漏れが無いことを確認した

> 実例（この決まりが無くて起きたこと）: iOSのビルド番号を上げずに再アップして**修正前のビルドが
> 審査を通り配信された**（2026-07-22）／agent-platform の .pptx 11枚が「通し実行は成功、
> **見栄えの目視は未了**」のまま止まっている／`photo-inpainter` は依存の入れ忘れが
> 暗黙フォールバックに落ち、**エラーも出ないまま**「使えない」と判断されて開発が止まっていた。

#### 検証の最低ライン（アプリ種別ごと。無いテストを無理に作らない）

| 種別 | やること |
|---|---|
| Streamlit（不動産・ツール） | `smoke_test.py` があれば実行 ＋ **`--server.address 127.0.0.1`** で起動して HTTP 200 ＋ 主要画面を `./va.sh shot` で目視 |
| Next.js | `npm run lint` と `npm run build`（`ai-tools-base` は `validate` も）＋ `./va.sh check` でUI崩れ検出 |
| 静的HTML・ゲーム | `./va.sh` で開いて **Console エラー0件** ＋ 画面確認 |
| iOS | `./ios-build-guard.sh <アプリ>` でビルド番号の衝突確認（**再配信の事故防止**） |

**`run.sh` を検証に使わない。** 不動産カテゴリの `run.sh` は `0.0.0.0` なので、
サブPCで叩くと社内LANに晒される。検証は必ず `127.0.0.1` を明示して起動する。

### 6. 自律で進めてよい範囲と、必ず聞くこと

**指示待ちにはならない。** 現在のタスクが終わったら `TODO.md` を見て、次の未完了タスクへ進む。
ただし**このリポジトリには外部に作用するアプリが多い**ので、範囲を線で区切る。

**自律で進めてよい**（ローカルで完結するもの）: バグ修正 / テスト・検証の追加 /
内部リファクタリング / エラーハンドリング改善 / 速度改善 / ドキュメント更新 / UI崩れの修正。

**必ず人に聞く**:

- **外部へ出る操作**（相手や公開物が動く）: Chatwork・LINEへの返信（`chatwork-ai-manager`）、
  メール送信（`mail-merge-pro`）、FTPでの本番サイト公開（`flyer-creator` / `theta-viewer`）、
  Vercel本番デプロイ・Zenn/noteへの投稿（`ai-tools-base`。**Zennは1日2本の上限あり**）、
  App Storeへの提出
- **戻せない操作**: DBスキーマの破壊的変更・`prisma db push`、データ削除、`git reset --hard`・force push
- **個人情報を含むデータの扱い**（`flyer-creator` の案件フォルダには**入居申込者の身分証が同居**している）
- **解釈が分かれる判断**（例: 2台のPCで別々に改名していたとき、どちらを正にするか。
  2026-08-17に実際に発生。自己判断で進めると片方の環境を壊していた）
- 課金が発生するもの（`agent-platform` は `AP_ALLOW_PAID=0` が既定＝無料の範囲だけ）

同じエラーで2回止まったら、**原因・試したこと・現在の状態・次に必要なこと**を
`<アプリ>/SESSION_LOG.md` に書いてから聞く（現象だけ消して進まない）。

### 7. タスクの書き方 — 軽いものは1行、重いものだけ様式化

`<アプリ>/TODO.md` は**1行で足りるなら1行**。次の場合だけ、様式を使う。

> **複数セッションにまたがる／複数ファイルを触る／外部に影響が出る**改修

そのときは `目的 / 実装内容 / 完了条件 / 検証方法 / 状態（TODO・進行中・保留・確認待ち・完了）/ 関連ファイル`
を書く。**それ以外に様式を広げない**（51本すべてに様式を課すと続かないため）。

構成が複雑なアプリ（`agent-platform` / `chatwork-ai-manager` / `building-manager`）は、
**構成と処理の流れを `<アプリ>/README.md` に図で残す**。他は不要。

### 書くときの原則

- **憶測を事実として書かない。** 確かめていないことは「未確認」と明記する
- 失敗した案・やめた案も理由つきで残す（後任が同じ失敗を繰り返さないため）
- 数値は測った値を書く（「速くなった」ではなく「4.2秒 → 1.1秒」）

---

## ★ PCの役割分担（2026-08-17確定・全アプリ共通）

**2台とも同じリポジトリを持つが、役割は違う。**

| | メインPC（Mac mini） | サブPC |
|---|---|---|
| launchd 常時起動 | **する**。「使う目的」で立ち上げっぱなし | **しない**。作成・改良のときだけ `./run.sh` で都度起動 |
| 社内LAN共有 | **する**（不動産カテゴリの完成済み） | **しない** |
| chatwork-ai-manager の worker / LINE / ngrok | **ここだけ**（二重起動禁止） | 管理画面8540のみ可 |

- サブPCで起動するのは**動作確認のため**であって、業務で使うためではない。
  常駐に登録しない（`launchctl load` しない）。個人情報を含む画面を二重にLANへ出さない
- したがって「LANに出ているか」の点検（`lsof -nP -iTCP:<port> -sTCP:LISTEN`）は
  **メインPCの表が正**。サブPCで待ち受けが残っていたら止める側

**run.sh を直しても常駐には効かない。** plistが `run.sh` を呼ばず
`/usr/bin/python3 -m streamlit run app.py …` を直接叩いている例がある（quote-generator）。
バインド先やPythonを変えたら、**plist を直してから入れ替えて `lsof` で見る**まででワンセット
（2026-08-17に 8526/8527 がこれでLAN公開のままだった）。

**ただし引数を変えたときは `launchctl kickstart -k` では反映されない。** kickstart は
**ロード済みの定義で再起動するだけ**で、ディスクの plist を読み直さない。PIDだけ変わって
中身が古いままになるので一番気づきにくい（2026-08-24に 8518 で実際に踏んだ）。

```bash
launchctl bootout   gui/$(id -u)/<label>                          # 外す
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist   # 入れ直す
launchctl print gui/$(id -u)/<label> | grep -A2 server.address    # 反映を確認
lsof -nP -iTCP:<port> -sTCP:LISTEN                                # 待ち受けを確認
```

`kickstart -k` で足りるのは「コードだけ直した（引数は同じ）」ときだけ。

## ★ 共通 Visual Agent — Claude Code がブラウザを見て操作する（2026-08-18 統合）

**画面を見ずに「直りました」と言わない。** UIを触ったら、実際に開いて撮って確かめる。
2台のPCが別々に作った2つの実装を**1つの仕組み・2つの入口**に統合した。
**設定もコードも git に入っている**ので、両PCとも `git pull` だけで同じものが使える。

| 入口 | 呼び方 | 得意 |
|---|---|---|
| **A: 会話の中（MCP）** | `cd ~ && claude` で自動有効（定義は `~/.mcp.json` の1ファイルだけ） | 対話しながら押す・入れる・読む。AI業務マネージャーの開発エージェントも同じ定義を読む |
| **B: シェル（`./va.sh`）** | `./va.sh goto/shot/check/responsive/console…` | UI崩れの機械検出・3幅比較・自動検証。`dev-doctor.py --verify` もこれ |

- **どちらも同じ Google Chrome を headless で開く**ので、見えるものが食い違わない
- 入口Bの Playwright(Python) は `VA_PYTHON` → `agent-platform/.venv` → `.va-venv` → `python3`
  の順に探す（**特定アプリの .venv に依存しない**）。Chrome が無いPCでは同梱Chromiumへ自動で切替
- **パスワードは入力しない。** 撮った画像は `.see/`（gitignore。コミットしない）
- 動くかどうかは `./visual-agent-check.sh`（`--mcp` / `--va` で片方だけも可）
- **使い方・つまずき所・実測はすべて `VISUAL_AGENT.md` にある**（ここには増やさない）
- Mac の画面そのものや `.pptx` / `.pdf` の見た目は `./see.sh screen` / `./see.sh file <ファイル>`

## ★ 最優先事項 — 全アプリ一覧（2026-08-07時点）

**カテゴリ:** 不動産 / ツール / ゲーム の3分類（全56本）※不動産32・ツール17・ゲーム7  
**社内LANルール:** 不動産カテゴリの完成済みのみ共有（launchd常時起動）

### 不動産（32本）

| アプリ名 | フォルダ名 | port | 社内LAN | 外部公開 |
|---|---|---|---|---|
| 手書き検針記録 | handwriting-ocr | — | 開発中 | — |
| 見積書自動生成ツール | quote-generator | 8503 | ✅ | **別リポジトリ**（下記） |
| 物件管理案内文ジェネレーター | property-notice-generator | 8504 | ✅ | — |
| マイソクコンバーター | maisoku-converter | 8505 | ✅ | — |
| 不動産写真AI | photo-inpainter | 8506 | ✅ | — |
| 原状回復費用自動精算 | restoration-calculator | 8508 | ✅ | — |
| AI不動産価格査定 | realestate-valuation | 8509 | ✅ | — |
| 決済案内書自動作成 | settlement-creator | 8510 | ✅ | — |
| 間取り図トレーサー | madori-tracer | 8511 | ✅ | — |
| THETAパノラマ3D空間化 | theta-viewer | 8512 | ✅ | GitHub Pages |
| 特約条項ジェネレーター | tokuyaku-generator | 8513 | ✅ | — |
| 入金突合（消込）システム | payment-reconciler | 8514 | ✅ | — |
| 物件写真一括リサイズ | image-resizer | 8515 | ✅ | GitHub Pages |
| 顧客追客マネージャー | tsuikyaku-crm | 8516 | ✅ | — |
| AI重説アシスタント（調査→公式書式へ自動入力→特約→検算） | jyuusetsu-research | 8536 | ✅ | — |
| 媒介契約書ジェネレーター | baikai-generator | 8517 | ✅ | — |
| AI受付＆起票カウンター | ai-ticket-counter | 8600 | ✅ | — |
| マンション・ビル管理 | building-manager | — | 開発中 | — |
| オーナー送金・月次締めマネージャー | owner-payout-tracker | 8519 | ✅ | — |
| 横断ファイル検索ブラウザ | file-finder | 8520 | ✅ | — |
| 不動産・金融マスター電卓 | realestate-calc | 8507 | ✅ | GitHub Pages / App Store ✅（**1.0 build7 が配信中**・2026-08-24 に API で確認） |
| 業務マニュアル（Web） | gyomu-manual | 8521 | ✅ | — |
| 駐車場配置図ビューア | parking-map | 8522 | ✅ | — |
| 覚書・合意書ジェネレーター | memorandum-generator | 8524 | ✅ | — |
| 送付書メーカー（**社員用**・大京商事固定＋担当者切替） | soufu-maker | 8525 | ✅ | — |
| 書類キャビネット（紙書類の所在管理・ファイル単位） | shorui-cabinet | 8528 | ✅ | — |
| 書類キャビネット スマホ用（撮影→Dropbox取込） | shorui-mobile | — | ー（Vercel・pass保護） | Vercel（shorui-mobile.vercel.app） |
| マルチプロダクション（企画→紙面→パワポ→音声→動画→SNS） | agent-platform | 8532 | ✅ | — |
| AI業務マネージャー（Chatwork/LINE常駐AIエージェント） | chatwork-ai-manager | 8540(画面)/8530(LINE) | ✅（画面0.0.0.0） | LINE(ngrok) |
| 事業計画案ジェネレーター（投資収支→Excel） | business-plan-generator | 8533 | ✅ | — |
| 社内メールアーカイバ（社員のメールを保管＋AI業務マネージャーの知識へ） | company-mail-archiver | 8538 | **出さない**（127.0.0.1固定・社員のメール本文のため） | — |
| KeyLine（NFC鍵・備品貸出管理） | keyline | 8534 | ✅ | **本体（8534）はこのMacの launchd に登録していない**（2026-08-28 オーナー判断で見送り。plist は `keyline/_launchd/` にある）。iOSアプリ **KeyTag**（掲載名 **KeyTag鍵管理**）は **1.0 / build 4 で再提出＝審査待ち**（2026-08-28 11:13 JST 提出・`WAITING_FOR_REVIEW` を API で確認）。差し戻しは2回: Guideline 2.1（NFCのデモ動画の要求）→ **動画をサポートページに公開して回答** https://shinsei99.github.io/project/keytagnfc-support/ ／ Guideline 4.3(a)（スパム）→ **掲載名・説明文・副カテゴリを作り直し、サーバー連携を公開仕様にして回答**。あわせて実機で判明した **NFCの不具合2件を build 3 で修正**（build 2 はまっさらなタグを読めず、タグに書けなかった）。詳細は `keyline/SESSION_LOG.md` 冒頭 |

### ツール（17本）※社内LAN共有なし

| アプリ名 | フォルダ名 | port | 外部公開 |
|---|---|---|---|
| 送付書ジェネレーター（**オーナー個人専用**・差出人4プロファイル／社内には配らない） | soufu-generator | 8518 | — |
| デジタル書斎 | digital-shosai | 3001 | App Store ✅（**アイコンを差し替えた 1.0.1 build2 が配信中**・2026-08-28 に API で確認＝審査を通った） |
| ブレイン・ダンプ自動整理 | brain-dump | 3002 | Vercel（brain-dump-sable-one.vercel.app） |
| スクラップメモ + PetaPeta Clipper | scrapmemo-petapeta + petapeta-extension | — | GitHub Pages / App Store ✅（**1.0.4 build8 が配信中**）。**1.0.5 build9 を 2026-08-28 に提出＝審査待ち**（`WAITING_FOR_REVIEW` を API で確認。長文編集時に「完了」へ指が届かない問題の修正）。build7は提出せず |
| 水泳記録トラッカー | swim-tracker-react | — | GitHub Pages / App Store ✅（**1.0 build1 が配信中**・2026-08-24 に API で確認） |
| ママカウンター | mom-counter | — | GitHub Pages / App Store ✅（**1.0 build4 が配信中**・2026-08-24 に API で確認。「v1.0.1」は誤記だった） |
| Mac一斉メール送信 | mail-merge-pro | — | Macアプリ |
| フォトリメイク | photo-remake | — | iOS App Store ✅（**1.1.0 build4 が配信中**・2026-08-27 に API で確認。図形13種。8/26提出→審査通過） |
| 買取DMジェネレーター | kaitori-dm-maker | 8526 | — |
| PSAカード管理 | psa-collection | 8527 | — |
| パシャカロ！（撮るだけカロリー記録） | pasha-calo | 3003 | Vercel（pasha-calo.vercel.app） |
| ポケモンカード図鑑（全31,520枚・画像100%収録／**PSAカード管理の中からも開ける**） | pokecard-dex | 8531 | — |
| ワンピースカード図鑑（全4,962枚・画像100%収録／公式サイト1本で完結／**PSAカード管理の中からも開ける**） | onepiece-dex | 8537 | — |
| チラシクリエーター（物件チラシ・型10種／物件サイト生成） | flyer-creator | 8529 | 物件サイトのみ daikyocorp.co.jp/slowlife/ |
| AIツールベース（Claude Code主軸の比較メディア＋制作記録） | ai-tools-base | 3004 | Vercel（**ai-tools-base.vercel.app**・手動 `npx vercel --prod`） |
| メールアーカイバ（IMAP容量対策・ローカル保管＋全文検索） | mail-archiver | 8535 | — |
| GrowLog（子ども向け成長記録・身長体重の記録とグラフ・PWA） | growth-tracker | 3005 | — |

### ゲーム（7本）※社内LAN共有なし

**★7本は「ネオンブロックス」の中に同居し、画面下の帯で行き来する。**
色・書体・タイトル・音ボタン・音の調・画面の向きを**揃える決まりは
`neon-blocks/NEON_STYLE.md`**（2026-08-29 制定）。どれか1本を触るときは先にそこを読むこと。
直したら `python3 neon-blocks/tools/sync-games.py` で集合側へ入れ直す。

| アプリ名 | フォルダ名 | 外部公開 |
|---|---|---|
| **ネオンタワー**（旧 ひよこ防衛軍） | piyo-defense | GitHub Pages ／ **App Store は提出直前**（2026-08-28。`com.shinsei99.piyodefense`・1.0/build2 の ipa まで書き出し済み。**残りは ASC で App 記録を作ること**＝APIでは作れない。手順は `piyo-defense/RELEASE.md`）。**2026-08-28 まで gh-pages に存在しなかった**（「GitHub Pages」は誤記だった）。`DEPLOY_FOLDERS` は **`piyo-defense:www`**（2026-08-29 に `piyo-defense` から変更。直下の控えが古く、公開ページだけ旧デザイン・旧題名のままだった）。**2026-08-29: UIをネオンに統一**（タイトル・ボタン・書体・草・HUD・ゲームオーバー。ひよこ本体は残す）。**スクショは旧デザインのまま**＝提出再開時に撮り直す |
| **ネオングラビティ**（旧 カラー・グラビティ） | color-gravity | GitHub Pages ／ **App Store は提出直前**（2026-08-28 に iOSアプリ化。`com.shinsei99.colorgravity`・1.0/build1 の ipa まで書き出し済み。**残りは ASC で App 記録を作ること**＝APIでは作れない。手順は `color-gravity/RELEASE.md`）。**本体は `www/` へ移した**ので gh-pages の取り出し元は `color-gravity:www` |
| **ネオンサイボーグ**（旧 サイボーグ防衛軍） | cyborg-defense | GitHub Pages ／ **App Store は提出直前**（2026-08-28 に iOSアプリ化。`com.daikyo.cyborgdefense`・1.0/build1 の ipa まで書き出し済み。**残りは ASC で App 記録を作ること**＝APIでは作れない。手順は `cyborg-defense/RELEASE.md`）。**本体は `www/` へ移した**ので gh-pages の取り出し元は `cyborg-defense:www` |
| **ネオンエスケープ**（旧 にゃんこ大脱出・**全40面**・★評価つき。2026-08-29 に世界観を「宇宙の脱出行」へ作り替え＝自機／追撃機／ワープゲート・**縦画面**・角ゴシック＋Orbitron） | neko-escape | GitHub Pages ／ **App Store は提出直前**（2026-08-28 に iOSアプリ化。`com.daikyo.nekoescape`・1.0/build1 の ipa まで書き出し済み。**残りは ASC で App 記録を作ること**＝APIでは作れない。手順は `neko-escape/RELEASE.md`）。**本体は `www/` へ移した**ので gh-pages の取り出し元は `neko-escape:www` |
| **ネオンアイス**（旧 にゃんこのアイス屋さん） | nyanko-ice | **2026-08-29: 4.3(a) でリジェクト → App 記録を削除した**（未配信のまま終了。**バンドルIDは再利用できない**）。手順は3段階で、**①提出物から項目を削除（Rejected → DEVELOPER_REJECTED になる）②配信可能状況を全地域でオフ（ここが本当の詰まり所。未配信でも米日が残っていた）③Appを削除**。詳細は `nyanko-ice/TODO.md`。**Web版（gh-pages）はそのまま公開中**。中身はネオンブロックスへ統合予定 |
| **ネオンランナー**（旧 グロウランナー・3Dランゲーム。2026-08-30 にネオンシリーズ7本目へ組み込み＝改名・書体・音・9:16の枠・**5面ごとのセーブ地点**・**1面クリアで補充されるアイテム3種**。Three.js は同梱＝通信不要） | glow-runner | **GitHub Pages**（2026-08-30 に公開。取り出し元は **`glow-runner:www`**） |
| ネオンブロック | neon-blocks | iOS App Store ✅（**1.0.3 build4 が配信中**・2026-08-24 に API で確認） |

## ★ 公開サイト（5つ）

**アプリ（動かすもの）とは別軸の索引。** 本数の内訳には入れない
（AIツールベースは port 3004 のアプリでもあるため、ツール分類に残したまま）。

| 名称 | URL | 実体・更新方法 |
|---|---|---|
| AIツールベース（AI開発ガイド） | https://ai-tools-base.vercel.app/ | `ai-tools-base`（3004）／`./publish.sh site` |
| Zenn（技術記事） | https://zenn.dev/shinsei99 | リポジトリ直下 `articles/` を push（GitHub連携）／`./publish.sh zenn` |
| note（非技術・読み物） | https://note.com/shinsei99 | `ai-tools-base/drafts/note/`／`./publish.sh note <名前>` |
| 緑と暮らすスローライフ（物件サイト） | https://daikyocorp.co.jp/slowlife/ | `flyer-creator` が生成→FTP（接続情報は `theta-viewer/server/ftp-config.json`） |
| 小説「不動産屋、はじめました。」 | https://kakuyomu.jp/works/2912051604243797830 | カクヨム連載・著者名 SHINSEI。**全31話・予約投稿済みで順次自動公開＝放置でよい**。原稿は GoogleDrive/新誠不動産/`カクヨム用/` |
| 続編「不動産屋、つくってます。」 | **未投稿**（作品ページも未作成） | **全32話・95,119字を 2026-08-22 に脱稿**。前作の続き（久美が独立し、自作アプリで管理業を作る話）。原稿は GoogleDrive/新誠不動産/`続編_カクヨム用/`（設計は `続編_構成案.md` / `続編_全話構成.md`）。**次は通し推敲 →作品ページ作成→投稿**（投稿は直近24時間の本数制限に注意） |

- 上の3つ（サイト・Zenn・note）は**1本の制作記録を3媒体に出す**運用。手順は `ai-tools-base/CLAUDE.md`
- **THETAパノラマ（daikyocorp.co.jp/vr/）やGitHub Pages公開のゲームはここに載せない。**
  あれは「アプリの公開先」なので、アプリ一覧の外部公開欄で足りる

### アプリ個別の詳細は各アプリの `README.md` にある（2026-08-17に移動）

CLAUDE.md は**全セッション・全ターンに乗る固定費**なので、共通ルールだけを置く。
アプリ1本にしか関係しない事情（はまりどころ・調べた事実・運用の決まり）は README にある。
**READMEはgitで両PCに渡る**ので、直せば2台で同じ内容になる。

- **大京商事 業務マニュアル（Web）**（`gyomu-manual`） … `gyomu-manual/README.md`
- **駐車場配置図ビューア**（`parking-map`） … `parking-map/README.md`
- **買取DMジェネレーター**（`kaitori-dm-maker`・port 8526） … `kaitori-dm-maker/README.md`
- **PSAカード管理**（`psa-collection`・port 8527） … `psa-collection/README.md`
  （**ポケモンカード図鑑をオプションとして中から開ける**。図鑑の実体は `pokecard-dex/` のまま）
- **マルチプロダクション**（`agent-platform`・port 8532） … `agent-platform/README.md`
- **AI業務マネージャー**（`chatwork-ai-manager`） … `chatwork-ai-manager/README.md`
- **AI重説アシスタント**（`jyuusetsu-research`・port 8536） … `jyuusetsu-research/README.md`
  （**書式を触ったら `print_check.py` で紙面を見る**。値の突き合わせでは書面の破損が見つからない）
- **チラシクリエーター**（`flyer-creator`・port 8529） … `flyer-creator/README.md`
- **書類キャビネット**（`shorui-cabinet`・port 8528） … `shorui-cabinet/README.md`
- **ワンピースカード図鑑**（`onepiece-dex`・port 8537） … `onepiece-dex/README.md`
- **不動産写真AI**（`photo-inpainter`・port 8506） … `photo-inpainter/README.md`
- **THETAパノラマ3D空間化**（`theta-viewer`） … `theta-viewer/README.md`
- **KeyLine（NFC鍵・備品貸出管理）**（`keyline`・port 8534） … `keyline/README.md`
  （iOSアプリ **KeyTag** の配信手順は `keyline/keytag/RELEASE.md`）
- **メールアーカイバ**（`mail-archiver`・port 8535） … `mail-archiver/README.md`
- **デジタル書斎**（`digital-shosai`・port 3001） … `digital-shosai/README.md`
  （App Store 提出の手順は `digital-shosai/HANDOFF-APPSTORE.md`）

※ `quote-generator` は**別リポジトリ**なので、その補足だけ下にそのまま残している。

### quote-generator（見積書自動生成ツール）補足 ※不動産・port 8503

- **このアプリだけ独立したリポジトリ**: `github.com/shinsei99/quote-generator`（public）。
  直下リポジトリの `git pull` では**来ない**ので、他PCでは別途 `git clone` する。
  親で追跡しようとすると embedded repository になり中身が渡らないため、`.gitignore` で除外したまま。
- launchd（`com.shinsei.quote-generator`）は **`run.sh` を経由せず** plist から
  `/usr/bin/python3 -m streamlit run app.py` を直接叩く。`run.sh` は手動起動・他PC用（venvを作る）。
- `data/issuers.csv`（発行者マスタ＝社名・担当者名）と `logs/` は先方リポジトリでも gitignore。
- 2026-08-17: メインPCの作業コピーが 2コミット遅れ、同じ内容が未コミットのまま残っていた
  （＝**すでにpush済みの内容だった**）。fast-forward で解消。

### 社内LAN常時起動ポート一覧（launchd / メインMac）

| port | アプリ名 | plist |
|---|---|---|
| 8503 | 見積書自動生成ツール | com.shinsei.quote-generator |
| 8504 | 物件管理案内文ジェネレーター | com.shinsei.property-notice-generator |
| 8505 | マイソクコンバーター | com.shinsei.maisoku-converter |
| 8506 | 不動産写真AI（インペインター） | com.shinsei.photo-inpainter |
| 8507 | 不動産・金融マスター電卓 | com.shinsei.realestate-calc |
| 8508 | 原状回復費用自動精算 | com.shinsei.restoration-calculator |
| 8509 | AI不動産価格査定 | com.shinsei.realestate-valuation |
| 8510 | 決済案内書自動作成 | com.shinsei.settlement-creator |
| 8511 | 間取り図トレーサー | com.shinsei.madori-tracer |
| 8512 | THETAパノラマ3D空間化 | com.shinsei.theta-viewer |
| 8513 | 特約条項ジェネレーター | com.shinsei.tokuyaku-generator |
| 8514 | 入金突合（消込）システム | com.shinsei99.payment-reconciler |
| 8515 | 物件写真一括リサイズ | com.shinsei.image-resizer |
| 8516 | 顧客追客マネージャー | com.shinsei.tsuikyaku-crm |
| 8517 | 媒介契約書ジェネレーター | com.shinsei.baikai-generator |
| 8519 | オーナー送金・月次締めマネージャー | com.shinsei.owner-payout-tracker |
| 8520 | 横断ファイル検索ブラウザ | com.shinsei.file-finder ＋ **-inventory（毎週日曜5:00**に共有フォルダを棚卸しして `全ファイル一覧.xlsx` を作り直し、8520に読み直させる。2026-08-30 追加。それまで**作る側の仕組みが無く7/22で更新が止まっていた**） |
| 8521 | 業務マニュアル（Web） | com.shinsei.gyomu-manual |
| 8522 | 駐車場配置図ビューア | com.shinsei.parking-map |
| 8523 | theta-viewer FTP APIサーバー（server.js） | com.shinsei.theta-viewer-api |
| 8524 | 覚書・合意書ジェネレーター | com.shinsei.memorandum-generator |
| 8525 | 送付書メーカー | com.shinsei.soufu-maker |
| 8526 | 買取DMジェネレーター（※ツール・localhost・社内共有なし／常時起動のみ） | com.shinsei.kaitori-dm-maker |
| 8527 | PSAカード管理（※ツール・localhost・社内共有なし／常時起動のみ。Desktop/社内ツールに.appショートカット有） | com.shinsei.psa-collection |
| 8528 | 書類キャビネット（※不動産・社内LAN共有あり・0.0.0.0／要フルディスクアクセス for /bin/bash＝Dropbox取込読取） | com.shinsei.shorui-cabinet |
| 8529 | チラシクリエーター（※ツール・127.0.0.1・launchd未登録） | （未登録） |
| 8531 | ポケモンカード図鑑（※ツール・127.0.0.1・**launchd未登録＝常駐させない**／**PSAカード管理(8527)の中から使う**／カード画像は著作物のためLANに出さない） | （未登録・2026-08-24に外した） |
| 8537 | ワンピースカード図鑑（※ツール・127.0.0.1・launchd未登録／**PSAカード管理(8527)の中からも開ける**／カード画像は著作物のためLANに出さない） | （未登録） |
| 8532 | マルチプロダクション | com.shinsei.agent-platform |
| 8533 | 事業計画案ジェネレーター | com.shinsei.business-plan-generator |
| 8534 | KeyLine（NFC鍵・備品貸出管理／※画像自動削除は -purge が毎日3:30） | com.shinsei.keyline ＋ -purge |
| 8535 | メールアーカイバ（※ツール・127.0.0.1・メール本文＝個人情報のためLANに出さない） | com.shinsei.mail-archiver（閲覧）＋ -sync（**毎日00:30**に取り込み＋翻訳＋1年超をサーバー削除。2026-08-28にOCRと時間帯をずらした） |
| 8538 | 社内メールアーカイバ（※不動産・**127.0.0.1**・社員のメール本文のためLANに出さない／取り込みは**毎日00:30**（個人用8535と同じ時刻に揃えた）・**サーバーからは1通も消さない**） | com.shinsei.company-mail-archiver-sync（**アカウント設定が揃うまで未登録**） |
| 8536 | AI重説アシスタント（※不動産・0.0.0.0／**plistは `/bin/bash run.sh` を呼ぶ**＝Dropboxの公式書式200本を読むため `/bin/bash` にフルディスクアクセスが要る） | com.shinsei.jyuusetsu-research |
| 8530 | AI業務マネージャー LINE webhook（※メインPCのみ稼働。ngrok固定ドメイン経由で公開） | com.shinsei.chatwork-ai-manager-line ＋ -ngrok |
| 8540 | AI業務マネージャー 管理画面（※不動産・0.0.0.0・パスワード認証あり） | com.shinsei.chatwork-ai-manager（worker は -worker） |
| 8600 | AI受付＆起票カウンター | com.shinsei.ai-ticket-counter |
| 5175 | 間取り図トレーサー 手動編集エディタ（editor/、Vite+React+TS） | com.shinsei.madori-tracer-editor |

**カード図鑑2本（8531 ポケカ・8537 ワンピ）は常駐させない**（2026-08-24 オーナー判断）。
常設するのは **PSAカード管理（8527）だけ**で、図鑑はその中から開いて使う。
PSA管理は図鑑の `app.py` を**モジュールとして直接読み込む**ので、**8531/8537 が
起動していなくても中から使える**。単独の画面が要るときだけ各 `run.sh` を都度叩く。
`com.shinsei.pokecard-dex` は `bootout` ＋ **`launchctl disable`** 済み
（plist は残してある。戻すなら `launchctl enable` → `bootstrap`）。

### バインド先のルール（2026-08-07整合・必読）

**Streamlitは `--server.address` を省略すると既定が `0.0.0.0`（＝LANに公開）。「指定しなければlocalhost」ではない。** 実際にpsa-collection / kaitori-dm-makerが「localhostバインド」とコメントしながらLANへ公開されていた（保有明細・資産額を含むため要注意）。各`run.sh`は必ず明示すること。

| 分類 | バインド | 対象 |
|---|---|---|
| 不動産だが**LANに出さない**（社員のメール本文） | `--server.address 127.0.0.1` | 8538 company-mail-archiver |
| 不動産（社内LAN共有あり） | `--server.address 0.0.0.0` | 8503〜8525 の19本（8506 photo-inpainter を2026-08-17に追加）＋8528 shorui-cabinet＋8532 agent-platform＋8533 business-plan-generator＋8534 keyline＋**8536 jyuusetsu-research**（2026-08-27に完成扱いへ移行）＋8540 chatwork-ai-manager |
| 不動産だが**開発中** | `--server.address 127.0.0.1` | （現在なし。8532 agent-platform は2026-08-17に、8536 jyuusetsu-research は2026-08-27に完成扱いへ移行） |
| ツール（社内共有なし） | `--server.address 127.0.0.1` | 8518 soufu-generator（個人専用） / 8526 kaitori-dm-maker / 8527 psa-collection / 8529 flyer-creator / 8535 mail-archiver / 8537 onepiece-dex / 3004 ai-tools-base（Next.js） |

確認は `lsof -nP -iTCP:<port> -sTCP:LISTEN`（`127.0.0.1:<port>` なら正しい。`*:<port>` は全公開）。

### 社内への配り方（入口の置き場・2026-08-17整理）

| 置き場 | 中身 |
|---|---|
| Dropbox `共有フォルダ/（★必読★）新共有フォルダ/社内ツール/` | 各アプリの `.url`（**24本**。2026-08-27にAI重説アシスタントを追加）＋ `icons/*.ico` |
| その**1つ上**（`（★必読★）新共有フォルダ/` 直下） | `横断ファイル検索.url` と `業務マニュアル.url` の2本だけ。全社員が毎日使う入口なので浅い位置に置く |
| `Desktop/社内ツール/`（このMacのみ） | `.app`（**31本**）。Mac用のランチャで、Dropboxには置かない |

- `.url` は **Shift-JIS(CP932)＋CRLF**。`URL=http://192.168.1.105:<port>`、
  `IconFile=%USERPROFILE%\大京商事　株式会社 Dropbox\…\社内ツール\icons\<名前>.ico`
  （※このMacは en0=192.168.1.140 / en1=**192.168.1.105** の2枚刺し。**配布は .105 で統一**）
- **AI業務マネージャー（8540）は社内に配らない。** オーナー管理の情報を扱うため、
  画面は 0.0.0.0＋パスワードで動かすが `.url` は置かない（2026-08-17判断）
- `.ico` が無いアプリは、Desktop の `.app` の `AppIcon.icns` を
  `sips -s format png` → PIL の `save(..., sizes=[...])` で変換すると見た目を揃えられる

---

## ★★ App Store への提出は停止中（2026-08-29〜）

**2026-08-29 に3本まとめて Guideline 4.3(a)（スパム）でリジェクトされた**
（KeyTag / スクラップメモ1.0.5 / にゃんこアイス）。3通とも同一の定型文で、提出は約6時間に集中。
**スクラップメモ 1.0.5 は「配信中アプリのUI修正だけの更新」なのに 4.3(a)** ＝ アプリ個別ではなく
**アカウント全体の出し方**を見られている。原因として実測できたのは次の3つ。

- 2か月で**9本**提出（多くが Capacitor の同じ殻で、**ネイティブ実行ファイルはほぼ同一バイト数**）
- ストア文言・サポート/プライバシーページを**アプリ間で置換して作っていた**（同じ型）
- **バースト提出**（3本を6時間に）

**★再開はこの順番（2026-08-30 オーナー指示）。1件ずつ、前の結果が出るまで次に進まない:**

1. **スクラップメモ 1.0.5 の更新** … 審査待ち（8/29 に返信つきで再提出済み）。待つだけ
2. **KeyTag の再申請** … 1が通ってから
3. **ネオンブロックスの更新**（**ネオンシリーズ7本入り**）… 2の結果が出てから。
   出すときは build 番号 +1・**スクショ撮り直し**（`tools/shoot-store.py --only blocks`）・
   掲載文を前回の型の使い回しにしないこと。**他6本は単体では出さない**（アプリを増やすと 4.3(a) に戻る）

**当面、App 記録の新規作成・提出・アップロード・再提出を行わない。** ipa やスクショの準備は可。
方針は「**まず KeyTag だけ Resolution Center に返信して様子を見る**」（`keyline/keytag/reply-4.3a-2026-08-29.md`）。
経緯と再開条件は直下 `TODO.md` の冒頭。

## ★ iOS App Store 再配信ルール（再発防止・必読）

**修正版を再アップロードするときは、必ずビルド番号（`CURRENT_PROJECT_VERSION`）を +1 する。**

> 2026-07-22の事故：photo-remake / neon-blocks とも、修正版を **build 1 のまま** 再アーカイブしていた。App Store Connect は「build 1 は既存」で新ビルドを受け付けず、**古い（修正前の）build 1 がそのまま審査を通り配信**されていた。ユーザーには「直したはずの不具合が残っている」状態に見えた。→ 両アプリを **1.0.1 / build 2** に繰り上げて解決。

### 再配信チェックリスト（Archive前に必ず）

1. `CURRENT_PROJECT_VERSION`（ビルド番号）を **既存の全アーカイブより大きい値**に +1 する
   - ネイティブ: `<app>.xcodeproj/project.pbxproj`（Debug/Release両方）＋ `project.yml`（xcodegen運用時）
   - Capacitor: `ios/App/App.xcodeproj/project.pbxproj`（※`ios/`はgitignore。`cap sync`しても番号は保持されるが、`cap add ios`でやり直すと1に戻る）
2. 必要なら `MARKETING_VERSION`（表示バージョン）も上げる（例 1.0.0 → 1.0.1）
3. **衝突チェック**: `./ios-build-guard.sh <app-folder>` を実行し「衝突なし」を確認（`--bump`で自動+1も可）
   - **審査の状態は `python3 appstore_api.py --review`** で確認できる（App Store Connect の画面を見に行かなくてよい。2026-08-23 追加）
4. Capacitorは `npx cap sync` を実行してからArchive（`.xcworkspace`を開く）
5. Archive → Upload → App Store Connectで **今上げたbuild番号** が選択肢に出ることを確認してから提出
6. 配信物のソースは必ずコミット＆push（修正が手元だけに残ると同じ事故が再発する）

### MinimumOSVersion は 15.0 以上（2027年春から必須）

**iOS 15.0 未満のアプリは、2027年春以降アップロードできなくなる**（警告 90068）。
2026-08-28 に全9本を API で実測したところ、**13.0 だったのは Capacitor 6 世代の
`neon-blocks` と `nyanko-ice` の2本だけ**。**両方 15.0 へ変更しビルド確認済み＝次に出すビルドから効く**
（配信中・審査中のビルドは 13.0 のまま）。**この2本は `ios/` が git に入らない**ので、
`npx cap add ios` で作り直したら入れ直すこと（`ios/App/Podfile` と pbxproj の
`IPHONEOS_DEPLOYMENT_TARGET`・4か所 → `pod install`）。

---

## Environment

- OS: macOS (darwin x86_64)
- Shell: zsh
- Custom binaries in `~/.local/bin` (added to PATH via `~/.zshrc`):
  - `gh` — GitHub CLI v2.94.0
  - `claude` — Claude Code CLI

## GitHub

Authenticated as **shinsei99** via `gh auth login`. The remote repository is `https://github.com/shinsei99/project` (public). Static HTML apps are published via GitHub Pages from the `gh-pages` branch (root), one folder per app, served at `https://shinsei99.github.io/project/<app>/`.

Common `gh` commands used in this repo:

```bash
gh repo view          # Show repository info
gh pr create          # Create a pull request
gh issue list         # List issues
```

## Git

```bash
git add <file>
git commit -m "message"
git push origin main
```
