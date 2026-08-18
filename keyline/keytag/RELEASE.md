# KeyTag — 配信手順

| | |
|---|---|
| ホーム画面の表示名 | **KeyTag** |
| App Store の掲載名（案） | **KeyTag ー 鍵の貸出管理** |
| Bundle ID | `com.shinsei99.keytag` |
| Team ID | `773DPMVW7Q`（既存6本と同じ） |
| 現在 | **1.0.0 / build 1**（未提出） |

App Store の掲載名を「KeyTag」単体にできない理由:
**同名アプリが既にある**（深圳市立显通科技有限公司・Utilities・
apps.apple.com/us/app/keytag/id1574286726）。掲載名は世界で一意である必要があるため、
「ー 鍵の貸出管理」を足して一意にする。ホーム画面の表示名は `KeyTag` のままなので
利用者から見た名前は変わらない。掲載名に「鍵」「貸出」「管理」が入るぶん検索にも有利。

---

## 🔴 提出前に必ず必要な作業（コードでは解決できない）

**Apple Developer Portal で App ID `com.shinsei99.keytag` に
「NFC Tag Reading」ケーパビリティを有効化する。**

これが無いと、`com.apple.developer.nfc.readersession.formats` エンタイトルメントを
持つプロビジョニングプロファイルが作られず、**実機でタグを読んだ瞬間に必ず失敗する**。
アーカイブ自体は通ってしまうので、気づくのが遅くなりやすい。

```
developer.apple.com → Certificates, IDs & Profiles → Identifiers
  → com.shinsei99.keytag → Capabilities → NFC Tag Reading にチェック → Save
```

---

## アーカイブの手順

```bash
cd ~/keyline/keytag

# ① Web資産をiOSへ反映（www/ を直したら必ず）
npx cap sync ios

# ② ビルド番号の衝突チェック（★これを飛ばさない）
cd ~ && ./ios-build-guard.sh keyline/keytag

# ③ Xcodeを開く
cd ~/keyline/keytag && npx cap open ios
```

Xcode で:

1. スキーム `App` / 実行先を **Any iOS Device (arm64)** にする
2. `Product > Archive`
3. Organizer が開いたら `Distribute App`

### ⚠️ 再配信のときは必ずビルド番号を +1

CLAUDE.md の再発防止ルール。2026-07-22 に photo-remake / neon-blocks で
**build 1 のまま再アーカイブし、古い（修正前の）ビルドが配信された**事故がある。

```bash
./ios-build-guard.sh keyline/keytag --bump    # 自動で +1
```

---

## App Store Connect に入れるもの

| 項目 | 内容 |
|---|---|
| 名前 | KeyTag ー 鍵の貸出管理 |
| サブタイトル | NFCタグをかざして誰が借りたか記録 |
| カテゴリ | ビジネス（またはユーティリティ） |
| 年齢制限 | 4+ |

### 審査ノート（Review Notes）に必ず書くこと

> このアプリはNFCタグの読み書きを行うため、**動作確認には物理的なNFCタグ
> （NTAG213/215/216 等）が必要**です。タグが無い場合は、「書き込み」画面で
> 内容を入力すると、タグに書き込まれる文字列とバイト数がその場で表示されるため、
> 機能の確認が可能です。
>
> 「設定 > サーバー連携」は**任意の機能**で、自社サーバーをお持ちの方のみが使います。
> 設定しなくても、鍵の登録・貸出・返却・台帳のすべてが端末内で動作します。

★ここが審査の要。**サーバー連携は任意で、単体で全機能が使える**ことを明示する。
審査員は社内LANに入れないので、これを書かないと「動かない」と判断されかねない。

### プライバシー

- 収集するデータ: **なし**（すべて端末内の localStorage に保存）
- サーバー連携を設定した場合のみ、利用者が指定したサーバーへ送信される
- プライバシーポリシーのURLが必要（未作成）

---

## 実機が手に入ったら確認すること

タグと実機が無いと検証できない項目。**ここが通って初めて完成**。

- [ ] 起動時に右上が「**NFC 利用可**」になる（ブラウザ表示のままなら実機判定に失敗）
- [ ] 「タグを読み取る」でiOSの読み取りシートが出る
- [ ] まっさら（未フォーマット）のタグでもUIDが読める ← **TAGエンタイトルメントの確認**
- [ ] 「タグに書き込む」で NTAG213 に書ける
- [ ] 書いたタグをかざすと内容が出る
- [ ] 貸出 → 再度かざす → 返却 が端末内だけで通る
- [ ] サーバー連携（6桁コード）が通り、貸出がKeyLine側にも反映される
- [ ] 平文 `http://192.168.1.105:8534` へ接続できる（ATS例外の確認）
- [ ] 「ローカルネットワーク上のデバイスへの接続」の許可ダイアログが出る

---

## iOSプロジェクトを作り直すとき

`ios/` は gitignore（Xcodeの生成物で巨大なため）。他PCや作り直しでは:

```bash
cd ~/keyline/keytag && ./setup-ios.sh
```

**`npx cap add ios` だけでは足りない。** NFCのエンタイトルメントもATS例外も付かず、
実機でタグを読んだ瞬間に失敗する。`setup-ios.sh` が全部まとめて当てる。

---

## ビルド確認の記録

2026-08-18 時点、いずれもエラー・警告ゼロ:

```
シミュレータ (Debug)  ** BUILD SUCCEEDED **
実機向け   (Release)  ** BUILD SUCCEEDED **
```

出来上がったバンドルの中身も確認済み:
表示名 KeyTag / `com.shinsei99.keytag` / 1.0.0 (1) /
`NFCReaderUsageDescription` あり / `NSAllowsLocalNetworking` あり /
Web資産6ファイル / アイコン 1024×1024。
