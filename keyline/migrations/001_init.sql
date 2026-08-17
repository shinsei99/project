-- KeyLine 001_init.sql — 初期スキーマ
--
-- 運用像（2026-08-17確定）
--   鍵ボックスの横に **鍵管理用スマホ1台**（共用）を置く。
--   NFCタグにかざす → Safari が開く → 「誰に貸すか」を選んで［貸出する］。
--   アプリ本体とDBは **メインPC（192.168.1.105:8534）**。社内LAN限定。
--
-- ★この運用から導かれる、いちばん大事な設計判断
--   「アプリを操作する人」と「鍵を借りる人」は **別のテーブル**にする。
--     users     … アプリを操作できる人（管理者・鍵管理端末）。少数・パスワードを持つ
--     borrowers … 鍵を借りる人（社員・業者・内見客）。多数・ログインしない
--   社外の業者や内見客にも貸すため、借主を users（ログインできる人）に紐づけると
--   破綻する。社員も borrowers 側に置いて、貸出先を1つの一覧で扱えるようにしている。
--
-- Postgres への移行を意識した書き方
--   * id は TEXT の UUID（PG の uuid 型へキャストできる）
--   * 時刻は TEXT の ISO8601 UTC（'2026-08-17T10:32:00Z'）。文字列のまま正しく
--     時系列にソート・比較でき、PG では timestamptz へキャストできる
--   * organization_id を全テナントテーブルに持たせる（今は値が1種類だけ）
--   * 外部キーは接続ごとに PRAGMA foreign_keys = ON が必要（db.py が必ず設定する）

-- ---------------------------------------------------------------------------
-- 組織
-- ---------------------------------------------------------------------------
CREATE TABLE organizations (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ---------------------------------------------------------------------------
-- 操作アカウント（アプリにログインできる人）
--
--   'admin'    … 管理画面すべて。管理対象の登録・編集、強制返却、利用者管理
--   'operator' … 鍵管理端末。貸出・返却と、貸出先の追加だけができる
--
-- 鍵管理端末は operator アカウント1つでログインしっぱなしにする。
-- 「操作した社員」は記録しない方針（2026-08-17決定）。現場で毎回1タップ増えるのを避けるため。
-- 責任の所在は borrowers（誰が持っているか）で追う。
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    -- PBKDF2-HMAC-SHA256。salt と反復回数も同じ文字列に含める
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('admin', 'operator')),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX idx_users_email      ON users (email);
CREATE        INDEX idx_users_org_active ON users (organization_id, is_active);

-- ---------------------------------------------------------------------------
-- ログインセッション（Cookie の実体）
--
-- 署名付きCookieだけで済ませずサーバー側にも持つのは、退職者や紛失した端末を
-- 即座に締め出すため。行を消せばそのCookieはその瞬間に無効になる。
-- ---------------------------------------------------------------------------
CREATE TABLE sessions (
    id           TEXT PRIMARY KEY,            -- セッショントークン（256bit乱数のhex）
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at   TEXT NOT NULL,
    user_agent   TEXT
);

CREATE INDEX idx_sessions_user    ON sessions (user_id);
CREATE INDEX idx_sessions_expires ON sessions (expires_at);

