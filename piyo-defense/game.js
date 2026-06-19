'use strict';

// ── CANVAS SETUP ──────────────────────────────────────────────
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const W = 390, H = 844;
canvas.width = W;
canvas.height = H;

function resize() {
  const vh = window.innerHeight, vw = window.innerWidth;
  const ratio = W / H;
  let cw = vh * ratio, ch = vh;
  if (cw > vw) { cw = vw; ch = vw / ratio; }
  canvas.style.width = cw + 'px';
  canvas.style.height = ch + 'px';
}
window.addEventListener('resize', resize);
resize();

// ── GAME STATE ────────────────────────────────────────────────
let gs = {
  state: 'title',
  stage: 1,
  earthHP: 100,
  evoGauge: 0,
  isEvolved: false,
  evoTimer: 0,
  piyoPoints: 0,
  lastEarnedPoints: 0,
  stagePointsEarned: 0,
  frame: 0,
  attackCooldown: 0,
  barrierActive: false,
  barrierTimer: 0,
};

// Persistent upgrades
let upg = { speed: 1, evoTime: 1, gunshi: false, nurse: false, barrier: false };

// Skill cooldowns (frames at 60fps)
let cds = { gunshi: 0, nurse: 0, barrier: 0 };
const CD_MAX = { gunshi: 600, nurse: 900, barrier: 750 };

// Collections
let enemies = [], projectiles = [], particles = [], floatingTexts = [], shopItems = [];

// Wave state
let stageConfig = null, currentWave = 0, waveSpawned = 0, waveTimer = 0, clearDelay = 0;

// ── STAGE CONFIG ──────────────────────────────────────────────
function getStageConfig(s) {
  if (s === 10) return { waves: 1, counts: [1], types: [['boss']], reward: 200 };
  const types =
    s <= 3 ? [['crow_s'], ['crow_s'], ['crow_s', 'crow_m']] :
    s <= 6 ? [['crow_s', 'crow_m'], ['crow_m'], ['crow_m', 'crow_l']] :
             [['crow_m', 'crow_l'], ['crow_l'], ['crow_l']];
  return { waves: 3, counts: [s + 2, s + 3, s + 5], types, reward: 20 + s * 15 };
}

// ── ENEMY ─────────────────────────────────────────────────────
class Enemy {
  constructor(type, x, y) {
    this.type = type;
    this.x = x; this.y = y;
    this.dead = false;
    this.wobble = Math.random() * Math.PI * 2;
    this.bossAttackTimer = 0;
    const cfg = {
      crow_s: { hp: 3,   dmg: 4,  size: 26, pts: 5,  spd: 1.2 },
      crow_m: { hp: 7,   dmg: 6,  size: 36, pts: 10, spd: 0.9 },
      crow_l: { hp: 14,  dmg: 10, size: 46, pts: 18, spd: 0.7 },
      boss:   { hp: 150, dmg: 0,  size: 90, pts: 100,spd: 0.4 },
    }[type];
    Object.assign(this, cfg);
    this.maxHp = this.hp;
    if (type === 'boss') {
      this.vx = 1.5; this.vy = 0;
    } else {
      this.vx = (Math.random() - 0.5) * 1.5;
      this.vy = this.spd;
    }
  }

  update() {
    this.wobble += 0.05;
    if (this.type === 'boss') {
      this.x += this.vx;
      if (this.x < 70 || this.x > W - 70) this.vx *= -1;
      this.y = 220 + Math.sin(gs.frame * 0.018) * 30;
      this.bossAttackTimer++;
      if (this.bossAttackTimer >= 120) {
        this.bossAttackTimer = 0;
        if (!gs.barrierActive) {
          gs.earthHP = Math.max(0, gs.earthHP - 6);
          spawnParticles(this.x, this.y + this.size * 0.5, 'boss_beam', 6);
          addFloat(W / 2, H / 2, 'ドゴーン！', '#9B59B6', 24);
        } else {
          addFloat(W / 2, H * 0.4, 'バリアが守った！', '#00FFFF', 20);
        }
      }
    } else {
      this.x += this.vx + Math.sin(this.wobble) * 0.4;
      this.y += this.vy;
      if (this.x < this.size || this.x > W - this.size) this.vx *= -1;
      if (this.y > H - 120) {
        if (!gs.barrierActive) {
          gs.earthHP = Math.max(0, gs.earthHP - this.dmg);
          spawnParticles(this.x, H - 120, 'hit_earth', 5);
        } else {
          addFloat(this.x, H - 130, 'バリア！', '#00FFFF', 16);
        }
        this.dead = true;
      }
    }
  }

  takeDamage(dmg) {
    this.hp -= dmg;
    if (this.hp <= 0) {
      this.hp = 0;
      this.dead = true;
      gs.stagePointsEarned += this.pts;
      gs.evoGauge = Math.min(100, gs.evoGauge + (this.type === 'boss' ? 50 : 12));
      spawnParticles(this.x, this.y, 'poof', 8);
      return true;
    }
    spawnParticles(this.x, this.y, 'hit', 2);
    return false;
  }
}

// ── PROJECTILE ────────────────────────────────────────────────
class Projectile {
  constructor(x, y, tx, ty, evolved) {
    this.x = x; this.y = y;
    this.evolved = evolved;
    const dx = tx - x, dy = ty - y;
    const d = Math.sqrt(dx * dx + dy * dy) || 1;
    const spd = evolved ? 7 : 11;
    this.vx = (dx / d) * spd;
    this.vy = (dy / d) * spd;
    this.size = evolved ? 18 : 12;
    this.life = 90;
    this.dead = false;
    this.rot = Math.atan2(dy, dx);
  }

  update() {
    this.x += this.vx;
    this.y += this.vy;
    this.life--;
    if (this.life <= 0 || this.x < -20 || this.x > W + 20 || this.y < -20 || this.y > H + 20) {
      this.dead = true;
      return;
    }
    for (const e of enemies) {
      if (e.dead) continue;
      const dx = this.x - e.x, dy = this.y - e.y;
      if (Math.sqrt(dx * dx + dy * dy) < e.size * 0.75 + this.size * 0.5) {
        if (this.evolved) this.explode();
        else e.takeDamage(2);
        this.dead = true;
        break;
      }
    }
  }

