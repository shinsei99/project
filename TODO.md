# TODO — 全アプリの索引

> ## 🖥 サブPCで今夜やること（2026-08-17 メインPCから依頼）
>
> **この節を読んだら、まず `git pull` してから下を上から順に実行する。終わったらこの節ごと消す。**
>
> ```bash
> cd ~
> git pull origin main    # ← 先にこれ。8/17にメインPCで .gitignore に許可行を追加してある
>
> # ① 8/16に作った整備ツール5本を、git に載せ直す
> git add SETUP.md dev-doctor.py dev-setup.sh secrets-sync.sh secrets-manifest.txt
> git status --short      # ← 5本が「A 」で並ぶことを目で見る（並ばないなら下の「確認」へ）
> git commit -m "サブPC整備の道具一式（.gitignore許可漏れで未コミットだったもの）"
> git push origin main
>
> # ② メインPCから渡した機密2件を取り込む
> mkdir -p psa-collection/data
> cp ~/Library/CloudStorage/Dropbox-個人/handoff-20260817/psa-collection/data/*.json \
>    psa-collection/data/
> ls -la psa-collection/data/*.json    # ← 入ったことを目で見てから③へ
>
> # ③ 使い終わった受け渡しファイルを Dropbox から消す（機密を置きっぱなしにしない）
> D=~/Library/CloudStorage/Dropbox-個人
> rm -rf "$D/handoff-20260817"                       # ②が終わっていれば用済み
>
> #   ポケモンカード図鑑の 4.0GB tar。**data/ が入っていることを確認してから**消す
> du -sh ~/pokecard-dex/data 2>/dev/null              # 4GB前後あればOK。無ければ先に展開する
> #   → 展開がまだなら: tar -xf "$D/pokecard-dex-handoff/pokecard-dex-data.tar" -C ~/pokecard-dex/
> rm -rf "$D/pokecard-dex-handoff"                    # 確認できてから実行（3.7GB空く）
>
> ls -d "$D"/*handoff* 2>/dev/null                    # ← 何も出なければ片付け完了
> ```
>
> **メインPC側の受け渡しファイルは 2026-08-17 に削除済み**（`handoff-20260815` ＝
> agent-platform の config/knowledge/.env と flyer-creator の .stats_key、5件とも
> メインPCに入っているのを確認済み ／ `chatwork-ai-manager-handoff` 165MB ＝
> サブPCが 8/16 に import 済み。必要になれば `handoff_export.sh` で作り直せる）。
>
> **なぜ①が要るのか（同じ失敗を繰り返さないため）**
> 8/16のコミットは**メッセージに5本が書いてあるのに、中身が入っていなかった**。
> 直下 `.gitignore` は1行目が `*`（全部無視）で、`!` で個別に許可する方式のため、
> 許可行の無い新規ファイルは `git add` してもエラーを出さずに無視される。
> → 直下に新規ファイルを置いたら `git show --stat <コミット>` で実体が入ったか必ず見る。
>
> **確認**: `git add` しても `A ` が出ない場合は `git check-ignore -v secrets-sync.sh` を実行。
> `.gitignore:2:*` と出たら①のpullがまだ効いていない（`git log --oneline -1` が `247d839` 以降か確認）。
>
> **やらなくてよくなったもの**
> - `digital-shosai/.env.local` の受け取り … **メインPCにも存在しない**（あるのは `.env.local.example` だけ）
> - `./secrets-sync.sh import` … 道具がメインPCに無く使えないため、②の手コピーで代替済み
>
> **触らないもの**
> - `ai-tools-lab` … メインPCへ移管済み。サブPCでは開発も公開もしない
> - `chatwork-ai-manager` の worker / LINE webhook / ngrok … メインPCで稼働中。**同時起動禁止**
>
> **ついでに判断してほしい**: サブPCの launchd 常駐2本（file-finder 8520 /
> owner-payout-tracker 8519）がメインPCと二重にLAN公開されている（どちらも個人情報を含む）。
> 止めるなら `launchctl unload ~/Library/LaunchAgents/com.shinsei.<アプリ>.plist`。

**この表だけで「いま何が進行中か」が分かるようにする。** 詳細は書かない。
詳細は各アプリの `<アプリ>/TODO.md` と `<アプリ>/SESSION_LOG.md` にある。

書き方: 1アプリ1行。終わったら行を消す（記録はアプリ側のログに残るので消してよい）。

| アプリ | いまの状態 / 次にやること | 最終更新 |
|---|---|---|
| pokecard-dex | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え | 2026-08-14 |
| flyer-creator | チラシクリエーター。型10種はagent-platform共通（直すのはagent-platform/core）。下帯ロゴ＋メイン写真の切取位置(上下)スライダー追加。次は物件データの未決3点 | 2026-08-16 |
| agent-platform | 講演スライドを .pptx で作り直し（4:3・型8種）＋フリー素材自動補充（Openverse）。11枚の通し実行は成功、**見栄えの目視確認が未了**。作り込みはいったん停止 | 2026-08-15 |
| ai-tools-lab | AIツールラボ。**メインPCで受領済み（2026-08-17: npm install／validate 通過）**。残: `npx vercel login` → `npx vercel link`（team: brain-dump / project: ai-tools-lab）と、Zenn/note 5本ずつの公開（8/17 19:56以降・1日2本まで）。Vercelは手動デプロイ `npx vercel --prod` | 2026-08-17 |
| scrapmemo-petapeta | スクラップ編集の先頭表示を修正＋ボタンを末尾へ。Web版は公開済み。1.0.3/build7 をASCへアップ済み。**残: ASCでビルド7を選び審査提出** | 2026-08-17 |
| chatwork-ai-manager | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。**常駐4サービスはメインPCで稼働中／サブPCは引き継ぎ受領済みで画面8540のみ起動**（worker・ngrokは1台のみ・同時起動禁止）。次はアプリ側TODO.mdを現状に更新 | 2026-08-16 |

## 横断作業（複数アプリにまたがるもの）

- **サブPCで `git pull` → 整備ツール5本をコミットし直す**（`SETUP.md` / `dev-doctor.py` /
  `dev-setup.sh` / `secrets-sync.sh` / `secrets-manifest.txt`）。2026-08-16のコミットに
  **実体が入っていなかった**（直下 `.gitignore` が「全部無視→`!`で個別許可」方式で許可行が無かった）。
  許可行は2026-08-17にメインPCで追加・push済み。
- ~~メインPCで `./secrets-sync.sh export`~~ → 上記のとおり道具がメインPCに無いため**手渡しで代替済み**
  （2026-08-17）。`Dropbox-個人/handoff-20260817/` に `psa-collection/data/{orders,albums}.json` を配置。
  **`digital-shosai/.env.local` はメインPCにも存在しない**（`.env.local.example` のみ）ので運べない＝要件取り下げ。
  残: サブPCで受け取り（フォルダ内の `引き継ぎ-先に読む.txt` のとおり）
- **ai-tools-lab: Zenn 5本 / note 5本の公開待ち。** Zennの投稿上限が **8/17 19:56** に解ける。
  1日2本ずつ Zenn→note の順で。手順は `ai-tools-lab/drafts/PUBLISH.md`
- サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）を
  止めるか要判断（メインPCと二重にLAN公開されている・個人情報を含む）

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
