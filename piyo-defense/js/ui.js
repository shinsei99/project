'use strict';

// ── Battle HUD ───────────────────────────────────────────────────────────────
function drawHudTop(earthHP, maxEarthHP, barrierActive, wave, score, level, xp, xpMax, kills, hs, frame) {
  _ctx.fillStyle = 'rgba(0,0,0,0.6)';
  _ctx.fillRect(0, 0, _W, 82);

  // Earth icon + HP bar
  drawEarth(24, 26, 18);
  var ratio = earthHP / maxEarthHP;
  var col = ratio > 0.55 ? '#2ECC71' : ratio > 0.3 ? '#F39C12' : '#E74C3C';
  rrect(48, 13, _W-110, 24, 12, '#111', '#333', 1.5);
  if (ratio > 0) rrect(49, 14, (_W-112)*ratio, 22, 11, col, null);
  _ctx.fillStyle = '#fff'; _ctx.font = 'bold 11px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('HP ' + earthHP + '/' + maxEarthHP, 48 + (_W-112)/2, 29);

  if (barrierActive) {
    _ctx.globalAlpha = 0.5 + Math.sin(frame*0.12)*0.3;
    rrect(47, 12, _W-110, 26, 13, null, '#00FFFF', 2.5);
    _ctx.globalAlpha = 1;
  }

  // Pause button (top-right)
  rrect(_W-46, 8, 36, 30, 6, 'rgba(0,0,0,0.65)', '#555', 1.5);
  _ctx.fillStyle = '#ccc'; _ctx.font = 'bold 13px sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('❚❚', _W-28, 28);

  // Wave badge
  rrect(8, 44, 74, 30, 6, 'rgba(0,0,0,0.55)', '#4488BB', 1.5);
  _ctx.fillStyle = '#7EC8E3'; _ctx.font = 'bold 9px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('WAVE', 45, 56);
  _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 15px "Kosugi Maru",sans-serif';
  _ctx.fillText(wave, 45, 71);

  // Score
  rrect(90, 44, 118, 30, 6, 'rgba(0,0,0,0.55)', '#555', 1.5);
  _ctx.fillStyle = '#888'; _ctx.font = '9px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('SCORE', 149, 55);
  _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 13px "Kosugi Maru",sans-serif';
  _ctx.fillText(score, 149, 70);

  // Level + XP bar
  rrect(216, 44, 82, 30, 6, 'rgba(0,0,0,0.55)', '#9B59B6', 1.5);
  _ctx.fillStyle = '#CC88FF'; _ctx.font = 'bold 10px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('Lv.' + level, 257, 56);
  rrect(221, 62, 68, 7, 3, '#222', null);
  if (xp > 0) rrect(221, 62, 68 * Math.min(1, xp/xpMax), 7, 3, '#9B59B6', null);

  // Kills + HS tiny
  _ctx.fillStyle = '#777'; _ctx.font = '9px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'right';
  _ctx.fillText('撃破:' + kills, _W-52, 56);
  _ctx.fillStyle = '#FFD700';
  _ctx.fillText('HS:' + hs, _W-52, 68);
}

function drawEvoBar(evoGauge, isEvolved, evoTimer) {
  if (evoGauge <= 0 && !isEvolved) return;
  var bx = 8, by = 83, bw = _W-16, bh = 8;
  rrect(bx-1, by-1, bw+2, bh+2, bh/2+1, '#111', '#333', 1);
  if (evoGauge > 0) rrect(bx, by, bw*(evoGauge/100), bh, bh/2, isEvolved ? '#FF6B35' : '#FFD700', null);
  if (isEvolved) {
    _ctx.fillStyle = '#FF6B35'; _ctx.font = 'bold 9px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'right';
    _ctx.fillText('にわトリ変身中！ ' + Math.ceil(evoTimer/60) + 's', _W-10, by - 1);
  }
}

