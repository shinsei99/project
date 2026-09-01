# spacemarket-monitor（SpaceMarket 3施設の現状モニタ・新誠）

新誠プロパティマネジメントが SpaceMarket で運営する3施設の現状を、**読み取り専用**で
取得してレポートにする道具。TODO#98「3施設の利用促進・露出強化」の材料を作る。

| 施設 | URL |
|---|---|
| グリーンガーデン加東 | https://www.spacemarket.com/p/ePrMgAswaWYsjRzN |
| レセプル福島 | https://www.spacemarket.com/p/vom4LWVk4aNaD22Z |
| グリーンガーデン秋津 | https://www.spacemarket.com/p/Ew0cUleoB6xuwfHu |

## 使い方

```bash
./run.sh public   # 公開ページから現状を取る（ログイン不要・すぐ動く）
./run.sh login    # ホスト管理画面に「人が」1回だけ手動ログイン（Chromeが開く）
./run.sh host     # 実績レポートを作る（普段はこれ。RESTを直接叩くので速い）
./run.sh dump     # 管理画面を丸ごと巡回して保存（作りが変わったときの調査用）
```

出力は `reports/`（Markdown）と `local/`（生データ）。**どちらも git に入れない**
（このリポジトリは public。管理画面側には予約実績・売上が載る）。

## 設計上の決まり（守ること）

### 1. パスワードをこのツールに持たせない

`login.py` は**画面を開くだけ**で、ID・パスワードは人がキーボードで入力する。
ログイン後の Cookie が `local/profile` に残り、2回目からは無人で動く。

こうしている理由:

- 認証情報をリポジトリにも自動処理にも置かないため
- 2要素認証・CAPTCHA・見慣れない端末の確認メールが出ても、人が対処すれば通るため
  （パスワード直打ちの自動ログインは、これらが出た瞬間に動かなくなる）

### 2. 読み取り専用

掲載内容・料金・露出設定を**変更するコードは1行も置いていない**。
変更はオーナーの承認を挟んで別途行う（2026-08-31 のオーナー回答＝
「まず現状確認のみ。確認後に改善提案、良ければ承認して次に設定変更」）。

### 3. 相手のサーバーに負荷をかけない

1ページごとに `sm.POLITE_WAIT_SEC`（3秒）待つ。並列で叩かない。

**利用規約の確認結果（2026-09-01）**: [利用規約](https://www.spacemarket.com/about/terms/)
第9条の禁止行為に「スクレイピング」「クローラー」「自動化プログラム」という語は**無い**。
ただし第9条1項(9)に「当社による本サービスの運営を妨害するおそれのある行為」がある。
自社アカウントで自社の掲載を低頻度で読むだけ、という今の使い方はこれに当たらないと
判断しているが、**高頻度化・他社スペースの収集へ広げない**こと。

### 4. 管理画面は REST API を直接叩く（画面を読まない）

`host_dump.py` で巡回して分かったが、管理画面は裏で REST API を叩いている。
**HTMLを解析するより、この API を直接 GET するほうが速くて壊れにくい**ので、
`host_check.py` はそうしている。

```
GET https://mp-gateway.spacemarket.com/rest/1/owners/<slug>/rooms
GET .../analytics?grouping=monthly&date_range_type=year&year=YYYY
GET .../calendar?year=YYYY&month=M
GET .../search/reservations?filter=not_reply&...
```

**★Cookie では通らない（500 が返る）。** 次の3つのヘッダが要る。

| ヘッダ | 中身 |
|---|---|
| `authorization` | `Bearer <Firebase のセッショントークン>`。**短命** |
| `x-api-key` | 画面に埋め込まれている固定キー |
| `spacemarket-version` | `2019-06-28` |

Bearer が短命なので**値を保存しない**。`host_check.py` は実行のたびに管理画面を
1枚開き、画面が出すリクエストからヘッダを拾って、そのプロセスのメモリ内だけで使う。
**認証情報はリポジトリにもディスクにも残らない。**

広告出稿（スペマサーチ広告）の申込状況だけは JSON が無いので画面の文字を読む。

### 5. ホスト向けの公開APIは無い（2026-09-01 調査）

公開されている開発者向けAPIは見つからなかった。ホスト用には
[SPACEMARKET for HOST アプリ](https://academy.spacemarket.com/up-to-date_hostapp/)が
あるだけで、掲載や予約を外部から操作する公式APIは公開されていない。
よって管理画面側はブラウザ操作で取る（＝`login.py` / `host_dump.py`）。

## 調べて分かったこと（次の担当が同じ調査をしないため）

### 公開ページは `__NEXT_DATA__` を読めばよい

掲載ページは Next.js で、`<script id="__NEXT_DATA__">` にページの元データが
JSON でそのまま入っている。**HTMLの見た目をセレクタで拾う必要はない**ので、
デザイン変更で壊れない。取れるもの:

- 単価（時間/日）・プラン・**即予約可否**・最低利用時間・清掃オプション
- レビュー数/点数と5項目の内訳・直近の利用日・写真枚数・定員・面積
- **ホストアカウントの評価指標**（ランク / 返信の速さ / 返信率 / 承認しやすさ）
  → SpaceMarket 内の検索順位に効く数値。露出強化の話はここが起点になる

### レビュー内訳が 0 で返る施設がある（バグではない）

レセプル福島・グリーンガーデン秋津は `reputationSummary` の5項目内訳が
すべて 0 で返る（総合点と件数は正しい）。グリーンガーデン加東は入っている。
**0 を「評価0点」として表示すると誤読する**ので、レポートでは「—」にしている。

### URL

| 用途 | URL | 備考 |
|---|---|---|
| ログイン | https://www.spacemarket.com/login/ | |
| ホスト管理画面 | https://dashboard.spacemarket.com/ | 未ログインだと **401** を返す＝ログイン判定に使える |

`www.spacemarket.com` は末尾スラッシュ無しのURLに **308** を返す。
Python の urllib は `redirect_request` が 301/302/303/307 しか許可しておらず
（308 が入るのは 3.11 以降。`agent-platform/.venv` は **3.9.6**）、素のままだと
全ページ 308 で落ちる。`public_check.py` の `_Redirect308` が**コードを307に読み替えて**
追わせている。

## ファイル

| ファイル | 役割 |
|---|---|
| `sm.py` | 共通（プロファイル・ブラウザ起動・ログイン判定・JST日付） |
| `public_check.py` | 公開ページから現状取得（ログイン不要・Playwright不要） |
| `login.py` | 人が1回だけ手動ログインしてセッションを保存 |
| `host_check.py` | **実績レポート**（REST APIを直接叩く。普段はこれ） |
| `host_dump.py` | 管理画面を丸ごと巡回して保存（作りが変わったときの調査用） |
| `facilities.json` | 3施設の定義 |
| `run.sh` | 入口。Playwright入りの Python を自動で選ぶ |
