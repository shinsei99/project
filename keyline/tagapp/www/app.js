/* KeyLine Tag — アプリ本体。
 *
 * 設計の芯
 *   * **単体で完結すること。** サーバーが無くても、タグの読み書きと台帳が使える。
 *     App Store の審査員は社内LANに入れないので、ここが崩れると審査を通らない。
 *   * KeyLine連携は「設定でURLを入れた人だけ」の追加機能。
 *   * NFCが使えない環境（ブラウザでの開発中）でも画面は全部動く。
 *     読み書きのボタンだけが「実機が必要です」と言う。
 */

import * as N from './ndef.js';

const $ = id => document.getElementById(id);
const KEY = { ledger: 'keyline.ledger', conf: 'keyline.conf' };

// ---------------------------------------------------------------------------
// 保存（端末内のみ）
// ---------------------------------------------------------------------------
const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
const save = (k, v) => localStorage.setItem(k, JSON.stringify(v));

let conf = load(KEY.conf, { tagType: 'NTAG213', server: '', token: '', org: '' });
let ledger = load(KEY.ledger, []);

// ---------------------------------------------------------------------------
// NFC プラグイン
//
// ブラウザで開いているときは Capacitor が居ないので null になる。
// その場合も画面は動かし、読み書きのときだけ案内を出す。
// ---------------------------------------------------------------------------
let Nfc = null;
let nfcReady = false;

async function initNfc() {
  try {
    const cap = window.Capacitor;
    if (!cap || !cap.isNativePlatform || !cap.isNativePlatform()) {
      $('nfcstate').textContent = 'ブラウザ表示（NFCは実機のみ）';
      return;
    }
    Nfc = cap.Plugins.CapacitorNfc || (await import('@capgo/capacitor-nfc')).CapacitorNfc;
    const { supported } = await Nfc.isSupported();
    nfcReady = !!supported;
    $('nfcstate').textContent = nfcReady ? 'NFC 利用可' : 'NFC 非対応の端末です';
  } catch (e) {
    $('nfcstate').textContent = 'NFCを準備できませんでした';
  }
}

function needDevice(msgEl) {
  const m = nfcReady
    ? null
    : (Nfc ? 'この端末はNFCに対応していません。'
           : 'NFCの読み書きは実機でのみ動作します（いまはブラウザ表示）。');
  if (m && msgEl) { msgEl.textContent = '⚠️ ' + m; msgEl.className = 'msg err'; }
  return !!m;
}

/** タグを1枚検出するまで待つ。iOSは読み取りシートが自動で出る。 */
function scanOnce(alertMessage) {
  return new Promise(async (resolve, reject) => {
    let handle = null, done = false;
    const finish = (fn, v) => {
      if (done) return; done = true;
      if (handle) handle.remove().catch(() => {});
      Nfc.stopScanning().catch(() => {});
      fn(v);
    };
    try {
      handle = await Nfc.addListener('nfcEvent', ev => finish(resolve, ev && ev.tag));
      await Nfc.startScanning({
        // 'tag' セッションでないと、まっさらな（NDEF未フォーマットの）タグを掴めない。
        // iOSでは TAG エンタイトルメントが要る。
        sessionType: 'tag',
        alertMessage: alertMessage || 'タグに近づけてください',
        invalidateAfterFirstRead: true,
      });
      setTimeout(() => finish(reject, new Error('timeout')), 65000);
    } catch (e) { finish(reject, e); }
  });
}

// ---------------------------------------------------------------------------
// 画面切り替え
// ---------------------------------------------------------------------------
document.querySelectorAll('nav.tabs button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('nav.tabs button').forEach(x => x.classList.toggle('on', x === b));
    document.querySelectorAll('.screen').forEach(s => { s.hidden = s.id !== b.dataset.screen; });
    if (b.dataset.screen === 's-list') renderLedger();
    document.querySelector('main').scrollTop = 0;
  });
});

// ═══════════════════════════════════════════════════════════════
// 読み取り
// ═══════════════════════════════════════════════════════════════
$('btn-read').addEventListener('click', async () => {
  if (needDevice(null)) {
    $('readlead').textContent = Nfc
      ? 'この端末はNFCに対応していません。'
      : 'NFCの読み取りは実機でのみ動作します（いまはブラウザ表示）。';
    return;
  }
  const ring = $('readring'), lead = $('readlead');
  ring.classList.add('on'); lead.textContent = 'タグに近づけてください…';
  $('btn-read').disabled = true;
  try {
    const tag = await scanOnce('鍵のタグに近づけてください');
    showTag(N.parseTag(tag));
    lead.textContent = '読み取りました';
  } catch (e) {
    lead.textContent = '読み取れませんでした。もう一度お試しください。';
  } finally {
    ring.classList.remove('on');
    $('btn-read').disabled = false;
  }
});

