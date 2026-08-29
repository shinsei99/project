# ネオンブロック（neon-blocks）

全100面のポリオミノパズル。**ゲーム本体は `index.html` の1枚**（`www/index.html` は Capacitor が包む用の同じもの）。
App Store には **1.0.3 / build 4 が配信中**（2026-08-24 に API で確認）。

## iOS のこと

- **`ios/` は git に入っていない。** 別PCや作り直しのときは `npx cap add ios` から作る
- **そのとき `MinimumOSVersion`（動く最低のiOS）が既定の 13.0 に戻る**ので、下の値を入れ直すこと

### MinimumOSVersion は 15.0 にしてある（2026-08-28）

**2027年春以降、iOS 15.0 未満のアプリは App Store へアップロードできなくなる**
（アップロード時に Apple から警告 90068 が出る）。配信中の build 4 は **13.0** のままなので、
**次に更新するときに 15.0 で出す**。設定はこのMacで済ませてあり、**ビルドは通ることを確認済み**
（`** BUILD SUCCEEDED **`）。まだ Archive もアップロードもしていない。

```
ios/App/Podfile                        platform :ios, '15.0'
ios/App/App.xcodeproj/project.pbxproj  IPHONEOS_DEPLOYMENT_TARGET = 15.0（4か所）
→ 変えたら pod install
```

**機種が切り捨てられる心配はほぼない。** iOS 13 が動く機種（iPhone 6s 以降）は
そのまま iOS 15 にも上げられるため、影響するのは「OSを更新していない人」だけ。

### 次に出すときの手順

```bash
cd ~/neon-blocks
npx cap sync ios
cd ~ && ./ios-build-guard.sh neon-blocks --bump     # ★build 5 以上へ（配信中は build 4）
```

Archive〜アップロードは GUI 不要。`scrapmemo-petapeta/RELEASE_NOTES.md` 末尾の3コマンドと同じ
（このアプリも Capacitor＝CocoaPods なので **`-workspace ios/App/App.xcworkspace`** を使う）。
