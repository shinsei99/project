"""KeyLine の業務ロジック。

画面（app.py）はここを呼ぶだけにし、SQL は原則ここから外に出さない。

★このファイルで一番大事なのは checkout() と return_asset()。
  「状態だけ更新されて履歴が残らない」「2人に同時に貸し出す」を防ぐため、
  DBの制約・トランザクション・条件付きUPDATE の3層で守っている。詳しくは各関数の説明。
"""

from __future__ import annotations

import secrets
import sqlite3
from typing import Any, Optional

import db as dbmod
from db import Conflict

# ---------------------------------------------------------------------------
# 現場向けのエラー
#
# ご指示26のとおり、技術的な内容をそのまま画面に出さない。
# 例外のメッセージは**そのまま利用者に見せてよい文言**にしてある。
# ---------------------------------------------------------------------------
class NotFound(Exception):
    """対象が見つからない。"""


class Forbidden(Exception):
    """権限が足りない。"""


class InvalidInput(Exception):
    """入力が足りない・おかしい。"""


# ---------------------------------------------------------------------------
# NFCトークン
# ---------------------------------------------------------------------------
# タグに書き込む URL は http://<host>/t/<token> の形。
# トークンは **推測できないこと**が要る（連番だと他の鍵のページを総当たりで開けてしまう）。
# 一方でタグに書く文字列なので短い方がよい。16文字の base32 風＝約80bitで十分。
TOKEN_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"   # l/o/0/1 は目視で紛れるので除く
TOKEN_LENGTH = 16


def new_nfc_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def issue_nfc_token(con: sqlite3.Connection) -> str:
    """まだ使われていないトークンを作る。衝突はまず起きないが一応確かめる。"""
    for _ in range(10):
        token = new_nfc_token()
        if not con.execute("SELECT 1 FROM assets WHERE nfc_identifier = ?", (token,)).fetchone():
            return token
    raise RuntimeError("NFCトークンを発行できませんでした")


def tag_url(base_url: str, token: str) -> str:
    """NFCタグに書き込むURL。この文字列をタグにNDEF URLレコードとして書く。"""
    return f"{base_url.rstrip('/')}/t/{token}"


# タグに書くURLのホスト。
#
# ★ここを「アクセス中のURL」から取ってはいけない。
#   管理者が http://localhost:8534 で開いていると localhost 入りのURLが表示され、
#   それをタグに書くとスマホからは自分自身を指すので**永久に開けない**。
#   タグは物理的に書き直しになるため、事故に気づくのが遅いほど痛い。
#   したがって常に **LANのIP** を使い、環境変数で上書きできるようにする。
PORT = 8534


def lan_base_url() -> str:
    """社内LANから届くベースURL。KEYLINE_BASE_URL で上書きできる。"""
    import os
    import socket

    override = os.environ.get("KEYLINE_BASE_URL")
    if override:
        return override.rstrip("/")

    ip = None
    try:
        # 外に繋ぎに行かずに「どのIPで外へ出るか」だけをOSに聞く（UDPなので通信は発生しない）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.168.1.1", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        pass
    return f"http://{ip or socket.gethostbyname(socket.gethostname())}:{PORT}"


# ---------------------------------------------------------------------------
# 参照
# ---------------------------------------------------------------------------
def find_by_token(con: sqlite3.Connection, org_id: str, token: str) -> Optional[sqlite3.Row]:
    """NFCトークンから管理対象を引く。

    ★organization_id を必ず条件に入れる。
      トークンは推測されにくいだけで**秘密ではない**（タグを拾えば読める）。
      権限判定はログインセッション側の組織で行い、NFCの値を信用しない（ご指示28）。
    """
    return con.execute(
        "SELECT * FROM v_asset_overview WHERE nfc_identifier = ? AND organization_id = ?",
        (token, org_id),
    ).fetchone()


