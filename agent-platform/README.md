# マルチプロダクション（agent-platform）— オールインワン・マルチエージェント制作基盤

「新規事業の企画を、調査からパワポ・ナレーション・解説動画・SNS告知文まで一式作って」
という**抽象的な1文**を投げると、11の部隊が順に動いて成果物一式を出す。

- 画面: Streamlit（**port 8532** / `127.0.0.1` バインド＝社内LANには公開しない）
- CLI: `python main_orchestrator.py "指示文"`
- 出力: `output/<ジョブID>/` にジャンル別のフォルダで保存

---

## 0. メインPCへの引き継ぎ手順

git clone しただけでは動きません。**3つだけ手作業が要ります。**

```bash
cd agent-platform
cp .env.example .env
./run.sh                      # .venv を作って依存を入れる（初回5分ほど）
```

### ① Gemini APIキーを .env に入れる（必須）

このMacでは既存アプリのキーを流用しています。メインPCでも同じキーが使えます。

```bash
# キーの在処（どれも同じ値）
grep GEMINI_API_KEY ../brain-dump/.env.local
cat ../madori-tracer/.secret_key
```
`.env` の `GEMINI_API_KEY=` に貼る。**課金される機能は既定で全部オフ**（`AP_ALLOW_PAID=0`）。

### ② `claude` CLI が使えること（必須）

司令塔・法務・最終確認が使います。`which claude` で出ればOK。

### ③ 素材と学習データを持っていく（任意）

どちらも公開リポジトリに入れていないので、**Dropbox等で手渡し**します。

| フォルダ | 中身 | 無いとどうなるか |
|---|---|---|
| `assets/` | ダウンロードした素材（いらすとや等） | 記号だけで作る。**再配布禁止なのでgit不可** |
| `knowledge/` | 部隊の申し送り（学習データ） | ゼロから学び直す。成果物の中身が混ざるためgit不可 |

アイコン（Material Symbols）と日本語フォント（Noto Sans JP）は**初回に自動取得**するので、
持っていく必要はありません。

### 確認

```bash
.venv/bin/python main_orchestrator.py --doctor
```
「Claude Code CLI ✅」「Google Gemini ✅」「アイテム全部✅」なら準備完了です。

### 社内LANで社員に使ってもらう場合

`run.sh` の `--server.address` を `127.0.0.1` → `0.0.0.0` に変え、launchd に登録すれば
`192.168.1.105:8532` で全員が使えます。**物件情報や個人情報を扱うので社内WiFi内限定**。
他の不動産カテゴリのアプリと同じ扱いです。

---

## 1. 環境構築

```bash
cd agent-platform
cp .env.example .env      # 使うAPIキーだけ入れる（空でも動く）
./run.sh                  # 初回は .venv を作って依存を入れる（数分）
```

