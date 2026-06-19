'use strict';

const UPGRADE_DEFS = [
  { id:'atk_up',        name:'攻撃力アップ',       desc:'弾のダメージ +1',               icon:'⚔️'  },
  { id:'spd_up',        name:'攻撃速度アップ',      desc:'連射速度が15%上がる',            icon:'⚡'  },
  { id:'bullet_spd',    name:'弾速アップ',          desc:'弾の速度が20%上がる',            icon:'💨'  },
  { id:'pierce',        name:'貫通弾',              desc:'弾が敵を貫通する（重複可）',      icon:'🎯'  },
  { id:'double_shot',   name:'2連射',               desc:'1タップで2発発射する',            icon:'🔫'  },
  { id:'crit_up',       name:'クリティカル率アップ', desc:'クリティカル率 +10%',            icon:'💥'  },
  { id:'score_up',      name:'スコア倍率アップ',    desc:'スコア倍率 ×1.5',               icon:'⭐'  },
  { id:'max_hp',        name:'最大HPアップ',        desc:'地球の最大HP +20',               icon:'❤️'  },
  { id:'regen',         name:'自動回復',            desc:'5秒ごとにHP +1 回復（重複可）',  icon:'💚'  },
  { id:'range_up',      name:'射程アップ',          desc:'弾の飛距離が25%伸びる',          icon:'🏹'  },
  { id:'tower_normal',  name:'ノーマルタワー 設置', desc:'バランス型の自動砲台を設置',      icon:'🏰'  },
  { id:'tower_rapid',   name:'ラピッドタワー 設置', desc:'高速連射の自動砲台を設置',        icon:'🔰'  },
  { id:'tower_sniper',  name:'スナイパータワー 設置',desc:'超長射程の自動砲台を設置',       icon:'🎯'  },
  { id:'tower_support', name:'サポートタワー 設置', desc:'貫通弾で複数敵を攻撃',           icon:'💠'  },
];

const PlayerUpgrades = {
  atk:        1,
  atkSpd:     1.0,
  bulletSpd:  1.0,
  pierce:     0,
  doubleShot: false,
  critChance: 0,
  scoreMulti: 1.0,
  maxHp:      100,
  regen:      0,
  rangeMult:  1.0,

  reset() {
    this.atk=1; this.atkSpd=1.0; this.bulletSpd=1.0;
    this.pierce=0; this.doubleShot=false; this.critChance=0;
    this.scoreMulti=1.0; this.maxHp=100; this.regen=0; this.rangeMult=1.0;
  },

  apply(id) {
    switch (id) {
      case 'atk_up':     this.atk++; break;
      case 'spd_up':     this.atkSpd = Math.min(this.atkSpd * 1.15, 4.5); break;
      case 'bullet_spd': this.bulletSpd *= 1.2; break;
      case 'pierce':     this.pierce++; break;
      case 'double_shot':this.doubleShot = true; break;
      case 'crit_up':    this.critChance = Math.min(this.critChance + 0.1, 0.8); break;
      case 'score_up':   this.scoreMulti += 0.5; break;
      case 'max_hp':     this.maxHp += 20; break;
      case 'regen':      this.regen++; break;
      case 'range_up':   this.rangeMult *= 1.25; break;
    }
  }
};

function pickUpgrades(n) {
  n = n || 3;
  const pool   = UPGRADE_DEFS.slice();
  const result = [];
  while (result.length < n && pool.length > 0) {
    const i = ~~(Math.random() * pool.length);
    result.push(pool.splice(i, 1)[0]);
  }
  return result;
}

// Picks n-1 personal upgrades + 1 tower card (guaranteed tower option in pool)
function pickUpgradesWithTowers(n) {
  n = n || 3;
  // Separate tower defs from personal defs
  const personal = UPGRADE_DEFS.filter(function(d) { return d.id.indexOf('tower_') < 0; });
  const towerDefs = UPGRADE_DEFS.filter(function(d) { return d.id.indexOf('tower_') === 0; });
  const result = [];
  // n-1 personal upgrades
  const pPool = personal.slice();
  while (result.length < n - 1 && pPool.length > 0) {
    const i = ~~(Math.random() * pPool.length);
    result.push(pPool.splice(i, 1)[0]);
  }
  // 1 tower option
  if (towerDefs.length > 0) {
    result.push(towerDefs[~~(Math.random() * towerDefs.length)]);
  } else if (pPool.length > 0) {
    const i = ~~(Math.random() * pPool.length);
    result.push(pPool.splice(i, 1)[0]);
  }
  return result;
}