def get_asset(con: sqlite3.Connection, org_id: str, asset_id: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT * FROM v_asset_overview WHERE id = ? AND organization_id = ?",
        (asset_id, org_id),
    ).fetchone()
    if row is None:
        raise NotFound("その管理対象は見つかりませんでした")
    return row


def list_assets(con: sqlite3.Connection, org_id: str, status: Optional[str] = None,
                q: Optional[str] = None) -> list[sqlite3.Row]:
    """管理対象一覧（ご指示14）。貸出中を先頭に、超過を最優先で出す。"""
    sql = ["SELECT * FROM v_asset_overview WHERE organization_id = ?"]
    args: list[Any] = [org_id]
    if status:
        sql.append("AND status = ?")
        args.append(status)
    if q:
        # 名前・鍵番号・ボックス・借主のどれでも引っかかるようにする
        sql.append("""AND (name LIKE ? OR IFNULL(item_numbers,'') LIKE ?
                          OR IFNULL(box_code,'') LIKE ? OR IFNULL(borrower_name,'') LIKE ?
                          OR IFNULL(borrower_company,'') LIKE ?)""")
        args += [f"%{q}%"] * 5
    sql.append("ORDER BY is_overdue DESC, status = 'checked_out' DESC, due_at ASC, name ASC")
    return con.execute(" ".join(sql), args).fetchall()


def list_items(con: sqlite3.Connection, asset_id: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM asset_items WHERE asset_id = ? ORDER BY sort_order, created_at",
        (asset_id,),
    ).fetchall()


def list_boxes(con: sqlite3.Connection, org_id: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM boxes WHERE organization_id = ? AND is_active = 1 ORDER BY code",
        (org_id,),
    ).fetchall()


def recent_borrowers(con: sqlite3.Connection, org_id: str, limit: int = 12) -> list[sqlite3.Row]:
    """「最近の貸出先から選ぶ」用。直近に借りた順、次によく借りる順。

    現場で一番使う導線なので、ここが速いかどうかで使われるかが決まる。
    """
    return con.execute(
        """SELECT * FROM v_borrower_usage
            WHERE organization_id = ? AND is_active = 1
            ORDER BY last_checkout_at DESC NULLS LAST, checkout_count DESC, name
            LIMIT ?""",
        (org_id, limit),
    ).fetchall()


def search_borrowers(con: sqlite3.Connection, org_id: str, q: str,
                     limit: int = 30) -> list[sqlite3.Row]:
    return con.execute(
        """SELECT * FROM v_borrower_usage
            WHERE organization_id = ? AND is_active = 1
              AND (name LIKE ? OR IFNULL(company,'') LIKE ? OR IFNULL(phone,'') LIKE ?)
            ORDER BY last_checkout_at DESC NULLS LAST, name
            LIMIT ?""",
        (org_id, f"%{q}%", f"%{q}%", f"%{q}%", limit),
    ).fetchall()


def history(con: sqlite3.Connection, org_id: str, asset_id: Optional[str] = None,
            borrower_id: Optional[str] = None, limit: int = 200) -> list[sqlite3.Row]:
    """貸出履歴（ご指示12）。

    ★ORDER BY に rowid を必ず添える。checkout_at だけでは同一時刻の順序が決まらない
      （README「7. 時刻だけでは履歴の全順序を保証できない」参照）。
    """
    sql = ["""SELECT c.*, a.name AS asset_name, b.name AS borrower_name,
                     b.company AS borrower_company, b.kind AS borrower_kind
                FROM checkout_logs c
                JOIN assets a    ON a.id = c.asset_id
                JOIN borrowers b ON b.id = c.borrower_id
               WHERE c.organization_id = ?"""]
    args: list[Any] = [org_id]
    if asset_id:
        sql.append("AND c.asset_id = ?")
        args.append(asset_id)
    if borrower_id:
        sql.append("AND c.borrower_id = ?")
        args.append(borrower_id)
    sql.append("ORDER BY c.checkout_at DESC, c.rowid DESC LIMIT ?")
    args.append(limit)
    return con.execute(" ".join(sql), args).fetchall()


