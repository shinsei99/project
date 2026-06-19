'use strict';

// ── Canvas setup ─────────────────────────────────────────────────────────────
var canvas = document.getElementById('gameCanvas');
var ctx    = canvas.getContext('2d');
var W = 390, H = 844;
canvas.width  = W;
canvas.height = H;
setRenderCtx(ctx, W, H);

function resize() {
  var vh = window.innerHeight, vw = window.innerWidth;
  var ratio = W / H;
  var cw = vh * ratio, ch = vh;
  if (cw > vw) { cw = vw; ch = vw / ratio; }
  canvas.style.width  = cw + 'px';
  canvas.style.height = ch + 'px';
}
window.addEventListener('resize', resize);
resize();

SoundManager.init();

// ── Constants ────────────────────────────────────────────────────────────────
var CHICK_X = W / 2;
var CHICK_Y = H - 148;
var CD_MAX  = { gunshi: 600, nurse: 900, barrier: 750 };

// ── Game state ───────────────────────────────────────────────────────────────
var gs           = {};   // runtime state
var upg          = {};   // companion unlocks
var cds          = {};   // companion cooldowns
var enemies      = [];
var bullets      = [];
var particles    = [];
var floats       = [];

var wave         = 0;
var waveSpawned  = 0;
var waveTimer    = 0;
var waveTotal    = 0;
var clearDelay   = 0;

var score        = 0;
var kills        = 0;
var isNewHS      = false;
var level        = 1;
var xp           = 0;
var regenTimer   = 0;
var frame        = 0;
var levelChoices = [];

function xpToNext(lv) { return 5 + lv * 2; }

// ── Init ─────────────────────────────────────────────────────────────────────
function initGame() {
  gs = {
    state:        'battle',
    earthHP:      100,
    maxEarthHP:   100,
    evoGauge:     0,
    isEvolved:    false,
    evoTimer:     0,
    attackCooldown: 0,
    barrierActive:  false,
    barrierTimer:   0,
  };
  upg = { gunshi: false, nurse: false, barrier: false };
  cds = { gunshi: 0, nurse: 0, barrier: 0 };
  PlayerUpgrades.reset();
  enemies = []; bullets = []; particles = []; floats = [];
  wave = 0; waveSpawned = 0; waveTimer = 0; waveTotal = 0; clearDelay = 0;
  score = 0; kills = 0; isNewHS = false;
  level = 1; xp = 0; regenTimer = 0;
  startWave();
}

// ── Wave system ───────────────────────────────────────────────────────────────
function waveTypes(w) {
  if (w % 10 === 0) return ['boss'];
  var r = w % 10;
  if (r <= 3) return ['normal', 'normal', 'normal'];
  if (r <= 7) return ['normal', 'normal', 'normal', 'fast'];
  return ['normal', 'normal', 'fast', 'tank'];
}

function waveCount(w) {
  if (w % 10 === 0) return 1;
  return Math.min(4 + w, 26);
}

function startWave() {
  wave++;
  waveTotal    = waveCount(wave);
  waveSpawned  = 0;
  waveTimer    = 0;
  clearDelay   = 0;
  if (wave % 10 === 0) {
    SoundManager.bossAppear();
    SoundManager.startBgm('boss');
  } else {
    SoundManager.startBgm('battle');
  }
  addFloat(W/2, H*0.38, 'WAVE ' + wave + '!', '#FFD700', 26);
}

