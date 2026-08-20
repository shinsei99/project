# TODO — AI重説調査〜Excel自動入力

## 進行中・未了

- [ ] **ストリートビューが社内画面で 403**。`GOOGLE_MAPS_WEB_KEY` のリファラ制限が
      `https://daikyocorp.co.jp/*` のみ。**Google Cloud Console の設定なので人がやる**。
      推奨は「Maps Embed だけに絞ったキーを新規作成して社内画面用に使う」（README 参照）
- [ ] **e-Stat（人口・世帯数）が未実装**。`population_service.get_population()` は
      地域名を抜き出すだけでAPIを呼んでいない。**appId 登録が前提**。
      解き方: 住所 → 緯度経度 → 国土地理院 逆ジオコーディングで市区町村コード →
      e-Stat `statsDataId` + `cdArea`（部品は `realestate-valuation/services/geo_service.py` にある）
- [ ] 防火地域・高度地区の入手経路が無い（不動産情報ライブラリに該当レイヤが無いことは確認済み）。
      自治体の都市計画図しか無いなら「要確認」で固定する方針を決める

## 完了（2026-08-20）

- [x] 用途地域を XKT001 → **XKT002** に修正し、プロパティ名・単位も実測に合わせた
- [x] 最寄りポリゴンでの代用に 100m の上限（2.9km 先を返す事故を防止）
- [x] ジオコーディングを Google 併用（ROOFTOP のときだけ採用）＋ 画面に出典を表示
- [x] ストリートビューの節を追加（撮影時期の表示・印刷不可の注意）
