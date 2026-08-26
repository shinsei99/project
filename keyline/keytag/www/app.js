/* KeyTag — アプリ本体。
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
const KEY = { ledger: 'keytag.ledger', conf: 'keytag.conf' };

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

/** タグを1枚検出するまで待つ。iOSは読み取りシートが自動で出る。
 *
 *  keepOpen=true のときはセッションを開いたままにする。**書き込みには必須**。
 *  iOSはタグに繋がっているセッションの中でしか書けないので、検出後に
 *  stopScanning すると（プラグインが currentTag を null にするため）
 *  write が「No active NFC session or tag」で必ず失敗する。
 *  → 呼んだ側が最後に closeScan() を呼ぶこと。
 *
 *  ★2026-08-26 修正: オプション名は `sessionType` ではなく **`iosSessionType`**。
 *    間違えると黙って既定の NDEF セッションになり、まっさらな（NDEF未フォーマットの）
 *    タグをかざした瞬間に
 *    「Failed to read NDEF message: NDEF tag does not contain any NDEF message」
 *    でシートが赤くなる（実機で発生）。TAG セッションなら UID だけ拾って続けられる。
 */
function scanOnce(alertMessage, { keepOpen = false } = {}) {
  return new Promise(async (resolve, reject) => {
    let handle = null, done = false;
    const finish = (fn, v) => {
      if (done) return; done = true;
      if (handle) handle.remove().catch(() => {});
      if (!keepOpen) Nfc.stopScanning().catch(() => {});
      fn(v);
    };
    try {
      handle = await Nfc.addListener('nfcEvent', ev => finish(resolve, ev && ev.tag));
      await Nfc.startScanning({
        // TAG セッションでないと、まっさらな（NDEF未フォーマットの）タグを掴めない。
        // iOSでは TAG エンタイトルメントが要る（App.entitlements で付与済み）。
        iosSessionType: 'tag',
        alertMessage: alertMessage || 'タグに近づけてください',
        // 書き込むときは閉じさせない（閉じるとタグとの接続ごと失われる）
        invalidateAfterFirstRead: !keepOpen,
      });
      setTimeout(() => finish(reject, new Error('timeout')), 65000);
    } catch (e) { finish(reject, e); }
  });
}

/** keepOpen で開けたセッションを閉じる（読み取りシートも消える）。 */
function closeScan() {
  if (Nfc) Nfc.stopScanning().catch(() => {});
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
  $('lend').hidden = true;
  const ring = $('readring'), lead = $('readlead');
  ring.classList.add('on'); lead.textContent = 'タグに近づけてください…';
  $('btn-read').disabled = true;
  try {
    const tag = await scanOnce('鍵のタグに近づけてください');
    const t = N.parseTag(tag);
    showTag(t);
    lead.textContent = '読み取りました';
    await showLending(t);
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
// 貸出・返却（KeyLine連携時のみ）
//
// ★ここがあると、iOSのバックグラウンドタグ読み取り（平文httpで通知が出るかは
//   未検証）に頼らずに済む。アプリでかざして、そのまま貸出・返却まで終わる。
//   判定と二重貸出の防止はサーバー側（services.py）でやるので、画面と同じ挙動になる。
// ═══════════════════════════════════════════════════════════════
let lastTag = null;
let lendState = null;      // { source:'server'|'local', token, uid, asset, borrowers, dues, rec }

/* 貸出のデータの置き場は2つある。画面は同じで、ここだけが違う。
 *
 *   local  … この端末の台帳。サーバー不要。**これが既定**
 *   server … 自社の鍵管理サーバー（設定で連携したときだけ）。
 *            複数人で同じ台帳を見る必要がある会社向け。
 *            二重貸出の判定はサーバー側でやるので、2台で同時に操作しても壊れない。
 */

const DUES_LOCAL = [
  { label: '今日 18:00', hours: null, today18: true },
  { label: '明日 18:00', hours: null, tomorrow18: true },
  { label: '2時間後', hours: 2 },
  { label: '3日後', hours: 72 },
  { label: '指定しない', hours: 0 },
];

function localDues() {
  const now = new Date();
  const at18 = d => { const x = new Date(d); x.setHours(18, 0, 0, 0); return x; };
  const out = [];
  const t18 = at18(now);
  if (t18 > now) out.push({ label: '今日 18:00', value: t18.toISOString() });
  const tm = at18(new Date(now.getTime() + 86400000));
  out.push({ label: '明日 18:00', value: tm.toISOString() });
  out.push({ label: '2時間後', value: new Date(now.getTime() + 7200000).toISOString() });
  out.push({ label: '3日後', value: new Date(now.getTime() + 259200000).toISOString() });
  out.push({ label: '指定しない', value: '' });
  return out;
}

const fmtDT = iso => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} `
       + `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

const elapsedText = iso => {
  if (!iso) return '';
  const m = Math.max(0, Math.floor((Date.now() - new Date(iso)) / 60000));
  const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60);
  return d ? `${d}日${h}時間` : (h ? `${h}時間${m % 60}分` : `${m}分`);
};

