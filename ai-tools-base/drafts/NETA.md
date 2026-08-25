# ネタ帳 — 制作記録の在庫（2026-08-24 棚卸し・**66本**）

**目的**: 「次は何を書くか」で毎回悩まないように、**書ける題材を先に集めておく**。
`drafts/PUBLISH.md` は公開済みの台帳、こちらは**未着手の在庫**。

## 使い方

1. 上から順ではなく、**直前の1本と系統（章）が違うもの**を選ぶ。同じアプリ・同じ原因が続くと重複感が出る
2. **書く前に必ず裏を取る。** 根拠欄の commit / ログ / ファイルを開き、数値と挙動を実物で確認する。
   思い出しで書かない（測っていない数字を書いた時点で、この媒体の値打ちが消える）
3. 3媒体（本体＋Zenn＋note）に出せるのは **`category: "realestate"` だけ**。
   〔ツール〕〔ゲーム〕〔メディア〕は**本体のみ**
4. 書いたら、その行を消して `PUBLISH.md` に節を作る

**記号**: ✅=症状・原因・直し方が記録に揃っていて、そのまま書ける
／⚠️=事実は残っているが数値や現在の実装を要確認 ／🔍=素材はあるがコードを読む必要あり

**在庫**: 全66本から書いたぶんを引いていく（この行は数え直したときに更新する）。書き終わった項目は行ごと消し、`PUBLISH.md` に節を作る。

---

# A. サイレント障害 — 落ちないから気づけない

> この章がこの媒体でいちばん強い。「エラーが出ないバグ」は検索されるのに書き手が少ない。

---

# B. 常駐・デプロイ — 「直したのに反映されない」

**15.** ⚠️〔メディア〕**Vercel は git 連携ではない／`--scope` が要る**（`ai-tools-base`）
push しても本番は変わらない。`whoami` は通るのにデプロイが `Not authorized`（プロジェクトはチームの持ち物）。
→ `77c1dd6`、`ai-tools-base/CLAUDE.md`

**16.** ✅〔メディア〕**Zenn は投稿上限に当たると「成功」と出たまま黙って未反映**（`ai-tools-base`）
自動再試行もされない。24時間空けて空コミットで再push。**待ち時間で見分けられる**（正常なら約30秒〜1分）。
→ `ai-tools-base/SESSION_LOG.md` 2026-08-22

---

# C. 帳票の見た目 — Excel / Word を人に配れる形にする

---

# D. 紙を読む — PDF・公式書式・謄本

---

# E. AIを道具として使う — モデル・SDK・プロンプト

**34.** ✅〔不動産〕**`--allowedTools` は自動承認リストであって禁止リストではない**（`agent-platform`）★セキュリティ
「入れなければ Bash は使えない」と思っていたが、**実際には実行できた**（`echo TESTOK` が通る）。
権限設計の話として単独で強い。
→ `agent-platform/SESSION_LOG.md:315`

---

# F. スマホ・ブラウザ

**42.** ✅〔不動産〕**スマホから写真を送ると3枚目で必ず失敗する**（`shorui-mobile`）★本命
①Vercel のボディ上限 **4.5MB** ②**iOS Safari は FormData のファイル名に非ASCIIが混ざると例外**
③`createImageBitmap` が **iOS Safari では失敗しやすく**、失敗時に原本を送るので縮小されない。
縮小（長辺1600px・品質0.72）だけでは枚数次第で超えるので、**1枚＝1リクエストに分割**して
束IDでサーバー側の1フォルダに集約。
→ `30526bd` `7eeec42` `5b1285b` `f4d724d`

**43.** ✅〔ツール〕**iOSはキーボードが出るとWebView自体が縮む**（`scrapmemo-petapeta`）
`innerHeight` 874→538。編集シートの上部が画面外へ出て触れなくなる。
**前回の直しは Safari だけで確認していて、実機で再発**したという経緯まで書ける。
→ `4b717e5`、`scrapmemo-petapeta/SESSION_LOG.md:126`

**44.** ✅〔ツール〕**`npx cap sync` だけでは `www/` が古いまま**（`scrapmemo-petapeta`）
`npm run sync`（build:web → cap sync）が正。md5 不一致で発覚。
→ `scrapmemo-petapeta/SESSION_LOG.md:35`

**45.** ✅〔ツール〕**Capacitor 8 は SPM なので `.xcworkspace` が無い**（`scrapmemo-petapeta`）
`xcodebuild -workspace` が「存在しない」で失敗。`-project` を使う。
→ `scrapmemo-petapeta/SESSION_LOG.md:38`

**46.** ✅〔ツール〕**再配信でビルド番号を上げず、修正前のビルドが審査を通った**（`photo-remake` / `neon-blocks`）
2026-07-22 の実事故。`ios-build-guard.sh` で衝突チェックする運用に。
→ メモリ `feedback_ios_build_bump.md`、CLAUDE.md の該当節

---

# G. 日本語のデータ

---

# H. 外部API

