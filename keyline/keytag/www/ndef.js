/* NDEF の組み立てと読み取り。
 *
 * ★サーバー側の keyline/ndef.py と **同じ形式**で書く必要がある。
 *   片方だけ直すと、アプリで書いたタグをサーバーが読めない（またはその逆）。
 *   書式・区切り文字・削る順番を変えるときは必ず両方を直すこと。
 *
 * 書き込む内容（2レコード）
 *   1. URLレコード   http://192.168.1.105:8534/t/<token>
 *      … iPhoneがSafariで開くのはこれ。単体モードでは省略できる
 *   2. テキストレコード  物件名|鍵の名称|鍵番号|ボックス-位置
 *      … WiFiが無くても内容が読める控え
 *
 * タグの容量（NXPの仕様値・ユーザーメモリ）
 *   NTAG213 144 / NTAG215 504 / NTAG216 888
 */

export const TAG_CAPACITY = { NTAG213: 144, NTAG215: 504, NTAG216: 888 };
export const SEP = '|';

const TNF_WELL_KNOWN = 1;
const TYPE_URI = [0x55];   // 'U'
const TYPE_TEXT = [0x54];  // 'T'

// NDEF の URI Identifier Code。'http://' が 7バイト → 1バイトになる
const URI_PREFIXES = [
  [0x01, 'http://www.'], [0x02, 'https://www.'],
  [0x03, 'http://'], [0x04, 'https://'],
];

const enc = new TextEncoder();
const dec = new TextDecoder('utf-8');

const bytes = s => Array.from(enc.encode(s));
export const byteLen = s => enc.encode(s).length;

// ---------------------------------------------------------------------------
// 組み立て
// ---------------------------------------------------------------------------
export function uriRecord(url) {
  let code = 0x00, rest = url;
  for (const [c, prefix] of URI_PREFIXES) {
    if (url.startsWith(prefix)) { code = c; rest = url.slice(prefix.length); break; }
  }
  return { tnf: TNF_WELL_KNOWN, type: TYPE_URI, id: [], payload: [code, ...bytes(rest)] };
}

export function textRecord(text, lang = 'ja') {
  return {
    tnf: TNF_WELL_KNOWN, type: TYPE_TEXT, id: [],
    payload: [lang.length, ...bytes(lang), ...bytes(text)],
  };
}

/** タグ上で実際に消費するバイト数（レコードのヘッダとTLVの包みを含む）。
 *  ここを甘く見ると「書いたつもりで入っていない」が起きるので、
 *  ndef.py と同じ数え方をする。 */
export function messageSize(records) {
  let msg = 0;
  for (const r of records) {
    const short = r.payload.length < 256;
    msg += 1 + 1 + (short ? 1 : 4) + r.type.length + r.payload.length;
    if (r.id.length) msg += 1 + r.id.length;
  }
  return msg < 255 ? msg + 3 : msg + 5;   // TLV（0x03 + 長さ + 終端0xFE）
}

// ---------------------------------------------------------------------------
// 控えテキスト
// ---------------------------------------------------------------------------
export function boxLabel(code, position) {
  code = (code || '').trim(); position = (position || '').trim();
  if (code && position) return `${code}-${position}`;
  return code || (position ? `位置${position}` : '');
}

export function infoText({ property, name, numbers, boxCode, boxPosition }) {
  const box = boxLabel(boxCode, boxPosition);
  return [property, name, numbers, box].filter(Boolean).join(SEP);
}

/** UTF-8で budget バイトに収まるまで後ろを削る。日本語は1文字3バイト。 */
function cut(text, budget) {
  if (byteLen(text) <= budget) return text;
  budget = Math.max(budget - 3, 0);        // '…' の分
  let out = '', used = 0;
  for (const ch of text) {
    const b = byteLen(ch);
    if (used + b > budget) break;
    out += ch; used += b;
  }
  return out ? out + '…' : '';
}

/**
 * このタグに何が書けるかを決める。
 *
 * ★削る順番が肝。鍵番号とボックスはASCIIで安く、しかも現場で一番使う情報
 *   （どの鍵か・どこに戻すか）なので必ず残す。削るのは日本語の名前の方。
 *   ndef.py の plan() と同じ規則。
 */