  explode() {
    spawnParticles(this.x, this.y, 'explosion', 14);
    for (const e of enemies) {
      if (e.dead) continue;
      const dx = this.x - e.x, dy = this.y - e.y;
      if (Math.sqrt(dx * dx + dy * dy) < 90) e.takeDamage(4);
    }
    gs.earthHP = Math.min(100, gs.earthHP + 3);
    addFloat(this.x, this.y - 20, '+HP回復', '#2ECC71', 16);
  }
}

// ── PARTICLE ──────────────────────────────────────────────────
class Particle {
  constructor(x, y, type) {
    this.x = x; this.y = y; this.type = type;
    switch (type) {
      case 'poof':
        this.vx = (Math.random() - 0.5) * 3;
        this.vy = -Math.random() * 3 - 0.5;
        this.size = 14 + Math.random() * 14;
        this.life = this.maxLife = 45 + Math.random() * 20;
        this.color = ['#ccc', '#aaa', '#eee'][~~(Math.random() * 3)];
        break;
      case 'hit':
        this.vx = (Math.random() - 0.5) * 6;
        this.vy = (Math.random() - 0.5) * 6;
        this.size = 5 + Math.random() * 7;
        this.life = this.maxLife = 18;
        this.color = '#FFD700';
        break;
      case 'hit_earth':
        this.vx = (Math.random() - 0.5) * 5;
        this.vy = -Math.random() * 4 - 1;
        this.size = 8 + Math.random() * 10;
        this.life = this.maxLife = 30;
        this.color = '#FF4444';
        break;
      case 'explosion':
        this.vx = (Math.random() - 0.5) * 9;
        this.vy = (Math.random() - 0.5) * 9;
        this.size = 10 + Math.random() * 18;
        this.life = this.maxLife = 35;
        this.color = ['#FF6B00', '#FFD700', '#FF4444', '#FFF'][~~(Math.random() * 4)];
        break;
      case 'boss_beam':
        this.vx = (Math.random() - 0.5) * 5;
        this.vy = 2 + Math.random() * 4;
        this.size = 10;
        this.life = this.maxLife = 30;
        this.color = '#9B59B6';
        break;
      default:
        this.vx = 0; this.vy = -1;
        this.size = 8; this.life = this.maxLife = 30;
        this.color = '#fff';
    }
  }

  update() {
    this.x += this.vx;
    this.y += this.vy;
    if (this.type !== 'poof') this.vy += 0.15;
    this.life--;
  }

