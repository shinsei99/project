'use strict';

// ── Enemy ────────────────────────────────────────────────────────────────────
// baseHp is set so Stage1-Wave1 normal dies in 1 hit (base dmg=2)
const ENEMY_DEF = {
  normal:   { baseHp:2,  dmg:5,  size:28, pts:10,  spd:0.9,  xpGain:1 },
  fast:     { baseHp:1,  dmg:4,  size:20, pts:10,  spd:1.9,  xpGain:1 },
  ranged:   { baseHp:4,  dmg:8,  size:26, pts:15,  spd:0.65, xpGain:2 },
  tank:     { baseHp:8,  dmg:12, size:44, pts:20,  spd:0.4,  xpGain:2 },
  ghost:    { baseHp:3,  dmg:6,  size:26, pts:20,  spd:1.1,  xpGain:2 },
  healer:   { baseHp:5,  dmg:4,  size:28, pts:25,  spd:0.55, xpGain:3 },
  bomber:   { baseHp:5,  dmg:18, size:38, pts:30,  spd:0.48, xpGain:3 },
  sprinter: { baseHp:2,  dmg:5,  size:22, pts:18,  spd:0.5,  xpGain:2 },  // pauses then dashes
  armored:  { baseHp:6,  dmg:7,  size:30, pts:25,  spd:0.75, xpGain:2 },  // half damage
  regen:    { baseHp:8,  dmg:6,  size:28, pts:22,  spd:0.65, xpGain:2 },  // self-heals
  shielded: { baseHp:5,  dmg:6,  size:28, pts:24,  spd:0.8,  xpGain:3 },  // shield layer
  splitter: { baseHp:10, dmg:8,  size:36, pts:30,  spd:0.5,  xpGain:4 },  // splits on death
  swarm:    { baseHp:1,  dmg:3,  size:14, pts:5,   spd:1.3,  xpGain:1 },  // spawned by splitter
  boss:     { baseHp:60, dmg:0,  size:90, pts:150, spd:0.35, xpGain:5 },
};

class Enemy {
  constructor(type, x, y, stage, waveInStage) {
    this.type      = type;
    this.x         = x;
    this.y         = y;
    this.dead      = false;
    this.wobble    = Math.random() * Math.PI * 2;
    this.bossTimer = 0;
    this.hitFlash  = 0;

    const def = ENEMY_DEF[type];

    if (type === 'boss') {
      // Boss scales more steeply per stage
      const bossScale = 1 + (stage - 1) * 0.5;
      this.maxHp = Math.ceil(def.baseHp * bossScale);
    } else {
      const stageScale = 1 + (stage - 1) * 0.35;
      const waveScale  = 1 + (waveInStage - 1) * 0.10;
      this.maxHp = Math.max(1, Math.ceil(def.baseHp * stageScale * waveScale));
    }

    this.hp      = this.maxHp;
    this.dmg     = def.dmg;
    this.size    = def.size;
    this.pts     = def.pts;
    this.xpGain  = def.xpGain;
    // Speed also scales gently with stage
    this.spd     = def.spd * (1 + (stage - 1) * 0.05);

    if (type === 'boss') {
      this.vx = 1.5; this.vy = 0;
      this.phase = 1;
      this.summonTimer = 0;
    } else if (type === 'ranged') {
      this.stopY       = 175 + Math.random() * 90;
      this.rangedTimer = 0;
      this.vx = (Math.random() - 0.5) * 1.2;
      this.vy = this.spd;
    } else if (type === 'healer') {
      this.stopY     = 128 + Math.random() * 64;
      this.healTimer = 0;
      this.vx = (Math.random() - 0.5) * 0.8;
      this.vy = this.spd;
    } else if (type === 'ghost') {
      this.vx = (Math.random() - 0.5) * 2.0;
      this.vy = this.spd;
    } else if (type === 'bomber') {
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = this.spd;
    } else if (type === 'sprinter') {
      this.vx = (Math.random() - 0.5) * 1.2;
      this.vy = this.spd;
      this.sprintTimer = ~~(Math.random() * 40);  // stagger spawns
      this.sprintPhase = 0;  // 0=pause, 1=dash
    } else if (type === 'armored') {
      this.vx = (Math.random() - 0.5) * 1.0;
      this.vy = this.spd;
    } else if (type === 'regen') {
      this.vx = (Math.random() - 0.5) * 1.2;
      this.vy = this.spd;
      this.regenTimer = 0;
    } else if (type === 'shielded') {
      this.vx = (Math.random() - 0.5) * 1.2;
      this.vy = this.spd;
      this.maxShield = Math.max(2, Math.ceil(this.maxHp * 0.6));
      this.shield     = this.maxShield;
    } else if (type === 'splitter') {
      this.vx = (Math.random() - 0.5) * 1.0;
      this.vy = this.spd;
    } else if (type === 'swarm') {
      this.vx = (Math.random() - 0.5) * 2.5;
      this.vy = this.spd;
    } else {
      this.vx = (Math.random() - 0.5) * 1.5;
      this.vy = this.spd;
    }
  }