export function plan(fields, tagType = 'NTAG213') {
  const cap = TAG_CAPACITY[tagType] || TAG_CAPACITY.NTAG213;
  const { url } = fields;
  const build = text => {
    const rs = [];
    if (url) rs.push(uriRecord(url));
    if (text) rs.push(textRecord(text));
    return rs;
  };

  const text = infoText(fields);
  let records = build(text);
  let size = messageSize(records);
  if (size <= cap) {
    return { records, text, bytes: size, capacity: cap, free: cap - size,
             truncated: false, fits: true, tagType };
  }

  // 鍵番号とボックスは残す前提で、名前に使える枠を測る
  const box = boxLabel(fields.boxCode, fields.boxPosition);
  const cheap = [fields.numbers, box].filter(Boolean).join(SEP);
  const base = messageSize(build(cheap || null));
  let budget = cap - base - (cheap ? 1 : 0);

  const names = [fields.property, fields.name].filter(Boolean);
  if (budget > 0 && names.length) {
    const share = Math.floor(budget / names.length);
    const cutNames = names.map((n, i) =>
      cut(n, share + (i === names.length - 1 ? budget % names.length : 0)));
    const t = [...cutNames.filter(Boolean), ...(cheap ? [cheap] : [])].join(SEP);
    records = build(t); size = messageSize(records);
    if (size <= cap) {
      return { records, text: t, bytes: size, capacity: cap, free: cap - size,
               truncated: true, fits: true, tagType };
    }
  }

  if (cheap) {
    records = build(cheap); size = messageSize(records);
    if (size <= cap) {
      return { records, text: cheap, bytes: size, capacity: cap, free: cap - size,
               truncated: true, fits: true, tagType };
    }
  }

  records = build(null); size = messageSize(records);
  return { records, text: '', bytes: size, capacity: cap, free: cap - size,
           truncated: true, fits: size <= cap, tagType };
}

// ---------------------------------------------------------------------------
// 読み取り
// ---------------------------------------------------------------------------
const b2a = p => (p instanceof Uint8Array ? p : Uint8Array.from(p || []));

export function parseRecord(r) {
  const type = String.fromCharCode(...(r.type || []));
  const payload = b2a(r.payload);
  if (type === 'U') {
    const [code, ...rest] = payload;
    const prefix = (URI_PREFIXES.find(p => p[0] === code) || [0, ''])[1];
    return { kind: 'url', value: prefix + dec.decode(Uint8Array.from(rest)) };
  }
  if (type === 'T') {
    const langLen = payload[0] & 0x3f;
    return { kind: 'text', value: dec.decode(payload.slice(1 + langLen)) };
  }
  return { kind: 'other', value: dec.decode(payload) };
}

/** タグ1枚を読んで、鍵の情報に組み立て直す。 */
export function parseTag(tag) {
  const out = { uid: null, url: null, text: null, fields: null, records: [] };
  if (tag && tag.id && tag.id.length) {
    out.uid = tag.id.map(b => b.toString(16).padStart(2, '0').toUpperCase()).join(':');
  }
  for (const r of (tag && tag.ndefMessage) || []) {
    const p = parseRecord(r);
    out.records.push(p);
    if (p.kind === 'url' && !out.url) out.url = p.value;
    if (p.kind === 'text' && !out.text) out.text = p.value;
  }
  if (out.text) {
    // 物件名|鍵の名称|鍵番号|ボックス の順。後ろから欠けるので前から詰めて読む
    const parts = out.text.split(SEP);
    out.fields = {
      property: parts[0] || '',
      name: parts[1] || '',
      numbers: parts[2] || '',
      box: parts[3] || '',
    };
  }
  return out;
}

/** KeyLineサーバーのURLかどうか（/t/<トークン> の形か）。 */
export function keylineToken(url) {
  if (!url) return null;
  const m = String(url).match(/^https?:\/\/[^/]+\/t\/([a-z0-9]{8,32})$/i);
  return m ? m[1] : null;
}