/** 端末内の1件を、画面が使う形に直す（サーバーの返す形に合わせる）。 */
function localAsset(r) {
  const overdue = r.status === 'out' && r.due && new Date(r.due) < new Date();
  const total = (r.numbers || '').split(' / ').filter(Boolean)
    .reduce((n, s) => n + (parseInt((s.match(/×\s*(\d+)/) || [])[1], 10) || 1), 0);
  return {
    property_name: r.property || '', name: r.name || '',
    label: (r.property ? r.property + ' / ' : '') + r.name,
    item_numbers: r.numbers || '', total_keys: total,
    box: N.boxLabel(r.boxCode, r.boxPosition), box_name: '',
    status: r.status === 'out' ? 'checked_out' : 'in_stock',
    status_label: r.status === 'out' ? '貸出中' : '保管中',
    borrower: r.borrower ? { ...r.borrower } : null,
    checked_out_at: fmtDT(r.since), due_at: r.due ? fmtDT(r.due) : '',
    elapsed: elapsedText(r.since), is_overdue: !!overdue,
  };
}

async function showLending(t) {
  $('lend').hidden = true;
  lendState = null;
  lastTag = t;

  const token = N.keylineToken(t.url);

  // ① サーバー連携していて、そのサーバーのタグなら、サーバーを見る
  if (token && conf.server && conf.token) {
    const d = await api('/api/asset?token=' + encodeURIComponent(token));
    if (d && d.ok && d.found) {
      lendState = { source: 'server', token, ...d };
      renderLending();
      return;
    }
    if (d && d.ok && !d.found) {
      setMsg($('k-msg'), 'このタグはサーバーに登録されていません。', false);
      $('lend').hidden = false;
      return;
    }
    setMsg($('k-msg'), '⚠️ サーバーに繋がりませんでした。この端末の記録で操作します。', true);
  }

  // ② それ以外は端末内の台帳で操作する（サーバー不要）
  const rec = findLocal(t);
  if (!rec) {
    // 台帳に無いタグ。読み取り結果はそのまま出し、登録への導線だけ足す
    const link = $('r-link');
    const b = document.createElement('button');
    b.className = 'btn primary'; b.style.marginTop = '.9rem';
    b.textContent = 'この鍵を登録する';
    b.addEventListener('click', () => {
      // 読めた内容があれば書き込み画面に引き継ぐ
      const f = t.fields || {};
      if (f.property) $('w-prop').value = f.property;
      if (f.name) $('w-name').value = f.name;
      if (f.box) {
        const m = String(f.box).match(/^(.*?)-([^-]+)$/);
        if (m) { $('w-box').value = m[1]; $('w-pos').value = m[2]; }
        else $('w-box').value = f.box;
      }
      document.querySelector('nav.tabs button[data-screen=s-write]').click();
      preview();
      $('w-name').focus();
    });
    link.appendChild(b);
    return;
  }
  lendState = {
    source: 'local', uid: rec.uid, rec,
    asset: localAsset(rec),
    borrowers: localBorrowers().map((b, i) => ({
      id: 'L' + i, name: b.name, company: b.company, kind: b.kind, open_count: 0 })),
    dues: localDues(),
  };
  renderLending();
}

