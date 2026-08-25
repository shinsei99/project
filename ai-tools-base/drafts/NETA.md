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

**2.** ✅〔不動産〕**CLIの絶対パス決め打ちで、別のPCではAIが黙って無効になる**（`tokuyaku-generator` / `baikai-generator` / `restoration-calculator` / 直下 `registry_parser.py`）
`/opt/homebrew/bin/claude` 固定。Intel Mac や `~/.local/bin` では見つからず、正規表現の簡易版で動き続けていた。
→ `55be186` `514b104`、`registry_parser.py:29-50`

**6.** ⚠️〔不動産〕**本番の常駐だけが違うPythonで動いている**（`chatwork-ai-manager`）
worker は launchd の `/usr/bin/python3`。`requests` 前提のモジュールを足すと本番だけ ImportError になる。
「HTTPは urllib を使う」という制約が `requirements.txt` に書いてある理由。
→ `chatwork-ai-manager/SESSION_LOG.md:27`

---

# B. 常駐・デプロイ — 「直したのに反映されない」

**12.** ✅〔不動産〕**常駐が Dropbox の権限をまれに失う → 自分で死んで生き返る**（`parking-map`）
権限エラーが連続したら**自終了して KeepAlive で再起動**。**30分5回の上限**で無限ループを防ぐ。
→ `8c002b5`

**13.** ⚠️〔不動産〕**launchd の常駐は CloudStorage を読めない／TCCの責任プロセスは `/bin/bash`**（`shorui-cabinet`）
Python 本体に許可を与えても効かず、`/bin/bash` にフルディスクアクセスを与えると通る。
→ メモリ `reference_launchd_cloudstorage_fda.md`、`shorui-cabinet/README.md`

**15.** ⚠️〔メディア〕**Vercel は git 連携ではない／`--scope` が要る**（`ai-tools-base`）
push しても本番は変わらない。`whoami` は通るのにデプロイが `Not authorized`（プロジェクトはチームの持ち物）。
→ `77c1dd6`、`ai-tools-base/CLAUDE.md`

**16.** ✅〔メディア〕**Zenn は投稿上限に当たると「成功」と出たまま黙って未反映**（`ai-tools-base`）
自動再試行もされない。24時間空けて空コミットで再push。**待ち時間で見分けられる**（正常なら約30秒〜1分）。
→ `ai-tools-base/SESSION_LOG.md` 2026-08-22

---

# C. 帳票の見た目 — Excel / Word を人に配れる形にする

**17.** ✅〔不動産〕**Excelに貼った写真が縦に潰れる**（`maisoku-converter`）
列幅→ptの換算が `幅×7px` で**2割狭く**、`TwoCellAnchor` がセル範囲まで引き伸ばしていた。
Excel に実測させた **`_PT_PER_CHAR = 6.0`** と **`OneCellAnchor`（実寸をEMUで固定）** へ。
実測 帯1150.00pt / 画像1149.75pt・縦横比0.8141。
→ `46ce8c7`

**18.** ✅〔不動産〕**openpyxl の内部APIを触ったら、Excelが「修復」して題字が消えた**（`chatwork-ai-manager`）
列幅の単位を合わせようと `wb._named_styles["Normal"].font` を書き換えたのが原因。
→ `chatwork-ai-manager/SESSION_LOG.md:201`

**19.** ✅〔不動産〕**Wordの表に罫線が出ない**（`chatwork-ai-manager`）
`Table Grid` スタイルの解釈が**ビューア依存**。`w:tblBorders` を直接書く＋`autofit = False`。
→ `chatwork-ai-manager/SESSION_LOG.md:270`

**20.** ✅〔不動産〕**Wordのページ末尾に `□` が残る**（`chatwork-ai-manager`）
`add_page_break()` が空段落を足し、直前の箇条書きスタイルを引き継いでいた。
見出し段落の `page_break_before` へ。あわせて箇条書きのぶら下げインデント。
→ `chatwork-ai-manager/SESSION_LOG.md:274-279`

**21.** 🔍〔不動産〕**帳票を「A4 1枚」に収め続ける**（`restoration-calculator`）
文字切れ・行間・縦フィット・項目追加のたびの調整。17番と9本目（行の高さ）に続く帳票三部作の3本目。
→ `f9d7407` `b60afd4` `91cc68a`、`services/pledge_export_service.py`

