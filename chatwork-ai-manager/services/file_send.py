"""社内資料（Dropbox共有フォルダ）を Chatwork へ添付送信する（Stage 9・2026-08-19）。

## なぜ作ったか

2026-08-19、塚本さんが「グランビルド岩城3階の図面を送って」と**3回**依頼したが、
AIは3回とも「ファイル添付の送信機能は持っていません」と答え、Dropboxのパスを
案内するだけだった。資料の場所は分かるのに渡せない、という状態を解消する。

## 安全の考え方（社内資料を外へ出す操作なので、ここは厚くする）

1. **送信元を共有フォルダ配下に限定**（オーナー判断 2026-08-19: 共有フォルダ全体は許可）。
   realpath で解決してから判定するので、`..` やシンボリックリンクで外へ出られない。
   → `/etc/passwd` や他アプリの `.env`、`flyer-creator` の案件フォルダ（入居申込者の
     身分証が同居）などは**構造的に送れない**。
2. **サイズ上限**（Chatwork側が5MB）。超えるものは送らずパスを案内する。
3. **必ず記録**（`sent_files` テーブル）。いつ・何を・どこへ・誰の依頼で、を残す。
4. **送信ごとにLINEへ通知**。意図しない送信にその場で気づけるようにする。
"""
import os
import unicodedata

from db.connection import get_conn
from services import config, settings

MAX_BYTES = 5 * 1024 * 1024      # Chatwork のファイル上限


def _norm(s: str) -> str:
    """ファイル名を比較するための正規化。

    **macOS は濁点・半濁点を分解した NFD でファイル名を返す**（`グランビルド` の
    「グ」が「ク」+濁点になる）。こちらのコードやDB由来の文字列は NFC なので、
    見た目が同じでも `==` や `in` が一致しない。
    2026-08-19 に実際にこれで「ファイルが見つかりません」となった。
    比較の前に必ず両方を NFC に揃える（**開くときは OS が返した実際のパスを使う**）。
    """
    return unicodedata.normalize("NFC", s or "")


def allowed_roots() -> list:
    """送信を許可するフォルダ（の絶対パス）。ここに無いものは送らない。"""
    roots = []
    src = config.get("knowledge_source_dir")
    if src:
        roots.append(os.path.realpath(src))
    # 追加で許可したいフォルダがあれば設定から（カンマ区切り）。既定は空。
    extra = settings.get_setting("file_send_extra_roots", "") or ""
    for p in str(extra).split(","):
        p = p.strip()
        if p:
            roots.append(os.path.realpath(p))
    return [r for r in roots if r]


def is_archived(path: str) -> bool:
    """「_アーカイブ（2027年7月削除予定）」配下かどうか。

    共有フォルダには**現行と同じ資料がアーカイブ側にも重複して残っている**
    （2026-08-19 実測: グランビルド岩城3F.jpg は現行とアーカイブに同一ハッシュで存在）。
    どちらを送っても中身は同じだが、アーカイブは削除予定なので
    「そこを見に行けばある」と案内してしまうと、あとで参照先が消える。
    現行があるなら必ず現行を送る。
    """
    # ここも NFC に揃えてから判定する。macOSが返すパスは NFD なので、
    # 素の `"アーカイブ" in path` では**一致せず、アーカイブを現行と誤判定する**
    # （2026-08-19 実測。find_files がアーカイブを「現行」と表示していた）。
    return "アーカイブ" in _norm(path)


def _is_inside(path: str, root: str) -> bool:
    """path が root の中かを厳密に見る（前方一致だけだと別フォルダを誤許可する）。"""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:      # ドライブ違い等で比較できない
        return False


def source_note(real_path: str) -> str:
    """「共有フォルダのどこから持ってきたか」を示す一文を作る。

    絶対パスをそのまま貼ると `/Users/apple/Library/CloudStorage/Dropbox-…` という
    このMac固有の長い前置きが付いて読みにくいので、**共有フォルダから見た相対パス**に直す。
    受け取った社員がそのままDropboxを辿れる形にするのが目的。
    """
    for root in allowed_roots():
        if _is_inside(real_path, root):
            rel = os.path.relpath(real_path, root)
            folder = os.path.dirname(rel)
            note = ("📁 保管場所（社内共有フォルダ「" + os.path.basename(root) + "」内）\n"
                    + (folder if folder and folder != "." else "（直下）"))
            if is_archived(real_path):
                # 現行側に無く、アーカイブしか無かった場合。参照先が将来消えることを伝える。
                note += ("\n⚠️ このファイルはアーカイブ（削除予定）フォルダにしかありません。"
                         "必要なら現行フォルダへの移動をご検討ください。")
            return note
    return "📁 保管場所: " + real_path