function drawCompanionBtns(upg, cds, CD_MAX, frame) {
  var BTNS = [
    { id:'gunshi',  label:'軍師',  x:50,       color:'#8B4513', acc:'glasses' },
    { id:'nurse',   label:'ナース',x:_W/2,     color:'#C0397B', acc:'nurse'   },
    { id:'barrier', label:'バリア',x:_W-50,    color:'#1A5DAD', acc:'helmet'  },
  ];
  var BY = _H - 65, BR = 30;
  BTNS.forEach(function(btn) {
    var unlocked = upg[btn.id], cd = cds[btn.id], cdMax = CD_MAX[btn.id];
    _ctx.beginPath(); _ctx.arc(btn.x, BY+3, BR, 0, Math.PI*2);
    _ctx.fillStyle = 'rgba(0,0,0,0.35)'; _ctx.fill();
    _ctx.beginPath(); _ctx.arc(btn.x, BY, BR, 0, Math.PI*2);
    _ctx.fillStyle = unlocked ? (cd>0 ? '#333' : btn.color) : '#1A1A1A'; _ctx.fill();
    _ctx.strokeStyle = unlocked ? (cd>0 ? '#555' : '#fff') : '#333'; _ctx.lineWidth = 2.5; _ctx.stroke();
    if (unlocked && cd > 0) {
      _ctx.globalAlpha = 0.55; _ctx.fillStyle = '#000';
      _ctx.beginPath(); _ctx.moveTo(btn.x, BY);
      _ctx.arc(btn.x, BY, BR, -Math.PI/2, -Math.PI/2 + Math.PI*2*(cd/cdMax));
      _ctx.closePath(); _ctx.fill(); _ctx.globalAlpha = 1;
      _ctx.fillStyle = '#fff'; _ctx.font = 'bold 12px sans-serif'; _ctx.textAlign = 'center';
      _ctx.fillText(Math.ceil(cd/60) + 's', btn.x, BY+5);
    } else if (unlocked) {
      drawChick(btn.x, BY-2, 22, false, btn.acc);
    } else {
      _ctx.fillStyle = '#555'; _ctx.font = '20px sans-serif';
      _ctx.textAlign = 'center'; _ctx.textBaseline = 'middle';
      _ctx.fillText('🔒', btn.x, BY); _ctx.textBaseline = 'alphabetic';
    }
    _ctx.fillStyle = unlocked ? '#ddd' : '#444';
    _ctx.font = '9px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
    _ctx.fillText(btn.label, btn.x, BY + BR + 13);
  });
}

// ── Title ────────────────────────────────────────────────────────────────────
function drawTitle(frame, hs, hw, bgmOn, seOn) {
  drawBg(frame);
  _ctx.textAlign = 'center';
  _ctx.shadowColor = '#FF6B00'; _ctx.shadowBlur = 14;
  _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 36px "Kosugi Maru",sans-serif';
  _ctx.fillText('ひよこ防衛軍', _W/2, 160);
  _ctx.shadowColor = '#FF9900'; _ctx.shadowBlur = 8;
  _ctx.fillStyle = '#FFA040'; _ctx.font = 'bold 17px "Kosugi Maru",sans-serif';
  _ctx.fillText('～地球救出大作戦～', _W/2, 192);
  _ctx.shadowBlur = 0;

  drawChick(_W/2, 308, 66, false);
  drawCrow({ x:88,  y:268, size:28, hp:3,  maxHp:3,  wobble:frame*0.05,   type:'normal', hitFlash:0 });
  drawCrow({ x:302, y:262, size:22, hp:3,  maxHp:3,  wobble:frame*0.05+1, type:'fast',   hitFlash:0 });
  drawCrow({ x:195, y:250, size:40, hp:24, maxHp:24, wobble:frame*0.05+2, type:'tank',   hitFlash:0 });
  drawEarth(_W/2, 422, 40);

  // High score
  rrect(55, 468, 280, 40, 8, 'rgba(0,0,0,0.55)', '#444', 1.5);
  _ctx.fillStyle = '#aaa'; _ctx.font = '11px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('ベストスコア: ' + hs + '  最高Wave: ' + hw, _W/2, 492);

  // START
  var pulse = Math.sin(frame*0.07) * 4;
  rrect(72, 520+pulse, 246, 56, 14, '#E84B2B', '#FFD700', 3);
  _ctx.fillStyle = '#fff'; _ctx.font = 'bold 24px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('START', _W/2, 555+pulse);

  // HOW TO PLAY
  rrect(72, 588, 246, 46, 11, 'rgba(20,20,80,0.85)', '#445588', 2);
  _ctx.fillStyle = '#AAC0FF'; _ctx.font = 'bold 16px "Kosugi Maru",sans-serif';
  _ctx.fillText('あそびかた', _W/2, 617);

  // BGM / SE toggles
  rrect(45, 648, 138, 40, 8, bgmOn ? 'rgba(20,80,20,0.85)' : 'rgba(60,20,20,0.85)', '#555', 1.5);
  _ctx.fillStyle = bgmOn ? '#88FF88' : '#FF8888'; _ctx.font = 'bold 14px "Kosugi Maru",sans-serif';
  _ctx.fillText('BGM ' + (bgmOn ? 'ON' : 'OFF'), 114, 673);

  rrect(207, 648, 138, 40, 8, seOn ? 'rgba(20,80,20,0.85)' : 'rgba(60,20,20,0.85)', '#555', 1.5);
  _ctx.fillStyle = seOn ? '#88FF88' : '#FF8888';
  _ctx.fillText('SE ' + (seOn ? 'ON' : 'OFF'), 276, 673);

  _ctx.fillStyle = '#444'; _ctx.font = '10px sans-serif';
  _ctx.fillText('PIYO-DEFENSE  v2.0', _W/2, _H - 24);
}

