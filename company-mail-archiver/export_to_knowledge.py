#!/usr/bin/env python3
"""社内メールを **AI業務マネージャーの知識索引**（大京商事）へ渡す。

    /usr/bin/python3 export_to_knowledge.py --stats        いまの状況を見る
    /usr/bin/python3 export_to_knowledge.py --dry          何を入れる/外すかだけ見る
    /usr/bin/python3 export_to_knowledge.py --since-days 365
    /usr/bin/python3 export_to_knowledge.py --limit 200    少しずつ試す

## 何をするか

1. 社内メールアーカイバのDBから、**業務メールだけ**を選ぶ（下の「選び方」）
2. 1通1ファイルの `.md` に書き出す（本文＋**添付から取り出した文字**）
3. `chatwork-ai-manager` の `knowledge.ingest_folder(company='大京商事株式会社')` で索引に入れる

## ★会社の壁（絶対に守る）

**必ず `company='大京商事株式会社'` を渡す。** 渡さないと DB の既定に落ちるが、
既定が変わったときに新誠側から読めてしまう。`services/company_scope.py` の設計どおり、
**壁はSQLで作る**（プロンプトでのお願いにしない）。

## ★書き出し先はローカル固定（共有フォルダへ出さない）

`knowledge_out/` はこのフォルダの中（gitignore）。
**大京の共有Dropboxへ書いてはいけない**——社員のメール本文が全社員に見えてしまう。
索引DB自体もメインPCのローカルにしかない。

## 選び方（ノイズを入れない）

入れるほど良いわけではない。**メルマガや自動通知が混ざると、AIの回答が薄まる。**
次を外す（外した理由は必ず記録して数える。黙って捨てない）:

- `List-Unsubscribe` ヘッダがある（＝配信停止リンク付き＝メルマガ・広告）
- `Precedence: bulk / list / junk`、`Auto-Submitted: auto-*`（自動送信）
- 差出人が `noreply` / `no-reply` / `donotreply` / `mailer-daemon` / `postmaster`
- 本文も添付の中身も空

**逆に、社内ドメインとのやりとりは優先して入れる**（`daikyocorp.co.jp`）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
MAIL_ARCHIVER = os.path.join(os.path.dirname(HERE), "mail-archiver")
CWAI = os.path.join(os.path.dirname(HERE), "chatwork-ai-manager")

# ★コードは複製しない。メールアーカイバの db.py / config.py をそのまま使い、
#   環境変数で「どのDB・どの保管先か」だけを差し替える（run.sh が設定する）。
sys.path.insert(0, MAIL_ARCHIVER)

COMPANY = "大京商事株式会社"      # ★会社の壁。ここを変えない
INTERNAL_DOMAIN = "daikyocorp.co.jp"
OUT_DIR = os.path.join(HERE, "knowledge_out")

_NOREPLY = re.compile(r"(?:^|[<\s.])(?:noreply|no-reply|no_reply|donotreply|do-not-reply|"
                      r"mailer-daemon|postmaster|bounce)", re.I)


def _headers_of(raw_path: str) -> dict:
    """`.eml` の**ヘッダだけ**読む（本文まで読むと遅い）。"""
    out = {}
    try:
        with open(raw_path, "rb") as f:
            blob = f.read(16384)
    except OSError:
        return out
    head = blob.split(b"\r\n\r\n", 1)[0].split(b"\n\n", 1)[0]
    text = head.decode("utf-8", "replace")
    text = re.sub(r"\n[ \t]+", " ", text)          # 折り返しをつなぐ
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def judge(row, headers: dict, body_len: int) -> tuple:
    """(入れるか, 理由) を返す。**外した理由も数えられるように文字列で返す。**"""
    frm = (row["from_addr"] or "") + " " + (row["from_name"] or "")
    if "list-unsubscribe" in headers:
        return False, "メルマガ（配信停止リンクあり）"
    prec = (headers.get("precedence") or "").lower()
    if prec in ("bulk", "list", "junk"):
        return False, "一斉配信（Precedence: {}）".format(prec)
    if (headers.get("auto-submitted") or "").lower().startswith("auto"):
        return False, "自動送信"
    if _NOREPLY.search(frm):
        return False, "返信不可アドレスからの通知"
    if body_len == 0:
        return False, "本文も添付の中身も空"
    return True, "業務メール"


def safe_name(s: str, limit: int = 60) -> str:
    s = re.sub(r"[\\/:*?\"<>|\n\r\t]", "_", s or "").strip()
    return (s[:limit] or "無題")


def build_markdown(row, attachments) -> str:
    """索引に入れる本文。**誰と誰の、いつの、何の話か**が1行目で分かる形にする。"""
    lines = [
        "# {}".format(row["subject"] or "（件名なし）"),
        "",
        "- 日時: {}".format((row["date_utc"] or "")[:19].replace("T", " ")),
        "- From: {} <{}>".format(row["from_name"] or "", row["from_addr"] or ""),
        "- To: {}".format(row["to_addrs"] or ""),
    ]
    if row["cc_addrs"]:
        lines.append("- Cc: {}".format(row["cc_addrs"]))
    lines += ["- 取得元: 社内メール（{}）".format(row["account_name"] or ""), "", "## 本文", "",
              (row["body_text"] or "").strip()]
    for a in attachments:
        lines += ["", "## 添付〈{}〉".format(a["filename"]), "", (a["text"] or "").strip()]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-days", type=int, default=365, help="この日数より新しいメールだけ")
    ap.add_argument("--limit", type=int, default=0, help="最大N通（少しずつ試す用）")
    ap.add_argument("--dry", action="store_true", help="書き出しも索引もしない（内訳だけ）")
    ap.add_argument("--stats", action="store_true", help="いまの状況だけ見る")
    ap.add_argument("--no-ingest", action="store_true", help="書き出すだけ（索引に入れない）")
    args = ap.parse_args()

    import config
    import db
    conn = db.connect(config.DB_PATH)

    if args.stats:
        s = db.stats(conn)
        n_out = sum(len(fs) for _, _, fs in os.walk(OUT_DIR)) if os.path.isdir(OUT_DIR) else 0
        print("社内メール: {:,} 通 / 書き出し済み: {:,} ファイル".format(s["messages"], n_out))
        print("書き出し先: {}".format(OUT_DIR))
        return 0

    since = (datetime.now(timezone.utc) - timedelta(days=args.since_days)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = ("SELECT m.*, a.name AS account_name FROM messages m "
           "JOIN accounts a ON a.id = m.account_id "
           "WHERE m.date_utc >= ? ORDER BY m.date_utc DESC")
    params = [since]
    if args.limit:
        sql += " LIMIT ?"
        params.append(args.limit)
    rows = conn.execute(sql, params).fetchall()

    print("{} 社内メール → 知識索引（{}）".format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), COMPANY))
    print("  対象 {:,}通（直近{}日）／書き出し先 {}".format(len(rows), args.since_days, OUT_DIR))

    kept, dropped = 0, {}
    written = 0
    for row in rows:
        atts = db.attachment_texts_of(conn, row["id"])
        body_len = len((row["body_text"] or "").strip()) + sum(len(a["text"] or "") for a in atts)
        headers = _headers_of(os.path.join(config.DATA_DIR, row["raw_path"]))
        ok, why = judge(row, headers, body_len)
        if not ok:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        kept += 1
        if args.dry:
            continue
        # 保存先: knowledge_out/社内メール/<アカウント>/<YYYY-MM>/<id>_<件名>.md
        #   ★category_of() がフォルダ構成から分類名を作るので、ここが索引の見出しになる
        ym = (row["date_utc"] or "")[:7] or "日付不明"
        d = os.path.join(OUT_DIR, "社内メール", safe_name(row["account_name"] or "不明", 40), ym)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "{}_{}.md".format(row["id"], safe_name(row["subject"] or "")))
        text = build_markdown(row, atts)
        # 中身が同じなら書かない（mtime が変わると ingest が再取込するため）
        if os.path.exists(path):
            try:
                if open(path, encoding="utf-8").read() == text:
                    continue
            except OSError:
                pass
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        written += 1

    print("  入れる {:,}通 / 外す {:,}通".format(kept, sum(dropped.values())))
    for why, n in sorted(dropped.items(), key=lambda x: -x[1]):
        print("     外した: {} … {:,}通".format(why, n))
    if args.dry:
        print("  --dry なので書き出していない")
        return 0
    print("  新しく書き出した: {:,}ファイル".format(written))

    if args.no_ingest:
        return 0

    # ---- 知識索引へ（会社の壁を必ず指定する）
    sys.path.insert(0, CWAI)
    os.chdir(CWAI)                       # knowledge.py は相対で secrets を読む
    from db.migrate import migrate       # noqa: E402
    from services import knowledge       # noqa: E402
    migrate()
    res = knowledge.ingest_folder(OUT_DIR, incremental=True, company=COMPANY)
    print("  索引: 取込 {ingested} / 変更なし {unchanged} / 飛ばし {skipped} / "
          "失敗 {failed} / チャンク {chunks}".format(**res))
    for e in (res.get("errors") or [])[:5]:
        print("     ! {}".format(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