def resolve(file_path: str) -> str:
    """絶対パスでなくても実体を探し当てる（見つからなければ元の解決結果を返す）。

    Claude が持っている手がかりは「全ファイル一覧」由来の**相対パス**や
    ファイル名だけのことが多く、絶対パスを知らない。そのままだと送れないので、
    共有フォルダ配下を順に当たって実体に解決する。
    （全22,207ファイルの走査が実測0.1秒なので、素直に探して問題ない）
    """
    if not file_path:
        return ""
    p = os.path.expanduser(file_path)
    real = os.path.realpath(p)
    if os.path.isfile(real):
        return real
    roots = allowed_roots()
    # ① 共有フォルダからの相対パスとして解釈する
    rel = p.lstrip("/")
    for root in roots:
        cand = os.path.realpath(os.path.join(root, rel))
        if os.path.isfile(cand) and _is_inside(cand, root):
            return cand
    # ② ファイル名（末尾）が一致するものを探す。
    #    同名が複数あるときは**現行を優先し、アーカイブは最後**にする（削除予定のため）。
    name = _norm(os.path.basename(p))
    if name:
        found = []
        for root in roots:
            for dirpath, _dirs, files in os.walk(root):
                for f in files:
                    if _norm(f) == name:
                        found.append(os.path.join(dirpath, f))   # OSが返した実体を使う
        if found:
            found.sort(key=lambda f: (is_archived(f), len(f)))
            return found[0]
    return real


def find_files(name_part: str, limit: int = 20) -> dict:
    """共有フォルダからファイル名の一部で探す（送る前の候補出しに使う）。"""
    if not (name_part or "").strip():
        return {"ok": False, "error": "探す文字列が必要です"}
    key = _norm(name_part.strip()).lower()
    hits = []
    for root in allowed_roots():
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if key in _norm(f).lower():
                    full = os.path.join(dirpath, f)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        continue
                    hits.append({"path": full, "name": f, "size": size,
                                 "folder": os.path.relpath(dirpath, root),
                                 "archived": is_archived(full),
                                 "sendable": size <= MAX_BYTES and size > 0})
    # 並び: 送れるもの → 現行（アーカイブでない）→ 名前順。
    # アーカイブは削除予定なので、同じ資料が両方にあるときは必ず現行が先に来る。
    hits.sort(key=lambda h: (not h["sendable"], h["archived"], h["name"]))
    hits = hits[:limit]
    return {"ok": True, "count": len(hits), "files": hits,
            "note": "sendable=true のものは chatwork_send_file の path にそのまま渡せる。"
                    "archived=true は削除予定フォルダなので、同名で archived=false があれば"
                    "**必ずそちらを送る**"}


def check(file_path: str) -> dict:
    """送ってよいかを判定する（送信はしない）。戻り値に理由を必ず入れる。"""
    if not file_path:
        return {"ok": False, "reason": "file_path が空です"}
    real = resolve(file_path)
    if not os.path.isfile(real):
        return {"ok": False, "reason": f"ファイルが見つかりません: {file_path}"}
    roots = allowed_roots()
    if not roots:
        return {"ok": False, "reason": "送信元フォルダ（knowledge_source_dir）が未設定です"}
    if not any(_is_inside(real, r) for r in roots):
        return {"ok": False,
                "reason": "社内共有フォルダの外にあるファイルは送信できません（安全のため）"}
    size = os.path.getsize(real)
    if size > MAX_BYTES:
        return {"ok": False, "size": size,
                "reason": f"Chatworkの上限5MBを超えています（{size / 1024 / 1024:.1f}MB）。"
                          f"送信できないのでパスを案内してください"}
    if size == 0:
        return {"ok": False, "reason": "中身が空のファイルです"}
    return {"ok": True, "path": real, "size": size, "name": os.path.basename(real)}