  draw() {
    const a = this.life / this.maxLife;
    ctx.globalAlpha = a;
    ctx.fillStyle = this.color;
    if (this.type === 'poof') {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size * (1.2 - a * 0.5), 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.beginPath();
      ctx.arc(this.x, this.y, Math.max(1, this.size * a), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
}

function spawnParticles(x, y, type, n) {
  for (let i = 0; i < n; i++) particles.push(new Particle(x, y, type));
}

function addFloat(x, y, text, color, size) {
  floatingTexts.push({ x, y, text, color, size, life: 80, vy: -1.2 });
}

// ── DRAW HELPERS ──────────────────────────────────────────────
function rrect(x, y, w, h, r, fill, stroke, lw = 2) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
}

// ── DRAW: CHICK ───────────────────────────────────────────────
function drawChick(x, y, sz = 40, evolved = false, acc = null) {
  ctx.save();
  ctx.translate(x, y);

  // Comb (evolved only)
  if (evolved) {
    ctx.fillStyle = '#E74C3C';
    ctx.strokeStyle = '#922B21';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-7, -sz * 0.72);
    ctx.quadraticCurveTo(-13, -sz * 1.0, -4, -sz * 0.88);
    ctx.quadraticCurveTo(0, -sz * 1.12, 4, -sz * 0.88);
    ctx.quadraticCurveTo(13, -sz * 1.0, 7, -sz * 0.72);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
  }

  // Body
  ctx.fillStyle = '#FFE135';
  ctx.strokeStyle = '#C8960C';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.ellipse(0, sz * 0.1, sz * 0.52, sz * 0.48, 0, 0, Math.PI * 2);
  ctx.fill(); ctx.stroke();

  // Head
  ctx.beginPath();
  ctx.arc(0, -sz * 0.3, sz * 0.36, 0, Math.PI * 2);
  ctx.fill(); ctx.stroke();

  // Wing left
  ctx.fillStyle = '#FFCD00';
  ctx.beginPath();
  ctx.ellipse(-sz * 0.52, sz * 0.08, sz * 0.18, sz * 0.26, -0.4, 0, Math.PI * 2);
  ctx.fill(); ctx.stroke();
  // Wing right
  ctx.beginPath();
  ctx.ellipse(sz * 0.52, sz * 0.08, sz * 0.18, sz * 0.26, 0.4, 0, Math.PI * 2);
  ctx.fill(); ctx.stroke();

  // Wattle (evolved)
  if (evolved) {
    ctx.fillStyle = '#E74C3C';
    ctx.strokeStyle = '#922B21';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(sz * 0.12, -sz * 0.1, sz * 0.1, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
  }

  // Eyes
  ctx.fillStyle = '#2C2C2C';
  ctx.beginPath();
  ctx.arc(-sz * 0.12, -sz * 0.33, sz * 0.07, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.arc(sz * 0.12, -sz * 0.33, sz * 0.07, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.beginPath();
  ctx.arc(-sz * 0.09, -sz * 0.36, sz * 0.03, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.arc(sz * 0.15, -sz * 0.36, sz * 0.03, 0, Math.PI * 2); ctx.fill();

  // Beak
  ctx.fillStyle = '#FF8C00';
  ctx.strokeStyle = '#CC6600';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(-sz * 0.1, -sz * 0.22);
  ctx.lineTo(sz * 0.1, -sz * 0.22);
  ctx.lineTo(0, -sz * 0.1);
  ctx.closePath();
  ctx.fill(); ctx.stroke();

  // Feet
  ctx.strokeStyle = '#FF8C00';
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  [[-sz*0.18, sz*0.55], [sz*0.18, sz*0.55]].forEach(([fx, fy]) => {
    ctx.beginPath(); ctx.moveTo(fx, fy);
    ctx.lineTo(fx - sz*0.12, fy + sz*0.12); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(fx, fy);
    ctx.lineTo(fx + sz*0.12, fy + sz*0.12); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(fx, fy);
    ctx.lineTo(fx, fy + sz*0.16); ctx.stroke();
  });

  // Accessories
  if (acc === 'glasses') {
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(-sz*0.12, -sz*0.33, sz*0.14, 0, Math.PI*2); ctx.stroke();
    ctx.beginPath(); ctx.arc(sz*0.12, -sz*0.33, sz*0.14, 0, Math.PI*2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-sz*0.02, -sz*0.33); ctx.lineTo(sz*0.02, -sz*0.33); ctx.stroke();
  } else if (acc === 'nurse') {
    rrect(-sz*0.3, -sz*0.72, sz*0.6, sz*0.28, 3, '#fff', '#999', 1.5);
    ctx.fillStyle = '#FF6B6B';
    ctx.fillRect(-sz*0.05, -sz*0.7, sz*0.1, sz*0.22);
    ctx.fillRect(-sz*0.15, -sz*0.56, sz*0.3, sz*0.08);
  } else if (acc === 'helmet') {
    ctx.fillStyle = '#4ECDC4';
    ctx.strokeStyle = '#2E9E96';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, -sz*0.3, sz*0.4, Math.PI, 0);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#2E9E96';
    ctx.fillRect(-sz*0.4, -sz*0.36, sz*0.8, sz*0.09);
  }

  ctx.restore();
}

// ── DRAW: CROW ────────────────────────────────────────────────
function drawCrow(e) {
  ctx.save();
  ctx.translate(e.x, e.y + Math.sin(e.wobble) * 4);
  const s = e.size;

  // Wings
  ctx.fillStyle = '#1A1A1A';
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-s*0.1, -s*0.05);
  ctx.quadraticCurveTo(-s*0.85, -s*0.45, -s*0.65, s*0.25);
  ctx.quadraticCurveTo(-s*0.35, s*0.1, -s*0.1, s*0.05);
  ctx.closePath();
  ctx.fill(); ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(s*0.1, -s*0.05);
  ctx.quadraticCurveTo(s*0.85, -s*0.45, s*0.65, s*0.25);
  ctx.quadraticCurveTo(s*0.35, s*0.1, s*0.1, s*0.05);
  ctx.closePath();
  ctx.fill(); ctx.stroke();

  // Body
  ctx.fillStyle = '#2C2C2C';
  ctx.beginPath();
  ctx.ellipse(0, 0, s*0.45, s*0.4, 0, 0, Math.PI*2);
  ctx.fill(); ctx.stroke();

  // Head
  ctx.beginPath();
  ctx.arc(s*0.28, -s*0.28, s*0.28, 0, Math.PI*2);
  ctx.fill(); ctx.stroke();

  // Beak
  ctx.fillStyle = '#333';
  ctx.beginPath();
  ctx.moveTo(s*0.5, -s*0.22);
  ctx.lineTo(s*0.82, -s*0.16);
  ctx.lineTo(s*0.5, -s*0.08);
  ctx.closePath();
  ctx.fill();

  // Evil eye
  ctx.fillStyle = '#FF0000';
  ctx.beginPath();
  ctx.arc(s*0.33, -s*0.3, s*0.09, 0, Math.PI*2);
  ctx.fill();
  ctx.fillStyle = '#000';
  ctx.beginPath();
  ctx.arc(s*0.35, -s*0.3, s*0.05, 0, Math.PI*2);
  ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.beginPath();
  ctx.arc(s*0.37, -s*0.32, s*0.02, 0, Math.PI*2);
  ctx.fill();

  // HP bar
  if (e.maxHp > 1) {
    const bw = s * 1.4, bx = -bw/2, by = s * 0.58;
    rrect(bx-1, by-1, bw+2, 10, 3, '#222', null);
    const ratio = e.hp / e.maxHp;
    rrect(bx, by, bw * ratio, 8, 2,
      ratio > 0.5 ? '#2ECC71' : ratio > 0.25 ? '#F39C12' : '#E74C3C', null);
  }

  ctx.restore();
}

// ── DRAW: BOSS ────────────────────────────────────────────────
function drawBoss(e) {
  ctx.save();
  ctx.translate(e.x, e.y);
  const s = e.size;

  // Beam warning
  if (e.bossAttackTimer > 95) {
    ctx.globalAlpha = (e.bossAttackTimer - 95) / 25 * 0.4;
    const g = ctx.createLinearGradient(0, s*0.4, 0, H - e.y);
    g.addColorStop(0, 'rgba(155,89,182,0.8)');
    g.addColorStop(1, 'rgba(155,89,182,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(-35, s*0.4); ctx.lineTo(35, s*0.4);
    ctx.lineTo(90, H - e.y); ctx.lineTo(-90, H - e.y);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // UFO dish
  ctx.fillStyle = '#707070';
  ctx.strokeStyle = '#444';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.ellipse(0, s*0.1, s*0.95, s*0.24, 0, 0, Math.PI*2);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#909090';
  ctx.beginPath();
  ctx.ellipse(0, s*0.08, s*0.7, s*0.16, 0, 0, Math.PI*2);
  ctx.fill();

  // UFO dome
  ctx.fillStyle = 'rgba(100,220,255,0.55)';
  ctx.strokeStyle = '#55BBDD';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.ellipse(0, -s*0.05, s*0.5, s*0.5, 0, Math.PI, 0);
  ctx.fill(); ctx.stroke();

  // Rotating lights
  ['#FF3333','#33FF33','#3333FF','#FFFF33','#FF33FF'].forEach((c, i) => {
    const a = (gs.frame * 0.06) + i * (Math.PI * 2 / 5);
    ctx.fillStyle = c;
    ctx.beginPath();
    ctx.arc(Math.cos(a)*s*0.62, s*0.08 + Math.sin(a)*s*0.12, 5, 0, Math.PI*2);
    ctx.fill();
  });

  // Crow on top
  ctx.fillStyle = '#111';
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(0, -s*0.62, s*0.22, s*0.18, 0, 0, Math.PI*2);
  ctx.fill(); ctx.stroke();
  ctx.beginPath();
  ctx.arc(s*0.15, -s*0.82, s*0.16, 0, Math.PI*2);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#FF0000';
  ctx.beginPath();
  ctx.arc(s*0.2, -s*0.83, 4, 0, Math.PI*2);
  ctx.fill();
  ctx.fillStyle = '#000';
  ctx.beginPath();
  ctx.arc(s*0.21, -s*0.83, 2.2, 0, Math.PI*2);
  ctx.fill();
  // Boss beak
  ctx.fillStyle = '#333';
  ctx.beginPath();
  ctx.moveTo(s*0.28, -s*0.78);
  ctx.lineTo(s*0.45, -s*0.75);
  ctx.lineTo(s*0.28, -s*0.7);
  ctx.closePath(); ctx.fill();

  // HP bar
  const bw = s * 2.2, bx = -bw/2, by = s * 0.45;
  rrect(bx-2, by-2, bw+4, 18, 5, '#222', '#444', 2);
  const ratio = e.hp / e.maxHp;
  rrect(bx, by, bw * ratio, 14, 4, '#E74C3C', null);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 11px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`${e.hp}/${e.maxHp}`, 0, by + 11);

  // BOSS label
  ctx.fillStyle = '#FF4444';
  ctx.font = 'bold 13px "Kosugi Maru",sans-serif';
  ctx.fillText('★ 巨大カラスUFO ★', 0, -s*1.05);

  ctx.restore();
}

// ── DRAW: EARTH ───────────────────────────────────────────────
function drawEarth(x, y, r) {
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI*2);
  ctx.fillStyle = '#1A6FBF'; ctx.fill();
  ctx.fillStyle = '#2ECC71';
  [[-.18,-.08,.28,.38],[.22,.12,.32,.22],[-.1,.3,.18,.14]].forEach(([ex,ey,ew,eh]) => {
    ctx.beginPath();
    ctx.ellipse(r*ex, r*ey, r*ew, r*eh, 0.6, 0, Math.PI*2);
    ctx.fill();
  });
  ctx.strokeStyle = '#1A4A8A'; ctx.lineWidth = 2.5;
  ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI*2); ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.28)';
  ctx.beginPath(); ctx.ellipse(-r*0.22, -r*0.22, r*0.18, r*0.12, -0.5, 0, Math.PI*2); ctx.fill();
  ctx.restore();
}

// ── DRAW: EGG ─────────────────────────────────────────────────
function drawEgg(x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = '#FFFDE7';
  ctx.strokeStyle = '#FF8C00';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.ellipse(0, 0, 10, 14, 0, 0, Math.PI*2);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#FF8C00';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('✨', 0, 0);
  ctx.restore();
}

// ── DRAW: BACKGROUND ──────────────────────────────────────────
function drawBg() {
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, '#06061A');
  g.addColorStop(0.7, '#101040');
  g.addColorStop(1, '#1A0A30');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < 55; i++) {
    const sx = (i * 141 + 47) % W;
    const sy = (i * 233 + 31) % (H * 0.78);
    ctx.globalAlpha = (Math.sin(gs.frame * 0.04 + i) * 0.25 + 0.65) * 0.75;
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(sx, sy, 0.8 + (i % 3) * 0.4, 0, Math.PI*2); ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function drawGround() {
  const g = ctx.createLinearGradient(0, H-120, 0, H);
  g.addColorStop(0, '#27AE60'); g.addColorStop(1, '#1E8449');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.moveTo(0, H-105);
  ctx.quadraticCurveTo(W*.25, H-122, W*.5, H-110);
  ctx.quadraticCurveTo(W*.75, H-98, W, H-115);
  ctx.lineTo(W, H); ctx.lineTo(0, H);
  ctx.closePath(); ctx.fill();
}

// ── UI ELEMENTS ───────────────────────────────────────────────
function drawEarthBar() {
  drawEarth(28, 32, 22);
  const bx = 57, by = 18, bw = W - 72, bh = 26;
  rrect(bx-1, by-1, bw+2, bh+2, bh/2+1, '#111', '#444', 1.5);
  const ratio = gs.earthHP / 100;
  const col = ratio > 0.55 ? '#2ECC71' : ratio > 0.3 ? '#F39C12' : '#E74C3C';
  if (ratio > 0) rrect(bx, by, bw * ratio, bh, bh/2, col, null);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 12px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`地球HP  ${gs.earthHP}`, bx + bw/2, by + bh * 0.72);
  if (gs.barrierActive) {
    ctx.globalAlpha = 0.5 + Math.sin(gs.frame * 0.12) * 0.3;
    ctx.strokeStyle = '#00FFFF'; ctx.lineWidth = 3;
    rrect(bx-3, by-3, bw+6, bh+6, bh/2+3, null, '#00FFFF', 3);
    ctx.globalAlpha = 1;
  }
}

