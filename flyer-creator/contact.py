"""問い合わせページと、その受け口のPHP。

会社サイトの `mailform/send.cgi`（2013年のPerl CGI）とは**別系統**にしてある。
あちらは売買・管理・土地活用まで受ける全社の窓口で、こちらは加東の貸家専用。
問い合わせが混ざらないよう、件名に［加東の貸家］を付けて送る。

    contact.html   フォーム
    send.php       受け口。サーバーはPHP 8.3が動く
    thanks.html    送信後

物件名と用件は、来たリンクの `?p=物件名&k=用件` で最初から選んでおく。
募集中の物件からは「内覧したい」、賃貸中の物件からは「空きが出たら連絡してほしい」で入る。

必須は お名前 と メールアドレスだけ。住所・電話は任意。
送信先は MAIL_TO。site/ を作り直すと send.php も一緒に書き出される。
"""
from __future__ import annotations

import html

import tracking
from properties import LICENSE

MAIL_TO = "info@shinsei-pm.co.jp"
# 差出人はドメインのアドレスにする（gmail等を差出人にすると迷惑メール判定されやすい）。
MAIL_FROM = "no-reply@daikyocorp.co.jp"
SUBJECT_TAG = "［加東の貸家］"

TEL = "06-6935-7267"

# 用件。賃貸中の物件から来た人のための「空き待ち」を1本目に近いところに置く。
VISIT = "内覧したい"
WAIT = "空きが出たら連絡してほしい"
KINDS = [VISIT, "空き状況を知りたい", WAIT, "その他"]

FORM_CSS = """
.form{padding:18px 18px 34px;max-width:640px;margin:0 auto}
.form label{display:block;margin:16px 0 5px;font-size:13.5px;font-weight:700;color:var(--navy)}
.form .req{color:#c0392b;font-size:11.5px;font-weight:700;margin-left:5px}
.form .any{color:var(--gray);font-size:11.5px;font-weight:700;margin-left:5px}
.form input[type=text],.form input[type=tel],.form input[type=email],
.form select,.form textarea{width:100%;padding:11px 12px;font-size:16px;
 border:1px solid #c7ccd8;border-radius:7px;background:#fff;color:var(--ink);
 font-family:inherit;-webkit-appearance:none}
.form select{background-image:linear-gradient(45deg,transparent 50%,#6b7280 50%),
 linear-gradient(135deg,#6b7280 50%,transparent 50%);
 background-position:calc(100% - 19px) 21px,calc(100% - 13px) 21px;
 background-size:6px 6px,6px 6px;background-repeat:no-repeat;padding-right:38px}
.form textarea{min-height:120px;line-height:1.7;resize:vertical}
.form input:focus,.form select:focus,.form textarea:focus{outline:2px solid var(--org);border-color:var(--org)}
.form .radios{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
.form .radios label{margin:0;font-weight:700;font-size:13.5px;border:1.5px solid #c7ccd8;
 border-radius:99px;padding:8px 15px;cursor:pointer;color:var(--ink);background:#fff}
.form .radios input{position:absolute;opacity:0;width:0;height:0}
.form .radios label:has(input:checked){border-color:var(--org);background:#fff6ec;color:#96460a}
.form .note{font-size:12px;color:var(--gray);margin:6px 0 0}
.form .send{width:100%;margin-top:24px;background:var(--org);color:var(--navy);border:0;
 border-radius:9px;padding:16px;font-size:17px;font-weight:900;font-family:inherit;cursor:pointer}
.form .send:active{opacity:.85}
.form .hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
.err{background:#fdecea;border:1px solid #f5b7b1;color:#943126;border-radius:8px;
 padding:12px 14px;font-size:13.5px;margin:0}
.lead{padding:18px 18px 0;max-width:640px;margin:0 auto;font-size:14px}
.lead p{margin:0}
.lead .tel{display:block;margin-top:12px;padding:13px;border:1.5px solid var(--navy);
 border-radius:9px;text-align:center;text-decoration:none;font-weight:900;font-size:19px;color:var(--navy)}
.lead .tel small{font-size:12.5px;color:var(--gray);font-weight:700;margin-left:10px}
.done{padding:30px 18px 44px;max-width:640px;margin:0 auto;text-align:center}
.done h1{font-size:22px;margin:0 0 12px}
.done p{font-size:14.5px}
.done a.back{display:inline-block;margin-top:22px;background:var(--navy);color:#fff;
 text-decoration:none;font-weight:800;padding:13px 26px;border-radius:9px}
"""