def send(room_id, file_path: str, message: str = None,
         requester: str = None, requester_account_id=None) -> dict:
    """共有フォルダのファイルを Chatwork のルームへ添付する。

    送信の可否は check() が決める。送った結果は成功・失敗・拒否のいずれも記録する。
    """
    if not room_id:
        return {"ok": False, "error": "room_id が必要です"}
    verdict = check(file_path)
    if not verdict.get("ok"):
        _record(room_id, file_path, os.path.basename(file_path or ""), None, message,
                requester, requester_account_id, None, "blocked", verdict.get("reason"))
        return {"ok": False, "error": verdict.get("reason")}

    real, size, name = verdict["path"], verdict["size"], verdict["name"]
    prefix = settings.get_setting("ai_prefix", "🤖AI業務マネージャー")
    body = message or f"{name} をお送りします。"
    # ★どこから持ってきたファイルなのかを必ず添える（2026-08-19 オーナー要望）。
    #   受け取った人が「これはどのフォルダの資料か」「最新版はどこを見ればよいか」を
    #   その場で判断できるようにするため。添付だけだと出所が分からず、
    #   結局フォルダを探し直すことになっていた。
    body = f"{body}\n\n{source_note(real)}"
    if prefix and prefix not in body:
        body = f"{prefix}\n\n{body}"

    from services.chatwork import ChatworkClient, ChatworkError
    try:
        file_id = ChatworkClient().post_file(room_id, real, message=body, filename=name)
    except ChatworkError as e:
        _record(room_id, real, name, size, body, requester, requester_account_id,
                None, "failed", str(e))
        return {"ok": False, "error": str(e)}
    except OSError as e:
        # Dropbox(CloudStorage)がTCCで読めない場合など
        _record(room_id, real, name, size, body, requester, requester_account_id,
                None, "failed", f"読み取り失敗: {e}")
        return {"ok": False, "error": f"ファイルを読めませんでした: {e}"}

    _record(room_id, real, name, size, body, requester, requester_account_id,
            file_id, "sent", None)
    # LINE通知は**既定で送らない**（2026-08-19 オーナー判断で撤回。送るたびに通知が来て煩い）。
    # 記録は sent_files に必ず残るので、後から見返すことはできる。
    # 監視したくなったら設定 file_send_notify_line=1 で戻せる。
    if settings.get_setting("file_send_notify_line", "0") == "1":
        _notify_sent(room_id, name, size, requester)
    return {"ok": True, "sent": True, "file_id": file_id, "file_name": name, "size": size}


def _record(room_id, path, name, size, message, requester, requester_account_id,
            file_id, status, error):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO sent_files (room_id, file_path, file_name, file_size, message, "
                "requester, requester_account_id, chatwork_file_id, status, error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (room_id, path, name, size, (message or "")[:1000], requester,
                 requester_account_id, file_id, status, (str(error)[:500] if error else None)))
    except Exception as e:
        print(f"[file_send] 記録に失敗: {type(e).__name__}: {e}", flush=True)


def _notify_sent(room_id, name, size, requester):
    """送信ごとにLINEへ知らせる（オーナー判断 2026-08-19）。宛先が無ければ何もしない。"""
    try:
        from services import line_client
        raw = config.get("line_admin_user_ids", "") or ""
        ids = [u.strip() for u in str(raw).split(",") if u.strip()] or \
            sorted(line_client.allowed_user_ids())
        room = ""
        try:
            from db.connection import query_one
            r = query_one("SELECT name FROM rooms WHERE room_id=?", (room_id,))
            room = r["name"] if r else ""
        except Exception:
            pass
        text = (f"📎 Chatworkへファイルを送信しました\n\n"
                f"ファイル: {name}（{size / 1024:.0f}KB）\n"
                f"送信先: {room or room_id}\n"
                f"依頼者: {requester or '不明'}")
        for uid in ids:
            line_client.push(uid, f"🩺 AI業務マネージャー\n\n{text}", label="file_send")
    except Exception as e:
        print(f"[file_send] 通知に失敗: {type(e).__name__}: {e}", flush=True)