def open_log(con: sqlite3.Connection, asset_id: str) -> Optional[sqlite3.Row]:
    """いま貸出中の履歴行。idx_checkout_open により必ず0本か1本。"""
    return con.execute(
        "SELECT * FROM checkout_logs WHERE asset_id = ? AND returned_at IS NULL", (asset_id,)
    ).fetchone()


def stats(con: sqlite3.Connection, org_id: str) -> dict:
    r = con.execute(
        """SELECT COUNT(*) AS total,
                  SUM(status = 'checked_out') AS out,
                  SUM(is_overdue)             AS overdue,
                  SUM(nfc_identifier IS NULL) AS no_tag
             FROM v_asset_overview WHERE organization_id = ?""",
        (org_id,),
    ).fetchone()
    return {k: (r[k] or 0) for k in ("total", "out", "overdue", "no_tag")}


# ---------------------------------------------------------------------------
# 貸出先
# ---------------------------------------------------------------------------
def create_borrower(con: sqlite3.Connection, org_id: str, name: str, kind: str = "vendor",
                    company: Optional[str] = None, phone: Optional[str] = None,
                    note: Optional[str] = None) -> str:
    name = (name or "").strip()
    if not name:
        raise InvalidInput("お名前を入力してください")
    if kind not in ("employee", "vendor", "customer", "other"):
        kind = "other"
    bid = dbmod.new_id()
    con.execute(
        """INSERT INTO borrowers (id, organization_id, kind, name, company, phone, note)
           VALUES (?,?,?,?,?,?,?)""",
        (bid, org_id, kind, name, (company or "").strip() or None,
         (phone or "").strip() or None, (note or "").strip() or None),
    )
    return bid


def get_borrower(con: sqlite3.Connection, org_id: str, borrower_id: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT * FROM borrowers WHERE id = ? AND organization_id = ?", (borrower_id, org_id)
    ).fetchone()
    if row is None:
        raise NotFound("その貸出先は見つかりませんでした")
    return row