`./run.sh` は http://localhost:8532 で画面を開く。CLIだけで使う場合は:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main_orchestrator.py --doctor    # ← まずこれで接続状況を確認
```

### `--doctor` で分かること

どのAIに接続できるか、役割ごとにどれが割り当たるか、画像・音声・動画のバックエンドは何か、
必要なライブラリと ffmpeg が揃っているか。**作業前に必ずこれを見る。**

---

## 2. 費用の方針 — 全部無料の範囲で動かす

`AP_ALLOW_PAID=0`（既定）の間、**課金される機能は一切呼ばない**。

| やらないこと | 理由 |
|---|---|
| AI画像生成（Gemini画像 / DALL-E 3 / Stability） | **無料枠が無い**（2026-08-14 確認）。日本語の文字も崩れる |
| Veo（画像→動画） | 無料枠なし・**秒課金**（fast $0.10/秒）。しかも実測で**元の写真に無い建物を作った**ので、実在物件の広告には使えない |

| 代わりに使うもの | 費用 |
|---|---|
| 実写真のアップロード | 無料（物件・商品の広告では**そもそも必須**） |
| HTML+CSS → Playwright で作図 | 無料・1枚2秒・**日本語が崩れない** |
| ケンバーンズ（ffmpegのズーム/パン） | 無料・1カット2秒・**写真の中身は変わらない** |
| Gemini のテキストモデル | 無料枠あり |
| claude CLI | キー不要 |

有料機能を使いたいときだけ `.env` で `AP_ALLOW_PAID=1`。

---

## 3. 部隊と使用API

| # | 部隊 | 役割 | 使用API・技術 | キーが無いとき |
|---|---|---|---|---|
| 1 | 🧭 司令塔 | 指示を作業計画に分解 | Claude（API / `claude` CLI） | 雛形の計画を作る |
| 2 | 🔍 リサーチャー | 市場調査・資料読み込み | Google Gemini（長文） | 項目だけの雛形 |
| 3 | 📝 企画・構成ライター | 構成・ナレーション・画像コンテ | Claude / GPT-4o | 定型の8章構成 |
| 4 | 🎨 ビジュアル制作 | 実写真の割り当て＋文字入りカードの作図 | **実写真 ＋ HTML/CSS→Playwright（無料）** | Pillowで簡易画像 |
| 5 | 📊 パワポビルダー | `.pptx` 組版 | python-pptx（ローカル） | 常に動く |
| 6 | 🔊 AIボイス | ナレーション合成 | OpenAI TTS / ElevenLabs / gTTS | 尺だけ合わせた無音WAV |
| 7 | 🎬 動画プロデューサー | 画像＋音声→`.mp4` | moviepy + FFmpeg | `render.sh` を出力 |
| 8 | ⚡ 高速チェッカー | 原稿の破綻検証 | Groq（Llama系） | 機械チェックのみ実施 |
| 9 | 📣 SNS発信 | X・YouTube・ブログ告知文 | 軽量LLM | 原稿から機械生成 |
| 10 | ⚖️ 法務・コンプラ監査 | 著作権・景表法・薬機法・炎上 | Claude / GPT-4o | 禁止表現の正規表現チェック |
| 11 | 🧪 テスト・QA | 成果物の検品＋自動テスト | pytest | 常に動く |

**各部隊は道具を持つ**: claude CLI 経由のとき、全部隊が **WebFetch / WebSearch / 資料フォルダの読み取り**
を使える（`AP_AGENT_TOOLS=on`）。URLを渡せば実際にページを開いて読む。
これが無いとマルチエージェントは Claude Code 単体の**下位互換**になってしまうため、
「単体と同じ道具を全部隊に配る」ことを前提にしている。
`Bash` / `Write` / `Edit` は既定で渡さない（部隊がPCを書き換える事故を避けるため。`.env` で追加可）。

**設計の芯**: どの部隊もキーが無ければ「縮退モード」で雛形を出して次へ渡す。
1つのAPI未設定でパイプライン全体が止まらないようにしてある。
縮退した工程は画面・レポートで ⚠️ 表示になるので、成果物を鵜呑みにする事故は起きない。

---

## 4. 実行の流れ

一列に流すのではなく、**依存の無い部隊は同時に走る**。
さらに**司令塔が「今回要らない部隊」を最初に外す**（チラシ1枚に動画部隊は出てこない）。

```
司令塔（作るものを決める）
  └→ リサーチャー ─→ 企画構成 ─┬→ 高速チェック ┐
                                 └→ 法務監査 ───┴→ 司令塔（中間調整・原稿を直す）
                                                     ├→ 画像生成 ─┬→ パワポ
                                                     ├→ 音声合成 ─┴→ 動画
                                                     └→ SNS告知
                                                                   └→ 検品/QA
