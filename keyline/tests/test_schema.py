"""Phase 1 のテスト — スキーマの制約が本当に効くかを確かめる。

ここで確認するのは「アプリが正しく書くか」ではなく「**アプリが間違えてもDBが拒むか**」。
貸出管理では、状態と履歴が食い違った瞬間に「誰が持っているか分からない」に戻るため、
最後の砦をDB側に置いてある。その砦が機能することをここで担保する。

実行:  cd ~/keyline && /usr/bin/python3 tests/test_schema.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import shutil
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db as dbmod  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"  … {detail}" if detail and not cond else ""))


def expect_abort(name: str, fn) -> None:
    """DBが拒否することを期待する。通ってしまったら失敗。"""
    try:
        fn()
    except sqlite3.Error:
        # IntegrityError（CHECK/UNIQUE/FK）も RAISE(ABORT)（OperationalError）もここ
        check(name, True)
        return
    check(name, False, "拒否されずに通ってしまった")


# ---------------------------------------------------------------------------
# 貸出・返却（Phase 4 の本実装の雛形。ここで正しさを固めてから services.py に移す）
# ---------------------------------------------------------------------------
def checkout(con, org_id, asset_id, borrower_id, due=None, image=None):
    """貸出。要点は3つ。

    1. BEGIN IMMEDIATE  … 最初から書き込みロックを取る。後から昇格させようとすると
                          2人同時のとき片方が SQLITE_BUSY で落ちる
    2. 条件付きUPDATE   … status='in_stock' の時だけ更新し、changes() で確かめる。
                          「読んでから書く」の間に横取りされる隙を作らない
    3. 同一トランザクションで履歴もINSERT … 状態だけ変わって履歴が残らない事故を防ぐ
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        now = dbmod.now_ts()
        con.execute(
            "UPDATE assets SET status='checked_out', current_borrower_id=?, checked_out_at=?,"
            " due_at=? WHERE id=? AND organization_id=? AND status='in_stock'",
            (borrower_id, now, due, asset_id, org_id))
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            raise dbmod.Conflict("すでに貸出中です")
        path, kind = image if image else (None, None)
        con.execute(
            "INSERT INTO checkout_logs (id, organization_id, asset_id, borrower_id, action,"
            " checkout_at, due_at, id_image_path, id_image_kind)"
            " VALUES (?,?,?,?,'checkout',?,?,?,?)",
            (dbmod.new_id(), org_id, asset_id, borrower_id, now, due, path, kind))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def do_return(con, org_id, asset_id, force=False):
    """返却。共用端末なので誰が操作したかは記録しない（2026-08-17決定）。

    force=True は管理者が管理画面から行う強制返却。履歴に区別して残す。
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        now = dbmod.now_ts()
        con.execute(
            "UPDATE assets SET status='in_stock', current_borrower_id=NULL, checked_out_at=NULL,"
            " due_at=NULL WHERE id=? AND organization_id=? AND status='checked_out'",
            (asset_id, org_id))
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            raise dbmod.Conflict("この鍵は貸出中ではありません")
        con.execute(
            "UPDATE checkout_logs SET action='returned', returned_at=?, return_type=?"
            " WHERE asset_id=? AND returned_at IS NULL",
            (now, "admin_force" if force else "normal", asset_id))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
def fixture(con: sqlite3.Connection) -> dict:
    """A社（鍵3本セット・貸出先3種）と B社 を作る。テナント分離の検証に両方要る。"""
    ids = {k: dbmod.new_id() for k in (
        "orgA", "orgB", "admin", "terminal", "bUser",
        "empYamada", "vendorTanaka", "custSuzuki", "bBorrower",
        "boxA", "boxB", "asset", "assetB", "assetNoTag")}

    con.execute("BEGIN")
    con.execute("INSERT INTO organizations (id, name) VALUES (?,?)", (ids["orgA"], "株式会社A"))
    con.execute("INSERT INTO organizations (id, name) VALUES (?,?)", (ids["orgB"], "株式会社B"))

    # 操作アカウント（ログインする人）
    for uid, org, email, name, role in [
        (ids["admin"],    ids["orgA"], "admin@a.example",    "管理者",       "admin"),
        (ids["terminal"], ids["orgA"], "terminal@a.example", "鍵管理端末",   "operator"),
        (ids["bUser"],    ids["orgB"], "admin@b.example",    "B社管理者",    "admin"),
    ]:
        con.execute("INSERT INTO users (id, organization_id, email, password_hash, display_name,"
                    " role) VALUES (?,?,?,?,?,?)", (uid, org, email, "dummy", name, role))

    # 貸出先（借りる人）。社員も業者も内見客も同じテーブルに入る
    for bid, org, kind, name, company in [
        (ids["empYamada"],   ids["orgA"], "employee", "山田太郎", None),
        (ids["vendorTanaka"], ids["orgA"], "vendor",   "田中一郎", "〇〇工務店"),
        (ids["custSuzuki"],  ids["orgA"], "customer", "鈴木花子", None),
        (ids["bBorrower"],   ids["orgB"], "vendor",   "B社の業者", "B工務店"),
    ]:
        con.execute("INSERT INTO borrowers (id, organization_id, kind, name, company)"
                    " VALUES (?,?,?,?,?)", (bid, org, kind, name, company))

    con.execute("INSERT INTO boxes (id, organization_id, code, name) VALUES (?,?,?,?)",
                (ids["boxA"], ids["orgA"], "BOX-01", "本社1F鍵ボックス"))
    con.execute("INSERT INTO boxes (id, organization_id, code, name) VALUES (?,?,?,?)",
                (ids["boxB"], ids["orgB"], "BOX-01", "B社のボックス"))

    # 本社正面入口＝鍵3本で1つの管理対象（ご指示3）
    con.execute(
        "INSERT INTO assets (id, organization_id, name, asset_type, nfc_identifier, nfc_source,"
        " box_id, box_position) VALUES (?,?,?,?,?,?,?,?)",
        (ids["asset"], ids["orgA"], "本社正面入口", "key", "a7f3k9x2", "written_token",
         ids["boxA"], "03"))
    for n, num in enumerate(["12345", "12346", "12347"]):
        con.execute("INSERT INTO asset_items (id, organization_id, asset_id, item_type,"
                    " item_number, sort_order) VALUES (?,?,?,?,?,?)",
                    (dbmod.new_id(), ids["orgA"], ids["asset"], "key", num, n))

    con.execute("INSERT INTO assets (id, organization_id, name) VALUES (?,?,?)",
                (ids["assetNoTag"], ids["orgA"], "タグ未貼付の鍵"))
    con.execute("INSERT INTO assets (id, organization_id, name, nfc_identifier, nfc_source)"
                " VALUES (?,?,?,?,?)",
                (ids["assetB"], ids["orgB"], "B社の鍵", "bbbb1111", "written_token"))
    con.execute("COMMIT")
    return ids


# ---------------------------------------------------------------------------
def main() -> None:
    con = dbmod.connect(":memory:")
    print(f"\nマイグレーション: {dbmod.migrate(con)}\n")
    ids = fixture(con)
    A = ids["orgA"]

    print("── セット（ご指示2・3・7）")
    check("鍵3本が1つの管理対象にぶら下がる",
          con.execute("SELECT COUNT(*) c FROM asset_items WHERE asset_id=?",
                      (ids["asset"],)).fetchone()["c"] == 3)
    row = con.execute("SELECT * FROM v_asset_overview WHERE id=?", (ids["asset"],)).fetchone()
    check("一覧で鍵番号が '12345 / 12346 / 12347' に畳まれる",
          row["item_numbers"] == "12345 / 12346 / 12347", str(row["item_numbers"]))
    check("ボックスと戻す位置が出る", row["box_code"] == "BOX-01" and row["box_position"] == "03")
    # 1本の鍵・2本セット・3本セットがすべて同じ形で扱えること（ご指示29）
    for label, nums in [("1本の鍵", ["55555"]), ("2本セット", ["66666", "66667"])]:
        aid = dbmod.new_id()
        con.execute("INSERT INTO assets (id, organization_id, name) VALUES (?,?,?)", (aid, A, label))
        for n, num in enumerate(nums):
            con.execute("INSERT INTO asset_items (id, organization_id, asset_id, item_number,"
                        " sort_order) VALUES (?,?,?,?,?)", (dbmod.new_id(), A, aid, num, n))
        check(f"{label}も同じ形で登録できる",
              con.execute("SELECT COUNT(*) c FROM asset_items WHERE asset_id=?",
                          (aid,)).fetchone()["c"] == len(nums))
    # 同じ番号の合鍵2本セット（item_number に UNIQUE を張っていない理由）
    dup = dbmod.new_id()
    con.execute("INSERT INTO assets (id, organization_id, name) VALUES (?,?,?)", (dup, A, "合鍵2本"))
    for _ in range(2):
        con.execute("INSERT INTO asset_items (id, organization_id, asset_id, item_number)"
                    " VALUES (?,?,?,?)", (dbmod.new_id(), A, dup, "77777"))
    check("同じ鍵番号の合鍵2本セットを登録できる",
          con.execute("SELECT COUNT(*) c FROM asset_items WHERE asset_id=?",
                      (dup,)).fetchone()["c"] == 2)
    con.execute("DELETE FROM asset_items WHERE asset_id=?", (dup,))
    check("構成品を削除できる（ご指示29）",
          con.execute("SELECT COUNT(*) c FROM asset_items WHERE asset_id=?",
                      (dup,)).fetchone()["c"] == 0)

    print("\n── NFC識別子（ご指示4・5・20）")
    expect_abort("同じNFC識別子は2つ登録できない", lambda: con.execute(
        "INSERT INTO assets (id, organization_id, name, nfc_identifier, nfc_source)"
        " VALUES (?,?,?,?,?)", (dbmod.new_id(), A, "重複", "a7f3k9x2", "written_token")))
    check("タグ未貼付の管理対象を作れる（ご指示15の登録前）",
          con.execute("SELECT nfc_identifier FROM assets WHERE id=?",
                      (ids["assetNoTag"],)).fetchone()["nfc_identifier"] is None)
    expect_abort("nfc_identifier だけ入れて source 無しは拒否", lambda: con.execute(
        "INSERT INTO assets (id, organization_id, name, nfc_identifier) VALUES (?,?,?,?)",
        (dbmod.new_id(), A, "片方だけ", "zzzz9999")))
    check("NFC識別子と鍵番号は別物として持てる（ご指示4・5）",
          row["nfc_identifier"] == "a7f3k9x2" and "a7f3k9x2" not in (row["item_numbers"] or ""))
    # タグ交換しても asset.id は変わらない＝履歴も構成品も維持される
    con.execute("UPDATE assets SET nfc_identifier='newtag01' WHERE id=?", (ids["asset"],))
    check("タグ交換後も管理対象と構成品が維持される（ご指示5）",
          con.execute("SELECT COUNT(*) c FROM asset_items WHERE asset_id=?",
                      (ids["asset"],)).fetchone()["c"] == 3)
    con.execute("UPDATE assets SET nfc_identifier='a7f3k9x2' WHERE id=?", (ids["asset"],))

    print("\n── 貸出（ご指示9）")
    due = dbmod.ts_plus(hours=8)
    checkout(con, A, ids["asset"], ids["empYamada"], due)
    a = con.execute("SELECT * FROM v_asset_overview WHERE id=?", (ids["asset"],)).fetchone()
    check("status が貸出中になる", a["status"] == "checked_out")
    check("現在の利用者が山田太郎になる", a["borrower_name"] == "山田太郎")
    check("貸出時刻が記録される", a["checked_out_at"] is not None)
    check("返却予定が記録される", a["due_at"] == due)
    check("履歴が1本立つ",
          con.execute("SELECT COUNT(*) c FROM checkout_logs WHERE asset_id=? AND returned_at IS NULL",
                      (ids["asset"],)).fetchone()["c"] == 1)

    print("\n── 二重貸出の防止（ご指示23・28）")
    try:
        checkout(con, A, ids["asset"], ids["vendorTanaka"], due)
        check("貸出中のものは再度貸出できない", False, "通ってしまった")
    except dbmod.Conflict:
        check("貸出中のものは再度貸出できない", True)
    expect_abort("未返却の履歴は1本しか作れない（DBの砦）", lambda: con.execute(
        "INSERT INTO checkout_logs (id, organization_id, asset_id, borrower_id, checkout_at)"
        " VALUES (?,?,?,?,?)",
        (dbmod.new_id(), A, ids["asset"], ids["vendorTanaka"], dbmod.now_ts())))

    print("\n── 返却（ご指示10）")
    do_return(con, A, ids["asset"])
    a = con.execute("SELECT * FROM assets WHERE id=?", (ids["asset"],)).fetchone()
    check("status が保管中に戻る", a["status"] == "in_stock")
    check("current_borrower_id が消える", a["current_borrower_id"] is None)
    check("due_at が消える", a["due_at"] is None)
    log = con.execute("SELECT * FROM checkout_logs WHERE asset_id=? ORDER BY checkout_at DESC",
                      (ids["asset"],)).fetchone()
    check("履歴に返却時刻が入る", log["returned_at"] is not None)
    check("借主が誰だったかは履歴に残り続ける", log["borrower_id"] == ids["empYamada"])
    check("action が returned になる", log["action"] == "returned")
    try:
        do_return(con, A, ids["asset"])
        check("保管中のものは返却できない", False, "通ってしまった")
    except dbmod.Conflict:
        check("保管中のものは返却できない", True)

    print("\n── 社外への貸出（今回の要件の中心）")
    checkout(con, A, ids["asset"], ids["vendorTanaka"], dbmod.ts_plus(hours=3),
             image=("id_images/2026/08/abc.jpg", "business_card"))
    a = con.execute("SELECT * FROM v_asset_overview WHERE id=?", (ids["asset"],)).fetchone()
    check("社外の業者に貸せる", a["borrower_name"] == "田中一郎")
    check("会社名が一緒に出る", a["borrower_company"] == "〇〇工務店")
    check("社員か社外かを区別できる", a["borrower_kind"] == "vendor")
    # 未返却の行は idx_checkout_open により必ず1本だけ＝この取り方は一意に決まる
    log = con.execute("SELECT * FROM checkout_logs WHERE asset_id=? AND returned_at IS NULL",
                      (ids["asset"],)).fetchone()
    vendor_log_id = log["id"]
    check("名刺画像のパスが履歴に残る", log["id_image_path"] == "id_images/2026/08/abc.jpg")
    check("画像の種類が残る", log["id_image_kind"] == "business_card")
    check("まだ削除されていない", log["id_image_purged_at"] is None)

    print("\n── 管理者の強制返却（ご指示11）")
    do_return(con, A, ids["asset"], force=True)
    # ★idを控えて引く。ORDER BY だけに頼ると、同一時刻の履歴があるとき取り違える
    log = con.execute("SELECT * FROM checkout_logs WHERE id=?", (vendor_log_id,)).fetchone()
    check("管理者は貸出中のものを強制返却できる", log["returned_at"] is not None)
    check("強制返却だと分かる形で残る", log["return_type"] == "admin_force")
    # 同一ミリ秒に2件入っても順序が一意に決まること（rowid をタイブレークに使う）
    order1 = [r["id"] for r in con.execute(
        "SELECT id FROM checkout_logs WHERE asset_id=? ORDER BY checkout_at DESC, rowid DESC",
        (ids["asset"],))]
    order2 = [r["id"] for r in con.execute(
        "SELECT id FROM checkout_logs WHERE asset_id=? ORDER BY checkout_at DESC, rowid DESC",
        (ids["asset"],))]
    check("履歴の並び順が一意に決まる（同一ミリ秒でも取り違えない）",
          order1 == order2 and order1[0] == vendor_log_id, f"{order1}")

    print("\n── 身分証画像の自動削除（返却から30日）")
    con.execute("UPDATE checkout_logs SET returned_at='2020-01-01T00:00:00Z',"
                " checkout_at='2019-12-31T00:00:00Z' WHERE id=?", (log["id"],))
    old = con.execute(
        "SELECT id FROM checkout_logs WHERE returned_at IS NOT NULL AND id_image_path IS NOT NULL"
        " AND id_image_purged_at IS NULL AND returned_at < ?",
        (dbmod.ts_plus(days=-30),)).fetchall()
    check("30日を過ぎた画像が削除対象として引ける", len(old) == 1, f"{len(old)}件")
    con.execute("UPDATE checkout_logs SET id_image_purged_at=? WHERE id=?", (dbmod.now_ts(), log["id"]))
    r = con.execute("SELECT * FROM checkout_logs WHERE id=?", (log["id"],)).fetchone()
    check("削除後も『撮ったが今は無い』と区別できる",
          r["id_image_purged_at"] is not None and r["id_image_path"] is not None)
    expect_abort("撮っていないものを削除済みにはできない", lambda: con.execute(
        "UPDATE checkout_logs SET id_image_purged_at=? WHERE id_image_path IS NULL",
        (dbmod.now_ts(),)))

    print("\n── 履歴（ご指示12）")
    rows = con.execute("SELECT * FROM checkout_logs WHERE asset_id=? ORDER BY checkout_at",
                       (ids["asset"],)).fetchall()
    check("過去の貸出履歴が消えずに積み上がる", len(rows) == 2, f"{len(rows)}件")
    check("全件に借主が残っている", all(r["borrower_id"] for r in rows))
    u = con.execute("SELECT * FROM v_borrower_usage WHERE id=?", (ids["vendorTanaka"],)).fetchone()
    check("貸出先ごとの利用回数が出る（『最近の貸出先』用）", u["checkout_count"] == 1)
    check("未返却の件数が出る", u["open_count"] == 0)

    print("\n── 状態の整合（アプリのバグを DB が拒む）")
    expect_abort("貸出中なのに借主が空、は作れない", lambda: con.execute(
        "INSERT INTO assets (id, organization_id, name, status) VALUES (?,?,?,'checked_out')",
        (dbmod.new_id(), A, "壊れた行")))
    expect_abort("保管中なのに借主が残る、は作れない", lambda: con.execute(
        "UPDATE assets SET current_borrower_id=? WHERE id=?", (ids["empYamada"], ids["asset"])))
    expect_abort("返却が貸出より前の履歴は作れない", lambda: con.execute(
        "INSERT INTO checkout_logs (id, organization_id, asset_id, borrower_id, action,"
        " checkout_at, returned_at, return_type) VALUES (?,?,?,?,'returned',"
        "'2026-08-17T10:00:00Z','2026-08-17T09:00:00Z','normal')",
        (dbmod.new_id(), A, ids["assetNoTag"], ids["empYamada"])))

    print("\n── 組織またぎの遮断（ご指示16・28）")
    expect_abort("A社の管理対象にB社のボックスは紐づけられない", lambda: con.execute(
        "UPDATE assets SET box_id=? WHERE id=?", (ids["boxB"], ids["asset"])))
    expect_abort("A社の管理対象をB社の貸出先に貸せない",
                 lambda: checkout(con, A, ids["asset"], ids["bBorrower"]))
    expect_abort("A社の管理対象にB社の構成品は足せない", lambda: con.execute(
        "INSERT INTO asset_items (id, organization_id, asset_id, item_number) VALUES (?,?,?,?)",
        (dbmod.new_id(), ids["orgB"], ids["asset"], "99999")))
    check("A社の一覧にB社の管理対象は出ない",
          all(r["organization_id"] == A for r in con.execute(
              "SELECT * FROM v_asset_overview WHERE organization_id=?", (A,))))
    check("B社の一覧にA社の管理対象は出ない",
          [r["name"] for r in con.execute(
              "SELECT name FROM v_asset_overview WHERE organization_id=?", (ids["orgB"],))] == ["B社の鍵"])
    # 組織を指定せずに asset_id を直接叩かれても、他組織のものは動かせないこと
    try:
        checkout(con, ids["orgB"], ids["asset"], ids["bBorrower"])
        check("他組織のasset_idを直接指定しても貸出できない（ご指示28）", False, "通ってしまった")
    except (dbmod.Conflict, sqlite3.Error):
        check("他組織のasset_idを直接指定しても貸出できない（ご指示28）", True)

    print("\n── 外部キー")
    expect_abort("存在しない管理対象の履歴は作れない", lambda: con.execute(
        "INSERT INTO checkout_logs (id, organization_id, asset_id, borrower_id, checkout_at)"
        " VALUES (?,?,?,?,?)", (dbmod.new_id(), A, "no-such-asset", ids["empYamada"], dbmod.now_ts())))
    expect_abort("存在しない貸出先には貸せない", lambda: con.execute(
        "INSERT INTO checkout_logs (id, organization_id, asset_id, borrower_id, checkout_at)"
        " VALUES (?,?,?,?,?)", (dbmod.new_id(), A, ids["asset"], "no-such-borrower", dbmod.now_ts())))
    con.execute("DELETE FROM assets WHERE id=?", (dup,))
    check("管理対象を消すと構成品も消える（CASCADE）",
          con.execute("SELECT COUNT(*) c FROM asset_items WHERE asset_id=?",
                      (dup,)).fetchone()["c"] == 0)

    print("\n── 返却期限の超過判定（ご指示13）")
    con.execute("UPDATE assets SET status='checked_out', current_borrower_id=?, checked_out_at=?,"
                " due_at='2020-01-01T00:00:00Z' WHERE id=?",
                (ids["vendorTanaka"], dbmod.now_ts(), ids["assetNoTag"]))
    r = con.execute("SELECT * FROM v_asset_overview WHERE id=?", (ids["assetNoTag"],)).fetchone()
    check("期限を過ぎたものに is_overdue=1 が立つ", r["is_overdue"] == 1)
    check("経過時間が算出される", r["elapsed_minutes"] is not None)
    check("保管中のものは超過扱いにならない",
          con.execute("SELECT is_overdue FROM v_asset_overview WHERE id=?",
                      (ids["asset"],)).fetchone()["is_overdue"] == 0)
    # 期限を設けない貸出（ご指示9で due_at は任意）
    con.execute("UPDATE assets SET due_at=NULL WHERE id=?", (ids["assetNoTag"],))
    check("返却予定なしでも超過扱いにならない",
          con.execute("SELECT is_overdue FROM v_asset_overview WHERE id=?",
                      (ids["assetNoTag"],)).fetchone()["is_overdue"] == 0)

    con.close()


def test_concurrent_checkout() -> None:
    """★2人が同時に同じ鍵を借りようとしたら、片方だけが成功すること（ご指示29）。

    :memory: はスレッド間で共有できないため、ここだけ実ファイルを使う。
    """
    print("\n── 同時貸出（実ファイル・2スレッド）")
    tmpdir = tempfile.mkdtemp()
    path = Path(tmpdir) / "concurrent.db"
    setup = dbmod.connect(path)
    dbmod.migrate(setup)
    ids = fixture(setup)
    setup.close()

    results: list[tuple[str, str]] = []
    barrier = threading.Barrier(2)
    lock = threading.Lock()

    def worker(borrower_key: str) -> None:
        con = dbmod.connect(path)
        try:
            barrier.wait()          # 2スレッドの開始を揃え、確実にぶつける
            checkout(con, ids["orgA"], ids["asset"], ids[borrower_key])
            with lock:
                results.append(("ok", borrower_key))
        except (dbmod.Conflict, sqlite3.Error):
            with lock:
                results.append(("ng", borrower_key))
        finally:
            con.close()

    threads = [threading.Thread(target=worker, args=(b,))
               for b in ("empYamada", "vendorTanaka")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = [r for r in results if r[0] == "ok"]
    check("同時に2人が貸出 → 成功は1人だけ", len(ok) == 1, f"成功{len(ok)}人 {results}")

    con = dbmod.connect(path)
    n = con.execute("SELECT COUNT(*) c FROM checkout_logs WHERE asset_id=? AND returned_at IS NULL",
                    (ids["asset"],)).fetchone()["c"]
    check("未返却の履歴は1本だけ", n == 1, f"{n}本")
    holder = con.execute("SELECT current_borrower_id FROM assets WHERE id=?",
                         (ids["asset"],)).fetchone()[0]
    check("借主が成功した1人と一致する", bool(ok) and holder == ids[ok[0][1]])
    con.close()
    # WAL モードだと -wal / -shm が残るので、ディレクトリごと消す
    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
    test_concurrent_checkout()
    print(f"\n{'='*56}\n  成功 {len(PASS)} / 失敗 {len(FAIL)}")
    if FAIL:
        print("  失敗:", ", ".join(FAIL))
    print("=" * 56)
    sys.exit(1 if FAIL else 0)