**22.** ⚠️〔不動産〕**直すと今まで配った帳票の見た目が変わる、という理由で直していないバグ**（`maisoku-converter`）
帯の「建設業免許番号」が横向きのとき担当者欄へはみ出す。**直せるのに直さない判断**を書ける珍しい題材。
→ `maisoku-converter/SESSION_LOG.md:197`

**23.** ✅〔不動産〕**スライダーの表示が 0.005 なのに 0.01 と出る**（`maisoku-converter`）
`st.slider` の既定書式が小数2桁。刻みを 0.005 にしたので丸められていた。`format="%.3f"`。
→ `maisoku-converter/SESSION_LOG.md:260`

---

# D. 紙を読む — PDF・公式書式・謄本

**24.** ✅〔不動産〕**実物の謄本で10項目中0項目しか取れない**（`jyuusetsu-research`）
合成テストでは通っていた。登記事項証明書は**罫線アート（`┏━━┯┃`）の表**で、見出しが
`所 在` `① 地 番` のように**半角スペース混じり**。自前パーサは全角スペース前提だった。
→ `jyuusetsu-research/SESSION_LOG.md:393`

**25.** ✅〔不動産〕**正規表現が罫線を値として拾う**（`jyuusetsu-research`）
種類の欄に `│ ② 構 造 │ ③ 床 面 積 ㎡ │ 原因及びその日付…` が入り、本体の値まで上書きしていた。
`re.search` で1件目に決め打ちすると見出し行を拾って終わる。
→ `jyuusetsu-research/SESSION_LOG.md:24`

**26.** ✅〔不動産〕**Excelの見出しから入力欄を割り出す（11/17 → 17/17）**（`jyuusetsu-research`）
①見出しは左だけでなく**上の列見出し**にもある ②**結合セルは左上以外の値が None**。
上下両方を探し、結合セルの左上を解決する索引を作った。
→ `jyuusetsu-research/SESSION_LOG.md:445`

**27.** ✅〔不動産〕**同梱テンプレートに他社の実案件が残っていた**（`jyuusetsu-research`）
白紙だと思っていた `templates/*.xlsx` 4本が記入済みファイル。書式は3〜9項目しか上書きしないので、
**残りが前案件のまま出る**。作った書類に身に覚えのない会社名が載る事故。
→ `jyuusetsu-research/SESSION_LOG.md:440`

**28.** ✅〔不動産〕**チェック欄の「外側の□」を指していた**（`jyuusetsu-research`）
災害3項目の割り当て先が、中身が `□` のセルで、しかも3項目とも「外」側。公式書式25本すべてで実測して判明。
→ `jyuusetsu-research/SESSION_LOG.md:198`

**29.** ✅〔不動産〕**土地専用の書式には「土地／建物」の目印が無い**（`jyuusetsu-research`）
1つしかないので書かれていない。シート名から側を決める。**「無いことが情報」**という話。
→ `jyuusetsu-research/SESSION_LOG.md:210`

**30.** ✅〔不動産〕**同名の書式が3つあり、先に見つかったほうを拾っていた**（`jyuusetsu-research`）
一般売主／宅建業者売主／消費者契約用。媒介が大半なので**一般売主が正しい既定**。
賃貸側では部分一致で「サブリース住宅賃貸借契約書」を拾っていた（→前方一致を先に見る）。
→ `jyuusetsu-research/SESSION_LOG.md:265` `347`

**31.** ⚠️〔不動産〕**旧Word(.doc)を、表を壊さずに .docx へ変換する**（`jyuusetsu-research`）
`python-docx` は `.doc` を読めない。AppleScript の `save as` は現行Wordで `-1708`。
`textutil`→RTF→`pandoc` に切り替え、`\'xx`(CP932) だけを Unicode エスケープに変換。
→ `9aaf254`、`jyuusetsu-research/SESSION_LOG.md:405`

**32.** ⚠️〔不動産〕**PDF・画像の向きを、読ませる前に自動で直す**（全アプリ横断の共有モジュール）
スキャンPDFが横向き・逆さのままAIに入ると精度が落ちる。`pdf_orient.py` を全アプリへ。
→ `b77e692`、メモリ `reference_pdf_orient.md`

**33.** ⚠️〔不動産〕**旧Excel(.xls)から画像を取り出す**（`kato-flyer` / `maisoku-converter`）
OLEセクタとBIFFの CONTINUE、**二段の分断**を解く。LibreOffice を使わない実装。
→ メモリ `reference_xls_images.md`

