'use strict';

let _ctx, _W, _H;
function setRenderCtx(ctx, W, H) { _ctx = ctx; _W = W; _H = H; }

// ── Primitives ───────────────────────────────────────────────────────────────
function rrect(x, y, w, h, r, fill, stroke, lw) {
  lw = lw === undefined ? 2 : lw;
  _ctx.beginPath();
  _ctx.moveTo(x+r, y);
  _ctx.lineTo(x+w-r, y); _ctx.quadraticCurveTo(x+w, y, x+w, y+r);
  _ctx.lineTo(x+w, y+h-r); _ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
  _ctx.lineTo(x+r, y+h); _ctx.quadraticCurveTo(x, y+h, x, y+h-r);
  _ctx.lineTo(x, y+r); _ctx.quadraticCurveTo(x, y, x+r, y);
  _ctx.closePath();
  if (fill)   { _ctx.fillStyle   = fill;   _ctx.fill();   }
  if (stroke) { _ctx.strokeStyle = stroke; _ctx.lineWidth = lw; _ctx.stroke(); }
}

/* ★2026-08-29: パネル・ボタンの縁を**ネオン管**にした。
   画面の中身（敵・ボス・空・地面）はネオンにしたのに、UIだけ
   「赤いSTART・茶色のボタン・緑の草」の昔のままで浮いていたため。
   ★ここ1か所で全画面（タイトル／設定／図鑑／実績／ショップ／ゲームオーバー）に効く。
     呼び出し側が渡す stroke の色をそのまま光らせるので、色の意味（青＝図鑑・金＝実績…）は残る。 */
function rrectGrd(x, y, w, h, r, grd, stroke, lw) {
  lw = lw === undefined ? 2 : lw;
  _ctx.beginPath();
  _ctx.moveTo(x+r, y);
  _ctx.lineTo(x+w-r, y); _ctx.quadraticCurveTo(x+w, y, x+w, y+r);
  _ctx.lineTo(x+w, y+h-r); _ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
  _ctx.lineTo(x+r, y+h); _ctx.quadraticCurveTo(x, y+h, x, y+h-r);
  _ctx.lineTo(x, y+r); _ctx.quadraticCurveTo(x, y, x+r, y);
  _ctx.closePath();
  _ctx.fillStyle = grd; _ctx.fill();
  if (stroke) {
    _ctx.save();
    _ctx.shadowColor = _neonGlowOf(stroke); _ctx.shadowBlur = Math.max(8, lw * 5);
    _ctx.strokeStyle = stroke; _ctx.lineWidth = lw; _ctx.stroke();
    _ctx.restore();
  }
}
/* 縁の色から「光の色」を作る。rgba(…) は不透明にしないと光って見えない */
function _neonGlowOf(col) {
  if (typeof col !== 'string') return 'rgba(65,227,255,.8)';
  var m = /^rgba?\(([^)]+)\)/.exec(col);
  if (m) {
    var p = m[1].split(',');
    return 'rgba(' + p[0].trim() + ',' + p[1].trim() + ',' + p[2].trim() + ',0.85)';
  }
  return col;
}

// ── Background ───────────────────────────────────────────────────────────────
// 空の色。t=天頂 / m=中空 / b=地平線側 / g=地平線のグロー / n=星雲 / mo=月あかり
//
// **地平線側(b)を一番明るくしてある。** 旧版は b が一番暗く、st20 は #000000 だった
// ため、画面の2/3が黒一色になり「何も無い」画面に見えていた（2026-08-28 に実測）。
// 明るい下空に黒いカラスが乗ると輪郭が立つので、見た目と遊びやすさが同時に良くなる。
// ステージが進むと空は禍々しくなるが、**真っ黒にはしない**（暗さ＝緊張感は色で出す）。
var _SBG = [
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FFC489', n:'#3E63C8', mo:'#FFF4D6' }, //  1 夜明け前
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FFB878', n:'#3E63C8', mo:'#FFF0CE' }, //  2
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FFA96A', n:'#4460C8', mo:'#FFEDC6' }, //  3
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF9A62', n:'#5A5AC8', mo:'#FFE9BE' }, //  4
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF8FA8', n:'#7A46C8', mo:'#FFE2D2' }, //  5 紫の夜
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF85B0', n:'#8446C8', mo:'#FFDCD4' }, //  6
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF7BB8', n:'#8E46C8', mo:'#FFD6D6' }, //  7
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF71C0', n:'#9846C8', mo:'#FFD0D8' }, //  8
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF7A5A', n:'#C8464A', mo:'#FFC4B0' }, //  9 赤い異変
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF6B4A', n:'#C8383C', mo:'#FFBAA4' }, // 10
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF5C3A', n:'#C82A2E', mo:'#FFB098' }, // 11
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#FF4D2A', n:'#C81C20', mo:'#FFA68C' }, // 12
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#9BFF7A', n:'#58C86A', mo:'#DCFFCE' }, // 13 毒の空
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#86FF6A', n:'#4AC85E', mo:'#D2FFC4' }, // 14
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#71FF5A', n:'#3CC852', mo:'#C8FFBA' }, // 15
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#5CFF4A', n:'#2EC846', mo:'#BEFFB0' }, // 16
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#8FA8FF', n:'#5050D8', mo:'#D6E2FF' }, // 17 深宇宙
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#9FB4FF', n:'#5A50D8', mo:'#DCE6FF' }, // 18
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#AFC0FF', n:'#6450D8', mo:'#E2EAFF' }, // 19
  { t:'#0B0720', m:'#160D33', b:'#241247', g:'#C0CCFF', n:'#7050D8', mo:'#E8EEFF' }, // 20
];

// '#RRGGBB' → 'r,g,b'（rgba() に混ぜるため）
function _rgb(hex) {
  return parseInt(hex.substr(1,2),16)+','+parseInt(hex.substr(3,2),16)+','+parseInt(hex.substr(5,2),16);
}

// hideMoon: 月の位置(_W*0.79, 214)に画面側の絵が来るときに true を渡す
// （ゲームオーバー/エンディングは同じ場所に地球を描くので、並ぶと灰色の塊に見える）
function drawBg(frame, stage, hideMoon) {
  var si = Math.max(0, Math.min(19, (stage||1) - 1));
  var bg = _SBG[si];

  // ① 空 ─────────────────────────────────────────────────────────────────────
  var g = _ctx.createLinearGradient(0, 0, 0, _H);
  g.addColorStop(0, bg.t); g.addColorStop(0.52, bg.m); g.addColorStop(1, bg.b);
  _ctx.fillStyle = g; _ctx.fillRect(0, 0, _W, _H);

  // ② 地平線から立ちのぼる光（画面下端の外に光源を置く）────────────────────────
  var hg = _ctx.createRadialGradient(_W*0.5, _H*1.04, 0, _W*0.5, _H*1.04, _W*1.05);
  hg.addColorStop(0,    'rgba('+_rgb(bg.g)+',0.34)');
  hg.addColorStop(0.45, 'rgba('+_rgb(bg.g)+',0.11)');
  hg.addColorStop(1,    'rgba('+_rgb(bg.g)+',0)');
  _ctx.fillStyle = hg; _ctx.fillRect(0, 0, _W, _H);

  // ③ 星雲（ステージが進むほど濃く）──────────────────────────────────────────
  var na = 0.05 + Math.min(si, 12)/12 * 0.13;
  var ng = _ctx.createRadialGradient(_W*0.68, _H*0.20, 0, _W*0.68, _H*0.20, _W*0.85);
  ng.addColorStop(0, 'rgba('+_rgb(bg.n)+','+na+')'); ng.addColorStop(1, 'rgba('+_rgb(bg.n)+',0)');
  _ctx.fillStyle = ng; _ctx.fillRect(0, 0, _W, _H);
  var ng2 = _ctx.createRadialGradient(_W*0.14, _H*0.44, 0, _W*0.14, _H*0.44, _W*0.62);
  ng2.addColorStop(0, 'rgba('+_rgb(bg.n)+','+(na*0.7)+')'); ng2.addColorStop(1, 'rgba('+_rgb(bg.n)+',0)');
  _ctx.fillStyle = ng2; _ctx.fillRect(0, 0, _W, _H);

  // ④ 星（上ほど多く、地平線側では消す＝明るい空に白点が浮くのを避ける）─────────
  var cnt = 70 + Math.min(si, 9) * 5;
  for (var i = 0; i < cnt; i++) {
    var sx = (i*141+47) % _W, sy = (i*233+31) % (_H*0.80);
    var fade = 1 - sy/(_H*0.86);                       // 下に行くほど薄く
    if (fade <= 0.04) continue;
    _ctx.globalAlpha = (Math.sin(frame*0.04+i)*0.24+0.66) * fade;
    _ctx.fillStyle = si >= 12 ? '#EAFFEA' : si >= 8 ? '#FFDCD0' : '#FFFFFF';
    _ctx.beginPath(); _ctx.arc(sx, sy, 0.55+(i%4)*0.38, 0, Math.PI*2); _ctx.fill();
  }
  _ctx.globalAlpha = 1;

  // ⑤ 月 ─────────────────────────────────────────────────────────────────────
  if (!hideMoon) _drawMoon(frame, si, bg);

  // ⑥ 雲（2層。手前ほど速い＝視差）────────────────────────────────────────────
  _drawClouds(frame, si, bg);

  // ⑦ 流れ星（300フレームに1回、45フレームだけ横切る）──────────────────────────
  var sp = frame % 300;
  if (sp < 45) {
    var seed = Math.floor(frame/300) * 2654435761 % 1000 / 1000;
    var p    = sp / 45;
    var stx  = (0.12 + seed*0.7) * _W + p*130, sty = (0.06 + seed*0.34) * _H + p*90;
    _ctx.globalAlpha = Math.sin(p*Math.PI) * 0.85;
    var sg = _ctx.createLinearGradient(stx-46, sty-32, stx, sty);
    sg.addColorStop(0, 'rgba(255,255,255,0)'); sg.addColorStop(1, '#FFFFFF');
    _ctx.strokeStyle = sg; _ctx.lineWidth = 2; _ctx.lineCap = 'round';
    _ctx.beginPath(); _ctx.moveTo(stx-46, sty-32); _ctx.lineTo(stx, sty); _ctx.stroke();
    _ctx.globalAlpha = 1; _ctx.lineCap = 'butt';
  }
}

// 月。ステージ帯ごとに色と満ち欠けが変わる（st13以降は蝕んだ月）
function _drawMoon(frame, si, bg) {
  var mx = _W*0.79, my = 214, r = 33;
  var pulse = Math.sin(frame*0.012)*0.06 + 1;
  _ctx.save();
  // 暈（かさ）
  var hg = _ctx.createRadialGradient(mx, my, r*0.7, mx, my, r*3.4*pulse);
  hg.addColorStop(0, 'rgba('+_rgb(bg.mo)+',0.20)'); hg.addColorStop(1, 'rgba('+_rgb(bg.mo)+',0)');
  _ctx.fillStyle = hg; _ctx.beginPath(); _ctx.arc(mx, my, r*3.4*pulse, 0, Math.PI*2); _ctx.fill();
  // 本体
  var mg = _ctx.createRadialGradient(mx-r*0.3, my-r*0.32, r*0.15, mx, my, r);
  mg.addColorStop(0, '#FFFFFF'); mg.addColorStop(1, bg.mo);
  _ctx.fillStyle = mg; _ctx.beginPath(); _ctx.arc(mx, my, r, 0, Math.PI*2); _ctx.fill();
  // クレーター
  _ctx.fillStyle = 'rgba(0,0,0,0.07)';
  [[-0.30,-0.10,0.24],[0.26,0.18,0.17],[0.02,0.42,0.12],[0.34,-0.34,0.10]].forEach(function(c){
    _ctx.beginPath(); _ctx.arc(mx+r*c[0], my+r*c[1], r*c[2], 0, Math.PI*2); _ctx.fill();
  });
  // 欠け（空の色でくり抜く＝ステージが進むほど深く欠ける）
  var phase = Math.min(0.72, si/19 * 0.72);
  if (phase > 0.03) {
    _ctx.globalCompositeOperation = 'destination-out';
    _ctx.beginPath(); _ctx.arc(mx + r*(0.55+phase*0.9), my - r*0.10, r*1.02, 0, Math.PI*2); _ctx.fill();
    _ctx.globalCompositeOperation = 'source-over';
  }
  _ctx.restore();
}

// 雲。sin で漂わせるだけ（乱数を使わないので毎フレーム同じ形になる）
var _CLOUDS = [
  { y:296, s:1.00, sp:0.16, a:0.13, o:0    },
  { y:352, s:0.72, sp:0.11, a:0.10, o:180  },
  { y:470, s:1.28, sp:0.26, a:0.15, o:60   },
  { y:556, s:0.90, sp:0.34, a:0.12, o:300  },
  { y:628, s:1.45, sp:0.46, a:0.14, o:120  },
];
function _drawClouds(frame, si, bg) {
  var span = _W + 260;
  for (var i = 0; i < _CLOUDS.length; i++) {
    var c  = _CLOUDS[i];
    var cx = ((frame*c.sp + c.o) % span) - 130;
    var cy = c.y + Math.sin(frame*0.008 + i)*4;
    _ctx.globalAlpha = c.a;
    _ctx.fillStyle   = bg.mo;
    _ctx.beginPath();
    _ctx.ellipse(cx,            cy,        46*c.s, 15*c.s, 0, 0, Math.PI*2);
    _ctx.ellipse(cx-30*c.s,     cy+5*c.s,  30*c.s, 11*c.s, 0, 0, Math.PI*2);
    _ctx.ellipse(cx+34*c.s,     cy+4*c.s,  26*c.s, 10*c.s, 0, 0, Math.PI*2);
    _ctx.ellipse(cx+8*c.s,      cy-10*c.s, 27*c.s, 13*c.s, 0, 0, Math.PI*2);
    _ctx.fill();
  }
  _ctx.globalAlpha = 1;
}