  // Returns {type, dmg?} event or null
  update(barrierActive, frame, H) {
    this.wobble += 0.05;
    if (this.hitFlash > 0) this.hitFlash--;

    if (this.type === 'boss') {
      // Phase check (phase advances, never decreases)
      var hpRatio = this.hp / this.maxHp;
      var newPhase = hpRatio < 0.25 ? 3 : hpRatio < 0.60 ? 2 : 1;
      if (newPhase > this.phase) {
        this.phase = newPhase;
        this.bossTimer = 0;
        return { type: 'phase_change', phase: newPhase };
      }
      // Phase-based movement speed
      var targetSpd = this.phase === 3 ? 4.0 : this.phase === 2 ? 2.5 : 1.5;
      this.vx = Math.sign(this.vx || 1) * targetSpd;
      this.x += this.vx;
      if (this.x < 70 || this.x > 320) this.vx *= -1;
      this.y = 230 + Math.sin(frame * 0.018) * 30;
      // Phase 2+: summon minions periodically
      if (this.phase >= 2) {
        this.summonTimer++;
        if (this.summonTimer >= 220) {
          this.summonTimer = 0;
          return { type: 'boss_summon' };
        }
      }
      // Beam attack (faster per phase)
      var beamInterval = this.phase === 3 ? 44 : this.phase === 2 ? 72 : 120;
      var beamDmg      = this.phase === 3 ? 9  : 6;
      this.bossTimer++;
      if (this.bossTimer >= beamInterval) {
        this.bossTimer = 0;
        if (!barrierActive) return { type: 'beam', dmg: beamDmg };
        else                return { type: 'barrier' };
      }
    } else if (this.type === 'ranged') {
      if (this.y < this.stopY) {
        // Descend to hover position
        this.x += this.vx + Math.sin(this.wobble) * 0.3;
        this.y += this.vy;
        if (this.x < this.size || this.x > 390 - this.size) this.vx *= -1;
      } else {
        // Hover and charge shot
        this.x += Math.sin(this.wobble * 0.7) * 0.9;
        if (this.x < this.size) this.x = this.size;
        if (this.x > 390 - this.size) this.x = 390 - this.size;
        this.rangedTimer++;
        if (this.rangedTimer >= 85) {
          this.rangedTimer = 0;
          if (!barrierActive) return { type: 'rangedbullet', x: this.x, y: this.y + this.size * 0.5, dmg: this.dmg };
          else                return { type: 'barrier' };
        }
      }
    } else if (this.type === 'healer') {
      if (this.y < this.stopY) {
        this.x += this.vx + Math.sin(this.wobble) * 0.4;
        this.y += this.vy;
        if (this.x < this.size || this.x > 390 - this.size) this.vx *= -1;
      } else {
        // Hover and periodically heal all enemies
        this.x += Math.sin(this.wobble * 0.5) * 1.0;
        if (this.x < this.size) this.x = this.size;
        if (this.x > 390 - this.size) this.x = 390 - this.size;
        this.healTimer++;
        if (this.healTimer >= 100) {
          this.healTimer = 0;
          return { type: 'heal', amount: 2 };
        }
      }
    } else if (this.type === 'ghost') {
      // Erratic waving motion, semi-transparent
      this.x += this.vx + Math.sin(this.wobble * 1.5) * 0.8;
      this.y += this.vy;
      if (this.x < this.size || this.x > 390 - this.size) this.vx *= -1;
      if (this.y > H - 160) {
        this.dead = true;
        if (!barrierActive) return { type: 'reach', dmg: this.dmg };
        else                return { type: 'barrier' };
      }
    } else if (this.type === 'bomber') {
      // Falls nearly straight down, explodes on impact
      this.x += Math.sin(this.wobble * 0.3) * 0.3;
      this.y += this.vy;
      if (this.y > H - 150) {
        this.dead = true;
        if (!barrierActive) return { type: 'bomb', dmg: this.dmg };
        else                return { type: 'barrier' };
      }
    } else if (this.type === 'sprinter') {
      this.sprintTimer++;
      if (this.sprintPhase === 0) {
        // Pause: creep slowly
        this.x += Math.sin(this.wobble) * 0.5;
        this.y += this.vy * 0.15;
        if (this.sprintTimer >= 55) { this.sprintTimer = 0; this.sprintPhase = 1; }
      } else {
        // Dash: very fast
        this.x += this.vx;
        this.y += this.vy * 4.5;
        if (this.sprintTimer >= 18) { this.sprintTimer = 0; this.sprintPhase = 0; }
      }
      if (this.x < this.size || this.x > 390 - this.size) this.vx *= -1;
      if (this.y > H - 160) {
        this.dead = true;
        if (!barrierActive) return { type: 'reach', dmg: this.dmg };
        else                return { type: 'barrier' };
      }
    } else if (this.type === 'regen') {
      this.x += this.vx + Math.sin(this.wobble) * 0.4;
      this.y += this.vy;
      if (this.x < this.size || this.x > 390 - this.size) this.vx *= -1;
      this.regenTimer++;
      if (this.regenTimer >= 90) { this.regenTimer = 0; this.hp = Math.min(this.maxHp, this.hp + 1); }
      if (this.y > H - 160) {
        this.dead = true;
        if (!barrierActive) return { type: 'reach', dmg: this.dmg };
        else                return { type: 'barrier' };
      }
    } else {
      this.x += this.vx + Math.sin(this.wobble) * 0.4;
      this.y += this.vy;
      if (this.x < this.size || this.x > 390 - this.size) this.vx *= -1;
      if (this.y > H - 160) {
        this.dead = true;
        if (!barrierActive) return { type: 'reach', dmg: this.dmg };
        else                return { type: 'barrier' };
      }
    }
    return null;
  }