-- ---------------------------------------------------------------------------
-- 貸出先（鍵を借りる人）
--
--   'employee' … 自社の社員
--   'vendor'   … 業者（客付け業者・リフォーム・清掃・鍵屋）。繰り返し貸すのでマスタ化が効く
--   'customer' … 内見のお客様など、一度きりのことが多い相手
--
-- 名前・会社名・電話は OCR（免許証・名刺）でも埋められるが、
-- **必ず人が確認・修正してから保存する**。OCRの誤読をそのまま台帳にしない。
-- ---------------------------------------------------------------------------
CREATE TABLE borrowers (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL DEFAULT 'vendor'
                    CHECK (kind IN ('employee', 'vendor', 'customer', 'other')),
    name            TEXT NOT NULL,            -- '田中一郎'
    company         TEXT,                     -- '〇〇工務店'
    phone           TEXT,
    note            TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_borrowers_org      ON borrowers (organization_id, is_active, kind);
CREATE INDEX idx_borrowers_org_name ON borrowers (organization_id, name);

-- ---------------------------------------------------------------------------
-- 鍵ボックス
-- ---------------------------------------------------------------------------
CREATE TABLE boxes (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,            -- 'BOX-01'
    name            TEXT NOT NULL,            -- '本社1F鍵ボックス'
    location        TEXT,                     -- '本社1F 事務所奥'
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE UNIQUE INDEX idx_boxes_org_code ON boxes (organization_id, code);

-- ---------------------------------------------------------------------------
-- 管理対象（Asset）= NFCタグ1枚 = 1つの貸出管理単位
--
-- ★ここがこのシステムの芯。「鍵1本」ではなく「実際に貸出・返却する単位」を1行にする。
--   鍵3本セットでも1行。構成する鍵の実物は asset_items に入る。
--
-- NFC について（ご指示5の構造をそのまま実装している）
--   NFCタグ → nfc_identifier → assets → asset_items(鍵番号)
--   * nfc_identifier は **鍵番号ではない**。管理対象を特定するためだけの識別子
--   * タグを交換しても assets.id は変わらないので、履歴も構成品も維持される
--   * nfc_source は値の出どころ。今は 'written_token'（こちらが生成してタグに書いた
--     URL用のトークン）。将来ネイティブアプリで実タグUIDを読む方式に替えても
--     'tag_uid' を入れるだけでよく、スキーマ変更が要らない
-- ---------------------------------------------------------------------------
CREATE TABLE assets (
    id                  TEXT PRIMARY KEY,
    organization_id     TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,        -- '本社正面入口'
    asset_type          TEXT NOT NULL DEFAULT 'key'
                        CHECK (asset_type IN ('key', 'tool', 'card', 'device', 'other')),

    nfc_identifier      TEXT,                 -- NULL可（タグ貼付前に登録できる）
    nfc_source          TEXT CHECK (nfc_source IN ('written_token', 'tag_uid')),

    box_id              TEXT REFERENCES boxes(id) ON DELETE SET NULL,
    box_position        TEXT,                 -- '03'

    status              TEXT NOT NULL DEFAULT 'in_stock'
                        CHECK (status IN ('in_stock', 'checked_out', 'lost', 'repair', 'disabled')),
    current_borrower_id TEXT REFERENCES borrowers(id) ON DELETE SET NULL,
    checked_out_at      TEXT,
    due_at              TEXT,

    note                TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- 状態と借主の食い違いを DB 側で禁じる。
    -- アプリのバグで「貸出中なのに借主が空」「保管中なのに借主が残っている」が起きると、
    -- 誰が持っているか分からなくなる＝このシステムの存在意義が消える。
    CHECK (
        (status =  'checked_out' AND current_borrower_id IS NOT NULL AND checked_out_at IS NOT NULL)
     OR (status <> 'checked_out' AND current_borrower_id IS     NULL AND checked_out_at IS     NULL)
    ),
    -- nfc_identifier と nfc_source は必ず揃って入る（片方だけを禁じる）
    CHECK ((nfc_identifier IS NULL) = (nfc_source IS NULL))
);

-- NFC識別子の一意性。
-- ご指示20は「organization単位で」だが、ここは **意図的に全体で一意**にしている。
-- URL が /t/<token> の形で組織を含まないため、全体一意でないと
-- どの組織の管理対象か決まらず解決できないから。全体一意は組織単位一意を満たす（より厳しい）。
CREATE UNIQUE INDEX idx_assets_nfc ON assets (nfc_identifier) WHERE nfc_identifier IS NOT NULL;

CREATE INDEX idx_assets_org_status   ON assets (organization_id, status);
CREATE INDEX idx_assets_org_box      ON assets (organization_id, box_id, box_position);
CREATE INDEX idx_assets_org_borrower ON assets (organization_id, current_borrower_id);
-- 返却期限超過の抽出用（貸出中のものだけ見ればよい）
CREATE INDEX idx_assets_due          ON assets (organization_id, due_at) WHERE status = 'checked_out';

-- ---------------------------------------------------------------------------
-- 構成品（Asset Item）= 管理対象に含まれる実物
--
-- item_number は **鍵本体に刻印されている番号**。システムが採番するものではない。
--
-- ★(asset_id, item_number) に UNIQUE を張っていないのは意図的。
--   「同じ鍵番号の合鍵2本セット」が現実に存在するため。ここを一意にすると登録できなくなる。
-- ---------------------------------------------------------------------------
CREATE TABLE asset_items (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    asset_id        TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    item_type       TEXT NOT NULL DEFAULT 'key'
                    CHECK (item_type IN ('key', 'card', 'tool', 'device', 'other')),
    item_number     TEXT,                     -- '12345'（刻印番号）
    label           TEXT,                     -- '玄関/ディンプル' など補足
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_asset_items_asset  ON asset_items (asset_id, sort_order);
CREATE INDEX idx_asset_items_number ON asset_items (organization_id, item_number);

-- ---------------------------------------------------------------------------
-- 貸出履歴（checkout_logs）
--
-- 1行 = 1回の貸出。借りた時に INSERT し、返した時に同じ行へ returned_at を入れる。
-- 「いま貸出中」は returned_at IS NULL の行が表す。
--
-- 身分証・名刺の画像について（2026-08-17決定）
--   * 撮影した画像は data/id_images/ に置き、パスだけをここに持つ（DBに画像を入れない）
--   * **返却から30日で自動削除**する。消したら id_image_purged_at を立て、
--     「撮ったが今は無い」と「そもそも撮っていない」を区別できるようにする
--   * 消すのは purge_images.py（Phase 5）。data/ は .gitignore 済み
--
-- ★ idx_checkout_open が二重貸出を防ぐ最後の砦。
--   1つの管理対象について「未返却の行」は同時に1本しか作れない。
--   アプリ側のif文ではなく **DBの制約**で守るので、同時アクセスでも破れない。
-- ---------------------------------------------------------------------------
CREATE TABLE checkout_logs (
    id                  TEXT PRIMARY KEY,
    organization_id     TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    asset_id            TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    borrower_id         TEXT NOT NULL REFERENCES borrowers(id),

    action              TEXT NOT NULL DEFAULT 'checkout'
                        CHECK (action IN ('checkout', 'returned')),
    checkout_at         TEXT NOT NULL,
    due_at              TEXT,
    returned_at         TEXT,
    -- 'normal'      … 鍵管理端末で普通に返却した
    -- 'admin_force' … 管理者が管理画面から強制返却した（ご指示11）
    return_type         TEXT CHECK (return_type IN ('normal', 'admin_force')),

    -- 貸出時に撮った身分証・名刺
    id_image_path       TEXT,                 -- 'id_images/2026/08/<uuid>.jpg'
    id_image_kind       TEXT CHECK (id_image_kind IN ('drivers_license', 'business_card', 'other')),
    id_image_purged_at  TEXT,                 -- 自動削除した時刻

    note                TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    -- 返却済みの行は returned_at / return_type / action が必ず揃う
    CHECK (
        (returned_at IS     NULL AND return_type IS     NULL AND action = 'checkout')
     OR (returned_at IS NOT NULL AND return_type IS NOT NULL AND action = 'returned')
    ),
    -- 返却が貸出より前になることはない
    CHECK (returned_at IS NULL OR returned_at >= checkout_at),
    -- 画像を撮ったなら種類も必ず入る
    CHECK ((id_image_path IS NULL) = (id_image_kind IS NULL)),
    -- 撮っていないものを「削除した」ことにはできない
    CHECK (id_image_purged_at IS NULL OR id_image_path IS NOT NULL)
);

-- ★二重貸出の防止（DBレベル）
CREATE UNIQUE INDEX idx_checkout_open ON checkout_logs (asset_id) WHERE returned_at IS NULL;

-- ★履歴を並べるときは必ず ORDER BY checkout_at DESC, rowid DESC と書くこと。
--   時刻だけでは全順序を保証できない（2026-08-17に実際に踏んだ）。ミリ秒まで持っても、
--   同一ミリ秒に2件入れば順序が決まらず、最新1件を取り違える。
--   rowid は挿入順に増える SQLite の暗黙列なので、これをタイブレークに使えば必ず一意に決まる。
--   Postgres へ移すときは rowid が無いので、seq bigserial を足して置き換えること。

CREATE INDEX idx_checkout_org_asset    ON checkout_logs (organization_id, asset_id,    checkout_at DESC);
CREATE INDEX idx_checkout_org_borrower ON checkout_logs (organization_id, borrower_id, checkout_at DESC);
CREATE INDEX idx_checkout_org_time     ON checkout_logs (organization_id, checkout_at DESC);
-- 画像の自動削除バッチが「返却済み・画像あり・未削除」を引くため
CREATE INDEX idx_checkout_purge        ON checkout_logs (returned_at)
    WHERE id_image_path IS NOT NULL AND id_image_purged_at IS NULL;

-- ---------------------------------------------------------------------------
-- updated_at の自動更新
-- アプリ側で書き忘れても必ず現在時刻になるようにする。
-- WHEN 句が無いと UPDATE が自分自身を再帰的に呼ぶため、条件を必ず付けること。
-- ---------------------------------------------------------------------------
CREATE TRIGGER trg_organizations_updated AFTER UPDATE ON organizations
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
    BEGIN UPDATE organizations SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_users_updated AFTER UPDATE ON users
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
    BEGIN UPDATE users SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_borrowers_updated AFTER UPDATE ON borrowers
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
    BEGIN UPDATE borrowers SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_boxes_updated AFTER UPDATE ON boxes
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
    BEGIN UPDATE boxes SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_assets_updated AFTER UPDATE ON assets
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
    BEGIN UPDATE assets SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_asset_items_updated AFTER UPDATE ON asset_items
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
    BEGIN UPDATE asset_items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id; END;

-- ---------------------------------------------------------------------------
-- 組織をまたいだ参照を禁じる
--
-- Postgres+RLS が無い今、テナント分離を守るのはこの層しかない。
-- 「A社の管理対象に B社のボックスを紐づける」「B社の貸出先に貸す」を
-- **DBが拒否する**ようにしておく。アプリのバグでは破れない。
-- ---------------------------------------------------------------------------
CREATE TRIGGER trg_assets_org_guard_ins BEFORE INSERT ON assets
FOR EACH ROW BEGIN
    SELECT RAISE(ABORT, 'box belongs to another organization')
    WHERE NEW.box_id IS NOT NULL
      AND (SELECT organization_id FROM boxes WHERE id = NEW.box_id) <> NEW.organization_id;
    SELECT RAISE(ABORT, 'borrower belongs to another organization')
    WHERE NEW.current_borrower_id IS NOT NULL
      AND (SELECT organization_id FROM borrowers WHERE id = NEW.current_borrower_id) <> NEW.organization_id;
END;

CREATE TRIGGER trg_assets_org_guard_upd BEFORE UPDATE ON assets
FOR EACH ROW BEGIN
    SELECT RAISE(ABORT, 'box belongs to another organization')
    WHERE NEW.box_id IS NOT NULL
      AND (SELECT organization_id FROM boxes WHERE id = NEW.box_id) <> NEW.organization_id;
    SELECT RAISE(ABORT, 'borrower belongs to another organization')
    WHERE NEW.current_borrower_id IS NOT NULL
      AND (SELECT organization_id FROM borrowers WHERE id = NEW.current_borrower_id) <> NEW.organization_id;
END;

CREATE TRIGGER trg_asset_items_org_guard BEFORE INSERT ON asset_items
FOR EACH ROW BEGIN
    SELECT RAISE(ABORT, 'asset belongs to another organization')
    WHERE (SELECT organization_id FROM assets WHERE id = NEW.asset_id) <> NEW.organization_id;
END;

CREATE TRIGGER trg_checkout_org_guard BEFORE INSERT ON checkout_logs
FOR EACH ROW BEGIN
    SELECT RAISE(ABORT, 'asset belongs to another organization')
    WHERE (SELECT organization_id FROM assets WHERE id = NEW.asset_id) <> NEW.organization_id;
    SELECT RAISE(ABORT, 'borrower belongs to another organization')
    WHERE (SELECT organization_id FROM borrowers WHERE id = NEW.borrower_id) <> NEW.organization_id;
END;

-- ---------------------------------------------------------------------------
-- 管理画面用のビュー（ご指示13・14）
-- 経過時間と超過判定まで DB 側で出しておき、画面側で計算しない。
-- ---------------------------------------------------------------------------
CREATE VIEW v_asset_overview AS
SELECT
    a.id,
    a.organization_id,
    a.name,
    a.asset_type,
    a.status,
    a.nfc_identifier,
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
    -- 貸出からの経過分数
    CASE WHEN a.checked_out_at IS NULL THEN NULL
         ELSE CAST((julianday('now') - julianday(a.checked_out_at)) * 1440 AS INTEGER)
    END AS elapsed_minutes,
    -- 返却予定超過（1=超過）
    CASE WHEN a.status = 'checked_out' AND a.due_at IS NOT NULL
              AND strftime('%Y-%m-%dT%H:%M:%fZ', 'now') > a.due_at
         THEN 1 ELSE 0
    END AS is_overdue,
    -- 鍵番号を '12345 / 12346 / 12347' の形で1列に畳む
    (SELECT group_concat(i.item_number, ' / ')
       FROM (SELECT item_number FROM asset_items
              WHERE asset_id = a.id AND item_number IS NOT NULL
              ORDER BY sort_order, created_at) i
    ) AS item_numbers,
    (SELECT COUNT(*) FROM asset_items WHERE asset_id = a.id) AS item_count
FROM assets a
LEFT JOIN boxes     b  ON b.id  = a.box_id
LEFT JOIN borrowers br ON br.id = a.current_borrower_id;

-- 貸出先の一覧（「最近の貸出先から選ぶ」用）。
-- 直近に借りた順で出すため、最終貸出日時と回数を数えておく。
CREATE VIEW v_borrower_usage AS
SELECT
    br.*,
    (SELECT MAX(checkout_at) FROM checkout_logs WHERE borrower_id = br.id) AS last_checkout_at,
    (SELECT COUNT(*)         FROM checkout_logs WHERE borrower_id = br.id) AS checkout_count,
    (SELECT COUNT(*) FROM checkout_logs
      WHERE borrower_id = br.id AND returned_at IS NULL)                   AS open_count
FROM borrowers br;