```

- **確認を先に行う**: 実行を押すと、司令塔が「答えによって成果物が変わること」だけを
  最大3つ聞き返す（無ければ聞かずに進む）。枚数などの設定は画面に置かない。
- **司令塔は最初と中間の2回関与する**。中間では、レビューと法務の指摘を読んで
  **制作に入る前に原稿を直す**（動画まで作ってから直すのが一番高くつくため）。

工程間の受け渡しは `JobContext.state` の辞書で行う。

| キー | 作る部隊 | 中身 |
|---|---|---|
| `plan` | 司令塔 | タイトル・対象・目的・枚数・尺 |
| `research` | リサーチャー | 調査結果（`verified` フラグ付き） |
| `deck` | 企画構成 | スライド配列（見出し/箇条書き/ナレーション/画像プロンプト） |
| `images` `audio` | 画像・音声 | 各スライドのファイルパスと実尺 |
| `pptx` `video` | パワポ・動画 | 成果物のパス |
| `review` `legal` `qa` | チェック系 | 指摘一覧 |

`deck` が全成果物の原本。ここを直せば以降すべてに反映される。

---

## 5. 出力フォルダ

```
output/20260814-153000/
├── input/      アップロードされた資料
├── plan/       job_plan.json, deck.json, narration.md
├── research/   research.md / research.json
├── images/     slide_01.png …
├── slides/     <タイトル>.pptx
├── audio/      narration_01.mp3 …
├── video/      <タイトル>.mp4（または render.sh）
├── social/     social.md（X・YouTube・ブログ）
├── reports/    report.md, review.md, legal.md, qa.md
├── run.log     進捗ログ（JSONL）
└── job.json    ジョブの全状態
```

---

## 6. 実測値（2026-08-14・Intel Mac / 4枚構成）

| 工程 | 所要 | 備考 |
|---|---|---|
| 司令塔（claude CLI） | 33秒 | |
| リサーチャー | 2分45秒 | 9項目・うち7項目は「要確認」 |
| 企画・構成ライター | 32秒 | 4枚・ナレーション587文字 |
| 画像生成（Gemini） | **60秒/枚** | 599KB/枚 |
| 音声合成（gTTS） | 3秒/枚 | 4本で2分13秒の尺 |
| 動画書き出し | **1080pで約10分** | → 既定を**720p＋veryfast**に変更して短縮 |

**動画が重いとき**は `.env` の `AP_VIDEO_WIDTH/HEIGHT`（既定1280×720）、
`AP_VIDEO_PRESET`（既定 `veryfast`）、`AP_VIDEO_FPS`（既定24）を下げる。

**ナレーションの音量**は画面のスライダー、または `.env` の `AP_AUDIO_VOLUME`（1.0=原音）で変える。
画面のスライダーが `.env` より優先される。

---

## 7. 調べて分かったこと（再調査不要）

- **Geminiは `google-genai`（新SDK）で使う。** 旧 `google-generativeai` は提供終了。
  madori-tracer も新SDKで動いているので合わせた。
- **`gemini-2.0-flash` は提供終了（404）。** 既定は `gemini-3.5-flash` に更新済み。
  使えるモデルは `client.models.list()` で確認できる。
- **Gemini の画像生成モデル（`gemini-3.1-flash-image`）が使えるので、OpenAIキーが無くても
  実画像を作れる。** キーは madori-tracer / brain-dump と同じものが使い回せる
  （madori-tracer は `.secret_key`、brain-dump は `.env.local` に置いている。中身は同一）。
- **google-genai のタイムアウトはミリ秒指定**（`types.HttpOptions(timeout=...)`）。
  指定しないと応答が来ないとき無限に待つ（実際に5分以上ハングした）。
- **書き出し途中の mp4 は `moov atom not found` で再生できない。** moviepy はヘッダを最後に書くため。
  一時ファイル名で書いてから rename し、完成品だけが最終パスに出るようにしてある。
- **このMacに ffmpeg は入っていない。** `imageio-ffmpeg` の同梱バイナリを
  `IMAGEIO_FFMPEG_EXE` に流し込んで moviepy に使わせている（`agents/video_editor.py`）。
- **moviepy は v1系と v2系で API名が違う**（`set_audio`/`set_duration` → `with_audio`/`with_duration`、
  `moviepy.editor` の廃止）。どちらでも動く互換シムを入れてある。
- **Python は 3.9.6（システム標準）**。`str | None` などの PEP604 記法は使えないので
  `Optional[str]` で書くこと。
- **LLMのJSON出力は素の `json.loads` では取れない**（前置き・```フェンス・後書きが付く）。
  `core/llm.extract_json` が括弧の対応を数えて切り出す。文字列内の `}` も誤検出しない。
- **Streamlit は `--server.address` 省略時の既定が `0.0.0.0`**（＝LAN公開）。
  このアプリはツール分類なので `run.sh` で `127.0.0.1` を明示している。

---

## 8. よくある操作

```bash
# 一部の工程だけ試す（構成の作り直しなど）
.venv/bin/python main_orchestrator.py "…" --only planner,ppt

# 重い動画工程を飛ばす
.venv/bin/python main_orchestrator.py "…" --skip video

# 資料を渡す（テキストは調査に、画像はスライドに使われる）
.venv/bin/python main_orchestrator.py "…" --input 市場データ.csv 現場写真.jpg

# 技術ログまで見る
.venv/bin/python main_orchestrator.py "…" --verbose

# テスト（外部APIを一切叩かないので無料・オフラインで通る）
.venv/bin/python -m pytest -q tests
```

---

## 9. 注意

- **法務監査は法的助言ではない。** 人が最終確認すること。
- **リサーチャーはWeb検索を繋いでいない**（LLMの知識のみ）。数値は `verified=false` が付く。
  外部に出す資料では必ず裏取りする。
- **SNSへの自動投稿はしない。** 文面を作るところまで。投稿は人が確認してから。
- `.env` と `output/` は **gitignore 済み**（このリポジトリは public）。