function renderLending() {
  const a = lendState.asset;
  $('lend').hidden = false;
  // 鍵が特定できたので、生の読み取り結果は隠す。
  // 同じ内容が2つ並ぶうえ、台帳に無い項目が「（空のタグ）」と出て紛らわしい
  $('readresult').hidden = true;
  $('k-uid').textContent = (lastTag && lastTag.uid) || '-';
  $('k-raw').textContent = JSON.stringify(
    { uid: lastTag && lastTag.uid, records: (lastTag && lastTag.records) || [] }, null, 1);
  setMsg($('k-msg'), '', false);

  const badge = $('k-status');
  badge.textContent = a.is_overdue ? '返却期限超過' : a.status_label;
  badge.className = 'badge ' + (a.status === 'in_stock' ? 'in'
    : a.status === 'checked_out' ? (a.is_overdue ? 'over' : 'out') : 'other');

  $('k-prop').textContent = a.property_name;
  $('k-name').textContent = a.name;
  $('k-keys').textContent = a.item_numbers
    + (a.total_keys > 1 ? `  計${a.total_keys}本` : '');
  $('k-box').textContent = a.box ? (a.box + (a.box_name ? `（${a.box_name}）` : '')) : '';

  const isOut = a.status === 'checked_out';
  const canLend = a.status === 'in_stock';
  $('k-out').hidden = !isOut;
  $('k-in').hidden = !canLend;

  if (isOut) {
    const b = a.borrower || {};
    $('k-borrower').innerHTML = '';
    const nm = document.createElement('strong');
    nm.textContent = b.name || '';
    $('k-borrower').appendChild(nm);
    if (b.company) $('k-borrower').append(document.createElement('br'), b.company);
    if (b.phone) {
      const tel = document.createElement('a');
      tel.href = 'tel:' + b.phone; tel.textContent = b.phone;
      $('k-borrower').append(document.createElement('br'), tel);
    }
    $('k-since').textContent = `${a.checked_out_at}（${a.elapsed}経過）`;
    $('k-due').textContent = a.due_at || '指定なし';
    $('k-returnnote').textContent =
      (a.total_keys > 1 ? `${a.total_keys}本すべて揃っているか確かめて、` : '') +
      (a.box ? `${a.box} に戻してから押してください。` : '所定の位置に戻してから押してください。');
  }

  if (canLend) {
    // 貸出先の候補
    const picks = $('k-picks');
    picks.innerHTML = '';
    lendState.selected = null;
    (lendState.borrowers || []).forEach(b => {
      const el = document.createElement('button');
      el.type = 'button'; el.className = 'pick'; el.dataset.id = b.id;
      el.innerHTML = '<span class="nm"></span><span class="co"></span>';
      el.querySelector('.nm').textContent = b.name;
      el.querySelector('.co').textContent =
        (b.company || b.kind) + (b.open_count ? `・貸出中${b.open_count}件` : '');
      el.addEventListener('click', () => {
        const already = el.classList.contains('sel');
        picks.querySelectorAll('.pick').forEach(x => x.classList.remove('sel'));
        lendState.selected = already ? null : b.id;
        if (!already) {
          el.classList.add('sel');
          $('k-newbox').open = false;
          ['k-newname', 'k-newco', 'k-newtel'].forEach(i => $(i).value = '');
        }
      });
      picks.appendChild(el);
    });
    $('k-newbox').open = !(lendState.borrowers || []).length;

    // 返却予定
    const dues = $('k-dues');
    dues.innerHTML = '';
    (lendState.dues || []).forEach((d, i) => {
      const l = document.createElement('label');
      l.innerHTML = '<input type="radio" name="k-due"><span></span>';
      l.querySelector('input').value = d.value;
      l.querySelector('input').checked = i === 0;
      l.querySelector('span').textContent = d.label;
      dues.appendChild(l);
    });
  }
}

// 新規入力に触ったら候補の選択を外す（どちらに貸したのか曖昧にしない）
['k-newname', 'k-newco', 'k-newtel'].forEach(id =>
  $(id).addEventListener('input', () => {
    if (!lendState || !lendState.selected) return;
    lendState.selected = null;
    $('k-picks').querySelectorAll('.pick').forEach(x => x.classList.remove('sel'));
  }));