function drawEvoBar() {
  const bx = 15, by = 57, bw = W-30, bh = 13;
  ctx.fillStyle = '#ccc'; ctx.font = 'bold 9px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'left'; ctx.fillText('進化ゲージ', bx, by-2);
  rrect(bx-1, by-1, bw+2, bh+2, bh/2+1, '#111', '#333', 1);
  if (gs.evoGauge > 0) {
    rrect(bx, by, bw * (gs.evoGauge/100), bh, bh/2,
      gs.isEvolved ? '#FF6B35' : '#FFD700', null);
  }
  if (gs.isEvolved) {
    ctx.fillStyle = '#FF6B35'; ctx.textAlign = 'right';
    ctx.fillText(`にわトリ変身中！ ${Math.ceil(gs.evoTimer/60)}s`, W-15, by-2);
  }
}

function drawHUD() {
  // Stage badge
  rrect(W-92, 78, 82, 26, 6, 'rgba(0,0,0,0.55)', '#444', 1);
  ctx.fillStyle = '#FFD700'; ctx.font = 'bold 11px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`STAGE ${gs.stage}`, W-51, 93);
  ctx.fillStyle = '#888'; ctx.font = '9px sans-serif';
  ctx.fillText(`WAVE ${Math.min(currentWave+1, stageConfig?.waves||1)}/${stageConfig?.waves||1}`, W-51, 103);
  // Points
  rrect(10, 78, 78, 26, 6, 'rgba(0,0,0,0.55)', '#444', 1);
  ctx.fillStyle = '#FFD700'; ctx.font = 'bold 11px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`🐤 ${gs.piyoPoints}`, 49, 95);
}