FORM_JS = """
(function(){
  var q = new URLSearchParams(location.search);
  // 物件ページ・賃貸中の写真から ?p=物件名&k=用件 で来る。あれば選んでおく。
  function pick(id, value){
    var sel = document.getElementById(id);
    if (!sel || !value) return;
    for (var i=0;i<sel.options.length;i++){
      if (sel.options[i].value === value) { sel.selectedIndex = i; return; }
    }
  }
  pick('bukken', q.get('p'));
  pick('youken', q.get('k'));

  // send.php がエラーで戻したときだけ理由を出す。
  var e = q.get('e');
  if (e) {
    var box = document.createElement('div');
    box.className = 'form';
    box.style.paddingBottom = '0';
    box.innerHTML = '<p class="err"></p>';
    box.querySelector('.err').textContent = e;
    var form = document.querySelector('form.form');
    form.parentNode.insertBefore(box, form);
    box.scrollIntoView({block:'center'});
  }

  // 開いてすぐの送信は機械とみなす。人が書く時間ぶんの下駄をはかせる。
  var t = document.getElementById('t');
  if (t) t.value = String(Math.floor(Date.now()/1000));

  // どの看板・資料から来た人かをメールに載せる（看板ごとの反響を見るため）
  var sf = document.getElementById('src');
  if (sf) sf.value = sessionStorage.getItem('src') || 'search';
})();
"""


def page_contact(css: str, footer: str, vacant: list[tuple[str, str]], rented: list[str]) -> str:
    """vacant=募集中の(値, 表示名)、rented=賃貸中の物件名。どちらからも問い合わせできる。

    値は物件ページからの `?p=` と突き合わせるためのもので、表示名とは別。
    値は社内の呼び名（秋津9 など）、表示名はお客様に見せている物件名にする。
    """
    e = html.escape

    def group(label: str, names: list) -> str:
        if not names:
            return ""
        pairs = [(n, n) if isinstance(n, str) else n for n in names]
        opts = "".join(f'<option value="{e(v)}">{e(t)}</option>' for v, t in pairs)
        return f'<optgroup label="{e(label)}">{opts}</optgroup>'

    bukken = (group("募集中", vacant) + group("賃貸中（空き待ち）", rented)
              + '<option value="まだ決めていない">まだ決めていない</option>')
    youken = "".join(f'<option value="{e(k)}">{e(k)}</option>' for k in KINDS)
    ways = "".join(
        f'<label><input type="radio" name="way" value="{e(w)}"'
        f'{" checked" if i == 0 else ""}><span>{e(w)}</span></label>'
        for i, w in enumerate(["どちらでも", "メール", "電話"])
    )
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>お問い合わせ｜加東の貸家｜新誠プロパティマネジメント</title>
<meta name="description" content="兵庫県加東市の貸家についてのお問い合わせ。内覧希望、空き状況など。賃貸中物件の空き待ちのご連絡も承ります。">
<meta name="robots" content="noindex">
<style>{css}{FORM_CSS}</style></head><body>
<div class="bar"><img src="logo_white.png" alt="新誠プロパティマネジメント"><a href="index.html">← 物件一覧</a></div>
<div class="hero"><h1>お問い合わせ</h1></div>
<div class="lead">
  <p>内覧希望、空き状況などお問い合わせください。
  賃貸中物件も、空きが出たときにご連絡できます。</p>
  <a class="tel" href="tel:{TEL.replace('-', '')}">☎ {e(TEL)}<small>お急ぎの方はお電話で</small></a>