# ---------------------------------------------------------------------------
# ★ 貸出（ご指示9・23・28）
# ---------------------------------------------------------------------------
def checkout(con: sqlite3.Connection, org_id: str, asset_id: str, borrower_id: str,
             due_at: Optional[str] = None, image: Optional[tuple] = None,
             note: Optional[str] = None) -> str:
    """貸出する。返り値は作った履歴のID。

    二重貸出を3層で防いでいる:

      1. BEGIN IMMEDIATE
         最初から書き込みロックを取る。後から昇格させようとすると、2人同時のときに
         片方が SQLITE_BUSY で落ちてしまう。

      2. 条件付きUPDATE + changes() の確認
         status='in_stock' の時だけ更新する。「読んでから書く」の間に横取りされる隙を
         作らない。0件なら誰かに先を越されたということなので Conflict にする。

      3. idx_checkout_open（部分UNIQUEインデックス）
         万一1・2をすり抜けても、未返却の履歴は1本しか作れない。DBが最後に止める。

    そして状態の更新と履歴のINSERTを**同じトランザクション**に入れている。
    片方だけ成功すると「貸出中なのに誰に貸したか分からない」状態になるため。
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        # 貸出先が同じ組織のものか確かめる（DBのトリガーでも止まるが、
        # 現場向けの文言を返したいのでここでも見る）
        if not con.execute(
            "SELECT 1 FROM borrowers WHERE id = ? AND organization_id = ? AND is_active = 1",
            (borrower_id, org_id),
        ).fetchone():
            raise NotFound("その貸出先は見つかりませんでした")

        now = dbmod.now_ts()
        con.execute(
            """UPDATE assets SET status = 'checked_out', current_borrower_id = ?,
                                 checked_out_at = ?, due_at = ?
                WHERE id = ? AND organization_id = ? AND status = 'in_stock'""",
            (borrower_id, now, due_at, asset_id, org_id),
        )
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            # 在庫でなかった＝すでに貸出中／紛失・修理中／他組織のID
            raise Conflict("この鍵はすでに貸出中です。画面を更新してください")

        log_id = dbmod.new_id()
        path, kind = image if image else (None, None)
        con.execute(
            """INSERT INTO checkout_logs
                 (id, organization_id, asset_id, borrower_id, action, checkout_at, due_at,
                  id_image_path, id_image_kind, note)
               VALUES (?,?,?,?,'checkout',?,?,?,?,?)""",
            (log_id, org_id, asset_id, borrower_id, now, due_at, path, kind, note),
        )
        con.execute("COMMIT")
        return log_id
    except Exception:
        con.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# ★ 返却（ご指示10・11）
# ---------------------------------------------------------------------------
def return_asset(con: sqlite3.Connection, org_id: str, asset_id: str,
                 force: bool = False) -> None:
    """返却する。

    共用の鍵管理端末で運用するため、**誰が操作したかは記録しない**（2026-08-17決定）。
    force=True は管理者が管理画面から行う強制返却で、履歴に区別して残す。
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        now = dbmod.now_ts()
        con.execute(
            """UPDATE assets SET status = 'in_stock', current_borrower_id = NULL,
                                 checked_out_at = NULL, due_at = NULL
                WHERE id = ? AND organization_id = ? AND status = 'checked_out'""",
            (asset_id, org_id),
        )
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            raise Conflict("この鍵は貸出中ではありません。画面を更新してください")
        con.execute(
            """UPDATE checkout_logs SET action = 'returned', returned_at = ?, return_type = ?
                WHERE asset_id = ? AND returned_at IS NULL""",
            (now, "admin_force" if force else "normal", asset_id),
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# 管理対象の登録・編集（ご指示15）
# ---------------------------------------------------------------------------
def create_asset(con: sqlite3.Connection, org_id: str, name: str,
                 asset_type: str = "key", nfc_token: Optional[str] = None,
                 box_id: Optional[str] = None, box_position: Optional[str] = None,
                 item_numbers: Optional[list] = None, note: Optional[str] = None) -> str:
    """管理対象を作る。未登録タグからその場で登録する導線もここを通る。"""
    name = (name or "").strip()
    if not name:
        raise InvalidInput("管理対象の名前を入力してください")

    con.execute("BEGIN IMMEDIATE")
    try:
        if nfc_token and con.execute(
            "SELECT 1 FROM assets WHERE nfc_identifier = ?", (nfc_token,)
        ).fetchone():
            raise Conflict("そのNFCタグはすでに別の管理対象に使われています")

        aid = dbmod.new_id()
        con.execute(
            """INSERT INTO assets (id, organization_id, name, asset_type, nfc_identifier,
                                   nfc_source, box_id, box_position, note)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (aid, org_id, name, asset_type, nfc_token,
             "written_token" if nfc_token else None,
             box_id or None, (box_position or "").strip() or None,
             (note or "").strip() or None),
        )
        _replace_items(con, org_id, aid, item_numbers or [])
        con.execute("COMMIT")
        return aid
    except Exception:
        con.execute("ROLLBACK")
        raise


def update_asset(con: sqlite3.Connection, org_id: str, asset_id: str, name: str,
                 asset_type: str = "key", box_id: Optional[str] = None,
                 box_position: Optional[str] = None, item_numbers: Optional[list] = None,
                 note: Optional[str] = None, status: Optional[str] = None) -> None:
    con.execute("BEGIN IMMEDIATE")
    try:
        cur = con.execute("SELECT status FROM assets WHERE id = ? AND organization_id = ?",
                          (asset_id, org_id)).fetchone()
        if cur is None:
            raise NotFound("その管理対象は見つかりませんでした")

        # 貸出中のものの状態は、ここでは変えさせない。
        # 変えると assets の CHECK（状態と借主の整合）に引っかかるうえ、
        # 未返却の履歴が宙に浮く。返却は必ず return_asset() を通す。
        if status and cur["status"] == "checked_out":
            raise Conflict("貸出中のため状態を変更できません。先に返却してください")

        con.execute(
            """UPDATE assets SET name = ?, asset_type = ?, box_id = ?, box_position = ?,
                                 note = ?, status = COALESCE(?, status)
                WHERE id = ? AND organization_id = ?""",
            ((name or "").strip(), asset_type, box_id or None,
             (box_position or "").strip() or None, (note or "").strip() or None,
             status, asset_id, org_id),
        )
        if item_numbers is not None:
            _replace_items(con, org_id, asset_id, item_numbers)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def _replace_items(con: sqlite3.Connection, org_id: str, asset_id: str,
                   item_numbers: list) -> None:
    """構成品を入れ替える。**呼び出し側がトランザクションを張っている前提。**

    差分更新ではなく全消し＋入れ直しにしている。構成品には履歴が紐づいておらず、
    行のIDを保つ意味がないため。差分計算のバグで鍵が消える方が怖い。
    """
    con.execute("DELETE FROM asset_items WHERE asset_id = ?", (asset_id,))
    for n, num in enumerate(item_numbers):
        num = (num or "").strip()
        if not num:
            continue
        con.execute(
            """INSERT INTO asset_items (id, organization_id, asset_id, item_type,
                                        item_number, sort_order)
               VALUES (?,?,?,'key',?,?)""",
            (dbmod.new_id(), org_id, asset_id, num, n),
        )


def attach_tag(con: sqlite3.Connection, org_id: str, asset_id: str, token: str) -> None:
    """既存の管理対象にNFCタグを結びつける（タグ交換もこれ）。

    assets.id は変わらないので、履歴も構成品もそのまま残る（ご指示5）。
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        if con.execute("SELECT 1 FROM assets WHERE nfc_identifier = ? AND id <> ?",
                       (token, asset_id)).fetchone():
            raise Conflict("そのNFCタグはすでに別の管理対象に使われています")
        con.execute(
            """UPDATE assets SET nfc_identifier = ?, nfc_source = 'written_token'
                WHERE id = ? AND organization_id = ?""",
            (token, asset_id, org_id),
        )
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            raise NotFound("その管理対象は見つかりませんでした")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# ボックス
# ---------------------------------------------------------------------------
def create_box(con: sqlite3.Connection, org_id: str, code: str, name: str,
               location: Optional[str] = None) -> str:
    code, name = (code or "").strip(), (name or "").strip()
    if not code or not name:
        raise InvalidInput("ボックスの記号と名前を入力してください")
    if con.execute("SELECT 1 FROM boxes WHERE organization_id = ? AND code = ?",
                   (org_id, code)).fetchone():
        raise Conflict(f"「{code}」はすでに登録されています")
    bid = dbmod.new_id()
    con.execute(
        "INSERT INTO boxes (id, organization_id, code, name, location) VALUES (?,?,?,?,?)",
        (bid, org_id, code, name, (location or "").strip() or None),
    )
    return bid


# ---------------------------------------------------------------------------
# 返却予定の候補（ご指示25「不要な入力を増やさない」）
# ---------------------------------------------------------------------------
def due_choices() -> list:
    """現場で押しやすい選択肢だけ出す。日時ピッカーを触らせない。

    「今日18:00」は日本時間の18時。すでに18時を過ぎていたら出さない
    （押せない選択肢を並べない）。
    """
    from datetime import timedelta

    now_jst = dbmod.to_local(dbmod.now_ts())
    out = []
    for label, dt in (
        ("今日 18:00",  now_jst.replace(hour=18, minute=0, second=0, microsecond=0)),
        ("明日 18:00", (now_jst + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)),
    ):
        if dt > now_jst:
            out.append((label, dbmod.to_utc_ts(dt)))
    out.append(("2時間後", dbmod.ts_plus(hours=2)))
    out.append(("3日後", dbmod.ts_plus(days=3)))
    out.append(("指定しない", ""))
    return out