  // Returns true if killed
  takeDamage(dmg) {
    // Armored: takes half damage
    if (this.type === 'armored') dmg = Math.max(1, Math.ceil(dmg * 0.5));
    // Shielded: damage hits shield first
    if (this.type === 'shielded' && this.shield > 0) {
      this.shield -= dmg;
      if (this.shield < 0) { dmg = -this.shield; this.shield = 0; }
      else { this.hitFlash = 6; return false; }
    }
    this.hp -= dmg;
    this.hitFlash = 6;
    if (this.hp <= 0) { this.hp = 0; this.dead = true; return true; }
    return false;
  }
}

// ── Bullet ───────────────────────────────────────────────────────────────────
class Bullet {
  constructor(x, y, tx, ty, opts) {
    opts = opts || {};
    this.x          = x;
    this.y          = y;
    this.damage     = opts.damage    || 2;
    this.pierceLeft = opts.pierce    || 0;
    this.crit       = opts.crit      || false;
    this.evolved    = opts.evolved   || false;
    const speed     = (this.evolved ? 7 : 11) * (opts.bulletSpd || 1);
    const dx = tx - x, dy = ty - y;
    const d  = Math.sqrt(dx*dx + dy*dy) || 1;
    this.vx  = dx / d * speed;
    this.vy  = dy / d * speed;
    this.size = this.evolved ? 18 : 12;
    this.life = Math.round(90 * (opts.rangeMult || 1));
    this.dead = false;
    this.rot  = Math.atan2(dy, dx);
    this.hitSet = new Set();
  }

