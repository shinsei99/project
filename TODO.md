# TODO — 全アプリの索引

**この表だけで「いま何が進行中か」が分かるようにする。** 詳細は書かない。
詳細は各アプリの `<アプリ>/TODO.md` と `<アプリ>/SESSION_LOG.md` にある。

書き方: 1アプリ1行。終わったら行を消す（記録はアプリ側のログに残るので消してよい）。

| アプリ | いまの状態 / 次にやること | 最終更新 |
|---|---|---|
| pokecard-dex | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え | 2026-08-14 |
| flyer-creator | チラシクリエーターに改称（旧 kato-flyer）。型1→10種・配色切替。git登録済み・CLAUDE.mdツールに登録。次は物件データの未決3点 | 2026-08-15 |
| agent-platform | 講演スライドを .pptx で作り直し（4:3・型8種）＋フリー素材自動補充（Openverse）。11枚の通し実行は成功、**見栄えの目視確認が未了**。作り込みはいったん停止 | 2026-08-15 |
| chatwork-ai-manager | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。4サービスlaunchd稼働・大京商事グループ＋個人チャット監視。**機密引き継ぎはDropbox-個人のtar**（handoff_export/import.sh）。画面port8540(flyer-creator=8529と分離済) | 2026-08-16 |

## 横断作業（複数アプリにまたがるもの）

- **CLAUDE.md のスリム化（メインPCで実施予定・2026-08-15決定）**
  現状19,159字。うち**55%（約10,500字）がアプリ個別の補足**（psa-collection 3,539字／
  agent-platform 2,064字／photo-inpainter 1,518字／pdf-organizer 1,128字 ほか）。
  これを**各アプリの README.md へそのまま移し、CLAUDE.md には1行のポインタだけ残す**。
  狙い: CLAUDE.md は全セッション・全ターンに乗る固定費のため、半分以下（約8,700字）にする。
  **注意**: 移す前に `.gitignore` に許可行が要る。`photo-inpainter/` `pdf-organizer/` は
  フォルダごと無視されており、README を作っても**他PCへ渡らない**（README自体もまだ無い）。
  共通ルール（PDCA・バインド先・iOS再配信・ポート一覧・アプリ一覧）は**CLAUDE.mdに残す**。
- **agent-platform をメインPCで動かすには別途ファイルが要る**（gitに入れていない）:
  `config/`（会社名・免許番号などの発行者情報）、`knowledge/`（学習データ。物件名が混ざる）、
  `.env`（`.env.example` をコピーしてGeminiキーを入れる）。Dropbox等で渡す。