</div>
<form class="form" method="post" action="send.php">
  <label for="bukken">物件</label>
  <select id="bukken" name="bukken">{bukken}</select>

  <label for="youken">ご用件</label>
  <select id="youken" name="youken">{youken}</select>

  <label for="name">お名前<span class="req">必須</span></label>
  <input id="name" type="text" name="name" autocomplete="name" required>

  <label for="email">メールアドレス<span class="req">必須</span></label>
  <input id="email" type="email" name="email" autocomplete="email" inputmode="email" required>

  <label for="tel">電話番号<span class="any">任意</span></label>
  <input id="tel" type="tel" name="tel" autocomplete="tel" inputmode="tel">

  <label for="addr">ご住所<span class="any">任意</span></label>
  <input id="addr" type="text" name="addr" autocomplete="street-address"
         placeholder="例：大阪府大阪市北区…">
  <p class="note">資料の郵送をご希望の場合にご記入ください。</p>

  <label>ご希望の連絡方法</label>
  <div class="radios">{ways}</div>

  <label for="visit">内覧希望日<span class="any">任意</span></label>
  <input id="visit" type="text" name="visit" placeholder="例：今週末の午後、平日の夕方 など">

  <label for="body">お問い合わせ内容<span class="any">任意</span></label>
  <textarea id="body" name="body" placeholder="ご質問やご要望をご記入ください。"></textarea>

  <div class="hp"><label>この欄は入力しないでください
    <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
  <input type="hidden" name="t" id="t" value="0">
  <input type="hidden" name="src" id="src" value="">

  <button class="send" type="submit">この内容で送信する</button>
</form>
{footer}
<script>{FORM_JS}</script>
</body></html>"""


def page_thanks(css: str, footer: str) -> str:
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<title>送信しました｜加東の貸家｜新誠プロパティマネジメント</title>
<meta name="robots" content="noindex">
<style>{css}{FORM_CSS}</style></head><body>
<div class="bar"><img src="logo_white.png" alt="新誠プロパティマネジメント"><a href="index.html">← 物件一覧</a></div>
<div class="done">
  <h1>送信しました</h1>
  <p>お問い合わせありがとうございます。<br>
  確認のメールをお送りしましたのでご確認ください。<br>
  担当者から改めてご連絡いたします。</p>
  <p style="font-size:13px;color:var(--gray);margin-top:18px">
  お急ぎの場合は {TEL} までお電話ください。<br>
  確認メールが届かない場合、迷惑メールに入っていることがあります。</p>
  <a class="back" href="index.html">物件一覧へ戻る</a>
</div>
{footer}
</body></html>"""


src_labels = "[" + ", ".join(f"'{k}' => '{v}'" for k, v in tracking.SOURCES.items()) + "]"

