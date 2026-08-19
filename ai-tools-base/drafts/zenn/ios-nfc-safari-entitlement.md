---
title: "iPhoneでNFCを使う社内ツールを作るとき、Safariは最初から選択肢に入らない"
emoji: "🔑"
type: "tech"
topics: ["ios", "nfc", "safari", "capacitor", "appstore"]
published: true
---

鍵の貸出を「タグにかざすだけ」で記録する社内ツールを作りました。

社内ツールはブラウザで開く形がいちばん運用が楽なので、最初はその前提で設計していました。
**その前提が、着手した日のうちに崩れました。**

## 症状：ブラウザからNFCを読む方法が、どう調べても出てこない

Web NFC の記事は見つかるのに、手元の iPhone では動きません。

```js
console.log(typeof NDEFReader); // "undefined"
```

## 原因：Safari は Web NFC に対応していない

iOS / iPadOS / macOS の**いずれの Safari でも `NDEFReader` が存在せず**、
有効化するフラグもありません。Apple はネイティブ向けの Core NFC を提供していますが、
WebKit に Web NFC を入れていません（対応しているのは Chromium 系のブラウザです）。

「まだ実装されていない」ではなく「そのブラウザでは触れない」なので、
**ポリフィルも回避策もありません。** ここで方式を選び直すことになります。

あわせて確認しておくべき制約が2つあります。

- **iPad は NFC リーダー自体が非搭載**。共用端末を置くなら iPhone でなければならない
- NFC 読み取りは iPhone 7 以降、後述のバックグラウンド読み取りは **iPhone XS 以降**

## 直し方：タグ側に URL を書き、OSに開かせる

読む側を作れないなら、**書く側に寄せます。**

NFCタグに **NDEF の URL レコード**を書いておくと、iPhone をかざしただけで通知バナーが出て、
タップすると Safari がその URL を開きます。**アプリのインストールが要りません。**

```
NFCタグ（NDEF: URLレコード）
   → かざす → 通知バナー → タップ
   → Safari が http://<LANのIP>:<port>/t/<token> を開く
   → サーバー側でトークンから対象を引き、貸出画面を出す
```

読み取り機も、端末へのインストールも不要になりました。制約は次のとおりです。

- 画面が点いているときだけ読む
- 通知は**必ずユーザーがタップして承認する**（勝手には開かない）
- NDEF 書き込みが可能なタグが必要（NTAG213/215/216 など）

### 落とし穴：タグに書くURLを「アクセス中のURL」から作らない

サーバー側でタグ用URLを発行するとき、リクエストのホストから組み立てると事故ります。

```python
# ダメ: 管理者が localhost で開いていると localhost 入りのURLが出る
url = f"{request.base_url}t/{token}"
```

これをタグに書くと、**スマホからは自分自身を指すので永久に開けません。**
しかもタグは物理的に書き直しになるため、気づくのが遅いほど痛い。

```python
# 常にLAN側のアドレスを返す関数を通す（環境変数で上書き可能にしておく）
url = f"{lan_base_url()}/t/{token}"
```

## ネイティブアプリ側に寄せる場合：entitlement で弾かれる

タグの実UIDを読みたい、オフラインでも完結させたい、という段になると
Core NFC が要ります。ここで申請が自動で弾かれました。

```
ERROR ITMS-90778: Invalid entitlement ...
'NDEF' is disallowed
```

**新しいSDKでは `com.apple.developer.nfc.readersession.formats` に `NDEF` を含められません。**

```diff
- <array><string>TAG</string><string>NDEF</string></array>
+ <array><string>TAG</string></array>
```

`TAG` セッションから NDEF の読み書きもできるので、**機能は落ちません。**
なお Apple Developer Portal 側で App ID に「NFC Tag Reading」を有効化する手作業も要ります。

### npm パッケージは、名前があっても実在するとは限らない

Capacitor / React Native で候補に挙がるものを、npm の実物まで当たった結果です。

| パッケージ | 可否 |
|---|---|
| `@capgo/capacitor-nfc` | ✅ `sessionType:'tag'` でUIDが取れる |
| `react-native-nfc-manager` | ✅ Expo config plugin 同梱 |
| `@capacitor-community/nfc` | ❌ **npm に存在しない（404）** |
| `@capawesome-team/capacitor-nfc` | ❌ **npm 404**（スポンサー限定レジストリ） |
| `expo-nfc` | ❌ **v0.0.0 のプレースホルダ** |

記事や生成結果で名前を見かけても、`npm view` まで確認しないと設計が空振りします。

## まとめ

- **Safari で NFC は触れない。** 回避策ではなく、方式の選び直しが要る
- 読めないなら**書く側に寄せる**。タグにURLを書けばアプリ無しで動く
- タグに焼くURLは、**アクセス中のホストから組み立てない**（物理的な書き直しになる）
- ネイティブ化するなら entitlement は **`TAG` だけ**（`NDEF` を入れると申請が弾かれる）

なお**NFCタグと実機が手元に無いため、実機での読み取りはまだ検証できていません。**
上のうち「タグにかざすと通知が出るか」だけは仕様の確認どまりである点は、正直に書いておきます。

---

このツール（誰が・何を・いつ持ち出したかを記録する社内の鍵管理）の全体像と、
社外の相手にも貸すことを前提にしたデータ設計は本体にまとめています。

👉 [制作記録：SafariではNFCに触れない。だから「タグにURLを書く」ことにした](https://ai-tools-base.vercel.app/works/keyline)