// ── Ground ───────────────────────────────────────────────────────────────────
// ひよこが守っている「村」。遠い丘 → 村の家並み（窓の明かり）→ 手前の草地 の3層。
// 旧版は単色のベタ塗り1枚で、守るものが画面に無かった。
var _HOUSES = [
  { x:0.07, w:26, h:24, roof:'#5A3A6E', wall:'#3A2450' },
  { x:0.17, w:20, h:18, roof:'#4A3060', wall:'#32204A' },
  { x:0.30, w:32, h:30, roof:'#63407A', wall:'#402856' },
  { x:0.44, w:22, h:20, roof:'#4A3060', wall:'#32204A' },
  { x:0.60, w:28, h:26, roof:'#5A3A6E', wall:'#3A2450' },
  { x:0.72, w:19, h:17, roof:'#4A3060', wall:'#32204A' },
  { x:0.86, w:30, h:27, roof:'#63407A', wall:'#402856' },
];

function drawGround(stage) {
  var t  = Math.max(0, Math.min(1, ((stage||1)-1)/19));
  var si = Math.max(0, Math.min(19, (stage||1) - 1));
  var bg = _SBG[si];
  var HL = _H - 108;                       // 手前の草地の稜線

  // ① 遠い丘（奥ほど空の色に溶かす）──────────────────────────────────────────
  var hillTop = HL - 52;
  _ctx.save();
  _ctx.fillStyle = 'rgba('+_rgb(bg.b)+',0.62)';
  _ctx.beginPath();
  _ctx.moveTo(0, hillTop+8);
  _ctx.quadraticCurveTo(_W*0.20, hillTop-26, _W*0.44, hillTop+4);
  _ctx.quadraticCurveTo(_W*0.70, hillTop+30, _W, hillTop-6);
  _ctx.lineTo(_W, _H); _ctx.lineTo(0, _H); _ctx.closePath(); _ctx.fill();
  // 手前の丘（村が乗る面）
  _ctx.fillStyle = 'rgba('+_rgb(bg.t)+',0.88)';
  _ctx.beginPath();
  _ctx.moveTo(0, HL-26);
  _ctx.quadraticCurveTo(_W*0.30, HL-40, _W*0.58, HL-28);
  _ctx.quadraticCurveTo(_W*0.82, HL-18, _W, HL-32);
  _ctx.lineTo(_W, _H); _ctx.lineTo(0, _H); _ctx.closePath(); _ctx.fill();
  _ctx.restore();

  // ② 村（家＋窓の明かり）。ひよこ(y=_H-148)より上＝奥に置く ──────────────────
  var base = HL - 30;
  var HS   = 0.78;                                   // 遠景なので小さめ
  _HOUSES.forEach(function(h, i) {
    var hx = h.x*_W, hw = h.w*HS, hh = h.h*HS;
    _ctx.fillStyle = h.wall;
    _ctx.fillRect(hx - hw/2, base - hh, hw, hh);
    _ctx.fillStyle = h.roof;                         // 三角屋根
    _ctx.beginPath();
    _ctx.moveTo(hx - hw/2 - 2.5, base - hh);
    _ctx.lineTo(hx,              base - hh - hw*0.42);
    _ctx.lineTo(hx + hw/2 + 2.5, base - hh);
    _ctx.closePath(); _ctx.fill();
    // 窓の明かり（家ごとに違うゆらぎ。ここが村の生活感になる）
    var lit = 0.60 + Math.sin(i*2.1)*0.25;
    _ctx.save();
    _ctx.shadowColor = '#FFD98A'; _ctx.shadowBlur = 6;
    _ctx.fillStyle   = 'rgba(255,216,134,'+lit+')';
    _ctx.fillRect(hx - hw*0.28, base - hh*0.64, hw*0.24, hh*0.28);
    _ctx.fillRect(hx + hw*0.05, base - hh*0.64, hw*0.24, hh*0.28);
    _ctx.restore();
  });
  // 木（村のあいだ）
  [0.12, 0.375, 0.525, 0.665, 0.795, 0.945].forEach(function(px) {
    var tx = px*_W;
    _ctx.fillStyle = '#2A1A3C';
    _ctx.fillRect(tx-1.3, base-10, 2.6, 10);
    _ctx.fillStyle = 'rgba(46,30,66,0.95)';
    _ctx.beginPath(); _ctx.arc(tx, base-14, 6.6, 0, Math.PI*2); _ctx.fill();
    _ctx.beginPath(); _ctx.arc(tx-4, base-10, 4.8, 0, Math.PI*2); _ctx.fill();
    _ctx.beginPath(); _ctx.arc(tx+4, base-10, 4.8, 0, Math.PI*2); _ctx.fill();
  });

  // ③ 手前の草地 ────────────────────────────────────────────────────────────
  // ★ネオン版: 昼の草地 → 夜の草地。ステージが進むほど紫に寄せる（空と地続きに見せるため）
  var r1 = Math.round(28+t*30), g1 = Math.round( 70-t*34), b1 = Math.round(62+t*14);
  var r2 = Math.round(14+t*18), g2 = Math.round( 34-t*16), b2 = Math.round(40+t*10);
  var grd = _ctx.createLinearGradient(0, HL-20, 0, _H);
  grd.addColorStop(0, 'rgb('+r1+','+g1+','+b1+')');
  grd.addColorStop(1, 'rgb('+r2+','+g2+','+b2+')');
  _ctx.fillStyle = grd;
  _ctx.beginPath();
  _ctx.moveTo(0, HL);
  _ctx.quadraticCurveTo(_W*0.25, HL-17, _W*0.5, HL-4);
  _ctx.quadraticCurveTo(_W*0.75, HL+8,  _W,    HL-10);
  _ctx.lineTo(_W, _H); _ctx.lineTo(0, _H); _ctx.closePath(); _ctx.fill();

  // 稜線のハイライト（月あかりが当たっている縁）
  // ★稜線はネオン管に（夜の地面と空の境目をはっきりさせる）
  _ctx.save(); _ctx.shadowColor = '#41E3FF'; _ctx.shadowBlur = 10;
  _ctx.strokeStyle = 'rgba(65,227,255,0.55)'; _ctx.lineWidth = 2;
  _ctx.beginPath();
  _ctx.moveTo(0, HL);
  _ctx.quadraticCurveTo(_W*0.25, HL-17, _W*0.5, HL-4);
  _ctx.quadraticCurveTo(_W*0.75, HL+8,  _W,    HL-10);
  _ctx.stroke(); _ctx.restore();

  // 草と花（位置は式で決めているので毎フレーム同じ。ちらつかない）
  _ctx.strokeStyle = 'rgba(90,220,150,0.28)'; _ctx.lineWidth = 1.6;   // ★草は淡い蛍光の緑
  for (var i = 0; i < 46; i++) {
    var gx = (i*83+19) % _W;
    var gy = HL + 6 + (i*37 % 84);
    var lean = ((i%5)-2) * 1.6;
    _ctx.beginPath(); _ctx.moveTo(gx, gy); _ctx.quadraticCurveTo(gx+lean, gy-5, gx+lean*1.7, gy-9); _ctx.stroke();
  }
  var FLOWER = ['#FF7FD0','#FFE082','#7CE7FF'];   // ★花も発光色に
  for (var j = 0; j < 11; j++) {
    var fx = (j*131+41) % _W, fy = HL + 16 + (j*53 % 70);
    _ctx.fillStyle = FLOWER[j % 3];
    _ctx.globalAlpha = 0.72;
    _ctx.beginPath(); _ctx.arc(fx, fy, 2.1, 0, Math.PI*2); _ctx.fill();
    _ctx.globalAlpha = 1;
  }
}

