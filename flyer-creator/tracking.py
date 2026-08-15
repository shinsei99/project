"""流入元の計測。どの看板・どの資料から来たかを数える。

看板を複数出すので、**どれが効いたか**を分けて数えられないと出し直しの判断ができない。
GA4などの外部サービスは使わず、サーバーのPHPだけで完結させている（アカウント不要・
Cookie不使用・IPも保存しない。持つのは「月・流入元・件数」だけ）。

    hit.php          1×1の画像を返しながら数える
    stats.php        集計の表示（?k=KEY が要る）
    data/counts.json 集計の実体（.htaccess で外から読めないようにする）

配る URL は SOURCES の通り。`?from=` が付いていればそれを sessionStorage に覚えるので、
物件ページへ進んでも同じ流入元として数える。付いていなければ「検索など」に入る。

問い合わせフォームにも流入元を hidden で持たせてあるので、**届くメールに
「どの看板から来た人か」が出る**。件数だけでなく、実際の反響の出所が分かる。
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

# キー: URLに付ける値 / 値: 表示名
SOURCES = {
    "search": "検索など",
    "doc": "チラシ",
    "city": "看板（都会）",
    "local": "看板（田舎）",
}
DEFAULT_SOURCE = "search"

# 集計の閲覧キー。URLに付けて開く（stats.php?k=…）。変えたら再アップロードすること。
#
# **このリポジトリは公開なので、キーはソースに書かない。**
# `.stats_key`（gitignore対象・1行だけのファイル）から読む。
# 他PCには別途コピーすること。無い場合は空になり、集計ページは誰も開けなくなる
# （stats.php はキーが合わなければ404を返すので、安全側に倒れる）。
_KEY_FILE = Path(__file__).parent / ".stats_key"
STATS_KEY = _KEY_FILE.read_text(encoding="utf-8").strip() if _KEY_FILE.exists() else ""

BASE_URL = "https://daikyocorp.co.jp/slowlife/"


def from_url(key: str) -> str:
    """看板・チラシに載せるQRの飛び先。`?from=` で流入元を分けて数える。

    チラシは看板のホルダーに差して配るので、**チラシのQRも看板の一部**として扱う。
    置く看板が都会（中崎町）か田舎（現地・キャンプ場）かで使い分ける。
    """
    return BASE_URL if key == DEFAULT_SOURCE else f"{BASE_URL}?from={key}"


def qr_urls() -> list[tuple[str, str]]:
    """看板に載せるURLの一覧。(表示名, URL)"""
    return [(name, from_url(key)) for key, name in SOURCES.items()]


# 短いURLで数えるための転送。`?from=` を貼りたくない場所（予約メッセージなど）で使う。
# 例: https://daikyocorp.co.jp/slowlife/camp/ → /slowlife/?from=camp
REDIRECTS: dict = {}                  # ディレクトリ名 -> 流入元のキー（今は未使用）


def redirect_php(source: str) -> str:
    return ("<?php\n"
            "// 短いURLで流入元を数えるための転送。tracking.py が書き出す。\n"
            f"header('Location: ../?from={source}', true, 302);\n")


TRACK_JS = """
(function(){
  try{
    var q = new URLSearchParams(location.search);
    // 自分の確認を数えないための印。?noc=1 で付け、?noc=0 で外す。
    // 件数が少ないサイトなので、身内の閲覧が混ざると判断を誤る。
    if (q.get('noc') === '1') localStorage.setItem('noc', '1');
    if (q.get('noc') === '0') localStorage.removeItem('noc');
    if (localStorage.getItem('noc') === '1') return;

    var f = q.get('from');
    if (f) sessionStorage.setItem('src', f);          // 入口で覚えて、以降のページでも使う
    var src = sessionStorage.getItem('src') || 'search';
    var page = location.pathname.split('/').pop() || 'index.html';
    new Image().src = 'hit.php?f=' + encodeURIComponent(src)
                    + '&p=' + encodeURIComponent(page) + '&t=' + Date.now();
  }catch(e){}
})();
"""


def hit_php(sources: dict) -> str:
    keys = "', '".join(sources)
    return f"""<?php
// 流入元を数える。1×1の画像を返すだけなので、表示には影響しない。
// 保存するのは「月・流入元・ページ・件数」だけ。IPやCookieは持たない。
declare(strict_types=1);

const SOURCES = ['{keys}'];
const STORE = __DIR__ . '/data/counts.json';