function spawnEnemy() {
  var types = waveTypes(wave);
  var type  = types[~~(Math.random() * types.length)];
  var x     = 55 + Math.random() * (W - 110);
  var y     = (type === 'boss') ? 190 : -60;
  enemies.push(new Enemy(type, x, y, wave));
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function spawnP(x, y, type, n) {
  for (var i = 0; i < n; i++) particles.push(new Particle(x, y, type));
}
function addFloat(x, y, text, color, size) {
  floats.push(new FloatingText(x, y, text, color || '#FFD700', size || 18));
}

// ── Skills ────────────────────────────────────────────────────────────────────
function activateSkill(id) {
  if (!upg[id] || cds[id] > 0) return;
  cds[id] = CD_MAX[id];
  switch (id) {
    case 'gunshi':
      enemies.forEach(function(e) {
        if (!e.dead) {
          var killed = e.takeDamage(20);
          spawnP(e.x, e.y, 'explosion', 6);
          if (killed) onKill(e);
        }
      });
      spawnP(W/2, H/2, 'explosion', 18);
      addFloat(W/2, H*0.38, '一斉突撃！', '#FF4444', 28);
      break;
    case 'nurse':
      gs.earthHP = Math.min(gs.maxEarthHP, gs.earthHP + 45);
      spawnP(W/2, H*0.3, 'hit', 20);
      addFloat(W/2, H*0.38, '地球大回復！', '#FF69B4', 26);
      break;
    case 'barrier':
      gs.barrierActive = true;
      gs.barrierTimer  = 300;
      addFloat(W/2, H*0.38, '絶対防壁！', '#00FFFF', 26);
      break;
  }
}

// ── Attack ────────────────────────────────────────────────────────────────────
function fireBullet(tx, ty) {
  var pu   = PlayerUpgrades;
  var crit = Math.random() < pu.critChance;
  var opts = {
    damage:    pu.atk,
    pierce:    pu.pierce,
    crit:      crit,
    evolved:   gs.isEvolved,
    bulletSpd: pu.bulletSpd,
    rangeMult: pu.rangeMult,
  };
  bullets.push(new Bullet(CHICK_X, CHICK_Y - 20, tx, ty, opts));
  if (pu.doubleShot) {
    bullets.push(new Bullet(CHICK_X - 14, CHICK_Y - 20, tx, ty, opts));
    bullets.push(new Bullet(CHICK_X + 14, CHICK_Y - 20, tx, ty, opts));
  }
  SoundManager.shoot();
  spawnP(CHICK_X + (Math.random()-0.5)*30, CHICK_Y - 50, 'hit', 1);
  addFloat(CHICK_X + (Math.random()-0.5)*40, CHICK_Y - 56, 'ピヨ！', '#FF6B6B', 13);
}

function handleBattleTap(tx, ty) {
  // Pause button (top-right region)
  if (tx > W - 52 && ty < 46) { gs.state = 'paused'; return; }
  // Companion buttons
  var BY = H - 65, BR = 30;
  var BPOS = [50, W/2, W-50];
  for (var bi = 0; bi < BPOS.length; bi++) {
    var dx = tx - BPOS[bi], dy = ty - BY;
    if (Math.sqrt(dx*dx + dy*dy) < BR + 6) {
      var ids = ['gunshi','nurse','barrier'];
      activateSkill(ids[bi]);
      return;
    }
  }
  if (gs.attackCooldown > 0) return;
  var base = Math.max(12, 55 - 8);  // speed from upg not used anymore; use PlayerUpgrades.atkSpd
  gs.attackCooldown = Math.round(36 / PlayerUpgrades.atkSpd);
  fireBullet(tx, ty);
}

// ── Level up ─────────────────────────────────────────────────────────────────
function gainXP(amount) {
  xp += amount;
  var need = xpToNext(level);
  if (xp >= need) {
    xp -= need;
    level++;
    doLevelUp();
  }
}

function doLevelUp() {
  levelChoices = pickUpgrades(3);
  gs.state     = 'levelup';
  SoundManager.levelUp();
  spawnP(CHICK_X, CHICK_Y, 'levelup', 22);
}

function applyLevelUp(idx) {
  var ch = levelChoices[idx];
  PlayerUpgrades.apply(ch.id);
  if (ch.id === 'max_hp') gs.maxEarthHP = PlayerUpgrades.maxHp;
  gs.state = 'battle';
}

// ── Kill handler ──────────────────────────────────────────────────────────────
function onKill(e) {
  kills++;
  var pts = Math.round(e.pts * PlayerUpgrades.scoreMulti);
  score += pts;
  gs.evoGauge = Math.min(100, gs.evoGauge + (e.type === 'boss' ? 50 : e.type === 'tank' ? 15 : 10));
  spawnP(e.x, e.y, 'poof', 8);
  addFloat(e.x, e.y - 24, '+' + pts, '#FFD700', 14);
  if (e.type === 'boss' || e.type === 'tank') SoundManager.killBig();
  else SoundManager.kill();
  gainXP(e.xpGain);
}

// ── Update ────────────────────────────────────────────────────────────────────
function update() {
  frame++;
  if (gs.state !== 'battle') return;

  // Cooldowns
  if (gs.attackCooldown > 0) gs.attackCooldown--;
  var k;
  for (k in cds) { if (cds[k] > 0) cds[k]--; }

  // Barrier
  if (gs.barrierActive) {
    gs.barrierTimer--;
    if (gs.barrierTimer <= 0) gs.barrierActive = false;
  }

  // Auto-regen
  if (PlayerUpgrades.regen > 0) {
    regenTimer++;
    if (regenTimer >= 300) {
      regenTimer = 0;
      gs.earthHP = Math.min(gs.maxEarthHP, gs.earthHP + PlayerUpgrades.regen);
    }
  }

  // Evolution
  if (!gs.isEvolved && gs.evoGauge >= 100) {
    gs.isEvolved = true;
    gs.evoTimer  = [480, 600, 780, 960, 1200][Math.min(4, ~~((level-1)/2))];
    addFloat(W/2, H*0.4, 'にわトリに進化！', '#FFD700', 26);
    spawnP(CHICK_X, CHICK_Y, 'explosion', 16);
  }
  if (gs.isEvolved) {
    gs.evoTimer--;
    if (gs.evoTimer <= 0) {
      gs.isEvolved = false; gs.evoGauge = 0;
      addFloat(W/2, H*0.4, 'ひよこに戻った...', '#aaa', 16);
    }
  }

  // Enemies update
  for (var ei = 0; ei < enemies.length; ei++) {
    var e = enemies[ei];
    if (e.dead) continue;
    var result = e.update(gs.barrierActive, frame, H);
    if (result) {
      if (result.type === 'beam' || result.type === 'reach') {
        gs.earthHP = Math.max(0, gs.earthHP - result.dmg);
        spawnP(result.type === 'beam' ? e.x : e.x, result.type === 'beam' ? e.y + e.size*0.5 : H-160, 'hit_earth', 5);
        if (result.type === 'beam') { addFloat(W/2, H*0.45, 'ドゴーン！', '#9B59B6', 22); spawnP(e.x, e.y+e.size*0.5,'boss_beam',6); }
        else addFloat(e.x, H-170, '-' + result.dmg, '#FF4444', 13);
      } else if (result.type === 'barrier') {
        addFloat(e.x, H-170, 'バリア！', '#00FFFF', 13);
      }
    }
  }
  enemies = enemies.filter(function(e) { return !e.dead; });

  // Bullets update
  for (var bi = 0; bi < bullets.length; bi++) {
    var b = bullets[bi];
    if (b.dead) continue;
    var br = b.update(enemies);
    if (br) {
      if (br.type === 'explode') {
        spawnP(br.x, br.y, 'explosion', 14);
        enemies.forEach(function(en) {
          if (!en.dead) {
            var ddx = br.x - en.x, ddy = br.y - en.y;
            if (Math.sqrt(ddx*ddx + ddy*ddy) < 90) {
              var k2 = en.takeDamage(4);
              if (k2) onKill(en);
            }
          }
        });
        gs.earthHP = Math.min(gs.maxEarthHP, gs.earthHP + 3);
        addFloat(br.x, br.y - 20, '+HP', '#2ECC71', 14);
      } else if (br.type === 'hit') {
        if (br.killed) onKill(br.enemy);
        spawnP(b.x, b.y, br.crit ? 'crit' : 'hit', br.crit ? 5 : 2);
        if (br.crit) addFloat(b.x, b.y - 10, 'CRIT!', '#FF3333', 15);
        SoundManager.hit();
      }
    }
  }
  bullets   = bullets.filter(function(b) { return !b.dead; });
  // Remove enemies killed by AOE above
  enemies   = enemies.filter(function(e) { return !e.dead; });

  // Particles & floats
  particles.forEach(function(p) { p.update(); });
  particles = particles.filter(function(p) { return p.life > 0; });
  floats.forEach(function(f) { f.update(); });
  floats    = floats.filter(function(f) { return f.life > 0; });

  gs.earthHP = Math.max(0, Math.min(gs.maxEarthHP, gs.earthHP));
  if (gs.earthHP <= 0) { endGame(); return; }

  // Wave management
  if (clearDelay > 0) {
    clearDelay--;
    if (clearDelay === 0) startWave();
    return;
  }
  if (waveSpawned < waveTotal) {
    waveTimer++;
    var interval = (wave % 10 === 0) ? 240 : Math.max(30, 90 - wave * 3);
    if (waveTimer >= interval) {
      waveTimer = 0;
      spawnEnemy();
      waveSpawned++;
    }
  } else if (enemies.length === 0) {
    clearDelay = 90;
    addFloat(W/2, H*0.38, 'WAVE CLEAR!', '#FFD700', 28);
    spawnP(W/2, H/2, 'explosion', 12);
  }
}

function endGame() {
  gs.state = 'gameover';
  isNewHS  = SaveManager.save(score, wave);
  SoundManager.gameOver();
  SoundManager.startBgm('title');
}

// ── Draw ──────────────────────────────────────────────────────────────────────
function draw() {
  ctx.clearRect(0, 0, W, H);
  switch (gs.state) {
    case 'title':    drawTitleScr();  break;
    case 'howto':    drawHowToScr();  break;
    case 'battle':   drawBattleScr(); break;
    case 'levelup':  drawBattleScr(); drawLevelUp(levelChoices, level); break;
    case 'paused':   drawPauseScr();  break;
    case 'gameover': drawGameOverScr(); break;
  }
}

function drawTitleScr() {
  var h = SaveManager.getHigh();
  drawTitle(frame, h.score, h.wave, SoundManager.bgmOn, SoundManager.seOn);
}

function drawHowToScr() { drawHowTo(frame); }

function drawPauseScr() { drawPause(frame); }

function drawGameOverScr() {
  var h = SaveManager.getHigh();
  drawGameOver(score, wave, kills, isNewHS, h.score, h.wave, frame);
}

function drawBattleScr() {
  drawBg(frame);
  drawGround();
  drawEvoBar(gs.evoGauge, gs.isEvolved, gs.evoTimer);
  drawHudTop(gs.earthHP, gs.maxEarthHP, gs.barrierActive, wave, score, level, xp, xpToNext(level), kills, SaveManager.getHigh().score, frame);

  // Enemies
  enemies.forEach(function(e) {
    if (e.type === 'boss') drawBoss(e, frame);
    else                   drawCrow(e);
  });

  // Bullets
  bullets.forEach(function(b) {
    if (b.evolved) {
      drawEgg(b.x, b.y);
    } else {
      ctx.save();
      ctx.translate(b.x, b.y);
      ctx.rotate(b.rot + Math.PI/2);
      drawChick(0, 0, 11, false);
      ctx.restore();
    }
  });

  // Particles
  particles.forEach(function(p) { drawParticle(p); });

  // Floating texts
  floats.forEach(function(ft) {
    ctx.globalAlpha = Math.min(1, ft.life / 25);
    ctx.fillStyle   = ft.color;
    ctx.font        = 'bold ' + ft.size + 'px "Kosugi Maru",sans-serif';
    ctx.textAlign   = 'center';
    ctx.strokeStyle = 'rgba(0,0,0,0.7)'; ctx.lineWidth = 4;
    ctx.strokeText(ft.text, ft.x, ft.y);
    ctx.fillText(ft.text, ft.x, ft.y);
    ctx.globalAlpha = 1;
  });

  // Player chick
  var bob = Math.sin(frame * 0.1) * 3;
  if (gs.isEvolved) {
    ctx.globalAlpha = 0.18 + Math.sin(frame*0.12)*0.08;
    ctx.fillStyle   = '#FFD700';
    ctx.beginPath(); ctx.arc(CHICK_X, CHICK_Y, 65, 0, Math.PI*2); ctx.fill();
    ctx.globalAlpha = 1;
  }
  drawChick(CHICK_X, CHICK_Y + bob, gs.isEvolved ? 56 : 44, gs.isEvolved);

  // Barrier dome
  if (gs.barrierActive) {
    ctx.globalAlpha = 0.22 + Math.sin(frame*0.15)*0.08;
    ctx.strokeStyle = '#00FFFF'; ctx.lineWidth = 5;
    ctx.beginPath(); ctx.arc(W/2, H*0.48, W*0.7, 0, Math.PI*2); ctx.stroke();
    ctx.globalAlpha = 0.06; ctx.fillStyle = '#00FFFF'; ctx.fill();
    ctx.globalAlpha = 1;
  }

  drawCompanionBtns(upg, cds, CD_MAX, frame);
}

// ── Input ─────────────────────────────────────────────────────────────────────
function handleInput(tx, ty) {
  SoundManager.resume();
  switch (gs.state) {
    case 'title':
      if (ty >= 520 && ty <= 580 && tx >= 72 && tx <= 318) {
        initGame(); SoundManager.startBgm('battle');
      } else if (ty >= 588 && ty <= 638 && tx >= 72 && tx <= 318) {
        gs.state = 'howto';
      } else if (ty >= 644 && ty <= 692 && tx >= 45 && tx <= 183) {
        SoundManager.toggleBgm(); SoundManager.startBgm('title');
      } else if (ty >= 644 && ty <= 692 && tx >= 207 && tx <= 345) {
        SoundManager.toggleSe();
      }
      break;

    case 'howto':
      if (ty >= 748 && ty <= 804) gs.state = 'title';
      break;

    case 'battle':
      handleBattleTap(tx, ty);
      break;

    case 'levelup':
      for (var i = 0; i < levelChoices.length; i++) {
        if (ty >= 268 + i*180 && ty < 268 + i*180 + 162 && tx >= 20 && tx <= W-20) {
          applyLevelUp(i);
          break;
        }
      }
      break;

    case 'paused':
      if (ty >= 380 && ty <= 438) {
        gs.state = 'battle';
      } else if (ty >= 458 && ty <= 516) {
        initGame(); SoundManager.startBgm('battle');
      } else if (ty >= 536 && ty <= 594) {
        gs.state = 'title'; SoundManager.startBgm('title');
      }
      break;

    case 'gameover':
      if (ty >= 624 && ty <= 682 && tx >= 44 && tx <= W-44) {
        initGame(); SoundManager.startBgm('battle');
      } else if (ty >= 694 && ty <= 748 && tx >= 44 && tx <= W-44) {
        gs.state = 'title'; SoundManager.startBgm('title');
      }
      break;
  }
}

canvas.addEventListener('touchstart', function(e) {
  e.preventDefault();
  var r  = canvas.getBoundingClientRect();
  var sx = W / r.width, sy = H / r.height;
  var t  = e.changedTouches[0];
  handleInput((t.clientX - r.left) * sx, (t.clientY - r.top) * sy);
}, { passive: false });

canvas.addEventListener('click', function(e) {
  var r  = canvas.getBoundingClientRect();
  var sx = W / r.width, sy = H / r.height;
  handleInput((e.clientX - r.left) * sx, (e.clientY - r.top) * sy);
});

// ── Main loop ─────────────────────────────────────────────────────────────────
gs.state = 'title';
SoundManager.startBgm('title');
function loop() { update(); draw(); requestAnimationFrame(loop); }
loop();
