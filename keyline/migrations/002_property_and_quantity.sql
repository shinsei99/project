-- KeyLine 002 — 物件名称と、鍵番号ごとの本数
--
-- 実務の形に合わせる（2026-08-17・利用者からの指摘）。
--
--   1つの箱に鍵が60本ほど入っていて、1件はこう表される:
--
--       BOX 01 / 位置 03
--         物件名称  大京本社ビル
--         鍵の名称  1階エントランスキー
--         鍵番号    10001 ×1 / 10002 ×1        （番号違いが1本ずつ）
--                   または 10003 ×3            （同じ番号が3本）
--
-- 足りなかったもの
--   * 物件名称の欄が無く、名前1つに「大京本社ビル 1階エントランスキー」と
--     混ぜて入れるしかなかった。60本の中から物件で探せない
--   * 同じ番号が3本のとき `10003, 10003, 10003` と3回打つことになっていた
--
-- なぜ物件名称を assets 側に置くか（boxes 側ではない）
--   1つの箱に複数物件の鍵が同居するため。箱に持たせると表現できない。
--   物件マスタ（別テーブル）にはしない。住所などを持たせる要件がまだ無く、
--   マスタを作ると「登録しないと鍵を作れない」手間が増えるだけだから。
--   表記ゆれは入力欄の候補表示（datalist）で抑える。

-- ---------------------------------------------------------------------------
-- 物件名称
-- ---------------------------------------------------------------------------
ALTER TABLE assets ADD COLUMN property_name TEXT;

-- 「大京本社ビルの鍵を全部出す」を引くための索引
CREATE INDEX idx_assets_property ON assets (organization_id, property_name);

-- ---------------------------------------------------------------------------
-- 鍵番号ごとの本数
--
-- 1行 = 1つの鍵番号 ＋ その本数。
-- 「10003が3本」を3行にせず1行にするのは、現場の数え方と揃えるため。
-- 既存行はすべて1本として扱う（DEFAULT 1）。
-- ---------------------------------------------------------------------------
ALTER TABLE asset_items ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1
    CHECK (quantity >= 1 AND quantity <= 99);

-- ---------------------------------------------------------------------------
-- 一覧用ビューを作り直す
--   * property_name を出す
--   * 鍵番号は「10001 ×1 / 10003 ×3」の形に畳む（1本のときは ×1 を出さない）
--   * total_keys ＝ 実際の鍵の総本数。返却時に本数を数え合わせるのに使う
-- ---------------------------------------------------------------------------
DROP VIEW v_asset_overview;

CREATE VIEW v_asset_overview AS
SELECT
    a.id,
    a.organization_id,
    a.property_name,
    a.name,
    -- 一覧や検索でまとめて扱いたいので、繋いだ表示名もここで作っておく
    CASE WHEN a.property_name IS NULL OR a.property_name = '' THEN a.name
         ELSE a.property_name || ' / ' || a.name END AS full_name,
    a.asset_type,
    a.status,
    a.nfc_identifier,
    a.box_id,
    a.box_position,
    a.note,
    b.code                AS box_code,
    b.name                AS box_name,
    a.current_borrower_id,
    br.name               AS borrower_name,
    br.company            AS borrower_company,
    br.phone              AS borrower_phone,
    br.kind               AS borrower_kind,
    a.checked_out_at,
    a.due_at,
    CASE WHEN a.checked_out_at IS NULL THEN NULL
         ELSE CAST((julianday('now') - julianday(a.checked_out_at)) * 1440 AS INTEGER)
    END AS elapsed_minutes,
    CASE WHEN a.status = 'checked_out' AND a.due_at IS NOT NULL
              AND strftime('%Y-%m-%dT%H:%M:%fZ', 'now') > a.due_at
         THEN 1 ELSE 0
    END AS is_overdue,
    -- '10001 / 10003 ×3' の形
    (SELECT group_concat(disp, ' / ') FROM (
        SELECT CASE WHEN quantity > 1 THEN item_number || ' ×' || quantity
                    ELSE item_number END AS disp
          FROM asset_items
         WHERE asset_id = a.id AND item_number IS NOT NULL
         ORDER BY sort_order, created_at)
    ) AS item_numbers,
    (SELECT COUNT(*)          FROM asset_items WHERE asset_id = a.id) AS item_count,
    (SELECT IFNULL(SUM(quantity), 0) FROM asset_items WHERE asset_id = a.id) AS total_keys
FROM assets a
LEFT JOIN boxes     b  ON b.id  = a.box_id
LEFT JOIN borrowers br ON br.id = a.current_borrower_id;