// ── COMPANION BUTTONS ─────────────────────────────────────────
const BTNS = [
  { id: 'gunshi', label: '軍師ひよこ', x: 50,    color: '#8B4513', acc: 'glasses' },
  { id: 'nurse',  label: 'ナースひよこ', x: W/2,  color: '#C0397B', acc: 'nurse'   },
  { id: 'barrier',label: 'バリアひよこ', x: W-50, color: '#1A5DAD', acc: 'helmet'  },
];
const BTN_Y = H - 58, BTN_R = 32;

function drawBtns() {
  BTNS.forEach(btn => {
    const unlocked = upg[btn.id];
    const cd = cds[btn.id];
    const cdMax = CD_MAX[btn.id];

    // Shadow
    ctx.beginPath(); ctx.arc(btn.x, BTN_Y+3, BTN_R, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fill();

    // Circle
    ctx.beginPath(); ctx.arc(btn.x, BTN_Y, BTN_R, 0, Math.PI*2);
    ctx.fillStyle = unlocked ? (cd>0 ? '#333' : btn.color) : '#1A1A1A';
    ctx.fill();
    ctx.strokeStyle = unlocked ? (cd>0 ? '#555' : '#fff') : '#333';
    ctx.lineWidth = 2.5; ctx.stroke();

    // Cooldown pie
    if (unlocked && cd > 0) {
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = '#000';
      ctx.beginPath();
      ctx.moveTo(btn.x, BTN_Y);
      ctx.arc(btn.x, BTN_Y, BTN_R, -Math.PI/2, -Math.PI/2 + Math.PI*2*(cd/cdMax));
      ctx.closePath(); ctx.fill();
      ctx.globalAlpha = 1;
      ctx.fillStyle = '#fff'; ctx.font = 'bold 13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(Math.ceil(cd/60)+'s', btn.x, BTN_Y+5);
    } else if (unlocked) {
      drawChick(btn.x, BTN_Y-2, 24, false, btn.acc);
    } else {
      ctx.fillStyle = '#555'; ctx.font = '22px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('🔒', btn.x, BTN_Y); ctx.textBaseline = 'alphabetic';
    }

    // Label
    ctx.fillStyle = unlocked ? '#ddd' : '#444';
    ctx.font = '9px "Kosugi Maru",sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(btn.label, btn.x, BTN_Y + BTN_R + 12);
  });
}

// ── SKILLS ────────────────────────────────────────────────────
function activateSkill(id) {
  if (!upg[id] || cds[id] > 0) return;
  cds[id] = CD_MAX[id];
  switch (id) {
    case 'gunshi':
      enemies.forEach(e => { if (!e.dead) { e.takeDamage(20); spawnParticles(e.x, e.y, 'explosion', 6); } });
      spawnParticles(W/2, H/2, 'explosion', 18);
      addFloat(W/2, H*0.38, '一斉突撃！', '#FF4444', 30);
      break;
    case 'nurse':
      gs.earthHP = Math.min(100, gs.earthHP + 45);
      spawnParticles(W/2, H*0.3, 'hit', 20);
      addFloat(W/2, H*0.38, '地球大回復！', '#FF69B4', 28);
      break;
    case 'barrier':
      gs.barrierActive = true;
      gs.barrierTimer = 300;
      addFloat(W/2, H*0.38, '絶対防壁！', '#00FFFF', 28);
      break;
  }
}

// ── WAVE SYSTEM ───────────────────────────────────────────────
function startStage(s) {
  gs.stage = s;
  stageConfig = getStageConfig(s);
  currentWave = 0; waveSpawned = 0; waveTimer = 0; clearDelay = 0;
  enemies = []; projectiles = []; particles = []; floatingTexts = [];
  gs.earthHP = 100; gs.evoGauge = 0;
  gs.isEvolved = false; gs.evoTimer = 0;
  gs.stagePointsEarned = 0;
  gs.barrierActive = false; gs.barrierTimer = 0;
  cds = { gunshi: 0, nurse: 0, barrier: 0 };
  gs.attackCooldown = 0;
  gs.state = 'battle';
}

function updateWaves() {
  if (clearDelay > 0) { clearDelay--; return; }

  const count = stageConfig.counts[currentWave] || 0;
  if (waveSpawned < count) {
    waveTimer++;
    const interval = gs.stage === 10 ? 240 : 90 - gs.stage * 4;
    if (waveTimer >= Math.max(interval, 30)) {
      waveTimer = 0;
      const types = stageConfig.types[currentWave];
      const type = types[~~(Math.random() * types.length)];
      const x = 50 + Math.random() * (W - 100);
      enemies.push(new Enemy(type, x, type === 'boss' ? 180 : -55));
      waveSpawned++;
    }
  }

  const allGone = enemies.length === 0 && waveSpawned >= count;
  if (allGone) {
    if (currentWave < stageConfig.waves - 1) {
      currentWave++; waveSpawned = 0; waveTimer = 0;
      addFloat(W/2, H*0.38, `WAVE ${currentWave+1}！`, '#FFD700', 24);
    } else {
      // Stage clear
      clearDelay = 130;
      const earned = gs.stagePointsEarned + stageConfig.reward;
      gs.lastEarnedPoints = earned;
      gs.piyoPoints += earned;
      addFloat(W/2, H*0.4, 'STAGE CLEAR!', '#FFD700', 32);
      spawnParticles(W/2, H/2, 'explosion', 20);
    }
  }
}

// ── TAP HANDLING ──────────────────────────────────────────────
const CHICK_X = W/2, CHICK_Y = H - 140;

function handleBattleTap(tx, ty) {
  // Check buttons
  for (const btn of BTNS) {
    const dx = tx - btn.x, dy = ty - BTN_Y;
    if (Math.sqrt(dx*dx + dy*dy) < BTN_R + 4) { activateSkill(btn.id); return; }
  }
  // Attack
  if (gs.attackCooldown > 0) return;
  const cooldowns_frames = [55, 42, 30, 20, 12][upg.speed - 1];
  gs.attackCooldown = cooldowns_frames;
  projectiles.push(new Projectile(CHICK_X, CHICK_Y - 20, tx, ty, gs.isEvolved));
  spawnParticles(CHICK_X + (Math.random()-0.5)*30, CHICK_Y - 50, 'hit', 1);
  addFloat(CHICK_X + (Math.random()-0.5)*40, CHICK_Y - 55, 'ピヨ！', '#FF6B6B', 16);
}

// ── SCREENS ───────────────────────────────────────────────────
function drawTitle() {
  drawBg();

  // Title text
  ctx.textAlign = 'center';
  ctx.shadowColor = '#FF6B00'; ctx.shadowBlur = 14;
  ctx.fillStyle = '#FFD700';
  ctx.font = 'bold 36px "Kosugi Maru",sans-serif';
  ctx.fillText('ひよこ防衛軍', W/2, 155);
  ctx.shadowColor = '#FF9900'; ctx.shadowBlur = 8;
  ctx.fillStyle = '#FFA040';
  ctx.font = 'bold 17px "Kosugi Maru",sans-serif';
  ctx.fillText('～地球救出大作戦～', W/2, 190);
  ctx.shadowBlur = 0;

  // Hero chick
  drawChick(W/2, 310, 72, false);
  // Enemy crows
  drawCrow({ x:95, y:270, size:32, hp:3, maxHp:3, wobble: gs.frame*0.05, type:'crow_s' });
  drawCrow({ x:295, y:260, size:32, hp:3, maxHp:3, wobble: gs.frame*0.05+1, type:'crow_s' });

  // Earth below
  drawEarth(W/2, 450, 50);

  // Start button
  const pulse = Math.sin(gs.frame * 0.07) * 4;
  rrect(W/2-110, 530+pulse, 220, 56, 14, '#E84B2B', '#FFD700', 3);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 22px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('タップしてはじめる', W/2, 563+pulse);

  ctx.fillStyle = '#888'; ctx.font = '12px "Kosugi Maru",sans-serif';
  ctx.fillText('タップで攻撃！地球を守れ！', W/2, 640);
  ctx.fillStyle = '#444'; ctx.font = '10px sans-serif';
  ctx.fillText('PIYO-DEFENSE  v1.0', W/2, H-35);
}

function drawBattle() {
  drawBg();
  drawGround();
  drawEarthBar();
  drawEvoBar();
  drawHUD();

  // Enemies
  enemies.forEach(e => {
    if (e.type === 'boss') drawBoss(e);
    else drawCrow(e);
  });

  // Projectiles
  projectiles.forEach(p => {
    if (p.evolved) { drawEgg(p.x, p.y); }
    else {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot + Math.PI/2);
      drawChick(0, 0, 13, false);
      ctx.restore();
    }
  });

  // Particles
  particles.forEach(p => p.draw());

  // Floating texts
  floatingTexts.forEach(ft => {
    ctx.globalAlpha = Math.min(1, ft.life / 25);
    ctx.fillStyle = ft.color;
    ctx.font = `bold ${ft.size}px "Kosugi Maru",sans-serif`;
    ctx.textAlign = 'center';
    ctx.strokeStyle = 'rgba(0,0,0,0.7)'; ctx.lineWidth = 4;
    ctx.strokeText(ft.text, ft.x, ft.y);
    ctx.fillText(ft.text, ft.x, ft.y);
    ctx.globalAlpha = 1;
  });

  // Player chick
  const bob = Math.sin(gs.frame * 0.1) * 3;
  if (gs.isEvolved) {
    ctx.globalAlpha = 0.18 + Math.sin(gs.frame*0.12)*0.08;
    ctx.fillStyle = '#FFD700';
    ctx.beginPath(); ctx.arc(CHICK_X, CHICK_Y, 65, 0, Math.PI*2); ctx.fill();
    ctx.globalAlpha = 1;
  }
  drawChick(CHICK_X, CHICK_Y + bob, gs.isEvolved ? 56 : 44, gs.isEvolved);

  // Barrier dome
  if (gs.barrierActive) {
    ctx.globalAlpha = 0.22 + Math.sin(gs.frame*0.15)*0.08;
    ctx.strokeStyle = '#00FFFF'; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.arc(W/2, H*0.48, W*0.7, 0, Math.PI*2); ctx.stroke();
    ctx.globalAlpha = 0.06;
    ctx.fillStyle = '#00FFFF';
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  drawBtns();
}

// ── SHOP SCREEN ───────────────────────────────────────────────
function buildShopItems() {
  shopItems = [];
  if (upg.speed < 5) shopItems.push({ id:'speed',   icon:'⚡', name:`スピードアップ Lv${upg.speed}→${upg.speed+1}`, desc:'攻撃の連打速度アップ', cost:[0,50,100,200,350][upg.speed] });
  if (upg.evoTime < 5) shopItems.push({ id:'evoTime', icon:'🔥', name:`変身延長 Lv${upg.evoTime}→${upg.evoTime+1}`,   desc:'にわトリの変身時間アップ', cost:[0,50,100,200,350][upg.evoTime] });
  if (!upg.gunshi)  shopItems.push({ id:'gunshi',  icon:null, acc:'glasses', name:'軍師ひよこを雇用', desc:'スキル「一斉突撃」が使える', cost:80 });
  if (!upg.nurse)   shopItems.push({ id:'nurse',   icon:null, acc:'nurse',   name:'ナースひよこを雇用', desc:'スキル「地球大回復」が使える', cost:80 });
  if (!upg.barrier) shopItems.push({ id:'barrier', icon:null, acc:'helmet',  name:'バリアひよこを雇用', desc:'スキル「絶対防壁」が使える', cost:80 });
  // Assign y positions
  let y = 140;
  shopItems.forEach(it => { it._y = y; y += 82; });
}

function drawShop() {
  const g = ctx.createLinearGradient(0,0,0,H);
  g.addColorStop(0,'#12061E'); g.addColorStop(1,'#061218');
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);

  ctx.textAlign = 'center';
  ctx.shadowColor = '#FF6B00'; ctx.shadowBlur = 10;
  ctx.fillStyle = '#FFD700'; ctx.font = 'bold 30px "Kosugi Maru",sans-serif';
  ctx.fillText('ショップ', W/2, 52);
  ctx.shadowBlur = 0;

  ctx.fillStyle = '#ccc'; ctx.font = '14px "Kosugi Maru",sans-serif';
  ctx.fillText(`ひよこ豆ポイント：${gs.piyoPoints} pts`, W/2, 80);
  ctx.fillStyle = '#7EC8E3'; ctx.font = '12px "Kosugi Maru",sans-serif';
  ctx.fillText(`今回獲得：+${gs.lastEarnedPoints} pts`, W/2, 100);

  buildShopItems();

  if (shopItems.length === 0) {
    ctx.fillStyle = '#aaa'; ctx.font = '16px "Kosugi Maru",sans-serif';
    ctx.fillText('アップグレード完了！', W/2, H/2 - 30);
  }

  shopItems.forEach(it => {
    const affordable = gs.piyoPoints >= it.cost;
    rrect(12, it._y, W-24, 72, 10, affordable ? '#1C2A40' : '#111', affordable ? '#4488BB' : '#333', 2);

    // Icon area
    ctx.beginPath(); ctx.arc(48, it._y+36, 26, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fill();

    if (it.icon) {
      ctx.font = '24px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(it.icon, 48, it._y+36); ctx.textBaseline = 'alphabetic';
    } else {
      drawChick(48, it._y+34, 23, false, it.acc);
    }

    ctx.fillStyle = '#fff'; ctx.font = 'bold 13px "Kosugi Maru",sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(it.name, 82, it._y + 29);
    ctx.fillStyle = '#888'; ctx.font = '11px "Kosugi Maru",sans-serif';
    ctx.fillText(it.desc, 82, it._y + 49);
    ctx.textAlign = 'right';
    ctx.fillStyle = affordable ? '#FFD700' : '#555';
    ctx.font = 'bold 14px "Kosugi Maru",sans-serif';
    ctx.fillText(`${it.cost} pts`, W-18, it._y + 40);
  });

  // Next button
  const nextY = H - 100;
  const label = gs.stage >= 10 ? 'タイトルへ' : `STAGE ${gs.stage + 1} へ進む ▶`;
  rrect(W/2-115, nextY, 230, 56, 14, '#E84B2B', '#FFD700', 3);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 20px "Kosugi Maru",sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(label, W/2, nextY + 34);
}

function handleShopTap(tx, ty) {
  const nextY = H - 100;
  if (ty >= nextY && ty <= nextY+56 && tx >= W/2-115 && tx <= W/2+115) {
    if (gs.stage >= 10) { resetGame(); gs.state = 'title'; }
    else startStage(gs.stage + 1);
    return;
  }
  shopItems.forEach(it => {
    if (ty >= it._y && ty <= it._y+72 && tx >= 12 && tx <= W-12) {
      if (gs.piyoPoints >= it.cost) {
        gs.piyoPoints -= it.cost;
        if (it.id === 'speed') upg.speed = Math.min(5, upg.speed+1);
        else if (it.id === 'evoTime') upg.evoTime = Math.min(5, upg.evoTime+1);
        else upg[it.id] = true;
        buildShopItems();
      }
    }
  });
}

// ── GAME OVER ─────────────────────────────────────────────────
function drawGameOver() {
  drawBg();
  ctx.fillStyle = 'rgba(0,0,0,0.72)'; ctx.fillRect(0,0,W,H);
  ctx.textAlign = 'center';
  ctx.shadowColor = '#F00'; ctx.shadowBlur = 18;
  ctx.fillStyle = '#FF4444'; ctx.font = 'bold 46px "Kosugi Maru",sans-serif';
  ctx.fillText('EARTH CRASH!', W/2, H*0.35);
  ctx.shadowBlur = 0;

  drawEarth(W/2, H*0.52, 55);
  // Crack
  ctx.strokeStyle = '#FF4444'; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.moveTo(W/2-8, H*0.52-48); ctx.lineTo(W/2+6, H*0.52+10); ctx.lineTo(W/2-12, H*0.52+52); ctx.stroke();

  ctx.fillStyle = '#aaa'; ctx.font = '16px "Kosugi Maru",sans-serif';
  ctx.fillText(`STAGE ${gs.stage} で力尽きた...`, W/2, H*0.68);
  ctx.fillText(`獲得ポイント：${gs.piyoPoints} pts`, W/2, H*0.72);

  rrect(W/2-95, H-130, 190, 52, 13, '#E84B2B', '#FFD700', 2.5);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 19px "Kosugi Maru",sans-serif';
  ctx.fillText('タイトルへ', W/2, H-98);
}

// ── ENDING ────────────────────────────────────────────────────
function drawEnding() {
  const g = ctx.createLinearGradient(0,0,0,H);
  g.addColorStop(0,'#001040'); g.addColorStop(1,'#001A08');
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);

  for (let i = 0; i < 60; i++) {
    const sx = (i*141+47)%W, sy = (i*233+31)%H;
    ctx.globalAlpha = (Math.sin(gs.frame*0.04+i)*0.3+0.7)*0.8;
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(sx, sy, 1+(i%3)*0.4, 0, Math.PI*2); ctx.fill();
  }
  ctx.globalAlpha = 1;

  // Fireworks
  [[120,220],[270,190],[195,320]].forEach(([fx,fy], k) => {
    const t = gs.frame * 0.04 + k * 2.2;
    ['#FF4444','#FFD700','#4ECDC4','#FF69B4','#fff'].forEach((c, j) => {
      const a = t + j * (Math.PI*2/5);
      const r = 25 * Math.abs(Math.sin(t * 0.7));
      ctx.globalAlpha = Math.max(0, Math.abs(Math.sin(t)));
      ctx.fillStyle = c;
      ctx.beginPath(); ctx.arc(fx+Math.cos(a)*r, fy+Math.sin(a)*r, 3, 0, Math.PI*2); ctx.fill();
    });
  });
  ctx.globalAlpha = 1;

  drawEarth(W/2, 200, 80);

  // Star badge
  ctx.fillStyle = '#FFD700'; ctx.font = '28px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('🌟', W/2, 115);

  // Hero
  drawChick(W/2, 390, 62, true);
  // Companions
  drawChick(W/2-95, 415, 36, false, 'glasses');
  drawChick(W/2+95, 415, 36, false, 'nurse');
  drawChick(W/2-40, 435, 30, false, 'helmet');

  ctx.textAlign = 'center';
  ctx.shadowColor = '#FF6B00'; ctx.shadowBlur = 12;
  ctx.fillStyle = '#FFD700'; ctx.font = 'bold 30px "Kosugi Maru",sans-serif';
  ctx.fillText('地球を救った！', W/2, 510);
  ctx.shadowBlur = 0;

  ctx.fillStyle = '#B8E8FF'; ctx.font = '16px "Kosugi Maru",sans-serif';
  ctx.fillText('ひよこたちのおかげで', W/2, 548);
  ctx.fillText('地球に平和が戻った！', W/2, 572);

  ctx.fillStyle = '#FFD700'; ctx.font = 'bold 15px "Kosugi Maru",sans-serif';
  ctx.fillText(`総獲得ポイント：${gs.piyoPoints} pts`, W/2, 615);

  rrect(W/2-95, H-112, 190, 52, 13, '#2C54AD', '#7EC8E3', 2.5);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 19px "Kosugi Maru",sans-serif';
  ctx.fillText('もう一度遊ぶ', W/2, H-80);
}