$('btn-lend').addEventListener('click', async () => {
  if (!lendState) return;
  const name = $('k-newname').value.trim();
  if (!lendState.selected && !name) {
    setMsg($('k-msg'), '⚠️ 貸出先を選ぶか、お名前を入力してください', true);
    $('k-newbox').open = true; $('k-newname').focus();
    return;
  }
  const due = document.querySelector('input[name=k-due]:checked');
  const btn = $('btn-lend');
  btn.disabled = true; btn.textContent = '処理中…';

  if (lendState.source === 'server') {
    const d = await api('/api/checkout', {
      token: lendState.token,
      borrower_id: lendState.selected || '',
      new_name: name, new_kind: $('k-newkind').value,
      new_company: $('k-newco').value.trim(), new_phone: $('k-newtel').value.trim(),
      due_at: due ? due.value : '',
    });
    btn.disabled = false; btn.textContent = '貸出する';
    if (!d || !d.ok) { setMsg($('k-msg'), '⚠️ ' + ((d && d.error) || '貸出できませんでした'), true); return; }
    lendState.asset = d.asset;
  } else {
    // 端末内で完結する貸出
    const picked = lendState.selected
      ? (lendState.borrowers.find(b => b.id === lendState.selected) || null) : null;
    const borrower = picked
      ? { name: picked.name, company: picked.company, kind: picked.kind, phone: '' }
      : { name, company: $('k-newco').value.trim(), phone: $('k-newtel').value.trim(),
          kind: ({ vendor: '業者', customer: 'お客様', employee: '社員', other: 'その他' })[$('k-newkind').value] };
    const r = lendState.rec;
    if (r.status === 'out') {
      btn.disabled = false; btn.textContent = '貸出する';
      setMsg($('k-msg'), '⚠️ この鍵はすでに貸出中です', true);
      return;
    }
    r.status = 'out'; r.borrower = borrower;
    r.since = new Date().toISOString();
    r.due = due && due.value ? due.value : '';
    save(KEY.ledger, ledger);
    lendState.asset = localAsset(r);
    btn.disabled = false; btn.textContent = '貸出する';
  }
  renderLending();
  setMsg($('k-msg'), '✅ 貸出しました', false);
});

$('btn-return').addEventListener('click', async () => {
  if (!lendState) return;
  const btn = $('btn-return');
  btn.disabled = true; btn.textContent = '処理中…';

  if (lendState.source === 'server') {
    const d = await api('/api/return', { token: lendState.token });
    btn.disabled = false; btn.textContent = '返却する';
    if (!d || !d.ok) { setMsg($('k-msg'), '⚠️ ' + ((d && d.error) || '返却できませんでした'), true); return; }
    // 返却後は貸出先の候補を取り直す（直近に借りた人が上に来るように）
    const fresh = await api('/api/asset?token=' + encodeURIComponent(lendState.token));
    lendState = (fresh && fresh.ok && fresh.found)
      ? { source: 'server', token: lendState.token, ...fresh }
      : { ...lendState, asset: d.asset };
  } else {
    const r = lendState.rec;
    if (r.status !== 'out') {
      btn.disabled = false; btn.textContent = '返却する';
      setMsg($('k-msg'), '⚠️ この鍵は貸出中ではありません', true);
      return;
    }
    // 履歴に積んでから状態を戻す。誰にいつ貸したかが消えないようにする
    r.history = (r.history || []);
    r.history.unshift({ name: r.borrower && r.borrower.name, company: r.borrower && r.borrower.company,
                        kind: r.borrower && r.borrower.kind, at: r.since,
                        returned: new Date().toISOString(), due: r.due });
    r.history = r.history.slice(0, 200);
    r.status = 'in'; r.borrower = null; r.since = ''; r.due = '';
    save(KEY.ledger, ledger);
    lendState.asset = localAsset(r);
    lendState.borrowers = localBorrowers().map((b, i) => ({
      id: 'L' + i, name: b.name, company: b.company, kind: b.kind, open_count: 0 }));
    lendState.dues = localDues();
    btn.disabled = false; btn.textContent = '返却する';
  }
  renderLending();
  setMsg($('k-msg'), '✅ 返却しました', false);
});