---

# E. AIを道具として使う — モデル・SDK・プロンプト

**34.** ✅〔不動産〕**`--allowedTools` は自動承認リストであって禁止リストではない**（`agent-platform`）★セキュリティ
「入れなければ Bash は使えない」と思っていたが、**実際には実行できた**（`echo TESTOK` が通る）。
権限設計の話として単独で強い。
→ `agent-platform/SESSION_LOG.md:315`

**35.** ✅〔不動産〕**モデルが提供終了して 404 になる**（`agent-platform`）
`gemini-2.0-flash is no longer available`。キーは有効なので認証エラーと紛らわしい。
使えるモデルは `client.models.list()` で確認する。
→ `agent-platform/SESSION_LOG.md:243`

**36.** ✅〔不動産〕**SDKごと廃止された**（`agent-platform`）
`google-generativeai` が提供終了。`google-genai` へ全面移行（呼び方も変わる）。
→ `agent-platform/SESSION_LOG.md:246`

**37.** ✅〔不動産〕**「思考」にも出力トークンを使うモデル**（`agent-platform`）
長いプロンプトで `max_output_tokens=4000` だと思考で使い切り、**本文が空か途中で切れる**。
JSONが壊れて別経路へフォールバックし、遅くなっていた。
→ `agent-platform/SESSION_LOG.md:249`

**38.** ✅〔不動産〕**タイムアウトを指定しないと待ち続ける**（`agent-platform`）
画像生成のテストが5分以上ハング。`types.HttpOptions(timeout=…)` を指定。**1枚60秒**で成功。
→ `agent-platform/SESSION_LOG.md:254`

**39.** ✅〔不動産〕**AIが書いたファイルの末尾にタグが混入していた**（`agent-platform`）
全31ファイルの末尾に `</content>`。`pip install -r requirements.txt` が
`Invalid requirement: '</content>'` で失敗して発覚。
→ `agent-platform/SESSION_LOG.md:239`

**40.** ✅〔不動産〕**「本文に書くな」と言っていなかったので内部記号が漏れた**（`chatwork-ai-manager`）
日報の要約に「（★発言0件）」。★が本人印であることは伝えたが、出力するなとは書いていなかった。
→ `chatwork-ai-manager/SESSION_LOG.md:340`

**41.** ✅〔不動産〕**設定ファイルにコメントを書いたら壊れた**（`agent-platform`）
`mcp.json` に `_comment` を足したら `Invalid MCP configuration`。厳密JSONのみ。説明は別ファイルへ。
→ `agent-platform/SESSION_LOG.md:313`

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

**47.** ✅〔不動産〕**Chromeの自動ダウンロード制限で、5本中1本しか落ちない**（`jyuusetsu-research`）
一括ダウンロードが途中で止まる。**自動では回避しない**（人が1回「常に許可」を押す）と決めた話。
→ `jyuusetsu-research/SESSION_LOG.md:448`

---

# G. 日本語のデータ

**48.** ✅〔不動産〕**全角マイナス U+2212 で住所を分割できない**（`jyuusetsu-research`）
`-－ー‐` は入れていたが「−」が抜けていた。**ハイフンに見える7種**を入れて解決。
→ `jyuusetsu-research/SESSION_LOG.md:344`

**49.** ⚠️〔不動産〕**FAX番号が全角・ハイフン混じりで検索に当たらない**（`tsuikyaku-crm`）
電話・郵便番号・氏名の姓名間スペースまで広げて「日本語業務データの正規化」として書ける。
→ `0982064` `177d8c5`

**50.** ✅〔ツール〕**IMAPのフォルダ名が NFD で持たれていて一致しない**（`mail-archiver`）
デコードは正しいのに「ポータル」と比較して不一致（`ホ`+`゚`）。表示名だけ NFC 正規化し、原本は触らない。
→ `aeb509b`、`mail-archiver/SESSION_LOG.md:21`

**51.** ✅〔不動産〕**住所文字列から正規表現で市区町村を抜くと「区」が落ちる**（`chatwork-ai-manager` / `jyuusetsu-research`）
人口の括弧内が「大阪府大阪市」になり実データ（中央区）と食い違った。
API が返す**正式名称**（`metaGetFlg=Y`）を使う。
→ `jyuusetsu-research/SESSION_LOG.md:499`