// ── How To Play ──────────────────────────────────────────────────────────────
function drawHowTo(frame) {
  drawBg(frame);
  _ctx.fillStyle = 'rgba(0,0,10,0.80)'; _ctx.fillRect(0, 0, _W, _H);
  _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 26px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('あそびかた', _W/2, 78);

  var rows = [
    ['🎯','タップして弾を発射！'],
    ['🌍','地球のHPが0になるとゲームオーバー'],
    ['💪','敵を倒してレベルアップ！'],
    ['⬆️','レベルアップ時に強化を選ぼう'],
    ['🔵','青カラス：速いが弱い'],
    ['🔴','赤カラス：遅くて硬い（HPバーあり）'],
    ['👾','10Waveごとにボスが出現！'],
    ['🐔','ゲージ満タンでにわトリに進化！'],
  ];
  rows.forEach(function(row, i) {
    rrect(28, 102+i*80, 334, 66, 10, 'rgba(10,10,40,0.85)', '#334', 2);
    _ctx.font = '26px sans-serif'; _ctx.textAlign = 'left';
    _ctx.fillText(row[0], 56, 146+i*80);
    _ctx.fillStyle = '#fff'; _ctx.font = '13px "Kosugi Maru",sans-serif';
    _ctx.fillText(row[1], 94, 146+i*80);
    _ctx.fillStyle = '#fff';
  });

  rrect(72, 750, 246, 52, 13, '#2C3E7B', '#7EC8E3', 2.5);
  _ctx.fillStyle = '#AAC0FF'; _ctx.font = 'bold 18px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('タイトルに戻る', _W/2, 782);
}

// ── Level Up ─────────────────────────────────────────────────────────────────
function drawLevelUp(choices, level) {
  _ctx.fillStyle = 'rgba(0,0,0,0.82)'; _ctx.fillRect(0, 0, _W, _H);
  _ctx.textAlign = 'center';
  _ctx.shadowColor = '#FFD700'; _ctx.shadowBlur = 20;
  _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 34px "Kosugi Maru",sans-serif';
  _ctx.fillText('LEVEL UP!', _W/2, 188);
  _ctx.shadowBlur = 0;
  _ctx.fillStyle = '#CC88FF'; _ctx.font = 'bold 14px "Kosugi Maru",sans-serif';
  _ctx.fillText('Lv.' + level + ' に上がった！', _W/2, 218);
  _ctx.fillStyle = '#aaa'; _ctx.font = '13px "Kosugi Maru",sans-serif';
  _ctx.fillText('強化を1つ選んでください', _W/2, 242);

  choices.forEach(function(ch, i) {
    var y = 268 + i*180;
    rrect(20, y, _W-40, 162, 14, 'rgba(8,18,55,0.97)', '#5566AA', 2.5);
    _ctx.font = '36px sans-serif'; _ctx.textAlign = 'center';
    _ctx.fillText(ch.icon, _W/2, y + 52);
    _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 19px "Kosugi Maru",sans-serif';
    _ctx.fillText(ch.name, _W/2, y + 88);
    _ctx.fillStyle = '#aaa'; _ctx.font = '13px "Kosugi Maru",sans-serif';
    _ctx.fillText(ch.desc, _W/2, y + 116);
    // tap hint
    _ctx.fillStyle = 'rgba(255,255,255,0.25)'; _ctx.font = '11px sans-serif';
    _ctx.fillText('タップして選択', _W/2, y + 142);
  });
}