// ── RESET ────────────────────────────────────────────────────
function resetGame() {
  gs.piyoPoints = 0;
  upg = { speed: 1, evoTime: 1, gunshi: false, nurse: false, barrier: false };
}

// ── UPDATE ────────────────────────────────────────────────────
function update() {
  gs.frame++;
  if (gs.state !== 'battle') return;

  if (gs.attackCooldown > 0) gs.attackCooldown--;
  Object.keys(cds).forEach(k => { if (cds[k] > 0) cds[k]--; });

  if (gs.barrierActive) { gs.barrierTimer--; if (gs.barrierTimer <= 0) gs.barrierActive = false; }

  // Evolution trigger
  if (!gs.isEvolved && gs.evoGauge >= 100) {
    gs.isEvolved = true;
    const durs = [480, 600, 780, 960, 1200];
    gs.evoTimer = durs[upg.evoTime - 1];
    addFloat(W/2, H*0.4, 'にわトリに進化！', '#FFD700', 28);
    spawnParticles(CHICK_X, CHICK_Y, 'explosion', 16);
  }
  if (gs.isEvolved) {
    gs.evoTimer--;
    if (gs.evoTimer <= 0) {
      gs.isEvolved = false; gs.evoGauge = 0;
      addFloat(W/2, H*0.4, 'ひよこに戻った...', '#aaa', 18);
    }
  }

  enemies.forEach(e => { if (!e.dead) e.update(); });
  enemies = enemies.filter(e => !e.dead);

  projectiles.forEach(p => { if (!p.dead) p.update(); });
  projectiles = projectiles.filter(p => !p.dead);

  particles.forEach(p => p.update());
  particles = particles.filter(p => p.life > 0);

  floatingTexts.forEach(ft => { ft.y += ft.vy; ft.life--; });
  floatingTexts = floatingTexts.filter(ft => ft.life > 0);

  gs.earthHP = Math.max(0, Math.min(100, gs.earthHP));

  if (gs.earthHP <= 0) { gs.state = 'gameover'; return; }

  if (clearDelay > 0) {
    clearDelay--;
    if (clearDelay === 0) {
      if (gs.stage === 10) gs.state = 'ending';
      else gs.state = 'shop';
    }
    return;
  }

  updateWaves();
}