  // Returns {type, enemy?, killed?, crit?} or null
  update(enemies) {
    this.x += this.vx; this.y += this.vy;
    this.life--;
    if (this.life <= 0 || this.x < -20 || this.x > 410 || this.y < -20 || this.y > 864) {
      this.dead = true; return null;
    }
    for (const e of enemies) {
      if (e.dead || this.hitSet.has(e)) continue;
      const dx = this.x - e.x, dy = this.y - e.y;
      if (Math.sqrt(dx*dx + dy*dy) < e.size * 0.75 + this.size * 0.5) {
        if (this.evolved) { this.dead = true; return { type:'explode', x:this.x, y:this.y }; }
        const dmg    = this.crit ? this.damage * 2 : this.damage;
        const killed = e.takeDamage(dmg);
        this.hitSet.add(e);
        if (this.pierceLeft <= 0) this.dead = true;
        else this.pierceLeft--;
        return { type:'hit', enemy:e, killed, crit:this.crit };
      }
    }
    return null;
  }
}

// ── EnemyBullet ──────────────────────────────────────────────────────────────
class EnemyBullet {
  constructor(x, y, dmg) {
    this.x    = x;
    this.y    = y;
    this.vy   = 4.5;
    this.size = 7;
    this.dmg  = dmg;
    this.dead = false;
    this.life = 220;
  }
  update(H) {
    this.y += this.vy;
    this.life--;
    if (this.y > H - 90 || this.life <= 0) {
      this.dead = true;
      return (this.y > H - 90) ? { type: 'hit_earth', dmg: this.dmg } : null;
    }
    return null;
  }
}

// ── Particle ─────────────────────────────────────────────────────────────────
class Particle {
  constructor(x, y, type) {
    this.x = x; this.y = y; this.type = type;
    switch (type) {
      case 'poof':
        this.vx=(Math.random()-0.5)*3; this.vy=-Math.random()*3-0.5;
        this.size=14+Math.random()*14; this.life=this.maxLife=45+Math.random()*20;
        this.color=['#ccc','#aaa','#eee'][~~(Math.random()*3)]; break;
      case 'hit':
        this.vx=(Math.random()-0.5)*6; this.vy=(Math.random()-0.5)*6;
        this.size=5+Math.random()*7; this.life=this.maxLife=18;
        this.color='#FFD700'; break;
      case 'crit':
        this.vx=(Math.random()-0.5)*9; this.vy=(Math.random()-0.5)*9;
        this.size=9+Math.random()*10; this.life=this.maxLife=22;
        this.color='#FF3333'; break;
      case 'hit_earth':
        this.vx=(Math.random()-0.5)*5; this.vy=-Math.random()*4-1;
        this.size=8+Math.random()*10; this.life=this.maxLife=30;
        this.color='#FF4444'; break;
      case 'explosion':
        this.vx=(Math.random()-0.5)*9; this.vy=(Math.random()-0.5)*9;
        this.size=10+Math.random()*18; this.life=this.maxLife=35;
        this.color=['#FF6B00','#FFD700','#FF4444','#FFF'][~~(Math.random()*4)]; break;
      case 'boss_beam':
        this.vx=(Math.random()-0.5)*5; this.vy=2+Math.random()*4;
        this.size=10; this.life=this.maxLife=30; this.color='#9B59B6'; break;
      case 'levelup':
        this.vx=(Math.random()-0.5)*7; this.vy=-Math.random()*5-2;
        this.size=7+Math.random()*12; this.life=this.maxLife=55;
        this.color=['#FFD700','#FF6B6B','#4ECDC4','#FF69B4','#FFFFFF'][~~(Math.random()*5)]; break;
      case 'stageclear':
        this.vx=(Math.random()-0.5)*8; this.vy=-Math.random()*6-3;
        this.size=8+Math.random()*16; this.life=this.maxLife=70;
        this.color=['#FFD700','#FF6B00','#FFF','#00FF88','#FF88FF'][~~(Math.random()*5)]; break;
      default:
        this.vx=0; this.vy=-1; this.size=8; this.life=this.maxLife=30; this.color='#fff';
    }
  }
  update() {
    this.x += this.vx; this.y += this.vy;
    if (this.type !== 'poof') this.vy += 0.15;
    this.life--;
  }
}

// ── FloatingText ─────────────────────────────────────────────────────────────
class FloatingText {
  constructor(x, y, text, color, size) {
    this.x=x; this.y=y; this.text=text;
    this.color=color||'#FFD700'; this.size=size||18;
    this.life=80; this.vy=-1.2;
  }
  update() { this.y += this.vy; this.life--; }
}