function showTag(t) {
  const f = t.fields || {};
  $('r-prop').textContent = f.property || '';
  $('r-name').textContent = f.name || (t.url ? '（このタグに鍵情報はありません）' : '（空のタグ）');
  $('r-numbers').textContent = f.numbers || '-';
  $('r-box').textContent = f.box || '-';
  $('r-uid').textContent = t.uid || '-';

  // KeyLineのタグなら、そのまま貸出・返却の画面へ行けるようにする
  const link = $('r-link');
  link.innerHTML = '';
  const token = N.keylineToken(t.url);
  if (t.url) {
    const a = document.createElement('a');
    a.className = 'btn ghost'; a.style.marginTop = '.9rem'; a.href = t.url;
    a.target = '_blank'; a.rel = 'noopener';
    a.textContent = token ? 'KeyLineで貸出・返却する' : 'このタグのURLを開く';
    link.appendChild(a);
  }
  $('r-raw').textContent = JSON.stringify(
    { uid: t.uid, records: t.records }, null, 1);
  $('readresult').hidden = false;
}

// ═══════════════════════════════════════════════════════════════
// 書き込み
// ═══════════════════════════════════════════════════════════════
function keyRow(num = '', qty = 1) {
  const d = document.createElement('div');
  d.className = 'keyrow';
  d.innerHTML =
    '<input type="text" class="num" placeholder="10001" autocomplete="off">' +
    '<span class="x">×</span>' +
    '<input type="text" class="qty" inputmode="numeric" value="1">' +
    '<span class="u">本</span>' +
    '<button type="button" class="del">×</button>';
  d.querySelector('.num').value = num;
  d.querySelector('.qty').value = qty;
  d.querySelectorAll('input').forEach(i => i.addEventListener('input', preview));
  // '10003 x3' と番号欄に打たれたら本数欄へ移す（打ちやすい方で入れてもらう）
  d.querySelector('.num').addEventListener('change', e => {
    const m = e.target.value.match(/^(.*?)\s*[xX×*]\s*(\d{1,2})$/);
    if (!m) return;
    e.target.value = m[1].trim();
    d.querySelector('.qty').value = Math.min(Math.max(parseInt(m[2], 10) || 1, 1), 99);
    preview();
  });
  d.querySelector('.del').addEventListener('click', () => {
    const rows = $('w-keys').querySelectorAll('.keyrow');
    if (rows.length <= 1) { rows[0].querySelector('.num').value = ''; rows[0].querySelector('.qty').value = '1'; }
    else d.remove();
    preview();
  });
  return d;
}

$('btn-addkey').addEventListener('click', () => {
  const d = keyRow();
  $('w-keys').appendChild(d);
  d.querySelector('.num').focus();
});

function currentKeys() {
  return [...$('w-keys').querySelectorAll('.keyrow')].map(r => ({
    num: r.querySelector('.num').value.trim(),
    qty: Math.min(Math.max(parseInt(r.querySelector('.qty').value, 10) || 1, 1), 99),
  })).filter(k => k.num);
}

function numbersText() {
  return currentKeys().map(k => k.qty > 1 ? `${k.num} ×${k.qty}` : k.num).join(' / ');
}

function fields() {
  return {
    property: $('w-prop').value.trim(),
    name: $('w-name').value.trim(),
    numbers: numbersText(),
    boxCode: $('w-box').value.trim(),
    boxPosition: $('w-pos').value.trim(),
    url: '',        // 連携時は書き込み直前にサーバーが発行したURLを入れる
  };
}

/** 何がタグに書かれるかを、書く前に見せる。あとで「入っていなかった」を防ぐ。 */
function preview() {
  const f = fields();
  const p = N.plan(f, conf.tagType);
  const pct = Math.min(100, Math.round(p.bytes / p.capacity * 100));
  const cls = !p.fits ? 'over' : (p.truncated ? 'warn' : '');
  $('w-preview').innerHTML =
    (p.text ? `<span class="t">${escapeHtml(p.text)}</span>` : '<span>（まだ何も入力されていません）</span>') +
    `<div class="bar"><i class="${cls}" style="width:${pct}%"></i></div>` +
    `${p.bytes} / ${p.capacity} バイト（${conf.tagType}）` +
    (p.truncated && p.fits
      ? '<span class="warn">⚠️ 容量が足りないため名前を短くします。鍵番号と保管場所は必ず残ります。</span>' : '') +
    (!p.fits ? '<span class="over">❌ このタグには収まりません</span>' : '');
  return p;
}

