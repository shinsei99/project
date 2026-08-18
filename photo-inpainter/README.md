# 不動産写真AI（photo-inpainter）

## 運用メモ（ルート CLAUDE.md から移動・2026-08-17）

> 元の見出し: 「不動産写真AI（photo-inpainter）補足 ※不動産・port 8506・完成（2026-08-10）」
> **他PCと共有される情報。** ここを直せば2台で同じ内容になる。

- 物件写真から**電柱・電線・通行人・車・室内の家具**を消すStreamlit。消去エンジンは **LaMa**、クリック選択は **Segment Anything (mobile_sam)**。どちらも **IOPaint（Apache-2.0・商用可）** の実装を`import`して使う。**全処理ローカル・APIキー不要**。
- モードは2つ。**🎯 AI選択**＝物体をクリックすると輪郭を自動抽出（点を足して範囲拡大／青クリックで除外）、**✏️ ブラシ**＝手動（電線など細いものはこちらが確実）。消去を**重ねがけ**でき、↩️元に戻す・複数枚アップロード・ZIP一括ダウンロードに対応。※Houghで電線を追跡する「電線クリック」モードも実装したが、実用性が薄く2026-08-10に削除済み（復活させないこと）。
- **⚠️ Intel Mac は torch==2.2.2 で固定必須（再調査不要）**。torch は **2.2.2 が macOS x86_64 向けの最終ビルド**で、2.3以降は arm64 ホイールしか公開されていない。`requirements.txt` でピン済み（arm64機でも2.2.2で問題なく動く）。
- **経緯（重要・同じ失敗を繰り返さないこと）**: 旧実装は `simple_lama_inpainting` を optional import していたが、これが **requirements.txt に一度も入っていなかった**ため `inpaint_lama()` は常に ImportError → `cv2.inpaint`（TELEA）へ暗黙フォールバックしていた。OpenCVは電線跡が茶色く滲むため「使えない」と判断され開発が止まっていた。**エンジン未導入が原因であってアルゴリズム選定の問題ではなかった。**
- モデルは初回実行時に `~/.cache/torch/hub/checkpoints` へ自動DL（`big-lama.pt` 約200MB / `mobile_sam.pt` 約40MB）。実測: 1600×1067 の電線消去が **CPUで約4秒**（長辺800px超は `HDStrategy.CROP` でマスク周辺だけ切り出して推論するため、原寸のまま高速かつマスク外は無劣化）。SAMは同一画像なら埋め込みを再利用し2回目以降 0.1秒。
- **SAMモデルは切替式**（mobile_sam / vit_b / vit_l / vit_h をサイドバーで選択）。既定は `default_sam_model()` が **MPSあり(Apple Silicon)→vit_b / なし(Intel)→mobile_sam** を自動判定。環境変数 `SAM_MODEL` で上書き可。**実測での注意（再検証不要）**: 軽バンを1クリックした場合 mobile_sam=選択14.2%/1.8s だが輪郭がギザギザで車体外にはみ出す、vit_b=選択5.6%/24.1s でスライドドア1枚を境界正確に選択。**大きいモデル＝広く取れる、ではない**。「意味のまとまり」で正確に切る方向に効くので、車1台なら追加クリック前提。
- `.venv`（1.3GB）と `samples/`（実物件の写真を含む）は**gitignore**。`run.sh` は不動産カテゴリのため `0.0.0.0` バインド。
- **2026-08-17にメインPCへ設置完了**（開発はサブPC・完成は2026-08-10）。launchd `com.shinsei.photo-inpainter`・
  社内LAN共有（`192.168.1.105:8506`）・Desktop の `.app` と Dropbox共有フォルダの `.url`＋`.ico` も設置済み。
- **⚠️ venv は Python 3.9 か 3.11 で作る（3.12は不可・再調査不要）。** `iopaint==1.6.0` が
  **`Pillow==9.5.0` をハード固定**しており、Pillow 9.5.0 には cp312 のホイールが無い
  （3.12だとソースビルドに落ちて失敗する）。9.5.0 のmacOS arm64ホイールは cp38〜cp311 まで。
  実績: `/usr/bin/python3`（3.9.6）で全依存が入り、torch 2.2.2 / streamlit 1.50.0 で稼働。
- アイコンの生成元は `photo-inpainter/icon-src/make_icon.py`（PILでバイオレットの角丸＋写真＋キラッ。
  `.icns` と `.ico` を両方出す）。