**52.** ✅〔不動産〕**日本語には語の区切りが無いので、法令名が前の語とくっつく**（`tokuyaku-generator`）
「重要事項の説明は宅地建物取引業法第35条」が引けない。末尾2〜12文字の候補を長い順に当てて**完全一致**を採る。
さらに `{2,30}` にしていたため**2文字の「民法」が条件を満たさなかった**。
→ `tokuyaku-generator/SESSION_LOG.md:16-20`

---

# H. 外部API

**54.** ⚠️〔不動産〕**ストリートビューが社内画面で403**（`jyuusetsu-research`）
既存キーのHTTPリファラ制限が `daikyocorp.co.jp` 限定で、127.0.0.1 が許可外。
**Maps Embed API だけに制限した専用キー**を新規作成（アプリ制限は付けない。ポートが変わるため）。
→ `f77f76a`、`jyuusetsu-research/SESSION_LOG.md:451`

**55.** ✅〔不動産〕**「キーはあるのに常に空」— APIの取り違えとズームの間引き**（`jyuusetsu-research`）
用途地域が常に空だったのは **XKT001 と XKT002 の取り違え**。さらに、同じ地点でも
**高ズームでは地物が間引かれる**（XKT014 は z14 で1件・z15 で0件）ので、
**各レイヤで使えるいちばん粗いズーム**を使う。
→ `539b1ed`、`jyuusetsu-research/SESSION_LOG.md:206`

**56.** ✅〔不動産〕**APIが既に「%」付きで返すのに、こちらも付けて `80%%`**（`jyuusetsu-research`）
`_with_percent()` で重複を防ぎ、`"60.0%"` は `60%` に正規化。小さいが誰でも踏む。
→ `jyuusetsu-research/SESSION_LOG.md:490`

**57.** ✅〔不動産〕**e-Gov は条の絞り込みができず全文を返す**（`tokuyaku-generator`）
民法1.7MB・借地借家法1.4MB。初回が数十秒。`.egov-cache/` に7日キャッシュ。
→ `tokuyaku-generator/SESSION_LOG.md:21`

**58.** ✅〔ツール〕**GETは200なのに中身が空。POSTでないと返さない**（`onepiece-dex`）
公式カードリストが 51KB（選択肢のみ）で返る。`POST` にすると 463KB。
→ `onepiece-dex/SESSION_LOG.md:176`

**59.** ✅〔ツール〕**相場データは「平均が空で最安だけ入る」ことがある**（`pokecard-dex`）
取引平均だけを見ていたので481件が画面から消えた。しかもそのとき `trend` に **0 が入る**。
→ `pokecard-dex/SESSION_LOG.md:64`

---

# I. データベースと並行処理

**60.** ✅〔不動産〕**`executescript()` は実行前に暗黙COMMITする**（`keyline`）
外側の `BEGIN` が消えてマイグレーションが失敗。`BEGIN`/`COMMIT` を**スクリプト文字列の中**に書く。
適用記録のINSERTも同じスクリプトに入れて原子性を保つ。
→ `keyline/SESSION_LOG.md:137`

**61.** ✅〔不動産〕**時刻だけでは全順序を保証できない**（`keyline`）
同一秒に貸出が2件入り `ORDER BY checkout_at` の順序が決まらない。
**ミリ秒に上げても同一ミリ秒に2件入るので解決しない** → `ORDER BY checkout_at DESC, rowid DESC`。
→ `keyline/SESSION_LOG.md:142`

**62.** ✅〔ツール〕**`executescript()` は busy_timeout を無視する**（`onepiece-dex`）
`database is locked` で落ちる。同じDBに `execute("BEGIN IMMEDIATE")` を投げたほうは**46秒待って成功**（実測）。
60番と同じ関数の別の顔なので、2本立てにもできる。
→ `onepiece-dex/SESSION_LOG.md:180`

**63.** ✅〔ツール〕**Streamlit は再実行のたびに別スレッド**（`mail-archiver`）
`@st.cache_resource` でSQLite接続を使い回して `ProgrammingError`。`check_same_thread=False`。
→ `mail-archiver/SESSION_LOG.md:43`

**64.** ✅〔不動産〕**DBの `datetime('now')` はUTC**（`chatwork-ai-manager`）
生成時刻が「05:43」（実際は14:43）。**表示だけ +9h**し、DBの値は他テーブルと揃えたまま、という判断。
→ `chatwork-ai-manager/SESSION_LOG.md:337`

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