// ── Chick ────────────────────────────────────────────────────────────────────
function drawChick(x, y, sz, evolved, acc, angel) {
  sz      = sz      === undefined ? 40    : sz;
  evolved = evolved === undefined ? false : evolved;
  acc     = acc     === undefined ? null  : acc;
  angel   = angel   === undefined ? false : angel;
  _ctx.save(); _ctx.translate(x, y);
  _ctx.shadowColor = 'rgba(0,0,0,0.5)'; _ctx.shadowBlur = sz*0.45;
  _ctx.shadowOffsetX = sz*0.05; _ctx.shadowOffsetY = sz*0.09;

  // ── エンジェル形態: ハロー＋白い翼（胴体の後ろに描く）──────────────────────
  if (angel) {
    _ctx.shadowBlur = 0; _ctx.shadowOffsetX = 0; _ctx.shadowOffsetY = 0;
    // 金色のハロー
    _ctx.shadowColor = '#FFD700'; _ctx.shadowBlur = sz*0.5;
    _ctx.strokeStyle = '#FFE840'; _ctx.lineWidth = sz*0.065;
    _ctx.beginPath(); _ctx.ellipse(0, -sz*0.76, sz*0.32, sz*0.09, 0, 0, Math.PI*2); _ctx.stroke();
    _ctx.shadowBlur = 0;
    // 胴体の影を復元
    _ctx.shadowColor = 'rgba(0,0,0,0.5)'; _ctx.shadowBlur = sz*0.45;
    _ctx.shadowOffsetX = sz*0.05; _ctx.shadowOffsetY = sz*0.09;
    // 白い大きな翼（胴体の後ろ）
    _ctx.fillStyle = 'rgba(255,255,255,0.92)'; _ctx.strokeStyle = '#C0C8EE'; _ctx.lineWidth = 1.5;
    _ctx.beginPath();
    _ctx.moveTo(-sz*0.12, sz*0.0);
    _ctx.quadraticCurveTo(-sz*1.1, -sz*0.5, -sz*0.82, sz*0.32);
    _ctx.quadraticCurveTo(-sz*0.4, sz*0.14, -sz*0.12, sz*0.08);
    _ctx.closePath(); _ctx.fill(); _ctx.stroke();
    _ctx.beginPath();
    _ctx.moveTo(sz*0.12, sz*0.0);
    _ctx.quadraticCurveTo(sz*1.1, -sz*0.5, sz*0.82, sz*0.32);
    _ctx.quadraticCurveTo(sz*0.4, sz*0.14, sz*0.12, sz*0.08);
    _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  }

  // ── 進化（エンジェル以外）: 赤いトサカ ──────────────────────────────────
  if (evolved && !angel) {
    _ctx.fillStyle = '#E74C3C'; _ctx.strokeStyle = '#922B21'; _ctx.lineWidth = 2;
    _ctx.beginPath();
    _ctx.moveTo(-7, -sz*0.72); _ctx.quadraticCurveTo(-13, -sz*1.0, -4, -sz*0.88);
    _ctx.quadraticCurveTo(0, -sz*1.12, 4, -sz*0.88); _ctx.quadraticCurveTo(13, -sz*1.0, 7, -sz*0.72);
    _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  }

  var bg = _ctx.createRadialGradient(-sz*0.12, sz*0.0, sz*0.04, 0, sz*0.1, sz*0.56);
  if (angel) {
    bg.addColorStop(0,'#FFFFFF'); bg.addColorStop(0.45,'#E8EEFF'); bg.addColorStop(1,'#B8B8EE');
    _ctx.fillStyle = bg; _ctx.strokeStyle = '#9898C8'; _ctx.lineWidth = 2;
  } else {
    bg.addColorStop(0,'#FFF9C4'); bg.addColorStop(0.45,'#FFE135'); bg.addColorStop(1,'#CC8800');
    _ctx.fillStyle = bg; _ctx.strokeStyle = '#B8860B'; _ctx.lineWidth = 2;
  }
  _ctx.beginPath(); _ctx.ellipse(0, sz*0.1, sz*0.52, sz*0.48, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  var hg = _ctx.createRadialGradient(-sz*0.08, -sz*0.38, sz*0.02, 0, -sz*0.3, sz*0.38);
  if (angel) {
    hg.addColorStop(0,'#FFFFFF'); hg.addColorStop(0.4,'#E8EEFF'); hg.addColorStop(1,'#C0C8FF');
  } else {
    hg.addColorStop(0,'#FFFDE7'); hg.addColorStop(0.4,'#FFE135'); hg.addColorStop(1,'#C08000');
  }
  _ctx.fillStyle = hg;
  _ctx.beginPath(); _ctx.arc(0, -sz*0.3, sz*0.36, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.shadowBlur = 0; _ctx.shadowOffsetX = 0; _ctx.shadowOffsetY = 0;

  // 小さな翼（エンジェルは大きな翼があるのでスキップ）
  if (!angel) {
    _ctx.fillStyle = '#F0BF00'; _ctx.strokeStyle = '#B8860B'; _ctx.lineWidth = 1.5;
    _ctx.beginPath(); _ctx.ellipse(-sz*0.52, sz*0.08, sz*0.18, sz*0.26, -0.4, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
    _ctx.beginPath(); _ctx.ellipse( sz*0.52, sz*0.08, sz*0.18, sz*0.26,  0.4, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  } else {
    // エンジェル: 小さな金色の肩飾り
    _ctx.fillStyle = '#FFD700'; _ctx.strokeStyle = '#CC8800'; _ctx.lineWidth = 1;
    _ctx.beginPath(); _ctx.ellipse(-sz*0.48, sz*0.06, sz*0.11, sz*0.16, -0.4, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
    _ctx.beginPath(); _ctx.ellipse( sz*0.48, sz*0.06, sz*0.11, sz*0.16,  0.4, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  }

  // 進化（エンジェル以外）: 肉垂
  if (evolved && !angel) {
    _ctx.fillStyle = '#E74C3C'; _ctx.strokeStyle = '#922B21'; _ctx.lineWidth = 1.5;
    _ctx.beginPath(); _ctx.arc(sz*0.12, -sz*0.1, sz*0.1, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  }

  _ctx.fillStyle = angel ? '#3344BB' : '#222';
  _ctx.beginPath(); _ctx.arc(-sz*0.12, -sz*0.33, sz*0.078, 0, Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( sz*0.12, -sz*0.33, sz*0.078, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = '#fff';
  _ctx.beginPath(); _ctx.arc(-sz*0.09, -sz*0.355, sz*0.034, 0, Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( sz*0.15, -sz*0.355, sz*0.034, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = 'rgba(255,255,255,0.9)';
  _ctx.beginPath(); _ctx.arc(-sz*0.07, -sz*0.375, sz*0.019, 0, Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( sz*0.17, -sz*0.375, sz*0.019, 0, Math.PI*2); _ctx.fill();

  _ctx.fillStyle = angel ? '#FFD700' : '#FF8C00'; _ctx.strokeStyle = angel ? '#CC8800' : '#CC5500'; _ctx.lineWidth = 1.5;
  _ctx.beginPath();
  _ctx.moveTo(-sz*0.1, -sz*0.22); _ctx.lineTo(sz*0.1, -sz*0.22); _ctx.lineTo(0, -sz*0.1); _ctx.closePath(); _ctx.fill(); _ctx.stroke();

  _ctx.strokeStyle = angel ? '#CC8800' : '#FF8C00'; _ctx.lineWidth = 2.5; _ctx.lineCap = 'round';
  [[-sz*0.18, sz*0.55],[sz*0.18, sz*0.55]].forEach(function(ft) {
    _ctx.beginPath(); _ctx.moveTo(ft[0], ft[1]); _ctx.lineTo(ft[0]-sz*0.12, ft[1]+sz*0.12); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(ft[0], ft[1]); _ctx.lineTo(ft[0]+sz*0.12, ft[1]+sz*0.12); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(ft[0], ft[1]); _ctx.lineTo(ft[0], ft[1]+sz*0.16); _ctx.stroke();
  });

  if (acc === 'glasses') {
    _ctx.strokeStyle = '#555'; _ctx.lineWidth = 2;
    _ctx.beginPath(); _ctx.arc(-sz*0.12, -sz*0.33, sz*0.14, 0, Math.PI*2); _ctx.stroke();
    _ctx.beginPath(); _ctx.arc( sz*0.12, -sz*0.33, sz*0.14, 0, Math.PI*2); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(-sz*0.02, -sz*0.33); _ctx.lineTo(sz*0.02, -sz*0.33); _ctx.stroke();
  } else if (acc === 'nurse') {
    rrect(-sz*0.3, -sz*0.72, sz*0.6, sz*0.28, 3, '#fff', '#ddd', 1.5);
    _ctx.fillStyle = '#FF6B6B';
    _ctx.fillRect(-sz*0.05, -sz*0.7,  sz*0.1,  sz*0.22);
    _ctx.fillRect(-sz*0.15, -sz*0.56, sz*0.3,  sz*0.08);
  } else if (acc === 'helmet') {
    _ctx.fillStyle = '#4ECDC4'; _ctx.strokeStyle = '#2E9E96'; _ctx.lineWidth = 2;
    _ctx.beginPath(); _ctx.arc(0, -sz*0.3, sz*0.4, Math.PI, 0); _ctx.fill(); _ctx.stroke();
    _ctx.fillStyle = '#2E9E96'; _ctx.fillRect(-sz*0.4, -sz*0.36, sz*0.8, sz*0.09);
  }
  _ctx.restore();
}

// ── Crow colors (全種類) ─────────────────────────────────────────────────────
var CROW_COLORS = {
  normal:    { wing:'#141414', body:'#282828', hi:'#424242', eye:'#FF1A1A', glow:'rgba(255,20,20,0.55)'   },
  fast:      { wing:'#001166', body:'#163388', hi:'#2850BB', eye:'#00EEFF', glow:'rgba(0,220,255,0.55)'   },
  ranged:    { wing:'#1A3A1A', body:'#1E6B1E', hi:'#3AAA3A', eye:'#FFCC00', glow:'rgba(255,210,0,0.58)'  },
  tank:      { wing:'#3A0000', body:'#7A0000', hi:'#BB1818', eye:'#FF5500', glow:'rgba(255,80,0,0.55)'    },
  ghost:     { wing:'#5A6A88', body:'#7A92AF', hi:'#A8C0D0', eye:'#88EEFF', glow:'rgba(100,210,255,0.55)' },
  healer:    { wing:'#7A1A4A', body:'#AA2060', hi:'#D85090', eye:'#FF88CC', glow:'rgba(255,120,200,0.58)' },
  bomber:    { wing:'#3A1800', body:'#8C3200', hi:'#CC5010', eye:'#FF8C00', glow:'rgba(255,110,0,0.60)'   },
  sprinter:  { wing:'#2A4400', body:'#548B00', hi:'#88CC00', eye:'#AAFF00', glow:'rgba(140,220,0,0.60)'   },
  armored:   { wing:'#2A2A3A', body:'#4A5060', hi:'#7A88A0', eye:'#AACCFF', glow:'rgba(140,180,255,0.50)' },
  regen:     { wing:'#003A14', body:'#006B28', hi:'#00AA40', eye:'#44FF88', glow:'rgba(40,220,100,0.58)'   },
  shielded:  { wing:'#0A1A3A', body:'#102866', hi:'#2050BB', eye:'#66AAFF', glow:'rgba(80,150,255,0.60)'  },
  splitter:  { wing:'#2A004A', body:'#550088', hi:'#8800CC', eye:'#CC44FF', glow:'rgba(180,60,255,0.60)'   },
  swarm:     { wing:'#3A0808', body:'#6A0C0C', hi:'#991414', eye:'#FF3333', glow:'rgba(220,40,40,0.50)'    },
  // 新型
  poison:    { wing:'#1A3A00', body:'#2A5A10', hi:'#55AA22', eye:'#AAFF44', glow:'rgba(140,255,60,0.65)'  },
  stealth:   { wing:'#1A1A2A', body:'#2A2A3A', hi:'#4A4A6A', eye:'#CCAAFF', glow:'rgba(180,140,255,0.60)' },
  berserker: { wing:'#4A0000', body:'#880000', hi:'#CC2222', eye:'#FF4400', glow:'rgba(255,60,0,0.70)'    },
  titan:     { wing:'#1A1A1A', body:'#333333', hi:'#555555', eye:'#FFAA00', glow:'rgba(255,160,0,0.65)'   },
  leech:     { wing:'#3A0020', body:'#660040', hi:'#AA0066', eye:'#FF44AA', glow:'rgba(255,60,160,0.60)'  },
  necro:     { wing:'#0A2A0A', body:'#103010', hi:'#228822', eye:'#88FF66', glow:'rgba(120,255,80,0.60)'  },
  phantom:   { wing:'#2A2A4A', body:'#3A3A6A', hi:'#6060AA', eye:'#FFFFFF', glow:'rgba(200,200,255,0.70)' },
};

/* ★2026-08-29: 敵とボスを「ネオンブロックの組み合わせ」で描く。
   ・ふつうの敵は**2〜3色の市松**にして、同じ形でも色で見分けが付くようにした
   ・ボスは**モザイク**（ブロックを並べて形を作る）。もとのボスのシルエットに寄せてある
     （鳥は翼、獣は角と四つ足、爬虫類は長い胴、機械は箱と脚、最終形態は大きく厚い）
   ・ボス固有の色（BOSS_CONFIG の col / eyeCol）を活かすので、20体それぞれ違う色になる */
var NEON_PALETTE = ['#41E3FF','#FF4FC3','#FFD54F','#7CFF4F','#B36BFF','#FF8A3D'];

// 種類ごとの「形」と「色の組み合わせ」。色は cells の文字に対応する
var NEON_SHAPES = {
  normal:   { cells:[[-1,-1,0],[0,-1,1],[-1,0,1],[0,0,0]],                    cols:['#41E3FF','#7CFF4F'] },
  fast:     { cells:[[-1,-1,0],[0,-1,1],[0,0,0]],                             cols:['#7CFF4F','#FFD54F'] },
  sprinter: { cells:[[-1,-1,0],[0,-1,1],[0,0,0]],                             cols:['#AAFF00','#41E3FF'] },
  tank:     { cells:[[-1,-1,0],[0,-1,1],[1,-1,0],[-1,0,1],[0,0,0],[1,0,1]],   cols:['#FF4FC3','#B36BFF'] },
  ghost:    { cells:[[-1,-1,0],[0,-1,0],[-1,0,1],[0,0,1]],                    cols:['#B36BFF','#8EF9FF'] },
  stealth:  { cells:[[-1,-1,0],[0,-1,1],[-1,0,1],[0,0,0]],                    cols:['#8EF9FF','#41E3FF'] },
  phantom:  { cells:[[-1,-1,0],[0,-1,1],[-1,0,1],[0,0,0]],                    cols:['#C56BFF','#FF4FC3'] },
  shield:   { cells:[[-1,-1,0],[0,-1,0],[1,-1,0],[0,0,1]],                    cols:['#FFD54F','#FF8A3D'] },
  bomber:   { cells:[[-1,-1,0],[0,-1,1],[-1,0,1],[0,0,0]],                    cols:['#FF8A3D','#FFD54F'] }
};
var NEON_ENEMY = NEON_SHAPES;   // 旧コードとの互換（存在判定に使っている）

// ブロック1個。中は暗く、輪郭が光る（ネオンブロックス本編と同じ描き方）
function _neonCell(x, y, u, col) {
  _ctx.fillStyle = 'rgba(10,8,26,0.85)';
  _ctx.fillRect(x, y, u, u);
  _ctx.shadowColor = col; _ctx.shadowBlur = Math.max(8, u * 0.9);
  _ctx.strokeStyle = col; _ctx.lineWidth = Math.max(1.6, u * 0.14);
  _ctx.strokeRect(x + u*0.09, y + u*0.09, u*0.82, u*0.82);
  _ctx.shadowBlur = 0;
  _ctx.strokeStyle = 'rgba(255,255,255,0.5)'; _ctx.lineWidth = Math.max(0.8, u * 0.06);
  _ctx.strokeRect(x + u*0.24, y + u*0.24, u*0.52, u*0.52);
}

function drawNeonBlock(e) {
  var s = e.size;
  var sh = NEON_SHAPES[e.type] || NEON_SHAPES.normal;
  var al = (e.hitFlash > 0 && e.hitFlash % 2 === 0) ? 0.35 : 1.0;
  if (!e.silhouette) {
    if (e.type === 'ghost') al *= (0.25 + Math.abs(Math.sin(e.wobble * 0.30)) * 0.75);
    if (e.type === 'stealth' && e.isHidden) al *= 0.08;
    if (e.type === 'phantom') al *= (0.55 + Math.abs(Math.sin(e.wobble * 0.4)) * 0.45);
  }
  var cols = e.silhouette ? ['#2E3659','#2E3659'] : sh.cols;

  _ctx.save();
  _ctx.translate(e.x, e.y + Math.sin(e.wobble) * 4);
  _ctx.rotate(Math.sin(e.wobble * 0.5) * 0.10);
  _ctx.globalAlpha = al;
  _ctx.globalAlpha = al * 0.30; _ctx.fillStyle = 'rgba(0,0,0,0.55)';
  _ctx.beginPath(); _ctx.ellipse(0, s * 0.95, s * 0.42, s * 0.10, 0, 0, Math.PI * 2); _ctx.fill();
  _ctx.globalAlpha = al;

  var u = s * 0.42;
  _ctx.lineJoin = 'round';
  for (var i = 0; i < sh.cells.length; i++) {
    var c = sh.cells[i];
    _neonCell(c[0] * u, c[1] * u, u, cols[c[2]] || cols[0]);
  }
  // 目（「的」だと分かるように）
  var ey = -u * 0.50;
  _ctx.shadowColor = cols[0]; _ctx.shadowBlur = 10; _ctx.fillStyle = '#FFFFFF';
  _ctx.beginPath(); _ctx.arc(-u * 0.38, ey, u * 0.22, 0, Math.PI * 2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( u * 0.38, ey, u * 0.22, 0, Math.PI * 2); _ctx.fill();
  _ctx.shadowBlur = 0; _ctx.fillStyle = '#0A081A';
  _ctx.beginPath(); _ctx.arc(-u * 0.38, ey, u * 0.10, 0, Math.PI * 2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( u * 0.38, ey, u * 0.10, 0, Math.PI * 2); _ctx.fill();
  _ctx.restore();
}

/* ボスのモザイク。B=本体色 A=差し色 E=目。もとのボスの形に寄せてある */
var NEON_BOSS = {
  bird: ['A.........A',
         'AB.......BA',
         'ABB..B..BBA',
         '.BBBBBBBBB.',
         '..B.EBE.B..',
         '....BBB....'],
  beast:['.A.....A.',
         '.ABBBBBA.',
         '.BBEBEBB.',
         '.BBBBBBB.',
         '.B.B.B.B.',
         '.B.....B.'],
  reptile:['.....BBB.',
           '....BEBEB',
           '...BBBBB.',
           '..BBB....',
           '.BBB.....',
           'ABB......'],
  mech: ['.A.....A.',
         '.BBBBBBB.',
         '.BEB.BEB.',
         '.BBBBBBB.',
         'A.BBBBB.A',
         '..B...B..',
         '..B...B..'],
  final:['..A.....A..',
         '.ABBBBBBBA.',
         '.BBEBBBEBB.',
         '.BBBBBBBBB.',
         'A.BBBBBBB.A',
         '..B.BBB.B..',
         '..B..B..B..',
         '.....B.....'],
  ufo:  ['...BBB...',
         '..BEBEB..',
         '.BBBBBBB.',
         'ABBBBBBBA',
         '..A...A..']
};

// ボス固有の色は暗いものが多い（#000011 など）。そのままだと光らないので明るく起こす
function _neonize(hex, boost) {
  var m = /^#([0-9a-f]{6})$/i.exec(hex || '');
  if (!m) return '#41E3FF';
  var n = parseInt(m[1], 16), r = (n>>16)&255, g = (n>>8)&255, b = n&255;
  var mx = Math.max(r,g,b) || 1, k = (boost || 210) / mx;
  r = Math.min(255, Math.round(r*k + 40));
  g = Math.min(255, Math.round(g*k + 40));
  b = Math.min(255, Math.round(b*k + 40));
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}

function drawNeonBoss(e, frame, cfg, kind) {
  var map = NEON_BOSS[kind] || NEON_BOSS.ufo;
  var rows = map.length, colsN = map[0].length;
  var u = (e.size * 2.1) / colsN;                 // 元のボスと同じくらいの見た目の大きさに
  var body   = _neonize(cfg && cfg.col, 200);
  var accent = NEON_PALETTE[(e._stageNum || 1) % NEON_PALETTE.length];
  var eye    = _neonize(cfg && cfg.eyeCol, 245);
  var al = (e.hitFlash > 0 && e.hitFlash % 2 === 0) ? 0.3 : 1.0;

  _ctx.save();
  _ctx.translate(e.x, e.y);
  _ctx.globalAlpha = al;
  if (typeof _drawBossAuraPhase === 'function' && cfg) _drawBossAuraPhase(e, frame, cfg.aura);
  var bob = Math.sin(frame * 0.06) * u * 0.18;    // ゆっくり上下（生きている感じ）
  _ctx.translate(-(colsN * u) / 2, -(rows * u) / 2 + bob);
  _ctx.lineJoin = 'round';
  for (var y = 0; y < rows; y++) {
    for (var x = 0; x < colsN; x++) {
      var ch = map[y][x];
      if (ch === '.') continue;
      _neonCell(x * u, y * u, u, ch === 'B' ? body : (ch === 'A' ? accent : eye));
    }
  }
  _ctx.restore();
}

function drawCrow(e) {
  if (typeof NEON_ENEMY !== 'undefined') { drawNeonBlock(e); return; }   // ★ネオン版はこちら
  _ctx.save();
  _ctx.translate(e.x, e.y + Math.sin(e.wobble) * 4);
  var s = e.size;
  var c = CROW_COLORS[e.type] || CROW_COLORS.normal;
  // 図鑑の未発見枠は影絵で見せる（何が居るのか形だけ分かる＝集めたくなる）
  if (e.silhouette) c = { wing:'#161B30', body:'#212844', hi:'#2E3659', eye:'#3C4472', glow:'rgba(0,0,0,0)' };
  var al = (e.hitFlash > 0 && e.hitFlash % 2 === 0) ? 0.25 : 1.0;

  // 透明化する種類。図鑑の影絵では適用しない（消えていると集める対象に見えない）
  if (!e.silhouette) {
    // ゴースト：透明パルス
    if (e.type === 'ghost') al *= (0.20 + Math.abs(Math.sin(e.wobble * 0.30)) * 0.80);
    // ステルス：完全透明
    if (e.type === 'stealth' && e.isHidden) al *= 0.06;
    // ファントム：幽霊的な透明感
    if (e.type === 'phantom') al *= (0.55 + Math.abs(Math.sin(e.wobble * 0.4)) * 0.45);
  }

  _ctx.globalAlpha = al;
  // 影
  _ctx.globalAlpha = al * 0.38;
  _ctx.fillStyle = 'rgba(0,0,0,0.55)';
  _ctx.beginPath(); _ctx.ellipse(0, s*0.9, s*0.46, s*0.1, 0, 0, Math.PI*2); _ctx.fill();
  _ctx.globalAlpha = al;

  // 種類ごとの演出（オーラ・シールド・炎など）。
  // 図鑑の未発見枠（影絵）では出さない。出すと未発見なのに種類が分かってしまう。
  if (!e.silhouette) {
  // スプリンター：ダッシュ中速度線
  if (e.type === 'sprinter' && e.sprintPhase === 1) {
    _ctx.globalAlpha = al*0.55; _ctx.strokeStyle = '#AAFF00'; _ctx.lineWidth = 2;
    for (var sl = 0; sl < 3; sl++) {
      _ctx.shadowColor = '#88FF00'; _ctx.shadowBlur = 6;
      _ctx.beginPath(); _ctx.moveTo((sl-1)*12, -s*0.4); _ctx.lineTo((sl-1)*12, s*1.2); _ctx.stroke();
    }
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // 装甲：金属オーバーレイ
  if (e.type === 'armored') {
    _ctx.globalAlpha = al*0.35; _ctx.strokeStyle = '#AACCFF'; _ctx.lineWidth = 2.5;
    _ctx.shadowColor = '#8899BB'; _ctx.shadowBlur = 8;
    _ctx.beginPath(); _ctx.ellipse(0, 0, s*0.52, s*0.46, 0, 0, Math.PI*2); _ctx.stroke();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // リジェネ：回復パルス
  if (e.type === 'regen' && e.regenTimer > 55) {
    var rr = (e.regenTimer-55)/30;
    _ctx.globalAlpha = al*rr*0.35; _ctx.shadowColor = '#44FF88'; _ctx.shadowBlur = 14;
    _ctx.fillStyle = '#44FF88'; _ctx.beginPath(); _ctx.arc(0, 0, s*0.80, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // シールド
  if (e.type === 'shielded' && e.shield > 0) {
    var sr = e.shield/e.maxShield;
    _ctx.globalAlpha = al*(0.15+sr*0.25); _ctx.shadowColor = '#66AAFF'; _ctx.shadowBlur = 16;
    _ctx.fillStyle = '#2266CC'; _ctx.beginPath(); _ctx.arc(0, 0, s*0.95, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al*(0.35+sr*0.25); _ctx.strokeStyle = '#88CCFF'; _ctx.lineWidth = 2.5;
    _ctx.beginPath(); _ctx.arc(0, 0, s*0.95, 0, Math.PI*2); _ctx.stroke(); _ctx.globalAlpha = al;
  }
  // 分裂：紫のクラック
  if (e.type === 'splitter') {
    _ctx.globalAlpha = al*0.5; _ctx.strokeStyle = '#CC44FF'; _ctx.lineWidth = 1.5;
    _ctx.shadowColor = '#AA00FF'; _ctx.shadowBlur = 8;
    _ctx.beginPath(); _ctx.moveTo(-s*0.3,-s*0.4); _ctx.lineTo(0,0); _ctx.lineTo(s*0.3,-s*0.4); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(-s*0.2,s*0.3); _ctx.lineTo(0,0); _ctx.lineTo(s*0.2,s*0.3); _ctx.stroke();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // ヒーラー：回復オーラ
  if (e.type === 'healer' && e.healTimer > 55) {
    var hr = Math.min(1,(e.healTimer-55)/40);
    _ctx.globalAlpha = al*hr*0.42; _ctx.shadowColor = '#FF88CC'; _ctx.shadowBlur = 22;
    _ctx.fillStyle = '#FF88CC'; _ctx.beginPath(); _ctx.arc(0, 0, s*0.88, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // ボンバー：ヒューズ光
  if (e.type === 'bomber' && e.y > 180) {
    var fuse = Math.min(1,(e.y-180)/(_H-320));
    var fuseFlash = Math.abs(Math.sin(e.wobble*(1.2+fuse*3.5)));
    _ctx.globalAlpha = al*fuse*fuseFlash*0.55; _ctx.shadowColor = '#FF5500'; _ctx.shadowBlur = 26;
    _ctx.fillStyle = '#FF7700'; _ctx.beginPath(); _ctx.arc(0, 0, s*0.94, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // 遠距離：チャージオーラ
  if (e.type === 'ranged' && e.rangedTimer > 35) {
    var cr = Math.min(1,(e.rangedTimer-35)/45);
    _ctx.globalAlpha = al*cr*0.55; _ctx.shadowColor = '#FFCC00'; _ctx.shadowBlur = 20;
    _ctx.fillStyle = '#FFE040'; _ctx.beginPath(); _ctx.arc(0, 0, s*0.78, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // 毒型：緑バブル
  if (e.type === 'poison') {
    var pb = Math.abs(Math.sin(e.wobble * 1.2)) * 0.4;
    _ctx.globalAlpha = al * (0.15 + pb * 0.3); _ctx.shadowColor = '#88FF44'; _ctx.shadowBlur = 12;
    _ctx.fillStyle = '#66EE22'; _ctx.beginPath(); _ctx.arc(0, -s*0.1, s*0.85, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // バーサーカー：エンレイジ時赤炎
  if (e.type === 'berserker' && e.enraged) {
    var rage = Math.abs(Math.sin(e.wobble * 2.0));
    _ctx.globalAlpha = al * (0.3 + rage * 0.35); _ctx.shadowColor = '#FF2200'; _ctx.shadowBlur = 22;
    _ctx.fillStyle = '#FF4400'; _ctx.beginPath(); _ctx.arc(0, 0, s * 1.05, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // タイタン：金属アーマーオーバーレイ
  if (e.type === 'titan') {
    _ctx.globalAlpha = al * 0.4; _ctx.strokeStyle = '#AAAAAA'; _ctx.lineWidth = 4;
    _ctx.shadowColor = '#888888'; _ctx.shadowBlur = 10;
    _ctx.beginPath(); _ctx.ellipse(0, 0, s*0.55, s*0.50, 0, 0, Math.PI*2); _ctx.stroke();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }
  // ネクロ：死亡待機時の幽霊エフェクト
  if (e.type === 'necro' && !e.necroRevived) {
    _ctx.globalAlpha = al * 0.28; _ctx.shadowColor = '#88FF66'; _ctx.shadowBlur = 16;
    _ctx.fillStyle = '#44AA44'; _ctx.beginPath(); _ctx.arc(0, 0, s*0.82, 0, Math.PI*2); _ctx.fill();
    _ctx.shadowBlur = 0; _ctx.globalAlpha = al;
  }

  } // /種類ごとの演出

  // ── 輪郭光 ───────────────────────────────────────────────────────────────
  // 敵はほとんどが暗色なので、空に溶けて見えなくなっていた（2026-08-28 実測）。
  // 月あかりが当たっている想定の淡い光を体の後ろに敷き、どの空の色でも輪郭が立つようにする。
  // ステルスが隠れている間は光らせない（隠れる意味が消えるため）。
  if (!(e.type === 'stealth' && e.isHidden) && !e.silhouette) {
    _ctx.save();
    _ctx.globalAlpha = al * 0.5;
    _ctx.shadowColor = 'rgba(255,248,225,0.95)'; _ctx.shadowBlur = s*0.55;
    _ctx.fillStyle   = 'rgba(255,248,225,0.30)';
    _ctx.beginPath(); _ctx.ellipse(0, 0, s*0.60, s*0.50, 0, 0, Math.PI*2); _ctx.fill();
    _ctx.restore();
  }

  // ── 共通ボディ描画 ───────────────────────────────────────────────────────
  _ctx.fillStyle = c.wing; _ctx.strokeStyle = 'rgba(0,0,0,0.6)'; _ctx.lineWidth = 1.5;
  _ctx.beginPath();
  _ctx.moveTo(-s*0.1, -s*0.05);
  _ctx.quadraticCurveTo(-s*0.85, -s*0.45, -s*0.65, s*0.25);
  _ctx.quadraticCurveTo(-s*0.35, s*0.1, -s*0.1, s*0.05);
  _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath();
  _ctx.moveTo(s*0.1, -s*0.05);
  _ctx.quadraticCurveTo(s*0.85, -s*0.45, s*0.65, s*0.25);
  _ctx.quadraticCurveTo(s*0.35, s*0.1, s*0.1, s*0.05);
  _ctx.closePath(); _ctx.fill(); _ctx.stroke();

  var bG = _ctx.createRadialGradient(-s*0.14, -s*0.08, s*0.04, 0, 0, s*0.5);
  bG.addColorStop(0, c.hi); bG.addColorStop(1, c.body);
  _ctx.fillStyle = bG; _ctx.strokeStyle = 'rgba(0,0,0,0.7)'; _ctx.lineWidth = 1.5;
  _ctx.beginPath(); _ctx.ellipse(0, 0, s*0.45, s*0.4, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  var hG = _ctx.createRadialGradient(s*0.14, -s*0.35, s*0.04, s*0.28, -s*0.28, s*0.3);
  hG.addColorStop(0, c.hi); hG.addColorStop(1, c.body);
  _ctx.fillStyle = hG;
  _ctx.beginPath(); _ctx.arc(s*0.28, -s*0.28, s*0.28, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  _ctx.fillStyle = '#555';
  _ctx.beginPath(); _ctx.moveTo(s*0.5,-s*0.22); _ctx.lineTo(s*0.82,-s*0.16); _ctx.lineTo(s*0.5,-s*0.08); _ctx.closePath(); _ctx.fill();

  _ctx.shadowColor = c.glow; _ctx.shadowBlur = s*0.45;
  _ctx.fillStyle = c.eye;
  _ctx.beginPath(); _ctx.arc(s*0.33, -s*0.3, s*0.09, 0, Math.PI*2); _ctx.fill();
  _ctx.shadowBlur = 0;
  _ctx.fillStyle = '#000'; _ctx.beginPath(); _ctx.arc(s*0.35, -s*0.3, s*0.05, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = 'rgba(255,255,255,0.85)'; _ctx.beginPath(); _ctx.arc(s*0.37, -s*0.32, s*0.025, 0, Math.PI*2); _ctx.fill();

  // タイタン：追加の鎧プレート（影絵では出さない）
  if (e.type === 'titan' && !e.silhouette) {
    _ctx.fillStyle = 'rgba(150,150,160,0.45)'; _ctx.strokeStyle = '#888'; _ctx.lineWidth = 1.5;
    _ctx.beginPath(); _ctx.rect(-s*0.35, -s*0.28, s*0.7, s*0.5); _ctx.fill(); _ctx.stroke();
    _ctx.fillStyle = 'rgba(200,200,210,0.25)';
    _ctx.beginPath(); _ctx.moveTo(-s*0.35,-s*0.28); _ctx.lineTo(s*0.35,-s*0.28); _ctx.lineTo(s*0.35,-s*0.14); _ctx.lineTo(-s*0.35,-s*0.14); _ctx.closePath(); _ctx.fill();
  }

  // HPバー（重要度高い敵のみ）
  var showHp = (e.type === 'tank' || e.type === 'healer' || e.type === 'bomber' ||
    e.type === 'splitter' || e.type === 'regen' || e.type === 'shielded' ||
    e.type === 'titan' || e.type === 'leech' || e.type === 'necro' || e.maxHp > 14);
  if (showHp && !e.noHpBar) {
    var bw = s*1.6, bx = -bw/2, by = s*0.65;
    rrect(bx-1, by-1, bw+2, 12, 4, 'rgba(0,0,0,0.75)', null);
    var ratio2 = e.hp/e.maxHp;
    var hc = ratio2 > 0.5 ? '#2ECC71' : ratio2 > 0.25 ? '#F39C12' : '#E74C3C';
    rrect(bx, by, bw*ratio2, 10, 3, hc, null);
    // ネクロ復活時は緑バー表示
    if (e.type === 'necro' && e.necroRevived) {
      _ctx.fillStyle = '#88FF66'; _ctx.font = 'bold 7px sans-serif'; _ctx.textAlign = 'center';
      _ctx.fillText('復活！', 0, by-2);
    }
  }
  // シールドバー
  if (e.type === 'shielded' && e.shield > 0) {
    var sbw = s*1.6, sbx = -sbw/2, sby = s*0.80;
    rrect(sbx, sby, sbw*(e.shield/e.maxShield), 6, 3, '#66AAFF', null);
  }

  _ctx.globalAlpha = 1; _ctx.restore();
}

// ── Boss UFO ─────────────────────────────────────────────────────────────────
function drawBoss(e, frame) {
  // ★ネオン版: ボスもブロックのモザイクで描く（形は元のシルエットに寄せてある）
  if (typeof NEON_BOSS !== 'undefined') {
    var ncfg = (typeof BOSS_CONFIG !== 'undefined' && e._stageNum) ? BOSS_CONFIG[e._stageNum] : null;
    var kind = ncfg ? ncfg.arch : (e.type === 'boss_snake' ? 'reptile'
                    : e.type === 'boss_chicken' ? 'bird' : 'ufo');
    drawNeonBoss(e, frame, ncfg, kind);
    return;
  }
  if (e.type === 'boss_chicken') { drawBossChicken(e, frame); return; }
  if (e.type === 'boss_snake')   { drawBossSnake(e, frame);   return; }
  if (e.type.startsWith('boss_s')) {
    var cfg = typeof BOSS_CONFIG !== 'undefined' ? BOSS_CONFIG[e._stageNum] : null;
    if (cfg) {
      switch (cfg.arch) {
        case 'bird':    drawBossArchBird(e, frame, cfg);    return;
        case 'beast':   drawBossArchBeast(e, frame, cfg);   return;
        case 'reptile': drawBossArchReptile(e, frame, cfg); return;
        case 'mech':    drawBossArchMech(e, frame, cfg);    return;
        case 'final':   drawBossArchFinal(e, frame, cfg);   return;
      }
    }
  }
  // UFOボス (既存)
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s = e.size;
  var al = (e.hitFlash > 0 && e.hitFlash % 2 === 0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;

  if (e.bossTimer > 92) {
    var wa = (e.bossTimer-92)/20;
    _ctx.globalAlpha = al*wa*0.55;
    var bG2 = _ctx.createLinearGradient(0, s*0.4, 0, _H-e.y);
    bG2.addColorStop(0,'rgba(200,80,255,0.95)'); bG2.addColorStop(1,'rgba(155,89,182,0)');
    _ctx.fillStyle = bG2;
    _ctx.beginPath(); _ctx.moveTo(-32,s*0.4); _ctx.lineTo(32,s*0.4); _ctx.lineTo(100,_H-e.y); _ctx.lineTo(-100,_H-e.y); _ctx.closePath(); _ctx.fill();
    _ctx.globalAlpha = al;
  }

  var phase = e.phase||1;
  var auraBase = phase===3?'rgba(255,60,60,':'rgba(175,75,255,';
  var pa = (0.07+Math.sin(frame*(0.05+phase*0.02))*0.04)*al*(1+(phase-1)*0.5);
  var aG = _ctx.createRadialGradient(0,0,s*0.3,0,0,s*(1.4+(phase-1)*0.2));
  aG.addColorStop(0,auraBase+pa+')'); aG.addColorStop(1,auraBase+'0)');
  _ctx.fillStyle = aG; _ctx.beginPath(); _ctx.arc(0,0,s*1.6,0,Math.PI*2); _ctx.fill();
  if (phase >= 2) {
    _ctx.globalAlpha = al*(0.12+Math.sin(frame*0.12)*0.08);
    _ctx.strokeStyle = phase===3?'#FF4444':'#FF8800'; _ctx.lineWidth = phase===3?4:2.5;
    _ctx.beginPath(); _ctx.arc(0,0,s*1.6,0,Math.PI*2); _ctx.stroke(); _ctx.globalAlpha = al;
  }

  _ctx.shadowColor = '#AA55FF'; _ctx.shadowBlur = 20;
  var dG = _ctx.createRadialGradient(0,s*0.0,s*0.1,0,s*0.1,s*1.0);
  dG.addColorStop(0,'#8868C8'); dG.addColorStop(0.5,'#504070'); dG.addColorStop(1,'#281840');
  _ctx.fillStyle = dG; _ctx.strokeStyle = '#CC88FF'; _ctx.lineWidth = 2.5;
  _ctx.beginPath(); _ctx.ellipse(0,s*0.1,s*0.95,s*0.24,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.shadowBlur = 0;
  _ctx.fillStyle = 'rgba(200,160,255,0.18)';
  _ctx.beginPath(); _ctx.ellipse(0,s*0.02,s*0.65,s*0.11,0,0,Math.PI*2); _ctx.fill();

  _ctx.shadowColor = '#DD88FF'; _ctx.shadowBlur = 18;
  var dmG = _ctx.createRadialGradient(-s*0.18,-s*0.28,s*0.04,0,-s*0.1,s*0.55);
  dmG.addColorStop(0,'rgba(230,170,255,0.82)'); dmG.addColorStop(0.6,'rgba(160,80,240,0.50)'); dmG.addColorStop(1,'rgba(100,40,180,0.22)');
  _ctx.fillStyle = dmG; _ctx.strokeStyle = '#EE99FF'; _ctx.lineWidth = 2;
  _ctx.beginPath(); _ctx.ellipse(0,-s*0.05,s*0.5,s*0.5,0,Math.PI,0); _ctx.fill(); _ctx.stroke();
  _ctx.shadowBlur = 0;

  ['#FF3333','#33FF66','#CC44FF','#FFFF33','#FF33FF'].forEach(function(col,i) {
    var a2 = (frame*0.06)+i*(Math.PI*2/5);
    _ctx.shadowColor=col; _ctx.shadowBlur=10; _ctx.fillStyle=col;
    _ctx.beginPath(); _ctx.arc(Math.cos(a2)*s*0.62,s*0.08+Math.sin(a2)*s*0.12,5.5,0,Math.PI*2); _ctx.fill();
  });
  _ctx.shadowBlur = 0;
  _ctx.fillStyle='#111'; _ctx.strokeStyle='#000'; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,-s*0.62,s*0.22,s*0.18,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath(); _ctx.arc(s*0.15,-s*0.82,s*0.16,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.shadowColor='#FF44FF'; _ctx.shadowBlur=8; _ctx.fillStyle='#FF00FF';
  _ctx.beginPath(); _ctx.arc(s*0.2,-s*0.83,4.5,0,Math.PI*2); _ctx.fill(); _ctx.shadowBlur=0;
  _ctx.fillStyle='#000'; _ctx.beginPath(); _ctx.arc(s*0.21,-s*0.83,2.5,0,Math.PI*2); _ctx.fill();
  _ctx.fillStyle='#444'; _ctx.beginPath(); _ctx.moveTo(s*0.28,-s*0.78); _ctx.lineTo(s*0.45,-s*0.75); _ctx.lineTo(s*0.28,-s*0.7); _ctx.closePath(); _ctx.fill();

  _drawBossHpBar(e, s, 'BOSS UFO', '#EE99FF', '#E066FF', '#7B00CC', '#7733AA');
  _ctx.globalAlpha=1; _ctx.restore();
}

// ── Boss Chicken（ニワトリ大魔王） ───────────────────────────────────────────
function drawBossChicken(e, frame) {
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash > 0 && e.hitFlash % 2 === 0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;

  var phase = e.phase || 1;
  // 怒りオーラ
  var auraCol = phase===3 ? 'rgba(255,80,0,' : phase===2 ? 'rgba(255,160,0,' : 'rgba(255,220,80,';
  var pa2 = (0.06 + Math.sin(frame*0.06)*0.04)*al*(1+(phase-1)*0.6);
  var aG2 = _ctx.createRadialGradient(0,0,s*0.3,0,0,s*1.5);
  aG2.addColorStop(0,auraCol+pa2+')'); aG2.addColorStop(1,auraCol+'0)');
  _ctx.fillStyle=aG2; _ctx.beginPath(); _ctx.arc(0,0,s*1.6,0,Math.PI*2); _ctx.fill();
  if (phase>=2) {
    _ctx.globalAlpha=al*(0.14+Math.sin(frame*0.1)*0.08);
    _ctx.strokeStyle=phase===3?'#FF4400':'#FF8800'; _ctx.lineWidth=phase===3?5:3;
    _ctx.beginPath(); _ctx.arc(0,0,s*1.4,0,Math.PI*2); _ctx.stroke(); _ctx.globalAlpha=al;
  }

  // 尾羽（後ろ）
  _ctx.fillStyle='#8B4513';
  for (var fi=0;fi<5;fi++) {
    var fa = -0.5 + fi*0.25;
    _ctx.beginPath(); _ctx.moveTo(0,s*0.1);
    _ctx.quadraticCurveTo(Math.sin(fa)*s*1.0, s*0.5, Math.sin(fa)*s*1.3, s*0.2+Math.cos(fa)*s*0.8);
    _ctx.lineWidth=8-(fi%3)*2; _ctx.strokeStyle=['#8B4513','#D2691E','#FF8C00','#CC6600','#994400'][fi];
    _ctx.stroke();
  }
  // 胴体
  var bodyG = _ctx.createRadialGradient(-s*0.1,-s*0.1,s*0.05,0,0,s*0.6);
  bodyG.addColorStop(0,'#FF8C00'); bodyG.addColorStop(0.5,'#CC5500'); bodyG.addColorStop(1,'#882200');
  _ctx.fillStyle=bodyG; _ctx.strokeStyle='rgba(0,0,0,0.6)'; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,s*0.1,s*0.52,s*0.48,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 頭
  var headG = _ctx.createRadialGradient(-s*0.06,-s*0.35,s*0.02,0,-s*0.28,s*0.38);
  headG.addColorStop(0,'#FFA030'); headG.addColorStop(1,'#AA4400');
  _ctx.fillStyle=headG; _ctx.beginPath(); _ctx.arc(0,-s*0.28,s*0.36,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 冠（トサカ）
  _ctx.fillStyle='#FF2222'; _ctx.strokeStyle='#AA0000'; _ctx.lineWidth=1.5;
  for (var ci=0;ci<4;ci++) {
    var cx2 = (ci-1.5)*s*0.14;
    _ctx.beginPath(); _ctx.ellipse(cx2,-s*0.66-Math.abs(ci-1.5)*s*0.08,s*0.08,s*0.18,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  }
  // くちばし
  _ctx.fillStyle='#FFCC00'; _ctx.strokeStyle='#AA8800'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.moveTo(-s*0.12,-s*0.22); _ctx.lineTo(s*0.12,-s*0.22); _ctx.lineTo(0,-s*0.08); _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  // 目（怒り目）
  _ctx.fillStyle='#FF2200'; _ctx.shadowColor='#FF0000'; _ctx.shadowBlur=s*0.3;
  _ctx.beginPath(); _ctx.arc(-s*0.13,-s*0.3,s*0.09,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( s*0.13,-s*0.3,s*0.09,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.fillStyle='#000';
  _ctx.beginPath(); _ctx.arc(-s*0.13,-s*0.3,s*0.05,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( s*0.13,-s*0.3,s*0.05,0,Math.PI*2); _ctx.fill();
  // 翼
  _ctx.fillStyle='#AA4400'; _ctx.strokeStyle='rgba(0,0,0,0.5)'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.moveTo(-s*0.08,-s*0.05); _ctx.quadraticCurveTo(-s*0.9,-s*0.4,-s*0.7,s*0.3); _ctx.quadraticCurveTo(-s*0.35,s*0.1,-s*0.08,s*0.05); _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath(); _ctx.moveTo( s*0.08,-s*0.05); _ctx.quadraticCurveTo( s*0.9,-s*0.4, s*0.7,s*0.3); _ctx.quadraticCurveTo( s*0.35,s*0.1, s*0.08,s*0.05); _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  // 肉垂（あごの赤いやつ）
  _ctx.fillStyle='#FF3333'; _ctx.strokeStyle='#CC0000'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.ellipse(0,-s*0.08,s*0.09,s*0.14,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();

  _drawBossHpBar(e, s, 'ニワトリ大魔王', '#FFCC66', '#FF8800', '#CC4400', '#884400');
  _ctx.globalAlpha=1; _ctx.restore();
}

// ── Boss Snake（巨大ヘビ） ────────────────────────────────────────────────────
function drawBossSnake(e, frame) {
  // 潜伏中は非表示
  if (e.isBurrowed) return;
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash > 0 && e.hitFlash % 2 === 0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;
  var phase = e.phase || 1;

  // オーラ
  var snakeAura = phase===3 ? 'rgba(80,220,80,' : 'rgba(50,180,50,';
  var spa = (0.06+Math.sin(frame*0.05)*0.04)*al;
  var sG = _ctx.createRadialGradient(0,0,s*0.3,0,0,s*1.5);
  sG.addColorStop(0,snakeAura+(spa)+')'); sG.addColorStop(1,snakeAura+'0)');
  _ctx.fillStyle=sG; _ctx.beginPath(); _ctx.arc(0,0,s*1.6,0,Math.PI*2); _ctx.fill();

  // 尻尾セグメント（後ろに描く）
  _ctx.strokeStyle='#2A6A2A'; _ctx.lineWidth=s*0.55;
  _ctx.lineCap='round';
  _ctx.beginPath();
  _ctx.moveTo(0,s*0.3);
  _ctx.quadraticCurveTo(-s*0.8,s*0.8,-s*0.5,s*1.4);
  _ctx.quadraticCurveTo(s*0.3,s*1.8,s*0.6,s*1.2);
  _ctx.stroke();
  _ctx.strokeStyle='#3A8A3A'; _ctx.lineWidth=s*0.35;
  _ctx.beginPath();
  _ctx.moveTo(0,s*0.3);
  _ctx.quadraticCurveTo(-s*0.8,s*0.8,-s*0.5,s*1.4);
  _ctx.quadraticCurveTo(s*0.3,s*1.8,s*0.6,s*1.2);
  _ctx.stroke();

  // 胴体（楕円）
  var snakeBodyG = _ctx.createRadialGradient(-s*0.12,-s*0.1,s*0.05,0,0,s*0.58);
  snakeBodyG.addColorStop(0,'#55AA44'); snakeBodyG.addColorStop(0.6,'#336622'); snakeBodyG.addColorStop(1,'#1A3A10');
  _ctx.fillStyle=snakeBodyG; _ctx.strokeStyle='rgba(0,0,0,0.6)'; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,s*0.08,s*0.52,s*0.44,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 鱗模様
  _ctx.strokeStyle='rgba(80,180,60,0.35)'; _ctx.lineWidth=1.5;
  for (var sci=0;sci<3;sci++) {
    _ctx.beginPath(); _ctx.arc(0,s*0.08,s*(0.22+sci*0.12),0,Math.PI*2); _ctx.stroke();
  }

  // 頭
  var snakeHeadG = _ctx.createRadialGradient(-s*0.08,-s*0.36,s*0.02,0,-s*0.3,s*0.40);
  snakeHeadG.addColorStop(0,'#66CC44'); snakeHeadG.addColorStop(1,'#224A18');
  _ctx.fillStyle=snakeHeadG; _ctx.strokeStyle='rgba(0,0,0,0.6)'; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,-s*0.3,s*0.42,s*0.32,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();

  // 目（縦長の瞳）
  _ctx.fillStyle='#FFEE00'; _ctx.shadowColor='#88FF44'; _ctx.shadowBlur=s*0.3;
  _ctx.beginPath(); _ctx.ellipse(-s*0.16,-s*0.33,s*0.1,s*0.12,0,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.ellipse( s*0.16,-s*0.33,s*0.1,s*0.12,0,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.fillStyle='#000';
  _ctx.beginPath(); _ctx.ellipse(-s*0.16,-s*0.33,s*0.04,s*0.10,0,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.ellipse( s*0.16,-s*0.33,s*0.04,s*0.10,0,0,Math.PI*2); _ctx.fill();

  // 舌
  _ctx.strokeStyle='#FF4444'; _ctx.lineWidth=3; _ctx.lineCap='round';
  _ctx.beginPath();
  _ctx.moveTo(-s*0.04,-s*0.01); _ctx.lineTo(0,-s*0.14);
  _ctx.moveTo(0,-s*0.14); _ctx.lineTo(-s*0.07,-s*0.24);
  _ctx.moveTo(0,-s*0.14); _ctx.lineTo( s*0.07,-s*0.24);
  _ctx.stroke();

  // 毒エフェクト（スプレータイマー）
  if (e.sprayTimer > 40) {
    var pt = (e.sprayTimer-40)/30;
    _ctx.globalAlpha = al*pt*0.45; _ctx.shadowColor='#88FF44'; _ctx.shadowBlur=20;
    _ctx.fillStyle='#66FF22';
    _ctx.beginPath(); _ctx.arc(0,-s*0.1,s*0.9,0,Math.PI*2); _ctx.fill();
    _ctx.shadowBlur=0; _ctx.globalAlpha=al;
  }

  _drawBossHpBar(e, s, '★ 巨大ヘビ ★', '#88FF88', '#44CC44', '#228822', '#114411');
  _ctx.globalAlpha=1; _ctx.restore();
}

// ── ボスHPバー共通 ───────────────────────────────────────────────────────────
function _drawBossHpBar(e, s, label, labelCol, barTop, barBot, border) {
  var bw=s*2.4, bx=-bw/2, by=s*0.52;
  rrect(bx-2,by-2,bw+4,22,6,'rgba(0,0,0,0.85)',border,1.5);
  var ratio=e.hp/e.maxHp;
  if (ratio > 0) {
    var hpG=_ctx.createLinearGradient(bx,by,bx,by+18);
    hpG.addColorStop(0,barTop); hpG.addColorStop(1,barBot);
    rrectGrd(bx,by,bw*ratio,18,5,hpG,null);
    _ctx.fillStyle='rgba(255,255,255,0.26)';
    _ctx.beginPath(); _ctx.moveTo(bx+4,by+2); _ctx.lineTo(bx+bw*ratio-4,by+2); _ctx.lineTo(bx+bw*ratio-4,by+7); _ctx.lineTo(bx+4,by+7); _ctx.closePath(); _ctx.fill();
  }
  _ctx.fillStyle='#fff'; _ctx.font='bold 11px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center';
  _ctx.fillText(e.hp+'/'+e.maxHp, 0, by+14);
  _ctx.shadowColor=labelCol; _ctx.shadowBlur=12;
  _ctx.fillStyle=labelCol; _ctx.font='bold 13px Orbitron,"Zen Kaku Gothic New",sans-serif';
  _ctx.fillText(label, 0, -s*1.06);
  _ctx.shadowBlur=0;
  // フェーズインジケーター
  var ph = e.phase||1;
  if (ph > 1) {
    _ctx.fillStyle=ph>=3?'#FF4444':'#FF8800'; _ctx.font='bold 11px Orbitron,"Zen Kaku Gothic New",sans-serif';
    _ctx.fillText('PHASE '+ph, 0, -s*1.06+16);
  }
}

// ── Earth ────────────────────────────────────────────────────────────────────
function drawEarth(x, y, r) {
  _ctx.save(); _ctx.translate(x, y);
  var gG=_ctx.createRadialGradient(0,0,r*0.8,0,0,r*1.7);
  gG.addColorStop(0,'rgba(40,130,255,0.22)'); gG.addColorStop(1,'rgba(40,130,255,0)');
  _ctx.fillStyle=gG; _ctx.beginPath(); _ctx.arc(0,0,r*1.7,0,Math.PI*2); _ctx.fill();
  var oG=_ctx.createRadialGradient(-r*0.3,-r*0.3,0,0,0,r);
  oG.addColorStop(0,'#3498DB'); oG.addColorStop(1,'#1A5A8E');
  _ctx.fillStyle=oG; _ctx.beginPath(); _ctx.arc(0,0,r,0,Math.PI*2); _ctx.fill();
  _ctx.fillStyle='#27AE60';
  [[-.18,-.08,.28,.38],[.22,.12,.32,.22],[-.1,.3,.18,.14]].forEach(function(v){
    _ctx.beginPath(); _ctx.ellipse(r*v[0],r*v[1],r*v[2],r*v[3],0.6,0,Math.PI*2); _ctx.fill();
  });
  _ctx.strokeStyle='#1A4A8A'; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.arc(0,0,r,0,Math.PI*2); _ctx.stroke();
  _ctx.strokeStyle='rgba(100,180,255,0.3)'; _ctx.lineWidth=r*0.13;
  _ctx.beginPath(); _ctx.arc(0,0,r*1.05,0,Math.PI*2); _ctx.stroke();
  _ctx.fillStyle='rgba(255,255,255,0.38)';
  _ctx.beginPath(); _ctx.ellipse(-r*0.22,-r*0.22,r*0.2,r*0.13,-0.5,0,Math.PI*2); _ctx.fill();
  _ctx.restore();
}

// ── Egg ──────────────────────────────────────────────────────────────────────
function drawEgg(x, y) {
  _ctx.save(); _ctx.translate(x, y);
  _ctx.shadowColor='#FFCC00'; _ctx.shadowBlur=14;
  _ctx.fillStyle='#FFFDE7'; _ctx.strokeStyle='#FF8C00'; _ctx.lineWidth=2.5;
  _ctx.beginPath(); _ctx.ellipse(0,0,10,14,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.shadowBlur=0;
  _ctx.fillStyle='#FF8C00'; _ctx.font='12px sans-serif'; _ctx.textAlign='center'; _ctx.textBaseline='middle'; _ctx.fillText('✨',0,0);
  _ctx.restore();
}

// ── Angel Bullet ─────────────────────────────────────────────────────────────
function drawAngelBullet(x, y) {
  _ctx.save(); _ctx.translate(x, y);
  _ctx.shadowColor = '#FFD700'; _ctx.shadowBlur = 16;
  var g = _ctx.createRadialGradient(0, 0, 0, 0, 0, 9);
  g.addColorStop(0, '#FFFFFF');
  g.addColorStop(0.5, '#FFE840');
  g.addColorStop(1, '#FF8800');
  _ctx.fillStyle = g;
  _ctx.beginPath(); _ctx.arc(0, 0, 9, 0, Math.PI*2); _ctx.fill();
  _ctx.strokeStyle = 'rgba(255,255,255,0.8)'; _ctx.lineWidth = 1.5; _ctx.lineCap = 'round';
  _ctx.shadowBlur = 0;
  _ctx.beginPath(); _ctx.moveTo(-11, 0); _ctx.lineTo(11, 0); _ctx.stroke();
  _ctx.beginPath(); _ctx.moveTo(0, -11); _ctx.lineTo(0, 11); _ctx.stroke();
  _ctx.restore();
}

// ── Coin ─────────────────────────────────────────────────────────────────────
function drawCoinIcon(x, y, r) {
  _ctx.save(); _ctx.translate(x, y);
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=8;
  _ctx.fillStyle='#FFD700'; _ctx.beginPath(); _ctx.arc(0,0,r,0,Math.PI*2); _ctx.fill();
  _ctx.fillStyle='#CC8800'; _ctx.beginPath(); _ctx.arc(0,0,r*0.72,0,Math.PI*2); _ctx.fill();
  _ctx.fillStyle='#FFE840'; _ctx.font='bold '+Math.round(r*1.0)+'px sans-serif';
  _ctx.textAlign='center'; _ctx.textBaseline='middle'; _ctx.fillText('$',0,0);
  _ctx.shadowBlur=0; _ctx.restore();
}

// ── Enemy Bullet ─────────────────────────────────────────────────────────────
function drawEnemyBullet(eb) {
  _ctx.save(); _ctx.translate(eb.x, eb.y);
  var col = eb.color || '#FF6600';
  _ctx.shadowColor=col; _ctx.shadowBlur=18;
  var g=_ctx.createRadialGradient(0,0,0,0,0,eb.size);
  if (eb.color === '#88FF44') {
    g.addColorStop(0,'#CCFF88'); g.addColorStop(0.6,'#88FF44'); g.addColorStop(1,'#44AA00');
  } else {
    g.addColorStop(0,'#FFE800'); g.addColorStop(0.6,'#FF8800'); g.addColorStop(1,'#FF3300');
  }
  _ctx.fillStyle=g; _ctx.beginPath(); _ctx.arc(0,0,eb.size,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.restore();
}

// ── Tower ─────────────────────────────────────────────────────────────────────
function drawTower(slot, showRange, frame) {
  frame = frame || 0;
  _ctx.save(); _ctx.translate(slot.x, slot.y);
  if (!slot.type) {
    // 空きスロット＝「浮かぶ雲の足場」。
    // 旧版は薄い破線の丸に「+」だけで、置ける場所だと気づけなかった（2026-08-28 実測）。
    var pulse = Math.sin(frame*0.06)*0.5 + 0.5;      // 0..1
    var lift  = Math.sin(frame*0.03)*1.6;            // ふわふわ上下
    _ctx.translate(0, lift);
    // 足場の雲
    _ctx.globalAlpha = 0.30 + pulse*0.10;
    _ctx.fillStyle = '#CFE2FF';
    _ctx.beginPath();
    _ctx.ellipse(0,     6, 20, 7.5, 0, 0, Math.PI*2);
    _ctx.ellipse(-11,   4, 11, 6,   0, 0, Math.PI*2);
    _ctx.ellipse( 11,   4, 11, 6,   0, 0, Math.PI*2);
    _ctx.ellipse(  1,  -1, 13, 7,   0, 0, Math.PI*2);
    _ctx.fill();
    // 光の輪（回る破線）
    _ctx.globalAlpha = 0.34 + pulse*0.26;
    _ctx.strokeStyle = '#8FD8FF'; _ctx.lineWidth = 2;
    _ctx.setLineDash([6, 7]); _ctx.lineDashOffset = -frame*0.35;
    _ctx.shadowColor = '#3FA8E8'; _ctx.shadowBlur = 8;
    _ctx.beginPath(); _ctx.arc(0, -1, 19, 0, Math.PI*2); _ctx.stroke();
    _ctx.setLineDash([]); _ctx.lineDashOffset = 0; _ctx.shadowBlur = 0;
    // ＋
    _ctx.globalAlpha = 0.55 + pulse*0.35;
    _ctx.strokeStyle = '#EAF7FF'; _ctx.lineWidth = 3; _ctx.lineCap = 'round';
    _ctx.beginPath(); _ctx.moveTo(-6.5,-1); _ctx.lineTo(6.5,-1); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(0,-7.5);  _ctx.lineTo(0,5.5);  _ctx.stroke();
    _ctx.lineCap = 'butt';
    _ctx.globalAlpha = 1; _ctx.restore(); return;
  }
  var def=(typeof TOWER_DEFS!=='undefined')?TOWER_DEFS[slot.type]:null;
  if (!def) { _ctx.restore(); return; }
  if (showRange) {
    _ctx.globalAlpha=0.07; _ctx.fillStyle=def.col;
    _ctx.beginPath(); _ctx.arc(0,0,def.range,0,Math.PI*2); _ctx.fill();
    _ctx.globalAlpha=0.18; _ctx.strokeStyle=def.col; _ctx.lineWidth=1;
    _ctx.beginPath(); _ctx.arc(0,0,def.range,0,Math.PI*2); _ctx.stroke(); _ctx.globalAlpha=1;
  }
  _ctx.globalAlpha=0.38; _ctx.fillStyle='rgba(0,0,0,0.5)';
  _ctx.beginPath(); _ctx.ellipse(0,16,18,5,0,0,Math.PI*2); _ctx.fill(); _ctx.globalAlpha=1;
  _ctx.shadowColor=def.col; _ctx.shadowBlur=12;
  var bG=_ctx.createRadialGradient(-7,-7,1,0,0,20);
  bG.addColorStop(0,'rgba(255,255,255,0.35)'); bG.addColorStop(1,def.col);
  _ctx.fillStyle=bG; _ctx.strokeStyle='rgba(255,255,255,0.35)'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.moveTo(-11,12); _ctx.lineTo(11,12); _ctx.lineTo(15,-2); _ctx.lineTo(0,-18); _ctx.lineTo(-15,-2); _ctx.closePath(); _ctx.fill(); _ctx.stroke(); _ctx.shadowBlur=0;
  _ctx.fillStyle='rgba(0,0,0,0.68)'; _ctx.beginPath(); _ctx.rect(2,-24,6,14); _ctx.fill();
  _ctx.fillStyle='rgba(255,255,255,0.28)'; _ctx.beginPath(); _ctx.rect(3,-24,2,12); _ctx.fill();
  for (var li=0;li<slot.level-1;li++) {
    _ctx.fillStyle='#FFD700'; _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=5;
    _ctx.beginPath(); _ctx.arc(-14+li*8,16,2.5,0,Math.PI*2); _ctx.fill(); _ctx.shadowBlur=0;
  }
  _ctx.font='13px sans-serif'; _ctx.textAlign='center'; _ctx.textBaseline='middle'; _ctx.fillText(def.icon,0,-5); _ctx.textBaseline='alphabetic';
  if (slot.maxHp>0) {
    var ratio=Math.max(0,slot.hp/slot.maxHp);
    var bw2=32,bh=4,bx2=-bw2/2,by2=22;
    _ctx.fillStyle='rgba(0,0,0,0.5)'; _ctx.fillRect(bx2,by2,bw2,bh);
    _ctx.fillStyle=ratio>0.5?'#4CFF6A':ratio>0.25?'#FFD700':'#FF4444'; _ctx.fillRect(bx2,by2,bw2*ratio,bh);
  }
  _ctx.restore();
}

// ── Particle ─────────────────────────────────────────────────────────────────
function drawParticle(p) {
  var a=p.life/p.maxLife;
  _ctx.save(); _ctx.globalAlpha=a;
  if (p.type==='crit'||p.type==='explosion'||p.type==='levelup'||p.type==='stageclear'||p.type==='boss_beam'||p.type==='achieve') {
    _ctx.shadowColor=p.color; _ctx.shadowBlur=12;
  }
  _ctx.fillStyle=p.color;
  _ctx.beginPath();
  if (p.type==='poof') _ctx.arc(p.x,p.y,p.size*(1.2-a*0.5),0,Math.PI*2);
  else if (p.type==='coin') {
    _ctx.arc(p.x,p.y,Math.max(1,p.size*a),0,Math.PI*2);
  }
  else _ctx.arc(p.x,p.y,Math.max(1,p.size*a),0,Math.PI*2);
  _ctx.fill();
  _ctx.shadowBlur=0; _ctx.globalAlpha=1; _ctx.restore();
}

// ── レーンインジケーター ────────────────────────────────────────────────────────
function drawLaneIndicators(chickLane, laneWarnings, frame) {
  var laneXs = typeof LANE_X !== 'undefined' ? LANE_X : [78, 195, 312];
  var groundY = _H - 128;

  // 薄いレーン縦線（常時）
  for (var li = 0; li < 3; li++) {
    _ctx.save();
    _ctx.globalAlpha = li === chickLane ? 0.18 : 0.07;
    _ctx.strokeStyle = li === chickLane ? '#AAFFEE' : '#667788';
    _ctx.lineWidth = li === chickLane ? 2 : 1;
    _ctx.setLineDash([12, 18]);
    _ctx.beginPath();
    _ctx.moveTo(laneXs[li], 90);
    _ctx.lineTo(laneXs[li], groundY);
    _ctx.stroke();
    _ctx.setLineDash([]);
    _ctx.restore();
  }

  // 警告カラム（赤フラッシュ）
  for (var wi = 0; wi < laneWarnings.length; wi++) {
    var warn = laneWarnings[wi];
    var ratio = warn.timer / warn.maxTimer;
    var flashAmt = (ratio > 0.5) ? 0.32 : (Math.abs(Math.sin(frame * 0.55)) * 0.45 + 0.1);
    for (var wli = 0; wli < warn.lanes.length; wli++) {
      var lx = laneXs[warn.lanes[wli]];
      _ctx.save();
      _ctx.globalAlpha = flashAmt;
      var wg = _ctx.createLinearGradient(lx - 52, 0, lx + 52, 0);
      wg.addColorStop(0, 'rgba(255,0,0,0)');
      wg.addColorStop(0.5, 'rgba(255,30,0,0.9)');
      wg.addColorStop(1, 'rgba(255,0,0,0)');
      _ctx.fillStyle = wg;
      _ctx.fillRect(lx - 52, 80, 104, groundY - 80);
      _ctx.restore();
      // ⚠ アイコン
      _ctx.save();
      _ctx.globalAlpha = 0.85;
      _ctx.font = 'bold 22px sans-serif';
      _ctx.textAlign = 'center';
      _ctx.fillStyle = '#FF4400';
      _ctx.shadowColor = '#FF0000';
      _ctx.shadowBlur = 16;
      _ctx.fillText('⚠', lx, 145 + Math.sin(frame * 0.25) * 5);
      _ctx.shadowBlur = 0;
      _ctx.restore();
    }
  }
}

// ── レーンボタン（左右矢印） ──────────────────────────────────────────────────
function drawLaneBtns(chickLane, frame) {
  var btns = [{x:22, dir:'◀', active:chickLane>0}, {x:_W-22, dir:'▶', active:chickLane<2}];
  btns.forEach(function(b) {
    _ctx.save();
    _ctx.globalAlpha = b.active ? (0.65 + Math.sin(frame*0.07)*0.15) : 0.22;
    _ctx.fillStyle = b.active ? 'rgba(0,255,220,0.15)' : 'rgba(100,100,100,0.1)';
    _ctx.strokeStyle = b.active ? '#00FFCC' : '#445566';
    _ctx.lineWidth = 1.5;
    _ctx.beginPath();
    _ctx.roundRect ? _ctx.roundRect(b.x-18, _H-242, 36, 88, 10) : _ctx.rect(b.x-18, _H-242, 36, 88);
    _ctx.fill(); _ctx.stroke();
    _ctx.fillStyle = b.active ? '#AAFFEE' : '#445566';
    _ctx.font = 'bold 22px sans-serif';
    _ctx.textAlign = 'center';
    _ctx.textBaseline = 'middle';
    _ctx.shadowColor = b.active ? '#00FFCC' : 'transparent';
    _ctx.shadowBlur = b.active ? 10 : 0;
    _ctx.fillText(b.dir, b.x, _H - 198);
    _ctx.shadowBlur = 0;
    _ctx.textBaseline = 'alphabetic';
    _ctx.restore();
  });
}

// ── ドロップ強化アイテム ──────────────────────────────────────────────────────
function drawDropItem(item, frame) {
  var bob  = Math.sin(item.bob) * 8;
  var life = item.life / item.maxLife;
  var fade = life < 0.25 ? (life / 0.25) : 1.0;
  var pulse = 0.7 + Math.sin(item.bob) * 0.3;

  _ctx.save();
  _ctx.translate(item.x, item.y + bob);
  _ctx.globalAlpha = fade;

  // 外周グロー
  _ctx.shadowColor = '#00FFCC';
  _ctx.shadowBlur  = 22 * pulse;
  var grd = _ctx.createRadialGradient(0, 0, 6, 0, 0, 26);
  grd.addColorStop(0, 'rgba(0,255,210,0.45)');
  grd.addColorStop(1, 'rgba(0,160,140,0)');
  _ctx.fillStyle = grd;
  _ctx.beginPath(); _ctx.arc(0, 0, 26, 0, Math.PI*2); _ctx.fill();

  // 本体
  _ctx.fillStyle   = 'rgba(0,30,28,0.85)';
  _ctx.strokeStyle = '#00FFCC';
  _ctx.lineWidth   = 2.5;
  _ctx.beginPath(); _ctx.arc(0, 0, 18, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  // アイコン
  _ctx.shadowBlur = 0;
  _ctx.font = '18px sans-serif';
  _ctx.textAlign = 'center';
  _ctx.textBaseline = 'middle';
  _ctx.fillText(item.upgrade ? item.upgrade.icon : '⬆', 0, 0);

  // 残り時間バー
  var bw = 38, bx = -bw/2, by = 22;
  _ctx.fillStyle = 'rgba(0,0,0,0.55)';
  _ctx.fillRect(bx, by, bw, 4);
  _ctx.fillStyle = life > 0.5 ? '#00FFCC' : life > 0.25 ? '#FFAA00' : '#FF4444';
  _ctx.fillRect(bx, by, bw * life, 4);

  _ctx.shadowBlur = 0;
  _ctx.textBaseline = 'alphabetic';
  _ctx.globalAlpha = 1;
  _ctx.restore();
}

// ── ボスアーキタイプ描画（bird / beast / reptile / mech / final） ─────────────

function _drawBossAuraPhase(e, frame, auraRGB) {
  var phase = e.phase || 1;
  var pa = (0.06 + Math.sin(frame * 0.05) * 0.04) * (1 + (phase-1) * 0.5);
  var aG = _ctx.createRadialGradient(0, 0, e.size*0.3, 0, 0, e.size*1.5);
  aG.addColorStop(0, 'rgba('+auraRGB+','+pa+')');
  aG.addColorStop(1, 'rgba('+auraRGB+',0)');
  _ctx.fillStyle = aG;
  _ctx.beginPath(); _ctx.arc(0, 0, e.size*1.6, 0, Math.PI*2); _ctx.fill();
  if (phase >= 2) {
    _ctx.globalAlpha *= (0.14 + Math.sin(frame*0.10)*0.08);
    _ctx.strokeStyle = phase===3 ? '#FF4400' : '#FF8800';
    _ctx.lineWidth = phase===3 ? 5 : 3;
    _ctx.beginPath(); _ctx.arc(0, 0, e.size*1.35, 0, Math.PI*2); _ctx.stroke();
    _ctx.globalAlpha = 1;
  }
}

// bird アーキタイプ（s1〜s4: カラス/フクロウ/ハゲタカ/ワシ）
function drawBossArchBird(e, frame, cfg) {
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash>0 && e.hitFlash%2===0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;
  _drawBossAuraPhase(e, frame, cfg.aura);

  // 羽
  _ctx.fillStyle = cfg.col;
  _ctx.strokeStyle = 'rgba(0,0,0,0.55)'; _ctx.lineWidth = 2;
  var wingFlap = Math.sin(frame*0.18)*0.32;
  _ctx.save(); _ctx.rotate(-0.3 + wingFlap);
  _ctx.beginPath(); _ctx.moveTo(-s*0.08,-s*0.05); _ctx.quadraticCurveTo(-s*0.95,-s*0.5,-s*0.70,s*0.25); _ctx.quadraticCurveTo(-s*0.35,s*0.1,-s*0.08,s*0.05); _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  _ctx.restore();
  _ctx.save(); _ctx.rotate(0.3 - wingFlap);
  _ctx.beginPath(); _ctx.moveTo(s*0.08,-s*0.05); _ctx.quadraticCurveTo(s*0.95,-s*0.5,s*0.70,s*0.25); _ctx.quadraticCurveTo(s*0.35,s*0.1,s*0.08,s*0.05); _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  _ctx.restore();

  // 胴体
  var bG = _ctx.createRadialGradient(-s*0.14,-s*0.08,s*0.04,0,0,s*0.5);
  bG.addColorStop(0,'rgba(255,255,255,0.18)'); bG.addColorStop(1, cfg.col);
  _ctx.fillStyle=bG; _ctx.strokeStyle='rgba(0,0,0,0.6)'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.ellipse(0,0,s*0.46,s*0.42,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 頭
  _ctx.fillStyle=cfg.col;
  _ctx.beginPath(); _ctx.arc(0,-s*0.32,s*0.32,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 目
  _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=s*0.28;
  _ctx.fillStyle=cfg.eyeCol;
  _ctx.beginPath(); _ctx.arc(-s*0.12,-s*0.33,s*0.09,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( s*0.12,-s*0.33,s*0.09,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.fillStyle='#000';
  _ctx.beginPath(); _ctx.arc(-s*0.12,-s*0.33,s*0.05,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( s*0.12,-s*0.33,s*0.05,0,Math.PI*2); _ctx.fill();
  // くちばし
  _ctx.fillStyle='#FFCC00'; _ctx.strokeStyle='#AA8800'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.moveTo(-s*0.1,-s*0.18); _ctx.lineTo(s*0.1,-s*0.18); _ctx.lineTo(0,-s*0.05); _ctx.closePath(); _ctx.fill(); _ctx.stroke();

  _drawBossHpBar(e, s, cfg.name, cfg.eyeCol, cfg.col, cfg.col, '#442200');
  _ctx.globalAlpha=1; _ctx.restore();
}

// beast アーキタイプ（s5〜s8: タイガー/ウルフ/グリズリー/デモン）
function drawBossArchBeast(e, frame, cfg) {
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash>0 && e.hitFlash%2===0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;
  _drawBossAuraPhase(e, frame, cfg.aura);

  // 耳
  _ctx.fillStyle=cfg.col; _ctx.strokeStyle='rgba(0,0,0,0.5)'; _ctx.lineWidth=1.5;
  [[-s*0.26,-s*0.62],[s*0.26,-s*0.62]].forEach(function(p) {
    _ctx.beginPath(); _ctx.moveTo(p[0]-s*0.1,p[1]+s*0.12); _ctx.lineTo(p[0],p[1]-s*0.18); _ctx.lineTo(p[0]+s*0.1,p[1]+s*0.12); _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  });
  // 胴体
  var bG2 = _ctx.createRadialGradient(-s*0.14,-s*0.08,s*0.04,0,0,s*0.55);
  bG2.addColorStop(0,'rgba(255,255,255,0.22)'); bG2.addColorStop(1,cfg.col);
  _ctx.fillStyle=bG2; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,s*0.05,s*0.52,s*0.45,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 頭
  _ctx.fillStyle=cfg.col;
  _ctx.beginPath(); _ctx.arc(0,-s*0.28,s*0.38,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 鼻
  _ctx.fillStyle='#222'; _ctx.beginPath(); _ctx.ellipse(0,-s*0.14,s*0.09,s*0.06,0,0,Math.PI*2); _ctx.fill();
  // 目
  _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=s*0.3;
  _ctx.fillStyle=cfg.eyeCol;
  _ctx.beginPath(); _ctx.arc(-s*0.14,-s*0.31,s*0.1,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( s*0.14,-s*0.31,s*0.1,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.fillStyle='#111';
  _ctx.beginPath(); _ctx.arc(-s*0.14,-s*0.31,s*0.055,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( s*0.14,-s*0.31,s*0.055,0,Math.PI*2); _ctx.fill();
  // ひっかき傷
  _ctx.strokeStyle='rgba(255,255,255,0.22)'; _ctx.lineWidth=1.5;
  [[-s*0.22,s*0.05],[-s*0.1,s*0.2],[s*0.1,s*0.05],[s*0.22,s*0.2]].forEach(function(p,i) {
    if (i%2===0) { _ctx.beginPath(); _ctx.moveTo(p[0],p[1]-s*0.12); _ctx.lineTo(p[0]+s*0.04,p[1]+s*0.12); _ctx.stroke(); }
  });

  _drawBossHpBar(e, s, cfg.name, cfg.eyeCol, cfg.col, cfg.col, '#333');
  _ctx.globalAlpha=1; _ctx.restore();
}

// reptile アーキタイプ（s9〜s12: ワニ/ヘビ王/カメレオン/ドラゴン）
function drawBossArchReptile(e, frame, cfg) {
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash>0 && e.hitFlash%2===0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;
  _drawBossAuraPhase(e, frame, cfg.aura);

  // 尾（後ろに）
  _ctx.strokeStyle=cfg.col; _ctx.lineWidth=s*0.45; _ctx.lineCap='round';
  _ctx.beginPath();
  _ctx.moveTo(0,s*0.3);
  _ctx.quadraticCurveTo(s*0.7,s*0.7,s*0.5,s*1.35);
  _ctx.quadraticCurveTo(-s*0.2,s*1.7,-s*0.5,s*1.15);
  _ctx.stroke();
  _ctx.strokeStyle='rgba(255,255,255,0.15)'; _ctx.lineWidth=s*0.18;
  _ctx.stroke();

  // 胴体
  var bG3 = _ctx.createRadialGradient(-s*0.12,-s*0.1,s*0.05,0,0,s*0.58);
  bG3.addColorStop(0,'rgba(255,255,255,0.18)'); bG3.addColorStop(1,cfg.col);
  _ctx.fillStyle=bG3; _ctx.strokeStyle='rgba(0,0,0,0.55)'; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,s*0.08,s*0.52,s*0.44,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 鱗
  _ctx.strokeStyle='rgba(255,255,255,0.15)'; _ctx.lineWidth=1.5;
  for (var ri=0;ri<3;ri++) { _ctx.beginPath(); _ctx.arc(0,s*0.08,s*(0.2+ri*0.1),0,Math.PI*2); _ctx.stroke(); }
  // 頭（扁平）
  var hG3 = _ctx.createRadialGradient(-s*0.08,-s*0.32,s*0.02,0,-s*0.28,s*0.42);
  hG3.addColorStop(0,'rgba(255,255,255,0.2)'); hG3.addColorStop(1,cfg.col);
  _ctx.fillStyle=hG3; _ctx.lineWidth=2;
  _ctx.beginPath(); _ctx.ellipse(0,-s*0.28,s*0.44,s*0.30,0,0,Math.PI*2); _ctx.fill(); _ctx.stroke();
  // 縦長の瞳
  _ctx.fillStyle=cfg.eyeCol; _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=s*0.28;
  _ctx.beginPath(); _ctx.ellipse(-s*0.16,-s*0.3,s*0.1,s*0.13,0,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.ellipse( s*0.16,-s*0.3,s*0.1,s*0.13,0,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.fillStyle='#000';
  _ctx.beginPath(); _ctx.ellipse(-s*0.16,-s*0.3,s*0.035,s*0.11,0,0,Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.ellipse( s*0.16,-s*0.3,s*0.035,s*0.11,0,0,Math.PI*2); _ctx.fill();
  // 舌
  _ctx.strokeStyle='#FF3333'; _ctx.lineWidth=2.5; _ctx.lineCap='round';
  _ctx.beginPath(); _ctx.moveTo(0,-s*0.02); _ctx.lineTo(0,-s*0.14);
  _ctx.moveTo(0,-s*0.14); _ctx.lineTo(-s*0.06,-s*0.23);
  _ctx.moveTo(0,-s*0.14); _ctx.lineTo( s*0.06,-s*0.23);
  _ctx.stroke();

  _drawBossHpBar(e, s, cfg.name, cfg.eyeCol, cfg.col, cfg.col, '#1A3A10');
  _ctx.globalAlpha=1; _ctx.restore();
}

// mech アーキタイプ（s13〜s16: メカ戦士/サイボーグ/ロボット/戦闘機）
function drawBossArchMech(e, frame, cfg) {
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash>0 && e.hitFlash%2===0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;
  _drawBossAuraPhase(e, frame, cfg.aura);

  // メインボディ（四角形）
  _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=12;
  var mG = _ctx.createLinearGradient(-s*0.5,-s*0.5,s*0.5,s*0.5);
  mG.addColorStop(0,'rgba(255,255,255,0.3)'); mG.addColorStop(1,cfg.col);
  _ctx.fillStyle=mG; _ctx.strokeStyle=cfg.eyeCol; _ctx.lineWidth=2.5;
  rrect(-s*0.48,-s*0.42,s*0.96,s*0.88,s*0.08,mG,cfg.eyeCol,2.5);
  _ctx.shadowBlur=0;
  // 装甲リベット
  [[-.35,-.32],[.35,-.32],[-.35,.32],[.35,.32]].forEach(function(p) {
    _ctx.fillStyle='rgba(255,255,255,0.4)';
    _ctx.beginPath(); _ctx.arc(s*p[0],s*p[1],s*0.055,0,Math.PI*2); _ctx.fill();
  });
  // スキャンアイ
  var scanX = Math.sin(frame * 0.09) * s * 0.15;
  _ctx.fillStyle=cfg.eyeCol; _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=14;
  _ctx.fillRect(-s*0.35,-s*0.15+scanX-s*0.08,s*0.70,s*0.16);
  _ctx.shadowBlur=0;
  // バイザーライン
  _ctx.strokeStyle='rgba(255,255,255,0.3)'; _ctx.lineWidth=1;
  _ctx.beginPath(); _ctx.moveTo(-s*0.35,-s*0.05+scanX); _ctx.lineTo(s*0.35,-s*0.05+scanX); _ctx.stroke();
  // 排気口
  _ctx.fillStyle='rgba(0,0,0,0.55)';
  [-s*0.25,0,s*0.25].forEach(function(bx) {
    _ctx.fillRect(bx-s*0.04,s*0.38,s*0.08,s*0.14);
  });
  // 点滅ライト
  var blink = Math.floor(frame/8)%2===0;
  _ctx.fillStyle=blink?cfg.eyeCol:'rgba(255,255,255,0.15)';
  _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=blink?10:0;
  _ctx.beginPath(); _ctx.arc(-s*0.38,s*0.18,s*0.055,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0;

  _drawBossHpBar(e, s, cfg.name, cfg.eyeCol, cfg.col, cfg.col, '#111133');
  _ctx.globalAlpha=1; _ctx.restore();
}

// final アーキタイプ（s17〜s20: 最終形態、宇宙存在）
function drawBossArchFinal(e, frame, cfg) {
  _ctx.save(); _ctx.translate(e.x, e.y);
  var s  = e.size;
  var al = (e.hitFlash>0 && e.hitFlash%2===0) ? 0.25 : 1.0;
  _ctx.globalAlpha = al;

  // 超強力オーラ（脈動）
  var phase = e.phase || 1;
  var pulseR = s * (1.4 + Math.sin(frame*0.07)*0.2) * (1+(phase-1)*0.25);
  var aG = _ctx.createRadialGradient(0,0,s*0.2,0,0,pulseR);
  aG.addColorStop(0,'rgba('+cfg.aura+','+(0.25+Math.sin(frame*0.05)*0.1)+')');
  aG.addColorStop(0.7,'rgba('+cfg.aura+',0.05)');
  aG.addColorStop(1,'rgba('+cfg.aura+',0)');
  _ctx.fillStyle=aG; _ctx.beginPath(); _ctx.arc(0,0,pulseR,0,Math.PI*2); _ctx.fill();
  // 回転リング
  for (var ri2=0;ri2<3;ri2++) {
    _ctx.save();
    _ctx.rotate(frame*(0.018+ri2*0.009)*(ri2%2===0?1:-1));
    _ctx.globalAlpha = al*(0.30+ri2*0.08);
    _ctx.strokeStyle=cfg.eyeCol; _ctx.lineWidth=ri2===2?3:2;
    _ctx.setLineDash(ri2===1?[s*0.18,s*0.12]:[]); _ctx.beginPath(); _ctx.arc(0,0,s*(0.72+ri2*0.28),0,Math.PI*2); _ctx.stroke();
    _ctx.setLineDash([]);
    _ctx.restore();
  }

  // コア（複合形状）
  _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=22;
  var cG = _ctx.createRadialGradient(-s*0.18,-s*0.18,s*0.05,0,0,s*0.6);
  cG.addColorStop(0,'rgba(255,255,255,0.65)'); cG.addColorStop(0.4,'rgba(255,255,255,0.22)'); cG.addColorStop(1,cfg.col);
  _ctx.fillStyle=cG; _ctx.strokeStyle=cfg.eyeCol; _ctx.lineWidth=3;
  // 六角形コア
  _ctx.beginPath();
  for (var hi2=0;hi2<6;hi2++) {
    var ha = (hi2/6)*Math.PI*2 - Math.PI/2 + Math.sin(frame*0.04)*0.12;
    var hx = Math.cos(ha)*s*0.52, hy = Math.sin(ha)*s*0.52;
    hi2===0 ? _ctx.moveTo(hx,hy) : _ctx.lineTo(hx,hy);
  }
  _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  _ctx.shadowBlur=0;

  // 眼（中央に単眼）
  _ctx.shadowColor=cfg.eyeCol; _ctx.shadowBlur=18;
  _ctx.fillStyle=cfg.eyeCol;
  _ctx.beginPath(); _ctx.arc(0,0,s*0.22,0,Math.PI*2); _ctx.fill();
  _ctx.shadowBlur=0; _ctx.fillStyle='#000';
  _ctx.beginPath(); _ctx.arc(Math.sin(frame*0.04)*s*0.06,Math.cos(frame*0.03)*s*0.06,s*0.10,0,Math.PI*2); _ctx.fill();
  _ctx.fillStyle='rgba(255,255,255,0.8)';
  _ctx.beginPath(); _ctx.arc(s*0.06,s*-0.06,s*0.04,0,Math.PI*2); _ctx.fill();

  // フェーズ2以上：追加の触手
  if (phase >= 2) {
    for (var ti=0;ti<4;ti++) {
      var ta = (ti/4)*Math.PI*2 + frame*0.04;
      var tx2=Math.cos(ta)*s*0.55, ty2=Math.sin(ta)*s*0.55;
      _ctx.strokeStyle=cfg.eyeCol; _ctx.lineWidth=3; _ctx.globalAlpha=al*0.55;
      _ctx.beginPath(); _ctx.moveTo(tx2,ty2); _ctx.quadraticCurveTo(tx2*1.4+Math.sin(frame*0.08+ti)*s*0.25,ty2*1.4,Math.cos(ta+0.6)*s*0.95,Math.sin(ta+0.6)*s*0.95); _ctx.stroke();
      _ctx.globalAlpha=al;
    }
  }

  _drawBossHpBar(e, s, cfg.name, cfg.eyeCol, cfg.col, cfg.col, '#110022');
  _ctx.globalAlpha=1; _ctx.restore();
}
