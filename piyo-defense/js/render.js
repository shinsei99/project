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

// ── Chick ────────────────────────────────────────────────────────────────────
function drawChick(x, y, sz, evolved, acc) {
  sz      = sz      === undefined ? 40    : sz;
  evolved = evolved === undefined ? false : evolved;
  acc     = acc     === undefined ? null  : acc;
  _ctx.save(); _ctx.translate(x, y);

  if (evolved) {
    _ctx.fillStyle = '#E74C3C'; _ctx.strokeStyle = '#922B21'; _ctx.lineWidth = 2;
    _ctx.beginPath();
    _ctx.moveTo(-7, -sz*0.72);
    _ctx.quadraticCurveTo(-13, -sz*1.0, -4, -sz*0.88);
    _ctx.quadraticCurveTo(0, -sz*1.12, 4, -sz*0.88);
    _ctx.quadraticCurveTo(13, -sz*1.0, 7, -sz*0.72);
    _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  }

  _ctx.fillStyle = '#FFE135'; _ctx.strokeStyle = '#C8960C'; _ctx.lineWidth = 2.5;
  _ctx.beginPath(); _ctx.ellipse(0, sz*0.1, sz*0.52, sz*0.48, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath(); _ctx.arc(0, -sz*0.3, sz*0.36, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  _ctx.fillStyle = '#FFCD00';
  _ctx.beginPath(); _ctx.ellipse(-sz*0.52, sz*0.08, sz*0.18, sz*0.26, -0.4, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath(); _ctx.ellipse( sz*0.52, sz*0.08, sz*0.18, sz*0.26,  0.4, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  if (evolved) {
    _ctx.fillStyle = '#E74C3C'; _ctx.strokeStyle = '#922B21'; _ctx.lineWidth = 1.5;
    _ctx.beginPath(); _ctx.arc(sz*0.12, -sz*0.1, sz*0.1, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  }

  _ctx.fillStyle = '#2C2C2C';
  _ctx.beginPath(); _ctx.arc(-sz*0.12, -sz*0.33, sz*0.07, 0, Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( sz*0.12, -sz*0.33, sz*0.07, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = '#fff';
  _ctx.beginPath(); _ctx.arc(-sz*0.09, -sz*0.36, sz*0.03, 0, Math.PI*2); _ctx.fill();
  _ctx.beginPath(); _ctx.arc( sz*0.15, -sz*0.36, sz*0.03, 0, Math.PI*2); _ctx.fill();

  _ctx.fillStyle = '#FF8C00'; _ctx.strokeStyle = '#CC6600'; _ctx.lineWidth = 1.5;
  _ctx.beginPath(); _ctx.moveTo(-sz*0.1, -sz*0.22); _ctx.lineTo(sz*0.1, -sz*0.22); _ctx.lineTo(0, -sz*0.1); _ctx.closePath(); _ctx.fill(); _ctx.stroke();

  _ctx.strokeStyle = '#FF8C00'; _ctx.lineWidth = 2.5; _ctx.lineCap = 'round';
  [[-sz*0.18, sz*0.55], [sz*0.18, sz*0.55]].forEach(function(ft) {
    var fx = ft[0], fy = ft[1];
    _ctx.beginPath(); _ctx.moveTo(fx, fy); _ctx.lineTo(fx-sz*0.12, fy+sz*0.12); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(fx, fy); _ctx.lineTo(fx+sz*0.12, fy+sz*0.12); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(fx, fy); _ctx.lineTo(fx,         fy+sz*0.16); _ctx.stroke();
  });

  if (acc === 'glasses') {
    _ctx.strokeStyle = '#555'; _ctx.lineWidth = 2;
    _ctx.beginPath(); _ctx.arc(-sz*0.12, -sz*0.33, sz*0.14, 0, Math.PI*2); _ctx.stroke();
    _ctx.beginPath(); _ctx.arc( sz*0.12, -sz*0.33, sz*0.14, 0, Math.PI*2); _ctx.stroke();
    _ctx.beginPath(); _ctx.moveTo(-sz*0.02, -sz*0.33); _ctx.lineTo(sz*0.02, -sz*0.33); _ctx.stroke();
  } else if (acc === 'nurse') {
    rrect(-sz*0.3, -sz*0.72, sz*0.6, sz*0.28, 3, '#fff', '#999', 1.5);
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

// ── Crow (normal / fast / tank) ──────────────────────────────────────────────
var CROW_COLORS = {
  normal: { wing:'#1A1A1A', body:'#2C2C2C', eye:'#FF0000' },
  fast:   { wing:'#001A66', body:'#1A3A99', eye:'#00FFFF' },
  tank:   { wing:'#3A0000', body:'#880000', eye:'#FF6600' },
};

function drawCrow(e) {
  _ctx.save();
  _ctx.translate(e.x, e.y + Math.sin(e.wobble) * 4);
  var s = e.size;
  var c = CROW_COLORS[e.type] || CROW_COLORS.normal;
  if (e.hitFlash > 0) _ctx.globalAlpha = (e.hitFlash % 2 === 0) ? 0.35 : 1.0;

  _ctx.fillStyle = c.wing; _ctx.strokeStyle = '#000'; _ctx.lineWidth = 2;
  _ctx.beginPath();
  _ctx.moveTo(-s*0.1, -s*0.05);
  _ctx.quadraticCurveTo(-s*0.85, -s*0.45, -s*0.65, s*0.25);
  _ctx.quadraticCurveTo(-s*0.35,  s*0.1,  -s*0.1,  s*0.05);
  _ctx.closePath(); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath();
  _ctx.moveTo(s*0.1, -s*0.05);
  _ctx.quadraticCurveTo(s*0.85, -s*0.45, s*0.65, s*0.25);
  _ctx.quadraticCurveTo(s*0.35,  s*0.1,  s*0.1,  s*0.05);
  _ctx.closePath(); _ctx.fill(); _ctx.stroke();

  _ctx.fillStyle = c.body;
  _ctx.beginPath(); _ctx.ellipse(0, 0, s*0.45, s*0.4, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath(); _ctx.arc(s*0.28, -s*0.28, s*0.28, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();

  _ctx.fillStyle = '#333';
  _ctx.beginPath(); _ctx.moveTo(s*0.5,-s*0.22); _ctx.lineTo(s*0.82,-s*0.16); _ctx.lineTo(s*0.5,-s*0.08); _ctx.closePath(); _ctx.fill();

  _ctx.fillStyle = c.eye;
  _ctx.beginPath(); _ctx.arc(s*0.33, -s*0.3, s*0.09, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = '#000';
  _ctx.beginPath(); _ctx.arc(s*0.35, -s*0.3, s*0.05, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = '#fff';
  _ctx.beginPath(); _ctx.arc(s*0.37, -s*0.32, s*0.02, 0, Math.PI*2); _ctx.fill();

  // HP bar for tank enemies
  if (e.type === 'tank' || e.maxHp > 12) {
    var bw = s*1.4, bx = -bw/2, by = s*0.58;
    rrect(bx-1, by-1, bw+2, 10, 3, '#222', null);
    var ratio = e.hp / e.maxHp;
    rrect(bx, by, bw*ratio, 8, 2, ratio > 0.5 ? '#2ECC71' : ratio > 0.25 ? '#F39C12' : '#E74C3C', null);
  }

  _ctx.globalAlpha = 1;
  _ctx.restore();
}

// ── Boss (UFO) ───────────────────────────────────────────────────────────────
function drawBoss(e, frame) {
  _ctx.save();
  _ctx.translate(e.x, e.y);
  var s = e.size;
  if (e.hitFlash > 0) _ctx.globalAlpha = (e.hitFlash % 2 === 0) ? 0.35 : 1.0;

  // Beam warning
  if (e.bossTimer > 95) {
    _ctx.globalAlpha = (e.bossTimer - 95) / 25 * 0.4;
    var grd = _ctx.createLinearGradient(0, s*0.4, 0, _H - e.y);
    grd.addColorStop(0, 'rgba(155,89,182,0.8)');
    grd.addColorStop(1, 'rgba(155,89,182,0)');
    _ctx.fillStyle = grd;
    _ctx.beginPath();
    _ctx.moveTo(-35, s*0.4); _ctx.lineTo(35, s*0.4);
    _ctx.lineTo(90, _H-e.y); _ctx.lineTo(-90, _H-e.y);
    _ctx.closePath(); _ctx.fill();
    _ctx.globalAlpha = 1;
  }

  // UFO dish
  _ctx.fillStyle = '#504070'; _ctx.strokeStyle = '#220044'; _ctx.lineWidth = 3;
  _ctx.beginPath(); _ctx.ellipse(0, s*0.1, s*0.95, s*0.24, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.fillStyle = '#7060A0';
  _ctx.beginPath(); _ctx.ellipse(0, s*0.08, s*0.7, s*0.16, 0, 0, Math.PI*2); _ctx.fill();

  // UFO dome
  _ctx.fillStyle = 'rgba(180,100,255,0.55)'; _ctx.strokeStyle = '#CC88FF'; _ctx.lineWidth = 2.5;
  _ctx.beginPath(); _ctx.ellipse(0, -s*0.05, s*0.5, s*0.5, 0, Math.PI, 0); _ctx.fill(); _ctx.stroke();

  // Rotating lights
  ['#FF3333','#33FF33','#CC44FF','#FFFF33','#FF33FF'].forEach(function(col, i) {
    var a = (frame * 0.06) + i * (Math.PI*2/5);
    _ctx.fillStyle = col;
    _ctx.beginPath(); _ctx.arc(Math.cos(a)*s*0.62, s*0.08 + Math.sin(a)*s*0.12, 5, 0, Math.PI*2); _ctx.fill();
  });

  // Crow on top
  _ctx.fillStyle = '#111'; _ctx.strokeStyle = '#000'; _ctx.lineWidth = 2;
  _ctx.beginPath(); _ctx.ellipse(0, -s*0.62, s*0.22, s*0.18, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.beginPath(); _ctx.arc(s*0.15, -s*0.82, s*0.16, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.fillStyle = '#FF00FF';
  _ctx.beginPath(); _ctx.arc(s*0.2, -s*0.83, 4, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = '#000';
  _ctx.beginPath(); _ctx.arc(s*0.21, -s*0.83, 2.2, 0, Math.PI*2); _ctx.fill();
  _ctx.fillStyle = '#333';
  _ctx.beginPath(); _ctx.moveTo(s*0.28,-s*0.78); _ctx.lineTo(s*0.45,-s*0.75); _ctx.lineTo(s*0.28,-s*0.7); _ctx.closePath(); _ctx.fill();

  // HP bar
  var bw = s*2.2, bx = -bw/2, by = s*0.45;
  rrect(bx-2, by-2, bw+4, 18, 5, '#222', '#440066', 2);
  var ratio = e.hp / e.maxHp;
  rrect(bx, by, bw*ratio, 14, 4, '#9B59B6', null);
  _ctx.fillStyle = '#fff'; _ctx.font = 'bold 11px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText(e.hp + '/' + e.maxHp, 0, by + 11);

  _ctx.fillStyle = '#CC66FF'; _ctx.font = 'bold 13px "Kosugi Maru",sans-serif';
  _ctx.fillText('★ 巨大カラスUFO ★', 0, -s*1.05);

  _ctx.globalAlpha = 1;
  _ctx.restore();
}

// ── Earth ────────────────────────────────────────────────────────────────────
function drawEarth(x, y, r) {
  _ctx.save(); _ctx.translate(x, y);
  _ctx.beginPath(); _ctx.arc(0, 0, r, 0, Math.PI*2); _ctx.fillStyle = '#1A6FBF'; _ctx.fill();
  _ctx.fillStyle = '#2ECC71';
  [[-.18,-.08,.28,.38],[.22,.12,.32,.22],[-.1,.3,.18,.14]].forEach(function(v) {
    _ctx.beginPath(); _ctx.ellipse(r*v[0], r*v[1], r*v[2], r*v[3], 0.6, 0, Math.PI*2); _ctx.fill();
  });
  _ctx.strokeStyle = '#1A4A8A'; _ctx.lineWidth = 2.5;
  _ctx.beginPath(); _ctx.arc(0, 0, r, 0, Math.PI*2); _ctx.stroke();
  _ctx.fillStyle = 'rgba(255,255,255,0.28)';
  _ctx.beginPath(); _ctx.ellipse(-r*0.22, -r*0.22, r*0.18, r*0.12, -0.5, 0, Math.PI*2); _ctx.fill();
  _ctx.restore();
}

// ── Egg (evolved projectile) ─────────────────────────────────────────────────
function drawEgg(x, y) {
  _ctx.save(); _ctx.translate(x, y);
  _ctx.fillStyle = '#FFFDE7'; _ctx.strokeStyle = '#FF8C00'; _ctx.lineWidth = 2.5;
  _ctx.beginPath(); _ctx.ellipse(0, 0, 10, 14, 0, 0, Math.PI*2); _ctx.fill(); _ctx.stroke();
  _ctx.fillStyle = '#FF8C00'; _ctx.font = '12px sans-serif';
  _ctx.textAlign = 'center'; _ctx.textBaseline = 'middle'; _ctx.fillText('✨', 0, 0);
  _ctx.restore();
}

// ── Background ───────────────────────────────────────────────────────────────
function drawBg(frame) {
  var g = _ctx.createLinearGradient(0, 0, 0, _H);
  g.addColorStop(0, '#06061A'); g.addColorStop(0.7, '#101040'); g.addColorStop(1, '#1A0A30');
  _ctx.fillStyle = g; _ctx.fillRect(0, 0, _W, _H);
  for (var i = 0; i < 55; i++) {
    var sx = (i*141+47) % _W;
    var sy = (i*233+31) % (_H * 0.78);
    _ctx.globalAlpha = (Math.sin(frame*0.04+i)*0.25+0.65) * 0.75;
    _ctx.fillStyle = '#fff';
    _ctx.beginPath(); _ctx.arc(sx, sy, 0.8+(i%3)*0.4, 0, Math.PI*2); _ctx.fill();
  }
  _ctx.globalAlpha = 1;
}

function drawGround() {
  var g = _ctx.createLinearGradient(0, _H-120, 0, _H);
  g.addColorStop(0, '#27AE60'); g.addColorStop(1, '#1E8449');
  _ctx.fillStyle = g;
  _ctx.beginPath();
  _ctx.moveTo(0, _H-105);
  _ctx.quadraticCurveTo(_W*0.25, _H-122, _W*0.5, _H-110);
  _ctx.quadraticCurveTo(_W*0.75, _H-98,  _W,     _H-115);
  _ctx.lineTo(_W, _H); _ctx.lineTo(0, _H); _ctx.closePath(); _ctx.fill();
}

// ── Particle ─────────────────────────────────────────────────────────────────
function drawParticle(p) {
  var a = p.life / p.maxLife;
  _ctx.globalAlpha = a; _ctx.fillStyle = p.color;
  _ctx.beginPath();
  if (p.type === 'poof') _ctx.arc(p.x, p.y, p.size*(1.2 - a*0.5), 0, Math.PI*2);
  else                   _ctx.arc(p.x, p.y, Math.max(1, p.size*a), 0, Math.PI*2);
  _ctx.fill(); _ctx.globalAlpha = 1;
}