// ── Pause ────────────────────────────────────────────────────────────────────
function drawPause(frame) {
  drawBg(frame);
  _ctx.fillStyle = 'rgba(0,0,0,0.78)'; _ctx.fillRect(0, 0, _W, _H);
  _ctx.fillStyle = '#fff'; _ctx.font = 'bold 38px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('PAUSE', _W/2, 310);

  rrect(72, 380, 246, 58, 14, '#2C54AD', '#7EC8E3', 2.5);
  _ctx.fillStyle = '#fff'; _ctx.font = 'bold 20px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('再開する', _W/2, 416);

  rrect(72, 458, 246, 58, 14, '#7B2020', '#FF6666', 2.5);
  _ctx.fillStyle = '#fff';
  _ctx.fillText('最初からやり直す', _W/2, 494);

  rrect(72, 536, 246, 58, 14, 'rgba(20,20,60,0.95)', '#445588', 2);
  _ctx.fillStyle = '#AAC0FF';
  _ctx.fillText('タイトルへ', _W/2, 572);
}

// ── Game Over ────────────────────────────────────────────────────────────────
function drawGameOver(score, wave, kills, isNewHS, hs, hw, frame) {
  drawBg(frame);
  _ctx.fillStyle = 'rgba(0,0,0,0.75)'; _ctx.fillRect(0, 0, _W, _H);
  _ctx.textAlign = 'center';
  _ctx.shadowColor = '#F00'; _ctx.shadowBlur = 20;
  _ctx.fillStyle = '#FF4444'; _ctx.font = 'bold 46px "Kosugi Maru",sans-serif';
  _ctx.fillText('EARTH CRASH!', _W/2, 168);
  _ctx.shadowBlur = 0;

  drawEarth(_W/2, 254, 42);
  _ctx.strokeStyle = '#FF4444'; _ctx.lineWidth = 4;
  _ctx.beginPath(); _ctx.moveTo(_W/2-6, 213); _ctx.lineTo(_W/2+5, 244); _ctx.lineTo(_W/2-10, 296); _ctx.stroke();

  if (isNewHS) {
    _ctx.shadowColor = '#FFD700'; _ctx.shadowBlur = 14;
    _ctx.fillStyle = '#FFD700'; _ctx.font = 'bold 20px "Kosugi Maru",sans-serif';
    _ctx.fillText('🏆 NEW HIGH SCORE! 🏆', _W/2, 320);
    _ctx.shadowBlur = 0;
  }

  var rows = [
    ['スコア', score],
    ['到達Wave', wave],
    ['撃破数', kills + ' 体'],
    ['ベストスコア', hs],
    ['最高Wave', hw],
  ];
  rows.forEach(function(row, i) {
    var y = 340 + i * 54;
    rrect(55, y, _W-110, 44, 8, 'rgba(10,10,30,0.85)', '#334', 1.5);
    _ctx.fillStyle = '#888'; _ctx.font = '12px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'left';
    _ctx.fillText(row[0], 76, y+27);
    _ctx.fillStyle = '#fff'; _ctx.font = 'bold 16px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'right';
    _ctx.fillText(row[1], _W-70, y+27);
  });

  rrect(44, 624, _W-88, 56, 14, '#E84B2B', '#FFD700', 3);
  _ctx.fillStyle = '#fff'; _ctx.font = 'bold 20px "Kosugi Maru",sans-serif'; _ctx.textAlign = 'center';
  _ctx.fillText('もう一度プレイ', _W/2, 659);

  rrect(44, 694, _W-88, 52, 13, 'rgba(20,20,60,0.95)', '#445588', 2);
  _ctx.fillStyle = '#AAC0FF'; _ctx.font = 'bold 18px "Kosugi Maru",sans-serif';
  _ctx.fillText('タイトルへ', _W/2, 726);
}