function setMsg(el, text, isErr) {
  el.textContent = text;
  el.className = 'msg' + (text ? (isErr ? ' err' : ' ok') : '');
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

    // ★セッションを開いたまま受け取る。閉じるとタグとの接続が切れて書けない
    const tag = await scanOnce('書き込むタグに近づけてください', { keepOpen: true });
    await Nfc.write({ records: p.records, allowFormat: true });

    // uid を控えておくと、次にかざしたとき確実にこの鍵だと分かる（サーバー不要）
    addToLedger(f, p, N.parseTag(tag).uid);
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
    closeScan();   // keepOpen で開けたセッションを必ず閉じる（成功・失敗とも）
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
/* 台帳の1件（端末内）
 *   { id, uid, at, property, name, numbers, boxCode, boxPosition, url,
 *     status: 'in'|'out', borrower, since, due, history: [...] }
 *
 * ★uid（タグ固有の番号）で鍵を特定する。タグに書いた文字は後から変わり得るが、
 *   uid は変わらない。サーバーが無くても「かざした鍵がどれか」が確実に決まる。
 */
function addToLedger(f, p, uid) {
  const rec = {
    id: 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    uid: uid || '',
    at: new Date().toISOString(),
    property: f.property, name: f.name, numbers: f.numbers,
    boxCode: f.boxCode, boxPosition: f.boxPosition,
    url: f.url || '', written: p.text, bytes: p.bytes,
    status: 'in', borrower: null, since: '', due: '', history: [],
  };
  // 同じタグに書き直した場合は、貸出状態と履歴を引き継いで中身だけ更新する
  const i = uid ? ledger.findIndex(r => r.uid && r.uid === uid) : -1;
  if (i >= 0) {
    const old = ledger[i];
    Object.assign(rec, {
      id: old.id, status: old.status, borrower: old.borrower,
      since: old.since, due: old.due, history: old.history || [],
    });
    ledger.splice(i, 1);
  }
  ledger.unshift(rec);
  ledger = ledger.slice(0, 2000);
  save(KEY.ledger, ledger);
  refreshProperties();
  return rec;
}

/** 端末内の台帳から鍵を探す。uid が最優先。 */
function findLocal(t) {
  if (t.uid) {
    const byUid = ledger.find(r => r.uid && r.uid === t.uid);
    if (byUid) return byUid;
  }
  if (t.url) {
    const byUrl = ledger.find(r => r.url && r.url === t.url);
    if (byUrl) return byUrl;
  }
  // uid を控える前に書いたタグのために、書いた文字が一致するものも見る
  if (t.text) return ledger.find(r => r.written && r.written === t.text) || null;
  return null;
}

/** 端末内の貸出先の候補。直近に貸した順。 */
function localBorrowers() {
  const seen = new Map();
  ledger.forEach(r => (r.history || []).concat(r.borrower ? [{ name: r.borrower.name,
      company: r.borrower.company, kind: r.borrower.kind, at: r.since }] : [])
    .forEach(h => {
      if (!h || !h.name) return;
      const k = h.name + '|' + (h.company || '');
      const prev = seen.get(k);
      if (!prev || (h.at || '') > (prev.at || '')) {
        seen.set(k, { name: h.name, company: h.company || '', kind: h.kind || '', at: h.at || '' });
      }
    }));
  return [...seen.values()].sort((a, b) => (b.at || '').localeCompare(a.at || '')).slice(0, 20);
}

function renderLedger() {
  $('l-count').textContent = ledger.length;
  $('l-empty').hidden = ledger.length > 0;
  const box = $('l-items');
  box.innerHTML = '';
  // 貸出中を先に、そのうち期限超過を最優先で出す
  const sorted = [...ledger].sort((a, b) => {
    const over = r => (r.status === 'out' && r.due && new Date(r.due) < new Date()) ? 0 : 1;
    const out = r => r.status === 'out' ? 0 : 1;
    return over(a) - over(b) || out(a) - out(b) || (b.at || '').localeCompare(a.at || '');
  });
  sorted.forEach(r => {
    const el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = '<div class="body"><div class="nm"></div><div class="sub"></div></div>' +
                   '<button class="go">再書込</button>';
    const overdue = r.status === 'out' && r.due && new Date(r.due) < new Date();
    const nm = el.querySelector('.nm');
    if (r.status === 'out') {
      const b = document.createElement('span');
      b.className = 'badge ' + (overdue ? 'over' : 'out');
      b.textContent = overdue ? '超過' : '貸出中';
      b.style.marginRight = '.4rem';
      nm.appendChild(b);
    }
    nm.append((r.property ? r.property + ' / ' : '') + r.name);
    el.querySelector('.sub').textContent = r.status === 'out'
      ? [`${(r.borrower && r.borrower.name) || ''} が借用中`,
         r.due ? `返却予定 ${fmtDT(r.due)}` : '返却予定なし',
         N.boxLabel(r.boxCode, r.boxPosition)].filter(Boolean).join('  ・  ')
      : [r.numbers, N.boxLabel(r.boxCode, r.boxPosition),
         (r.history || []).length ? `貸出${r.history.length}回` : ''].filter(Boolean).join('  ・  ');
    // 行の本体をタップ → その鍵の貸出・返却を開く。
    // NFCが使えない場面（タグを持っていない・シミュレータ）でも中身を確認できる
    el.querySelector('.body').addEventListener('click', async () => {
      document.querySelector('nav.tabs button[data-screen=s-read]').click();
      $('readresult').hidden = true;
      $('readlead').textContent = '台帳から開きました';
      await showLending({ uid: r.uid, url: r.url || null, text: r.written || null,
                          fields: null, records: [] });
      document.querySelector('main').scrollTop = 0;
    });
    el.querySelector('.body').style.cursor = 'pointer';

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

// ═══════════════════════════════════════════════════════════════
// お試し（サンプルの鍵）
//
// ★スクリーンショットのための細工ではなく、必要な機能。
//   NFCタグを持っていない人（App Storeの審査員を含む）が、
//   台帳・貸出・返却の動きを確かめられないと、このアプリは評価できない。
// ═══════════════════════════════════════════════════════════════
const SAMPLES = [
  { property: '本社ビル', name: '1階エントランス', numbers: '10001 / 10002',
    boxCode: 'BOX-01', boxPosition: '01' },
  { property: '本社ビル', name: '機械室', numbers: '10003 ×3',
    boxCode: 'BOX-01', boxPosition: '02',
    lend: { name: '田中 一郎', company: '〇〇工務店', kind: '業者' }, dueHours: 6 },
  { property: '本社ビル', name: '3階会議室', numbers: '10008',
    boxCode: 'BOX-01', boxPosition: '03' },
  { property: '第2倉庫', name: 'シャッター', numbers: '22001 ×2',
    boxCode: 'BOX-02', boxPosition: '01',
    lend: { name: '鈴木 次郎', company: '△△クリーンサービス', kind: '業者' }, dueHours: -2 },
  { property: '', name: '社用車 1号', numbers: 'CAR-01',
    boxCode: 'BOX-01', boxPosition: '10' },
];

$('btn-sample').addEventListener('click', () => {
  const now = Date.now();
  SAMPLES.forEach((sm, i) => {
    const f = { property: sm.property, name: sm.name, numbers: sm.numbers,
                boxCode: sm.boxCode, boxPosition: sm.boxPosition, url: '' };
    // サンプルだと分かる形のタグID（実物と混ざらないように 00: で始める）
    const uid = '00:' + String(i + 1).padStart(2, '0') + ':SA:MP:LE:00:00';
    const rec = addToLedger(f, N.plan(f, conf.tagType), uid);
    if (sm.lend) {
      rec.status = 'out';
      rec.borrower = { ...sm.lend, phone: '' };
      rec.since = new Date(now - 3 * 3600e3).toISOString();
      rec.due = new Date(now + sm.dueHours * 3600e3).toISOString();
    }
  });
  save(KEY.ledger, ledger);
  refreshProperties();
  renderLedger();
  setMsg($('s-msg'), `✅ サンプルを${SAMPLES.length}件入れました。「台帳」を開いてみてください`, false);
});

$('btn-clearall').addEventListener('click', () => {
  if (!confirm('この端末に保存した鍵の記録をすべて消します。よろしいですか？')) return;
  ledger = [];
  save(KEY.ledger, ledger);
  refreshProperties();
  renderLedger();
  $('lend').hidden = true;
  setMsg($('s-msg'), 'すべての記録を消しました', false);
});

// ---------------------------------------------------------------------------
const escapeHtml = s => String(s).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// 起動
$('w-keys').appendChild(keyRow());
refreshProperties();
renderLedger();
preview();
$('c-ver').textContent = 'KeyTag 1.0.0';
initNfc();

/* 開発・検証用の入口。**実機（Capacitor）では有効にならない。**
 * NFCはブラウザで動かせないため、かざした結果を差し込んで画面を確かめるために使う。 */
if (!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())) {
  window.__tagtest = {
    /** タグをかざしたことにする。tag は ndef.parseTag が返す形。 */
    async scan(tag) { showTag(tag); await showLending(tag); return lendState; },
    /** 台帳に1件足す（書き込みの代わり）。 */
    add(fields, uid) { return addToLedger(fields, N.plan(fields, conf.tagType), uid); },
    state: () => lendState,
    ledger: () => ledger,
    reset() { ledger = []; save(KEY.ledger, ledger); renderLedger(); },
  };
}
