#!/usr/bin/env python3
"""メールアーカイバ 同期スクリプト（取り込み／サーバー側削除）。

    python3 sync.py --sync                    # 取り込みだけ（既定・安全）
    python3 sync.py --sync --folder INBOX     # フォルダを絞る
    python3 sync.py --delete                  # 削除候補を出すだけ（dry-run。既定でこうなる）
    python3 sync.py --delete --yes            # ★実際にサーバーから消す
    python3 sync.py --verify                  # 保存済み .eml が壊れていないか総点検
    python3 sync.py --stats                   # 件数・容量

--------------------------------------------------------------------------------
削除の安全設計（「消す」は取り返しがつかないので、鍵を何段も掛けている）
--------------------------------------------------------------------------------
1. `.env` の `ARCHIVE_DELETE_ENABLED=1` … 設定として許可されている
2. 実行時の `--delete` … その回の意思
3. 実行時の `--yes` … dry-run ではなく本当に消す意思（付けなければ必ず dry-run）
そのうえで **1通ごとに** 次を全部満たしたものだけ消す。1つでも欠けたらその通は飛ばす。

  a. `synced_at` から 14日（`--days`）以上経っている
  b. ローカルの原本 `.eml` が実在し、**SHA256 が保存時と一致**する（0バイト・破損を弾く）
  c. DBに紐づく添付ファイルがすべて実在する
  d. フォルダの **UIDVALIDITY がサーバーと一致**する（違えば UID は別のメールを指す＝そのフォルダ全体を中止）
  e. サーバー側の **Message-ID がローカルの記録と一致**する（UIDのずれで別のメールを消さないため）
     Message-ID が無いメールは RFC822.SIZE の一致で代替する
  f. 既読（`--include-unseen` で解除）／フラグ無し（`--include-flagged` で解除）
  g. 除外フォルダ（ゴミ箱・迷惑メール）ではない

削除は `\\Deleted` を立てたあと **UID EXPUNGE**（UIDPLUS拡張）で「今指定したUIDだけ」を消す。
素の `EXPUNGE` は**そのフォルダで \\Deleted が付いている他のメールも道連れにする**ので、
UIDPLUS が無いサーバーでは `--allow-full-expunge` を明示しない限り中止する。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import config
import db
import imap_util as iu

BATCH = 100


def log(msg: str) -> None:
    print("[{}] {}".format(datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def safe_name(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", s)
    return s.strip() or "_"


def norm_msgid(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.strip().strip("<>").strip().lower()


# ------------------------------------------------------------------ 取り込み

def do_sync(conn, cfg: Dict[str, str], only_folder: Optional[str], limit: int,
            since_days: Optional[int]) -> None:
    imap = iu.connect(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]), cfg["IMAP_USER"],
                      cfg["IMAP_PASSWORD"], cfg.get("IMAP_SSL", "1") == "1")
    try:
        account_id = db.upsert_account(conn, cfg["MAIL_ACCOUNT"], cfg["IMAP_HOST"],
                                       int(cfg["IMAP_PORT"]), cfg["IMAP_USER"])
        excluded = config.excluded_folders(cfg)
        folders = iu.list_folders(imap)
        log("フォルダ {} 個".format(len(folders)))
        total_new = 0

        for f in folders:
            name = f["name"]
            if only_folder and only_folder not in (name, f["raw_name"]):
                continue
            if any(name.endswith(x) or name == x for x in excluded):
                log("skip（除外フォルダ）: {}".format(name))
                continue

            frow = db.upsert_folder(conn, account_id, f["raw_name"], name)
            try:
                n, uidvalidity = iu.select_folder(imap, f["raw_name"], readonly=True)
            except Exception as e:
                log("skip（開けない）: {} — {}".format(name, e))
                continue

            last_uid = int(frow["last_seen_uid"] or 0)
            if frow["uidvalidity"] is not None and int(frow["uidvalidity"]) != uidvalidity:
                # サーバー側でフォルダが作り直された。過去のUIDはもう当てにならない
                log("!! UIDVALIDITY が変わった: {} ({} → {})。既存分は 'gone' 扱いにして取り直す"
                    .format(name, frow["uidvalidity"], uidvalidity))
                conn.execute(
                    "UPDATE messages SET server_state='gone' "
                    "WHERE folder_id=? AND uidvalidity=? AND server_state='present'",
                    (frow["id"], int(frow["uidvalidity"])))
                conn.commit()
                last_uid = 0
            db.set_folder_uidvalidity(conn, frow["id"], uidvalidity)

            uids = iu.search_uids(imap, since_uid=last_uid)
            if since_days:
                since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
                typ, data = imap.uid("SEARCH", None, "SINCE", since)
                recent = set(int(x) for x in (data[0].split() if data and data[0] else []))
                uids = [u for u in uids if u in recent]
            if limit:
                uids = uids[:limit]
            if not uids:
                log("{}: 新着なし（{}通・last_uid={}）".format(name, n, last_uid))
                continue
            log("{}: {}通を取り込む（last_uid={}）".format(name, len(uids), last_uid))

            got = 0
            for uid in uids:
                if db.message_exists(conn, account_id, frow["id"], uidvalidity, uid):
                    continue
                try:
                    res = iu.fetch_raw(imap, uid)
                except Exception as e:
                    log("  uid={} 取得失敗: {}".format(uid, e))
                    continue
                if not res:
                    continue
                raw, flags = res
                try:
                    save_one(conn, cfg, account_id, frow, uidvalidity, uid, raw, flags)
                    got += 1
                except Exception as e:
                    conn.rollback()
                    log("  uid={} 保存失敗（この通は取り込まない）: {}".format(uid, e))
                    continue
                if got % 50 == 0:
                    db.update_folder_progress(conn, frow["id"], uid)
                    log("  … {}/{}".format(got, len(uids)))
            db.update_folder_progress(conn, frow["id"], max(uids))
            total_new += got
            log("{}: {}通を保存".format(name, got))

        log("取り込み完了: 新規 {}通".format(total_new))
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def sidecar_path(raw_abs: str) -> str:
    return raw_abs + ".json"


def write_sidecar(raw_abs: str, meta: Dict[str, Any]) -> None:
    """原本の隣に「DBを作り直すのに必要な情報」を置く（write-once）。

    DBは同期フォルダに置けない（壊れる）ので、**原本だけあればDBを再構築できる**形にしておく。
    ここに `synced_at` も入れるので、作り直しても14日ルールの起点がずれない。
    """
    with open(sidecar_path(raw_abs), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=1)


def save_one(conn, cfg, account_id: int, frow, uidvalidity: int, uid: int,
             raw: bytes, flags: str, state: str = "present") -> int:
    """原本を先にディスクへ、そのあとDBへ。**DBに行があるのにファイルが無い状態を作らない。**"""
    account_name = cfg.get("MAIL_ACCOUNT") or "default"
    folder_dir = os.path.join(safe_name(account_name), safe_name(frow["name"]), str(uidvalidity))
    raw_rel = os.path.join("raw", folder_dir, "{}.eml".format(uid))
    raw_abs = os.path.join(config.DATA_DIR, raw_rel)
    os.makedirs(os.path.dirname(raw_abs), exist_ok=True)
    with open(raw_abs, "wb") as fp:
        fp.write(raw)
    digest = db.sha256_bytes(raw)

    parsed = iu.parse_message(raw)
    synced_at = db.utcnow()   # ★ここが2週間の起点
    rec = {
        "account_id": account_id, "folder_id": frow["id"], "uid": uid,
        "uidvalidity": uidvalidity, "message_id": parsed["message_id"],
        "subject": parsed["subject"], "from_name": parsed["from_name"],
        "from_addr": parsed["from_addr"], "to_addrs": parsed["to_addrs"],
        "cc_addrs": parsed["cc_addrs"], "date_utc": parsed["date_utc"],
        "size_bytes": len(raw), "flags": flags,
        "body_text": parsed["body_text"],
        "has_attachments": 1 if parsed["attachments"] else 0,
        "raw_path": raw_rel, "raw_sha256": digest,
        "synced_at": synced_at, "server_state": state,
    }
    row_id = db.insert_message(conn, rec)

    atts = []
    for i, (fname, ctype, payload) in enumerate(parsed["attachments"], 1):
        rel = os.path.join("attachments", folder_dir, str(uid),
                           "{:02d}_{}".format(i, safe_name(fname)))
        abs_path = os.path.join(config.DATA_DIR, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as fp:
            fp.write(payload)
        sha = db.sha256_bytes(payload)
        db.insert_attachment(conn, row_id, fname, ctype, len(payload), rel, sha)
        atts.append({"filename": fname, "content_type": ctype, "size_bytes": len(payload),
                     "path": rel, "sha256": sha})

    write_sidecar(raw_abs, {
        "account": account_name, "account_host": cfg.get("IMAP_HOST", ""),
        "folder_name": frow["name"], "folder_raw": frow["raw_name"],
        "uid": uid, "uidvalidity": uidvalidity, "flags": flags,
        "message_id": parsed["message_id"], "size_bytes": len(raw), "sha256": digest,
        "synced_at": synced_at, "server_state": state,
        "raw_path": raw_rel, "attachments": atts,
    })
    conn.commit()
    return row_id


# ------------------------------------------------------------------ 健全性チェック

def local_copy_ok(conn, row) -> Tuple[bool, str]:
    """「ローカルに本当にあるか」の判定。ここが削除の可否を決める心臓部。"""
    raw_abs = os.path.join(config.DATA_DIR, row["raw_path"])
    if not os.path.exists(raw_abs):
        return False, "原本ファイルが無い: {}".format(row["raw_path"])
    try:
        with open(raw_abs, "rb") as fp:
            data = fp.read()
    except Exception as e:
        return False, "原本が読めない: {}".format(e)
    if not data:
        return False, "原本が0バイト"
    if db.sha256_bytes(data) != row["raw_sha256"]:
        return False, "SHA256 が一致しない（破損の疑い）"
    if row["size_bytes"] and len(data) != row["size_bytes"]:
        return False, "サイズが記録と違う（{} != {}）".format(len(data), row["size_bytes"])
    for a in db.attachments_of(conn, row["id"]):
        ap = os.path.join(config.DATA_DIR, a["path"])
        if not os.path.exists(ap) or os.path.getsize(ap) != a["size_bytes"]:
            return False, "添付が欠けている: {}".format(a["filename"])
    return True, ""


def do_verify(conn) -> int:
    rows = conn.execute("SELECT * FROM messages ORDER BY id").fetchall()
    bad = 0
    for r in rows:
        ok, why = local_copy_ok(conn, r)
        if not ok:
            bad += 1
            print("NG id={} uid={} {} — {}".format(r["id"], r["uid"], r["subject"], why))
    print("点検 {}通 / 問題 {}件".format(len(rows), bad))
    return bad


def do_rebuild(conn) -> int:
    """原本(.eml)とサイドカーから **DBを作り直す**。

    DBはローカル固定・原本は同期フォルダ、という置き方にしているので、DBが壊れても
    ここで戻せる。`synced_at` もサイドカーから復元するので、**14日ルールの起点がずれない**。
    """
    root = os.path.join(config.DATA_DIR, "raw")
    if not os.path.isdir(root):
        print("原本の置き場がありません: {}".format(root))
        return 1

    sidecars = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.endswith(".eml.json"):
                sidecars.append(os.path.join(dirpath, fn))
    print("サイドカー {} 件から作り直します（置き場: {}）".format(len(sidecars), config.DATA_DIR))

    for t in ("messages_fts", "attachments", "messages", "folders", "accounts", "delete_log"):
        conn.execute("DELETE FROM {}".format(t))
    conn.commit()

    accounts: Dict[str, int] = {}
    folders: Dict[tuple, Any] = {}
    ok = ng = 0
    for sc in sorted(sidecars):
        try:
            with open(sc, encoding="utf-8") as fp:
                meta = json.load(fp)
            raw_abs = sc[:-len(".json")]
            with open(raw_abs, "rb") as fp:
                raw = fp.read()
            if db.sha256_bytes(raw) != meta.get("sha256"):
                print("  SHA256不一致のため飛ばす: {}".format(meta.get("raw_path")))
                ng += 1
                continue
            acc = meta.get("account") or "default"
            if acc not in accounts:
                accounts[acc] = db.upsert_account(conn, acc, meta.get("account_host") or "",
                                                  993, meta.get("account_host") or acc)
            fkey = (acc, meta.get("folder_raw") or meta.get("folder_name"))
            if fkey not in folders:
                folders[fkey] = db.upsert_folder(conn, accounts[acc], fkey[1],
                                                 meta.get("folder_name") or fkey[1])
                db.set_folder_uidvalidity(conn, folders[fkey]["id"],
                                          int(meta.get("uidvalidity") or 0))
            frow = folders[fkey]
            state = meta.get("server_state") or "present"
            if os.path.exists(raw_abs + ".deleted.json"):
                state = "deleted"
            parsed = iu.parse_message(raw)
            rec = {
                "account_id": accounts[acc], "folder_id": frow["id"],
                "uid": int(meta.get("uid") or 0), "uidvalidity": int(meta.get("uidvalidity") or 0),
                "message_id": parsed["message_id"], "subject": parsed["subject"],
                "from_name": parsed["from_name"], "from_addr": parsed["from_addr"],
                "to_addrs": parsed["to_addrs"], "cc_addrs": parsed["cc_addrs"],
                "date_utc": parsed["date_utc"], "size_bytes": len(raw),
                "flags": meta.get("flags") or "", "body_text": parsed["body_text"],
                "has_attachments": 1 if parsed["attachments"] else 0,
                "raw_path": meta.get("raw_path"), "raw_sha256": meta.get("sha256"),
                "synced_at": meta.get("synced_at") or db.utcnow(),   # ★起点を復元
                "server_state": state,
            }
            row_id = db.insert_message(conn, rec)
            for a in meta.get("attachments") or []:
                db.insert_attachment(conn, row_id, a["filename"], a.get("content_type") or "",
                                     int(a.get("size_bytes") or 0), a["path"], a.get("sha256") or "")
            db.update_folder_progress(conn, frow["id"], int(meta.get("uid") or 0))
            ok += 1
        except Exception as e:
            print("  失敗 {}: {}".format(os.path.basename(sc), e))
            ng += 1
    conn.commit()
    print("作り直し完了: {}通 / 失敗 {}件".format(ok, ng))
    return 1 if ng else 0


# ------------------------------------------------------------------ 削除

def do_delete(conn, cfg: Dict[str, str], days: int, really: bool, only_folder: Optional[str],
              max_delete: int, include_unseen: bool, include_flagged: bool,
              allow_full_expunge: bool) -> None:
    if cfg.get("ARCHIVE_DELETE_ENABLED", "0") != "1":
        print("削除は設定で無効です（.env の ARCHIVE_DELETE_ENABLED=1 が要る）。中止します。")
        return
    acc = conn.execute("SELECT * FROM accounts WHERE name=?", (cfg["MAIL_ACCOUNT"],)).fetchone()
    if not acc:
        print("このアカウントはまだ1通も取り込んでいません。中止します。")
        return

    excluded = config.excluded_folders(cfg)
    cands = db.deletable_candidates(conn, acc["id"], days,
                                    keep_flagged=not include_flagged,
                                    keep_unseen=not include_unseen)
    if only_folder:
        cands = [c for c in cands if only_folder in (c["folder_name"], c["folder_raw"])]
    cands = [c for c in cands if not any(c["folder_name"].endswith(x) or c["folder_name"] == x
                                         for x in excluded)]
    if not cands:
        print("条件を満たす削除候補はありません（synced_at が {}日以上前・ローカル保存済み）".format(days))
        return

    by_folder: Dict[int, List[Any]] = {}
    for c in cands:
        by_folder.setdefault(c["folder_id"], []).append(c)

    mode = "deleted" if really else "dry-run"
    log("削除候補 {}通 / {}フォルダ（{}）".format(len(cands), len(by_folder),
                                                "★本番" if really else "dry-run"))

    imap = iu.connect(cfg["IMAP_HOST"], int(cfg["IMAP_PORT"]), cfg["IMAP_USER"],
                      cfg["IMAP_PASSWORD"], cfg.get("IMAP_SSL", "1") == "1")
    uidplus = False
    try:
        caps = iu.capabilities(imap)   # ログイン後に取り直す（認証前は名乗らないサーバーがある）
        uidplus = "UIDPLUS" in caps
        if really and not uidplus and not allow_full_expunge:
            print("!! このサーバーは UIDPLUS 非対応です。素の EXPUNGE は、あなたが Apple Mail 等で")
            print("   \\Deleted を付けた他のメールまで一緒に消します。")
            print("   それを承知のうえなら --allow-full-expunge を付けてください。中止します。")
            return

        done = 0
        skipped = 0
        freed = 0
        for folder_id, rows in by_folder.items():
            fname = rows[0]["folder_name"]
            raw_name = rows[0]["folder_raw"]
            try:
                _, server_uidvalidity = iu.select_folder(imap, raw_name, readonly=not really)
            except Exception as e:
                log("skip（開けない）: {} — {}".format(fname, e))
                continue
            if int(rows[0]["uidvalidity"]) != server_uidvalidity:
                log("!! UIDVALIDITY 不一致のためこのフォルダは中止: {}（local={} server={}）"
                    .format(fname, rows[0]["uidvalidity"], server_uidvalidity))
                for r in rows:
                    db.log_delete(conn, r, "skipped", "UIDVALIDITY 不一致")
                conn.commit()
                skipped += len(rows)
                continue

            ok_rows = []
            for r in rows:
                if max_delete and done + len(ok_rows) >= max_delete:
                    break
                ok, why = local_copy_ok(conn, r)
                if not ok:
                    db.log_delete(conn, r, "skipped", why)
                    skipped += 1
                    continue
                # サーバー側の本人確認（UIDのずれで別のメールを消さないため）
                try:
                    server_msgid = iu.fetch_message_id(imap, r["uid"])
                except Exception as e:
                    db.log_delete(conn, r, "skipped", "Message-ID 取得失敗: {}".format(e))
                    skipped += 1
                    continue
                if server_msgid is None:
                    # サーバー側に無い＝他端末が既に消した。ローカルは残す
                    db.mark_server_gone(conn, r["id"])
                    db.log_delete(conn, r, "skipped", "サーバーに存在しない（gone）")
                    skipped += 1
                    continue
                if r["message_id"]:
                    if norm_msgid(server_msgid) != norm_msgid(r["message_id"]):
                        db.log_delete(conn, r, "skipped", "Message-ID 不一致（別のメールの疑い）")
                        skipped += 1
                        continue
                else:
                    size = iu.fetch_size(imap, r["uid"])
                    if size is None or abs(size - int(r["size_bytes"])) > 2:
                        db.log_delete(conn, r, "skipped", "Message-ID 無し・サイズも不一致")
                        skipped += 1
                        continue
                ok_rows.append(r)
            conn.commit()

            if not ok_rows:
                log("{}: 消せるものなし".format(fname))
                continue

            if not really:
                for r in ok_rows:
                    db.log_delete(conn, r, "dry-run", "")
                    freed += int(r["size_bytes"] or 0)
                conn.commit()
                log("{}: {}通が条件を満たす（dry-run のため消していない）".format(fname, len(ok_rows)))
                done += len(ok_rows)
                continue

            uids = [str(r["uid"]) for r in ok_rows]
            for i in range(0, len(uids), BATCH):
                chunk = uids[i:i + BATCH]
                typ, _ = imap.uid("STORE", ",".join(chunk), "+FLAGS", "(\\Deleted)")
                if typ != "OK":
                    log("!! STORE 失敗。このフォルダは中止: {}".format(fname))
                    break
                if uidplus:
                    typ, _ = imap.uid("EXPUNGE", ",".join(chunk))
                else:
                    typ, _ = imap.expunge()
                if typ != "OK":
                    log("!! EXPUNGE 失敗: {}".format(fname))
                    break
                for r in ok_rows[i:i + BATCH]:
                    db.mark_server_deleted(conn, r["id"])
                    # 原本の隣に「サーバーからは消した」印を置く（DBを作り直しても分かる）
                    try:
                        marker = os.path.join(config.DATA_DIR, r["raw_path"]) + ".deleted.json"
                        with open(marker, "w", encoding="utf-8") as fp:
                            json.dump({"deleted_at": db.utcnow(), "uid": r["uid"],
                                       "uidvalidity": r["uidvalidity"],
                                       "message_id": r["message_id"]}, fp, ensure_ascii=False)
                    except Exception as e:
                        log("  墓標を書けなかった（削除自体は成功）: {}".format(e))
                    db.log_delete(conn, r, "deleted", "")
                    freed += int(r["size_bytes"] or 0)
                    done += 1
                conn.commit()
                log("{}: {}通を削除（累計 {}）".format(fname, len(chunk), done))

        print("--------")
        print("{}: 対象 {}通 / 見送り {}通 / 解放見込み {:.1f} MB"
              .format("削除しました" if really else "dry-run（何も消していません）",
                      done, skipped, freed / 1024 / 1024))
        if not really:
            print("本当に消すなら: python3 sync.py --delete --yes")
    finally:
        try:
            imap.logout()
        except Exception:
            pass


# ------------------------------------------------------------------ main

def main() -> int:
    p = argparse.ArgumentParser(description="メールアーカイバ 同期／削除")
    p.add_argument("--sync", action="store_true", help="IMAPからローカルへ取り込む")
    p.add_argument("--delete", action="store_true", help="サーバー側の削除（既定は dry-run）")
    p.add_argument("--yes", action="store_true", help="★dry-run ではなく本当に消す")
    p.add_argument("--verify", action="store_true", help="保存済み .eml の総点検")
    p.add_argument("--rebuild", action="store_true",
                   help="原本(.eml)とサイドカーからDBを作り直す（DBを消しても戻せる）")
    p.add_argument("--stats", action="store_true", help="件数・容量を表示")
    p.add_argument("--days", type=int, default=None, help="削除の据置日数（既定14）")
    p.add_argument("--folder", default=None, help="対象フォルダ名を1つに絞る")
    p.add_argument("--limit", type=int, default=0, help="1フォルダあたりの取り込み上限")
    p.add_argument("--since-days", type=int, default=None, help="この日数以内のメールだけ取り込む")
    p.add_argument("--max-delete", type=int, default=500, help="1回で消す上限（既定500）")
    p.add_argument("--include-unseen", action="store_true", help="未読も削除対象にする")
    p.add_argument("--include-flagged", action="store_true", help="フラグ付きも削除対象にする")
    p.add_argument("--allow-full-expunge", action="store_true",
                   help="UIDPLUS非対応サーバーで素のEXPUNGEを許す（他の\\Deletedも消える）")
    p.add_argument("--db", default=config.DB_PATH)
    args = p.parse_args()

    cfg = config.load()
    conn = db.connect(args.db)
    db.init_schema(conn)

    if args.stats:
        s = db.stats(conn)
        print("保存 {messages}通 / {bytes:.0f} bytes".format(**s))
        print("  サーバーに残っている: {}通 ({:.1f} MB)".format(s["present"], s["present_bytes"] / 1024 / 1024))
        print("  サーバーから削除済み: {}通 ({:.1f} MB)".format(s["deleted"], s["deleted_bytes"] / 1024 / 1024))
        print("  添付 {}件 ({:.1f} MB)".format(s["attachments"], s["attachment_bytes"] / 1024 / 1024))
        return 0

    if args.rebuild:
        return do_rebuild(conn)

    if args.verify:
        return 1 if do_verify(conn) else 0

    if not (args.sync or args.delete):
        p.print_help()
        return 0

    if not cfg["IMAP_HOST"] or not cfg["IMAP_USER"] or not cfg["IMAP_PASSWORD"]:
        print("接続設定がありません。.env.mail-archiver.example を写して .env.mail-archiver を作ってください。")
        return 2

    if args.sync:
        do_sync(conn, cfg, args.folder, args.limit, args.since_days)

    if args.delete:
        days = args.days if args.days is not None else int(cfg.get("ARCHIVE_DELETE_DAYS", "14"))
        do_delete(conn, cfg, days, args.yes, args.folder, args.max_delete,
                  args.include_unseen, args.include_flagged, args.allow_full_expunge)
    return 0


if __name__ == "__main__":
    sys.exit(main())