**58.** ✅〔ツール〕**GETは200なのに中身が空。POSTでないと返さない**（`onepiece-dex`）
公式カードリストが 51KB（選択肢のみ）で返る。`POST` にすると 463KB。
→ `onepiece-dex/SESSION_LOG.md:176`

**59.** ✅〔ツール〕**相場データは「平均が空で最安だけ入る」ことがある**（`pokecard-dex`）
取引平均だけを見ていたので481件が画面から消えた。しかもそのとき `trend` に **0 が入る**。
→ `pokecard-dex/SESSION_LOG.md:64`

---

# I. データベースと並行処理

**62.** ✅〔ツール〕**`executescript()` は busy_timeout を無視する**（`onepiece-dex`）
`database is locked` で落ちる。同じDBに `execute("BEGIN IMMEDIATE")` を投げたほうは**46秒待って成功**（実測）。
60番と同じ関数の別の顔なので、2本立てにもできる。
→ `onepiece-dex/SESSION_LOG.md:180`

**63.** ✅〔ツール〕**Streamlit は再実行のたびに別スレッド**（`mail-archiver`）
`@st.cache_resource` でSQLite接続を使い回して `ProgrammingError`。`check_same_thread=False`。
→ `mail-archiver/SESSION_LOG.md:43`

**65.** ✅〔ツール〕**キャッシュのキーが変わって「未照合」に戻る**（`kaitori-dm-maker`）
空欄の〒を補完するとキー（〒＋住所）が変わる。補完時に**新しいキーにも同じ結果を置く**。
→ `kaitori-dm-maker/SESSION_LOG.md:17`

**66.** ✅〔ツール〕**2つの画面が同じ `session_state` キーを共有していた**（`onepiece-dex` / `pokecard-dex`）
片方で選んだタブが、もう片方に無い値のまま残る。**相手のキーで自分のDBを引く**ところだった。
→ `onepiece-dex/SESSION_LOG.md:22`

---

# 付録：検証・自動操作の落とし穴（記事1本にまとめられる小ネタ集）

単独では弱いが、**「見たつもりで見ていなかった話」**として1本にまとめられる。

- `./va.sh shot` の引数は**保存ファイル名でURLではない** → 開きっぱなしの古いタブを撮っていた（`maisoku` / `jyuusetsu`）
- `input[type=file]` が複数あり、**サイドバーの会社ロゴ欄**に当たっていた → `>> nth=1`（`maisoku`）
- pytest が**本物のCLIを呼んで**返ってこない → `conftest.py` で強制的に道具をoff（`agent-platform`）
- Playwright は**50MB超のファイルを転送できない**（アプリ側の制限ではない）（`digital-shosai`）
- `class="hidden"` の `input` にはファイルを渡せない → 一時的に表示してから（`digital-shosai`）
- テキスト一致のセレクタが**本文に先にマッチ**し、「削除」ボタンでなく説明文を押していた（`digital-shosai`）
- `smoke_test.py` をシステムPythonで動かして `ModuleNotFoundError`（`jyuusetsu`）
- パスワード画面を見るために、**secrets を置かない symlink 複製**を作って起動した（`chatwork-ai-manager`）
- zsh の `path` は `PATH` に連動する**特殊変数**で、`for path in ...` がPATHを破壊する（`keyline`）
- Excel の PDF 書き出しが `-50`／オートメーション権限のダイアログが人の画面に出た（`maisoku`）
- mp4 が `moov atom not found` → **書き出し途中だっただけ**。一時名で書いて rename。
  ただし `.mp4.part` にすると **ffmpeg は拡張子でコンテナを決める**ので失敗（`agent-platform`）
- 動画に音が無いと思ったら **Mac本体がミュート**だった（`agent-platform`）

---

## まだ掘っていない層（記録が薄く、書くならコードから）

`handwriting-ocr` / `quote-generator`（別リポジトリ）/ `property-notice-generator` /
`settlement-creator` / `image-resizer` / `file-finder` / `realestate-calc` /
`owner-payout-tracker` / `soufu-maker` / `realestate-valuation` / `building-manager` の一部

`SESSION_LOG.md` が無いか症状の記録が0〜1件。**上の66本を出し切ってから**、コードを読んで
「なぜこう作ったか」を掘り起こす。ここから更に5〜8本は取れる見込み（未検証）。

## 設計判断として書けるもの（不具合ではない題材）

- **作った編集機能を、あとから全部外した**（`building-manager`・表示専用へ。コードは可逆に残置）→ `fc28c47`
- **PNGしか出せないエディタは翌日には使えない**（`madori-tracer`・保存/読込と自動保存を足した）→ `ff8f229`
- **同じ処理の実体を2本持つと片方だけ直る**（共有モジュール化）→ `55be186` `95004e0`
- **公開リポジトリに個人情報が入っていた**（`soufu-generator` の差出人マスタ）→ `97103d8`
- **直下の共有モジュールを import できない**（`sys.path` にリポジトリ直下が無かった）→ `business-plan-generator`