['w-prop', 'w-name', 'w-box', 'w-pos'].forEach(id => $(id).addEventListener('input', preview));

$('btn-clearfixed').addEventListener('click', () => {
  ['w-prop', 'w-box', 'w-pos'].forEach(id => $(id).value = '');
  preview();
});

$('btn-write').addEventListener('click', async () => {
  const msg = $('w-msg');
  msg.textContent = ''; msg.className = 'msg';

  const f = fields();
  if (!f.name) { msg.textContent = '⚠️ 鍵の名称を入れてください'; msg.className = 'msg err'; $('w-name').focus(); return; }
  if (needDevice(msg)) return;

  const btn = $('btn-write');
  btn.disabled = true; btn.textContent = 'タグに近づけてください…';
  try {
    // 連携が設定されていれば、先にサーバーへ登録してURLを受け取る。
    // 失敗しても単体の書き込みは続ける（現場を止めないため）。
    if (conf.server && conf.token) {
      const r = await registerOnServer(f);
      if (r && r.url) f.url = r.url;
      else msg.textContent = '⚠️ KeyLineに登録できませんでした。タグにはこの端末の情報だけ書きます。';
    }

    const p = N.plan(f, conf.tagType);
    if (!p.fits) throw new Error('このタグには収まりません');

    await scanOnce('書き込むタグに近づけてください');
    await Nfc.write({ records: p.records, allowFormat: true });

    addToLedger(f, p);
    msg.textContent = '✅ 書き込みました：' + (p.text || 'URLのみ');
    msg.className = 'msg ok';

    // 次の鍵へ。物件名・ボックスは残し、位置を繰り上げる
    $('w-name').value = '';
    $('w-keys').innerHTML = ''; $('w-keys').appendChild(keyRow());
    $('w-pos').value = nextPosition($('w-pos').value);
    preview();
    $('w-name').focus();
  } catch (e) {
    msg.textContent = '⚠️ ' + (e && e.message === 'timeout'
      ? 'タグを検出できませんでした。もう一度お試しください。'
      : (e && e.message) || '書き込めませんでした');
    msg.className = 'msg err';
  } finally {
    btn.disabled = false; btn.textContent = 'タグに書き込む';
  }
});

/** 『03』の次は『04』。桁数は保つ。数字でなければそのまま。 */
function nextPosition(pos) {
  const m = String(pos || '').trim().match(/^(\D*)(\d+)(\D*)$/);
  if (!m) return pos || '';
  return m[1] + String(parseInt(m[2], 10) + 1).padStart(m[2].length, '0') + m[3];
}

// ═══════════════════════════════════════════════════════════════
// 台帳（端末内）
// ═══════════════════════════════════════════════════════════════
function addToLedger(f, p) {
  ledger.unshift({
    at: new Date().toISOString(),
    property: f.property, name: f.name, numbers: f.numbers,
    boxCode: f.boxCode, boxPosition: f.boxPosition,
    url: f.url || '', written: p.text, bytes: p.bytes,
  });
  ledger = ledger.slice(0, 2000);
  save(KEY.ledger, ledger);
  refreshProperties();
}

function renderLedger() {
  $('l-count').textContent = ledger.length;
  $('l-empty').hidden = ledger.length > 0;
  const box = $('l-items');
  box.innerHTML = '';
  ledger.forEach((r, i) => {
    const el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = '<div class="body"><div class="nm"></div><div class="sub"></div></div>' +
                   '<button class="go">再書込</button>';
    el.querySelector('.nm').textContent = (r.property ? r.property + ' / ' : '') + r.name;
    el.querySelector('.sub').textContent =
      [r.numbers, N.boxLabel(r.boxCode, r.boxPosition), fmt(r.at)].filter(Boolean).join('  ・  ');
    el.querySelector('.go').addEventListener('click', () => {
      $('w-prop').value = r.property || '';
      $('w-box').value = r.boxCode || '';
      $('w-pos').value = r.boxPosition || '';
      $('w-name').value = r.name || '';
      $('w-keys').innerHTML = '';
      (r.numbers || '').split(' / ').filter(Boolean).forEach(s => {
        const m = s.match(/^(.*?)\s*×\s*(\d+)$/);
        $('w-keys').appendChild(m ? keyRow(m[1], m[2]) : keyRow(s, 1));
      });
      if (!$('w-keys').children.length) $('w-keys').appendChild(keyRow());
      document.querySelector('nav.tabs button[data-screen=s-write]').click();
      preview();
    });
    box.appendChild(el);
  });
}