SEND_PHP = f"""<?php
// 加東の貸家サイト専用の受け口。会社サイトの mailform/send.cgi とは別系統。
// このファイルは build_site.py（contact.py）から書き出される。直接編集しないこと。
declare(strict_types=1);
mb_internal_encoding('UTF-8');
mb_language('uni');

const MAIL_TO   = '{MAIL_TO}';
const MAIL_FROM = '{MAIL_FROM}';
const TAG       = '{SUBJECT_TAG}';
const SRC_LABELS = {src_labels};

// 流入元ごとの件数を数える（hit.php の bump を使う。直接開かれたときだけ画像を返す作り）
require_once __DIR__ . '/hit.php';

function back(string $msg): void {{
    header('Location: contact.html?e=' . rawurlencode($msg));
    exit;
}}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {{
    header('Location: contact.html');
    exit;
}}

// 空欄のはずの欄に入っていたら機械。黙って受け取ったふりをする。
if (trim((string)($_POST['website'] ?? '')) !== '') {{
    header('Location: thanks.html');
    exit;
}}
// 開いてから2秒未満の送信も機械とみなす。
// ただし $t はお客様の端末の時計で作られる。時計が進んでいる端末だと差が負になるので、
// そのときは判定しない。ここで落とすと本物の問い合わせが黙って消える。
$t = (int)($_POST['t'] ?? 0);
$elapsed = time() - $t;
if ($t > 0 && $elapsed >= 0 && $elapsed < 2) {{
    header('Location: thanks.html');
    exit;
}}

$clean = static function (string $key, int $max = 1000): string {{
    $v = (string)($_POST[$key] ?? '');
    $v = str_replace(["\\r\\n", "\\r"], "\\n", $v);
    $v = preg_replace('/[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F]/u', '', $v) ?? '';
    return mb_substr(trim($v), 0, $max);
}};

$src   = $clean('src', 40);
$name  = $clean('name', 80);
$email = $clean('email', 120);
$tel   = $clean('tel', 40);
$addr  = $clean('addr', 200);
$way   = $clean('way', 20);
$buk   = $clean('bukken', 80);
$yoken = $clean('youken', 40);
$visit = $clean('visit', 120);
$body  = $clean('body', 4000);

if ($name === '' || $email === '') {{
    back('お名前とメールアドレスをご記入ください。');
}}
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {{
    back('メールアドレスの形式をご確認ください。');
}}
// ヘッダに改行を混ぜる細工への備え
if (preg_match('/[\\n\\r]/', $name . $email)) {{
    back('入力内容をご確認ください。');
}}

$or = static fn(string $v, string $alt): string => $v !== '' ? $v : $alt;

$lines = [
    '加東の貸家サイトからお問い合わせがありました。',
    '',
    '物件　　　: ' . $or($buk, '（未選択）'),
    'ご用件　　: ' . $or($yoken, '（未選択）'),
    'お名前　　: ' . $name,
    'メール　　: ' . $email,
    '電話番号　: ' . $or($tel, '（未記入）'),
    'ご住所　　: ' . $or($addr, '（未記入）'),
    '連絡方法　: ' . $or($way, '（未選択）'),
    '内覧希望日: ' . $or($visit, '（未記入）'),
    '',
    '── お問い合わせ内容 ──',
    $or($body, '（未記入）'),
    '',
    '───────────────',
    '受信日時: ' . date('Y-m-d H:i:s'),
    '流入元　: ' . (SRC_LABELS[$src] ?? '（不明）'),
    '送信元IP: ' . ($_SERVER['REMOTE_ADDR'] ?? '-'),
    'ページ　: https://daikyocorp.co.jp/slowlife/',
];

$subject = TAG . $or($buk, 'お問い合わせ') . '／' . $or($yoken, '') . '／' . $name . ' 様';
$headers = [
    'From: ' . mb_encode_mimeheader('加東の貸家サイト') . ' <' . MAIL_FROM . '>',
    'Reply-To: ' . $email,
    'Content-Type: text/plain; charset=UTF-8',
    'X-Mailer: slowlife-form',
];
$ok = mb_send_mail(MAIL_TO, $subject, implode("\\n", $lines), implode("\\r\\n", $headers));
if (!$ok) {{
    back('送信できませんでした。お手数ですが {TEL} までお電話ください。');
}}

// 送信者への控え。届かなくても問い合わせ自体は成立しているので結果は見ない。
$reply = [
    $name . ' 様',
    '',
    'お問い合わせありがとうございます。以下の内容で承りました。',
    '担当者より改めてご連絡いたします。',
    '',
    '物件　　　: ' . $or($buk, '（未選択）'),
    'ご用件　　: ' . $or($yoken, '（未選択）'),
    '内覧希望日: ' . $or($visit, '（未記入）'),
    '',
    '── お問い合わせ内容 ──',
    $or($body, '（未記入）'),
    '',
    '───────────────',
    '新誠プロパティマネジメント株式会社',
    '〒531-0076 大阪市北区大淀中3-1-15',
    'TEL {TEL}（10:00〜19:00／日祝休）／FAX 06-7635-7811',
    '{LICENSE}',
    'https://daikyocorp.co.jp/slowlife/',
    '',
    '※このメールは送信専用です。ご返信は担当者からのご連絡にお願いします。',
];
@mb_send_mail(
    $email,
    TAG . 'お問い合わせを承りました',
    implode("\\n", $reply),
    implode("\\r\\n", [
        'From: ' . mb_encode_mimeheader('新誠プロパティマネジメント') . ' <' . MAIL_FROM . '>',
        'Content-Type: text/plain; charset=UTF-8',
    ])
);

@bump(in_array($src, SOURCES, true) ? $src : 'other', '', true);
header('Location: thanks.html');
"""