// ── DRAW LOOP ─────────────────────────────────────────────────
function draw() {
  ctx.clearRect(0, 0, W, H);
  switch (gs.state) {
    case 'title':    drawTitle();    break;
    case 'battle':   drawBattle();   break;
    case 'shop':     drawShop();     break;
    case 'gameover': drawGameOver(); break;
    case 'ending':   drawEnding();   break;
  }
}

// ── INPUT ─────────────────────────────────────────────────────
function handleInput(tx, ty) {
  switch (gs.state) {
    case 'title':
      startStage(1);
      break;
    case 'battle':
      handleBattleTap(tx, ty);
      break;
    case 'shop':
      handleShopTap(tx, ty);
      break;
    case 'gameover':
      resetGame();
      gs.state = 'title';
      break;
    case 'ending':
      if (ty > H - 112) { resetGame(); gs.state = 'title'; }
      break;
  }
}

canvas.addEventListener('touchstart', e => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  const sx = W / r.width, sy = H / r.height;
  const t = e.changedTouches[0];
  handleInput((t.clientX - r.left) * sx, (t.clientY - r.top) * sy);
}, { passive: false });

canvas.addEventListener('click', e => {
  const r = canvas.getBoundingClientRect();
  const sx = W / r.width, sy = H / r.height;
  handleInput((e.clientX - r.left) * sx, (e.clientY - r.top) * sy);
});

// ── MAIN LOOP ────────────────────────────────────────────────
function loop() { update(); draw(); requestAnimationFrame(loop); }
loop();