const fmt = iso => {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

$('btn-export').addEventListener('click', () => {
  if (!ledger.length) return;
  const head = ['日時', '物件名', '鍵の名称', '鍵番号', 'ボックス', '位置', 'URL'];
  const rows = ledger.map(r => [r.at, r.property, r.name, r.numbers, r.boxCode, r.boxPosition, r.url]);
  const csv = '﻿' + [head, ...rows]
    .map(cols => cols.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = 'keyline-tags.csv';
  a.click();
  URL.revokeObjectURL(a.href);
});

function refreshProperties() {
  const names = [...new Set(ledger.map(r => r.property).filter(Boolean))];
  $('proplist').innerHTML = names.map(n => `<option value="${escapeHtml(n)}">`).join('');
}

// ═══════════════════════════════════════════════════════════════
// 設定・KeyLine連携
// ═══════════════════════════════════════════════════════════════
$('c-tag').value = conf.tagType;
$('c-server').value = conf.server || '';
showLinkState();

$('c-tag').addEventListener('change', () => {
  conf.tagType = $('c-tag').value; save(KEY.conf, conf); preview();
});
$('c-server').addEventListener('change', () => {
  conf.server = $('c-server').value.trim().replace(/\/+$/, '');
  save(KEY.conf, conf);
});

function showLinkState() {
  const m = $('c-msg');
  if (conf.token) {
    m.textContent = `✅ ${conf.org || 'KeyLine'} と連携中`;
    m.className = 'msg ok';
  } else {
    m.textContent = '';
    m.className = 'msg';
  }
  $('c-code').closest('.linkbox').hidden = !!conf.token;
  $('btn-forget').hidden = !conf.token;
}

/** 管理画面が出した6桁コードを送ってトークンを受け取る。
 *  64文字のトークンを手打ちさせないための仕組み。 */
$('btn-pair').addEventListener('click', async () => {
  const m = $('c-msg');
  const url = $('c-server').value.trim().replace(/\/+$/, '');
  const code = $('c-code').value.trim();
  if (!url) { m.textContent = '⚠️ サーバーのURLを入れてください'; m.className = 'msg err'; return; }
  if (!/^\d{6}$/.test(code)) { m.textContent = '⚠️ 6桁の数字を入れてください'; m.className = 'msg err'; return; }

  m.textContent = '連携中…'; m.className = 'msg';
  try {
    const r = await fetch(url + '/api/pair', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    const d = await r.json();
    if (!d.ok) { m.textContent = '⚠️ ' + (d.error || '連携できませんでした'); m.className = 'msg err'; return; }
    conf.server = url; conf.token = d.token; conf.org = d.organization || '';
    save(KEY.conf, conf);
    $('c-code').value = '';
    showLinkState();
  } catch (e) {
    m.textContent = '⚠️ 接続できません。URLと、同じWi-Fiに繋がっているか確認してください。';
    m.className = 'msg err';
  }
});

$('btn-test').addEventListener('click', async () => {
  const m = $('c-msg');
  if (!conf.server || !conf.token) { m.textContent = '⚠️ まだ連携していません'; m.className = 'msg err'; return; }
  m.textContent = '確認中…'; m.className = 'msg';
  const d = await api('/api/ping');
  if (d && d.ok) {
    m.textContent = `✅ ${d.organization}（${d.user}）に接続できました`;
    m.className = 'msg ok';
  } else {
    m.textContent = '⚠️ 接続できません。連携をやり直してください。';
    m.className = 'msg err';
  }
});

$('btn-forget').addEventListener('click', () => {
  conf.token = ''; conf.org = ''; save(KEY.conf, conf);
  showLinkState();
  $('c-msg').textContent = '連携をやめました。単体モードで動きます。';
  $('c-msg').className = 'msg';
});

/** KeyLineのAPIを叩く。Cookieは使えないのでトークンをヘッダで送る。 */
async function api(path, body) {
  if (!conf.server || !conf.token) return null;
  try {
    const r = await fetch(conf.server + path, {
      method: body ? 'POST' : 'GET',
      headers: {
        'Authorization': 'Bearer ' + conf.token,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return await r.json();
  } catch (e) { return null; }
}

/** KeyLineへ登録してURLを受け取る。失敗しても例外は投げない（現場を止めない）。 */
async function registerOnServer(f) {
  const keys = currentKeys();
  const d = await api('/api/register', {
    property_name: f.property, name: f.name,
    box_position: f.boxPosition,
    item_number: keys.map(k => k.num), item_qty: keys.map(k => String(k.qty)),
  });
  return d && d.ok ? d : null;
}

// ---------------------------------------------------------------------------
const escapeHtml = s => String(s).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// 起動
$('w-keys').appendChild(keyRow());
refreshProperties();
renderLedger();
preview();
$('c-ver').textContent = 'KeyLine Tag 1.0.0';
initNfc();