function bump(string $src, string $page, bool $contact = false): void {{
    $dir = dirname(STORE);
    if (!is_dir($dir)) {{
        @mkdir($dir, 0755, true);
        // 集計ファイルを外から読めないようにする
        @file_put_contents($dir . '/.htaccess',
            "<IfModule mod_authz_core.c>\\nRequire all denied\\n</IfModule>\\n" .
            "<IfModule !mod_authz_core.c>\\nDeny from all\\n</IfModule>\\n");
    }}
    $fh = @fopen(STORE, 'c+');
    if (!$fh) return;
    if (!flock($fh, LOCK_EX)) {{ fclose($fh); return; }}

    $raw = stream_get_contents($fh);
    $d = $raw !== '' ? json_decode($raw, true) : [];
    if (!is_array($d)) $d = [];

    $m = date('Y-m');
    $key = $contact ? 'c' : 'v';
    $d[$m][$src][$key] = ($d[$m][$src][$key] ?? 0) + 1;
    if (!$contact && $page !== '') {{
        $d[$m]['_pages'][$page] = ($d[$m]['_pages'][$page] ?? 0) + 1;
    }}

    ftruncate($fh, 0);
    rewind($fh);
    fwrite($fh, json_encode($d, JSON_UNESCAPED_UNICODE));
    fflush($fh);
    flock($fh, LOCK_UN);
    fclose($fh);
}}

if (PHP_SAPI !== 'cli' && basename($_SERVER['SCRIPT_NAME'] ?? '') === 'hit.php') {{
    $src = (string)($_GET['f'] ?? '');
    if (!in_array($src, SOURCES, true)) $src = 'other';
    $page = preg_replace('/[^0-9A-Za-z._\\x{{3000}}-\\x{{9FFF}}\\x{{FF00}}-\\x{{FFEF}}-]/u', '',
                         (string)($_GET['p'] ?? ''));
    bump($src, mb_substr((string)$page, 0, 60));

    header('Content-Type: image/gif');
    header('Cache-Control: no-store, no-cache, must-revalidate');
    echo base64_decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');
}}
"""


def stats_php(sources: dict, key: str) -> str:
    labels = ", ".join(f"'{k}' => '{v}'" for k, v in sources.items())
    return f"""<?php
// 集計の表示。URLに ?k=… を付けて開く。
declare(strict_types=1);
if (($_GET['k'] ?? '') !== '{key}') {{
    http_response_code(404);
    exit('Not Found');
}}
$LABELS = [{labels}, 'other' => 'その他'];
$d = is_file(__DIR__ . '/data/counts.json')
   ? (json_decode((string)file_get_contents(__DIR__ . '/data/counts.json'), true) ?: []) : [];
krsort($d);
$h = fn($s) => htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
?><!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>加東の貸家サイト 流入元</title>
<style>
body{{font:14px/1.7 -apple-system,"Hiragino Kaku Gothic ProN",sans-serif;margin:22px;color:#20232d}}
h1{{font-size:18px}} h2{{font-size:15px;margin:26px 0 6px;color:#1b2340}}
table{{border-collapse:collapse;width:100%;max-width:640px;margin-bottom:10px}}
th,td{{border-bottom:1px solid #e2e5ec;padding:7px 8px;text-align:left}}
th{{background:#f6f8fc;white-space:nowrap}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.c{{color:#c2410c;font-weight:800}}
p.note{{color:#6b7280;font-size:12.5px}}
</style>
<h1>加東の貸家サイト｜流入元</h1>
<p class="note">「表示」＝ページが開かれた回数、「問い合わせ」＝フォームから送信された件数。
IPやCookieは記録していません。</p>
<?php if (!$d): ?><p>まだ記録がありません。</p><?php endif; ?>
<?php foreach ($d as $month => $rows): ?>
  <h2><?= $h($month) ?></h2>
  <table><tr><th>流入元</th><th>表示</th><th>問い合わせ</th></tr>
  <?php
    $tv = $tc = 0;
    foreach ($rows as $src => $r) {{
        if ($src === '_pages') continue;
        $v = (int)($r['v'] ?? 0); $c = (int)($r['c'] ?? 0);
        $tv += $v; $tc += $c;
        echo '<tr><td>' . $h($LABELS[$src] ?? $src) . '</td>'
           . '<td class="n">' . $v . '</td>'
           . '<td class="n c">' . ($c ?: '') . '</td></tr>';
    }}
    echo '<tr><th>合計</th><th class="n">' . $tv . '</th><th class="n">' . $tc . '</th></tr>';
  ?>
  </table>
  <?php if (!empty($rows['_pages'])): arsort($rows['_pages']); ?>
    <table><tr><th>ページ</th><th>表示</th></tr>
    <?php foreach ($rows['_pages'] as $p => $n): ?>
      <tr><td><?= $h(urldecode((string)$p)) ?></td><td class="n"><?= (int)$n ?></td></tr>
    <?php endforeach; ?>
    </table>
  <?php endif; ?>
<?php endforeach; ?>
</html>
"""
