"""初期セットアップ。組織と最初のアカウントを作る。

    /usr/bin/python3 seed.py                    … 対話式で作る
    /usr/bin/python3 seed.py --demo             … 動作確認用のサンプルも入れる

★--demo で入るデータは架空のもの。本番のDBに混ぜないこと（消すときは
  管理画面から個別に消すか、data/keyline.db を作り直す）。
"""

from __future__ import annotations

import getpass
import sys

import auth
import db as dbmod
import services as svc


def ensure_org(con, name: str) -> str:
    row = con.execute("SELECT id FROM organizations LIMIT 1").fetchone()
    if row:
        return row["id"]
    oid = dbmod.new_id()
    con.execute("INSERT INTO organizations (id, name) VALUES (?,?)", (oid, name))
    return oid


def main() -> int:
    demo = "--demo" in sys.argv
    con = dbmod.get_db()

    if con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] and not demo:
        print("すでにアカウントがあります。パスワードを変えたい場合は管理画面から行ってください。")
        return 0

    print("=== KeyLine 初期セットアップ ===\n")

    org_name = input("会社・組織の名前 [大京商事 株式会社]: ").strip() or "大京商事 株式会社"
    oid = ensure_org(con, org_name)

    # --- 管理者 ---
    if not con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        print("\n[管理者アカウント] PCの管理画面にログインする人")
        email = input("  メールアドレス: ").strip().lower()
        name = input("  表示名 [管理者]: ").strip() or "管理者"
        pw = getpass.getpass("  パスワード: ")
        if len(pw) < 8:
            print("  パスワードは8文字以上にしてください")
            return 1
        if pw != getpass.getpass("  パスワード（確認）: "):
            print("  パスワードが一致しません")
            return 1
        auth.create_user(con, oid, email, pw, name, "admin")
        print(f"  ✅ 管理者を作りました: {email}")

    # --- 鍵管理端末 ---
    if not con.execute("SELECT 1 FROM users WHERE role='operator'").fetchone():
        print("\n[鍵管理端末アカウント] 鍵ボックス横のスマホでログインしっぱなしにする")
        t_email = input("  メールアドレス [terminal@keyline.local]: ").strip().lower() \
                  or "terminal@keyline.local"
        t_pw = getpass.getpass("  パスワード: ")
        if len(t_pw) < 8:
            print("  パスワードは8文字以上にしてください")
            return 1
        auth.create_user(con, oid, t_email, t_pw, "鍵管理端末", "operator")
        print(f"  ✅ 鍵管理端末アカウントを作りました: {t_email}")

    if demo:
        _seed_demo(con, oid)

    con.close()
    print("\n完了しました。 ./run.sh で起動してください。")
    return 0


def _seed_demo(con, oid: str) -> None:
    """動作確認用のサンプル。**架空のデータ。**"""
    if con.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]:
        print("\n（サンプルは既に入っているので追加しません）")
        return

    print("\n[サンプルデータを投入します]")
    box1 = svc.create_box(con, oid, "BOX-01", "本社1F鍵ボックス", "本社1F 事務所奥")
    box2 = svc.create_box(con, oid, "BOX-02", "倉庫前キーボックス", "本社裏 倉庫入口")

    assets = [
        ("本社正面入口", ["12345", "12346", "12347"], box1, "03"),
        ("倉庫",         ["55555"],                   box1, "04"),
        ("角屋(横堤)モータープール 管理室", ["77001", "77002"], box2, "01"),
        ("社用車 1号",   ["CAR-01"],                  box1, "10"),
    ]
    for name, nums, box, pos in assets:
        aid = svc.create_asset(con, oid, name, "key", nfc_token=svc.issue_nfc_token(con),
                               box_id=box, box_position=pos, item_numbers=nums)
        print(f"  ✅ {name}")

    for kind, nm, co, ph in [
        ("employee", "山田 太郎", None,          "090-0000-0001"),
        ("employee", "佐藤 花子", None,          "090-0000-0002"),
        ("vendor",   "田中 一郎", "〇〇工務店",  "090-0000-0003"),
        ("vendor",   "鈴木 次郎", "△△クリーン", "090-0000-0004"),
    ]:
        svc.create_borrower(con, oid, nm, kind, co, ph)
    print("  ✅ 貸出先4件")

    # 1件だけ「貸出中・期限超過」の状態を作り、ダッシュボードの赤字表示を確かめられるようにする
    a = con.execute("SELECT id FROM assets WHERE name='倉庫'").fetchone()
    b = con.execute("SELECT id FROM borrowers WHERE name='田中 一郎'").fetchone()
    svc.checkout(con, oid, a["id"], b["id"], due_at=dbmod.ts_plus(hours=-3))
    print("  ✅ 「倉庫」を貸出中（返却期限超過）にしました")


if __name__ == "__main__":
    sys.exit(main())
