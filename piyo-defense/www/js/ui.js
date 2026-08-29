'use strict';

// ── Stage Intro ───────────────────────────────────────────────────────────────
function drawStageIntro(stage, timer, totalTime) {
  var progress = 1 - timer/totalTime;
  var alpha = progress < 0.35 ? progress/0.35 : progress > 0.70 ? 1-(progress-0.70)/0.30 : 1;
  _ctx.fillStyle='rgba(0,0,0,'+(alpha*0.78)+')'; _ctx.fillRect(0,0,_W,_H);
  var sc=0.82+alpha*0.18;
  _ctx.save(); _ctx.translate(_W/2,_H/2); _ctx.scale(sc,sc); _ctx.globalAlpha=alpha; _ctx.textAlign='center';
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=26;
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 26px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('STAGE',0,-36);
  _ctx.shadowColor='#FFFFFF'; _ctx.shadowBlur=22;
  _ctx.fillStyle='#FFFFFF'; _ctx.font='bold 86px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(stage,0,52);
  _ctx.shadowBlur=0;
  _ctx.fillStyle='rgba(180,210,255,0.70)'; _ctx.font='15px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('タップでスキップ',0,96);
  _ctx.globalAlpha=1; _ctx.restore();
}

// ── Button gradient ───────────────────────────────────────────────────────────
/* ★2026-08-29: ボタンの地を**一律で暗い紺**にした。
   呼び出し側は今までどおり色を渡してよい（無視する）。色分けは
   rrectGrd に渡す「縁の色」＝光る色のほうで付ける。
   こうしないと、赤や茶色の面がネオンの画面から浮く。
   ★暗くしすぎると押せる場所が分からなくなるので、上をわずかに明るくして立体を残している。 */
function _btnGrd(x, y, w, h, colTop, colBot) {
  var g=_ctx.createLinearGradient(x,y,x,y+h);
  g.addColorStop(0,'rgba(22,16,54,0.94)'); g.addColorStop(1,'rgba(8,5,24,0.94)'); return g;
}

// ── Battle HUD ───────────────────────────────────────────────────────────────
function drawHudTop(earthHP, maxEarthHP, barrierActive, stage, wave, wavesPerStage, score, level, xp, xpMax, kills, hs, frame, coins, poisonDebuff) {
  var barG=_ctx.createLinearGradient(0,0,0,82);
  barG.addColorStop(0,'rgba(8,12,32,0.88)'); barG.addColorStop(1,'rgba(4,8,20,0.95)');
  _ctx.fillStyle=barG; _ctx.fillRect(0,0,_W,82);
  _ctx.strokeStyle='rgba(80,140,220,0.22)'; _ctx.lineWidth=1.5;
  _ctx.beginPath(); _ctx.moveTo(0,82); _ctx.lineTo(_W,82); _ctx.stroke();

  drawEarth(24,26,18);
  var ratio=earthHP/maxEarthHP;
  rrect(48,13,_W-110,24,12,'rgba(0,0,0,0.7)','rgba(80,100,140,0.4)',1);
  if (ratio>0) {
    // ★2026-08-29: HPバーもネオン3色に（緑→黄→マゼンタ）。中は暗いまま、縁と光で見せる
    var hcol=ratio>0.55?'#7CFF4F':ratio>0.3?'#FFD54F':'#FF4FC3';
    var hG=_ctx.createLinearGradient(49,14,49,36);
    hG.addColorStop(0,hcol); hG.addColorStop(1,'rgba(10,8,26,0.85)');
    _ctx.save(); _ctx.shadowColor=hcol; _ctx.shadowBlur=12;
    rrectGrd(49,14,(_W-112)*ratio,22,11,hG,hcol,1.5);
    _ctx.restore();
  }
  // 毒デバフ表示
  if (poisonDebuff > 0) {
    _ctx.globalAlpha=0.7+Math.sin(frame*0.2)*0.2;
    rrect(47,12,_W-110,26,13,null,'#88FF44',2);
    _ctx.globalAlpha=1;
  }
  _ctx.fillStyle='#fff'; _ctx.font='bold 11px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center';
  _ctx.fillText('HP '+earthHP+'/'+maxEarthHP, 48+(_W-112)/2, 29);
  if (barrierActive) {
    _ctx.globalAlpha=0.55+Math.sin(frame*0.12)*0.3; rrect(47,12,_W-110,26,13,null,'#00FFFF',2.5); _ctx.globalAlpha=1;
  }

  var pG=_btnGrd(_W-46,8,36,30,'rgba(50,55,80,0.95)','rgba(20,22,40,0.95)');
  rrectGrd(_W-46,8,36,30,6,pG,'rgba(120,130,180,0.5)',1.5);
  _ctx.fillStyle='#ccc'; _ctx.font='bold 13px sans-serif'; _ctx.textAlign='center'; _ctx.fillText('❚❚',_W-28,28);

  // STAGE/WAVE
  var swG=_btnGrd(8,44,80,30,'rgba(20,40,80,0.92)','rgba(8,18,45,0.92)');
  rrectGrd(8,44,80,30,6,swG,'rgba(68,138,187,0.7)',1.5);
  _ctx.fillStyle='#7EC8E3'; _ctx.font='bold 9px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('STAGE '+stage,48,55);
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('WAVE '+wave+'/'+wavesPerStage,48,70);

  // SCORE
  var scG=_btnGrd(96,44,100,30,'rgba(25,25,45,0.92)','rgba(10,10,28,0.92)');
  rrectGrd(96,44,100,30,6,scG,'rgba(80,80,110,0.5)',1.5);
  _ctx.fillStyle='#888'; _ctx.font='9px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('SCORE',146,55);
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(score,146,70);

  // LV/XP
  var lvG=_btnGrd(204,44,80,30,'rgba(40,15,70,0.92)','rgba(18,6,36,0.92)');
  rrectGrd(204,44,80,30,6,lvG,'rgba(155,89,182,0.6)',1.5);
  _ctx.fillStyle='#CC88FF'; _ctx.font='bold 10px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('Lv.'+level,244,56);
  rrect(209,63,68,7,3,'rgba(0,0,0,0.55)',null);
  if (xp>0) {
    var xpG=_ctx.createLinearGradient(209,63,209,70);
    xpG.addColorStop(0,'#CC66FF'); xpG.addColorStop(1,'#7B00CC');
    rrectGrd(209,63,68*Math.min(1,xp/xpMax),7,3,xpG,null);
  }

  // コイン / 撃破 / HS
  // 旧版はコインのアイコンと「撃破:0 HS:0」が同じ座標帯に重なり、9pxの灰色文字で潰れていた。
  // 他のパネルと同じ枠を1つ置き、コイン＝上段・撃破/HS＝下段に分ける（2026-08-28）。
  var rx=_W-100, rw=92;
  var rG=_btnGrd(rx,44,rw,30,'rgba(30,26,10,0.92)','rgba(15,12,4,0.92)');
  rrectGrd(rx,44,rw,30,6,rG,'rgba(180,150,50,0.5)',1.5);
  drawCoinIcon(rx+12, 55, 6.5);
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 12px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='left';
  _ctx.fillText(coins, rx+22, 59);
  _ctx.fillStyle='#A0A0BC'; _ctx.font='9px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right';
  _ctx.fillText('撃破 '+kills+'  ｜  HS '+hs, rx+rw-7, 70);
}

function drawEvoBar(evoGauge, isEvolved, evoTimer, isAngel, angelTimer) {
  if (evoGauge<=0&&!isEvolved&&!isAngel) return;
  var bx=8,by=83,bw=_W-16,bh=8;
  rrect(bx-1,by-1,bw+2,bh+2,bh/2+1,'rgba(0,0,0,0.6)','rgba(60,60,80,0.4)',1);
  if (isAngel) {
    // エンジェルタイマーバー（青）
    var ea=_ctx.createLinearGradient(bx,by,bx,by+bh);
    ea.addColorStop(0,'#88CCFF'); ea.addColorStop(1,'#4488CC');
    rrectGrd(bx,by,bw*Math.max(0,Math.min(1,(angelTimer||0)/900)),bh,bh/2,ea,null);
    _ctx.fillStyle='#AADDFF'; _ctx.font='bold 9px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right';
    _ctx.fillText('😇 エンジェル変身中！ '+Math.ceil((angelTimer||0)/60)+'s',_W-10,by-1);
  } else {
    if (evoGauge>0) {
      var eg=_ctx.createLinearGradient(bx,by,bx,by+bh);
      eg.addColorStop(0,isEvolved?'#FF9060':'#FFE040'); eg.addColorStop(1,isEvolved?'#CC4400':'#E8A000');
      rrectGrd(bx,by,bw*(evoGauge/100),bh,bh/2,eg,null);
    }
    if (isEvolved) {
      _ctx.fillStyle='#FF6B35'; _ctx.font='bold 9px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right';
      _ctx.fillText('にわトリ変身中！ '+Math.ceil(evoTimer/60)+'s',_W-10,by-1);
    }
  }
}

function drawCompanionBtns(upg, cds, CD_MAX, frame) {
  // ★2026-08-29: 茶・桃・青の丸ボタンをやめ、**暗い地＋ネオンの輪**にした
  //   （中身のひよこは残す。誰を呼ぶかが分からなくなるため）。
  //   色の役割は輪のほうに移した: 軍師＝黄／ナース＝マゼンタ／バリア＝シアン。
  var BTNS=[
    {id:'gunshi', label:'軍師',   x:50,    neon:'#FFD54F', acc:'glasses'},
    {id:'nurse',  label:'ナース', x:_W/2,  neon:'#FF4FC3', acc:'nurse'  },
    {id:'barrier',label:'バリア', x:_W-50, neon:'#41E3FF', acc:'helmet' },
  ];
  var BY=_H-65,BR=30;
  BTNS.forEach(function(btn){
    var unlocked=upg[btn.id],cd=cds[btn.id],cdMax=CD_MAX[btn.id];
    _ctx.beginPath(); _ctx.arc(btn.x,BY+3,BR,0,Math.PI*2); _ctx.fillStyle='rgba(0,0,0,0.4)'; _ctx.fill();
    var ready=unlocked&&cd<=0;
    var cG=_ctx.createRadialGradient(btn.x-BR*0.3,BY-BR*0.3,2,btn.x,BY,BR);
    cG.addColorStop(0,'rgba(24,17,58,0.95)'); cG.addColorStop(1,'rgba(8,5,22,0.95)');
    _ctx.beginPath(); _ctx.arc(btn.x,BY,BR,0,Math.PI*2); _ctx.fillStyle=cG; _ctx.fill();
    _ctx.save();
    if(ready){ _ctx.shadowColor=btn.neon; _ctx.shadowBlur=14; _ctx.strokeStyle=btn.neon; _ctx.lineWidth=2.6; }
    else { _ctx.strokeStyle=unlocked?'rgba(120,130,180,0.5)':'rgba(70,75,110,0.45)'; _ctx.lineWidth=1.5; }
    _ctx.beginPath(); _ctx.arc(btn.x,BY,BR,0,Math.PI*2); _ctx.stroke();
    _ctx.restore();
    if(unlocked&&cd>0){
      _ctx.globalAlpha=0.55;_ctx.fillStyle='#000';_ctx.beginPath();_ctx.moveTo(btn.x,BY);_ctx.arc(btn.x,BY,BR,-Math.PI/2,-Math.PI/2+Math.PI*2*(cd/cdMax));_ctx.closePath();_ctx.fill();_ctx.globalAlpha=1;
      _ctx.fillStyle='#fff';_ctx.font='bold 12px sans-serif';_ctx.textAlign='center';_ctx.fillText(Math.ceil(cd/60)+'s',btn.x,BY+5);
    } else if(unlocked){drawChick(btn.x,BY-2,22,false,btn.acc);}
    else{_ctx.fillStyle='#555';_ctx.font='20px sans-serif';_ctx.textAlign='center';_ctx.textBaseline='middle';_ctx.fillText('🔒',btn.x,BY);_ctx.textBaseline='alphabetic';}
    _ctx.fillStyle=unlocked?(ready?btn.neon:'#9FB0D8'):'#4A4F70';_ctx.font='9px Orbitron,"Zen Kaku Gothic New",sans-serif';_ctx.textAlign='center';_ctx.fillText(btn.label,btn.x,BY+BR+13);
  });
}

// ── Boss Warning ──────────────────────────────────────────────────────────────
function drawBossWarn(timer, totalWarnTime) {
  var pulse=Math.abs(Math.sin(timer*0.18));
  _ctx.fillStyle='rgba(160,0,0,'+(pulse*0.38)+')'; _ctx.fillRect(0,0,_W,_H);
  var sc=1+Math.sin(timer*0.22)*0.08;
  _ctx.save(); _ctx.translate(_W/2,_H/2-30); _ctx.scale(sc,sc); _ctx.textAlign='center';
  _ctx.shadowColor='#FF0000'; _ctx.shadowBlur=28; _ctx.strokeStyle='#000'; _ctx.lineWidth=10; _ctx.fillStyle='#FF1A1A';
  _ctx.font='bold 48px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.strokeText('⚠️ WARNING!! ⚠️',0,0); _ctx.fillText('⚠️ WARNING!! ⚠️',0,0);
  _ctx.shadowColor='#FF8800'; _ctx.shadowBlur=16; _ctx.strokeStyle='#000'; _ctx.lineWidth=7; _ctx.fillStyle='#FFD700';
  _ctx.font='bold 31px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.strokeText('BOSS INCOMING!!',0,50); _ctx.fillText('BOSS INCOMING!!',0,50);
  _ctx.shadowBlur=0; _ctx.restore();
}

// ── Stage Clear ───────────────────────────────────────────────────────────────
function drawStageClear(stage, totalStages, timer, totalTime, frame) {
  var progress=1-(timer/totalTime), fadeIn=Math.min(1,progress*5);
  _ctx.fillStyle='rgba(0,0,0,'+(0.55*fadeIn)+')'; _ctx.fillRect(0,0,_W,_H);
  var sc=(1+Math.sin(frame*0.08)*0.04)*fadeIn;
  _ctx.save(); _ctx.translate(_W/2,_H*0.38); _ctx.scale(sc,sc); _ctx.textAlign='center';
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=28; _ctx.fillStyle='#FFD700'; _ctx.font='bold 44px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('STAGE '+stage,0,0);
  _ctx.shadowColor='#FFFFFF'; _ctx.shadowBlur=18; _ctx.fillStyle='#FFFFFF'; _ctx.font='bold 54px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('CLEAR!!',0,64);
  _ctx.shadowBlur=0; _ctx.restore();
  _ctx.globalAlpha=fadeIn;
  if (stage<totalStages) {
    _ctx.fillStyle='rgba(200,220,255,0.85)'; _ctx.font='16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('STAGE '+(stage+1)+' へ進む...',_W/2,_H*0.38+126);
    _ctx.fillStyle='#4EE890'; _ctx.font='14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('地球HP +20 ボーナス！',_W/2,_H*0.38+150);
  } else {
    _ctx.fillStyle='#FFD700'; _ctx.font='bold 20px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('ALL STAGES COMPLETE!!',_W/2,_H*0.38+126);
  }
  _ctx.globalAlpha=1;
}

// ── Title（全面刷新版） ────────────────────────────────────────────────────────
// タップ領域:
//   START:        y=450-510, x=50-340
//   図鑑:          y=522-568, x=50-190
//   実績:          y=522-568, x=200-340
//   設定&ショップ:  y=580-626, x=50-340
function drawTitle(frame, hs, bs, bgmOn, seOn, coins) {
  coins = coins || 0;
  // 背景・地面はバトル画面と同じものを使う（2026-08-28）。
  // 以前はタイトルだけ独自の空（下端が rgb(4,3,14) の真っ黒）と、
  // 平らな緑の長方形の地面を持っていて、遊び始めると絵が変わってしまっていた。
  drawBg(frame, 1);
  drawGround(1);

  // 浮遊パーティクル
  for (var j=0;j<20;j++) {
    var py=_H-((frame*0.48+j*42)%_H);
    var px=(j*91+Math.sin(frame*0.013+j*0.9)*28+22)%(_W-36)+18;
    var pa=Math.abs(Math.sin(frame*0.028+j*1.2))*0.44+0.06;
    _ctx.globalAlpha=pa;
    _ctx.fillStyle=j%4===0?'#FFD54F':j%4===1?'#FF4FC3':j%4===2?'#41E3FF':'#7CFF4F';
    _ctx.beginPath(); _ctx.arc(px,py,1.1+(j%3)*0.55,0,Math.PI*2); _ctx.fill();
  }
  _ctx.globalAlpha=1; _ctx.textAlign='center';

  // タイトルテキスト
  var titleBob=Math.sin(frame*0.042)*2.5, titleSc=1+Math.sin(frame*0.028)*0.016;
  var bloom=_ctx.createRadialGradient(_W/2,144+titleBob,0,_W/2,144+titleBob,150);
  bloom.addColorStop(0,'rgba(65,227,255,0.18)'); bloom.addColorStop(1,'rgba(65,227,255,0)');
  _ctx.fillStyle=bloom; _ctx.fillRect(0,50+titleBob,_W,170);
  _ctx.fillStyle='rgba(255,79,195,0.85)'; _ctx.font='bold 12px Orbitron,"Zen Kaku Gothic New",sans-serif';
  _ctx.save(); _ctx.shadowColor='#FF4FC3'; _ctx.shadowBlur=12;
  _ctx.fillText('N E O N   T O W E R',_W/2,98+titleBob); _ctx.restore();
  /* ★2026-08-29: 題字を**レインボー**に（6本共通の合図。neon-blocks/NEON_STYLE.md）。
     CSS の background-clip:text は canvas では使えないので、
     文字幅ぶんの横グラデーションを作って fillStyle にする。 */
  _ctx.save(); _ctx.translate(_W/2,152+titleBob); _ctx.scale(titleSc,titleSc);
  _ctx.font='bold 44px Orbitron,"Zen Kaku Gothic New",sans-serif';
  var tw=_ctx.measureText('ネオンタワー').width;
  var tg=_ctx.createLinearGradient(-tw/2,0,tw/2,0);
  // ★色の並びはゲームごとに違う（6色の輪を1つずつ回す。neon-blocks/NEON_STYLE.md）。タワーは3番目から
  tg.addColorStop(0,'#B026FF'); tg.addColorStop(0.4,'#FF2D95');
  tg.addColorStop(0.7,'#FFD54F'); tg.addColorStop(1,'#FF8A3D');
  _ctx.shadowColor='rgba(0,240,255,.55)'; _ctx.shadowBlur=26;
  _ctx.fillStyle=tg; _ctx.fillText('ネオンタワー',0,0);
  _ctx.shadowBlur=0; _ctx.fillText('ネオンタワー',0,0);   // 影なしでもう一度＝色をはっきりさせる
  _ctx.restore();
  _ctx.shadowColor='#41E3FF'; _ctx.shadowBlur=10;
  _ctx.fillStyle='#8FE9FF'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('～地球救出大作戦～',_W/2,176+titleBob);
  // 1行の説明（他の5本と同じ位置づけ）
  _ctx.shadowBlur=0;
  _ctx.fillStyle='rgba(178,196,236,0.9)'; _ctx.font='11px Orbitron,"Zen Kaku Gothic New",sans-serif';
  _ctx.fillText('タワーを置いて敵を撃ち落とせ。全20ステージ × 5Wave',_W/2,196+titleBob);
  _ctx.shadowBlur=0;

  // キャラゾーン
  var chickBob=Math.sin(frame*0.052)*5, chickSc=1+Math.sin(frame*0.038)*0.028;
  _ctx.globalAlpha=0.15+Math.sin(frame*0.08)*0.06;
  var aGrd=_ctx.createRadialGradient(_W/2,288+chickBob,0,_W/2,288+chickBob,88);
  aGrd.addColorStop(0,'#41E3FF'); aGrd.addColorStop(1,'rgba(65,227,255,0)');
  _ctx.fillStyle=aGrd; _ctx.beginPath(); _ctx.arc(_W/2,288+chickBob,88,0,Math.PI*2); _ctx.fill();
  _ctx.globalAlpha=1;

  // 歩くひよこ（タイトル画面アニメ）
  var walkCycle=Math.sin(frame*0.15)*0.12;
  var w1x=((frame*0.8+100)%(_W+80))-40;
  var w2x=_W-((frame*0.55+50)%(_W+80))+40;
  _ctx.save(); _ctx.translate(w1x, _H-148); _ctx.scale(1+Math.abs(walkCycle)*0.08,1); drawChick(0,walkCycle*20,24,false); _ctx.restore();
  _ctx.save(); _ctx.translate(w2x, _H-138); _ctx.scale(-1,1); drawChick(0,walkCycle*20,20,false); _ctx.restore();

  // 手前で揺れる光の穂（もとは緑の草。夜のネオンの地面に緑の草だけ残って浮いていた）
  for (var gi=0;gi<22;gi++) {
    var gx=(gi*43+17)%_W;
    var sway=Math.sin(frame*0.03+gi*0.7)*4;
    var gby=_H-96+(gi*29)%54;
    _ctx.globalAlpha=0.30+Math.abs(Math.sin(frame*0.04+gi))*0.18;
    _ctx.save();
    _ctx.shadowColor=gi%3===0?'#FF4FC3':'#41E3FF'; _ctx.shadowBlur=8;
    _ctx.strokeStyle=gi%3===0?'rgba(255,79,195,0.85)':'rgba(65,227,255,0.85)';
    _ctx.lineWidth=1.6; _ctx.lineCap='round';
    _ctx.beginPath(); _ctx.moveTo(gx,gby); _ctx.quadraticCurveTo(gx+sway,gby-9,gx+sway*1.5,gby-15); _ctx.stroke();
    _ctx.restore();
    _ctx.globalAlpha=1; _ctx.lineCap='butt';
  }

  // 飛んでいる敵。drawCrow は NEON_ENEMY があるとネオンブロックに切り替わるので、
  // ここは呼び出しのままでバトルと同じ絵になる（実測で確認済み・書き換え不要だった）
  var orb=Math.sin(frame*0.025)*7;
  drawCrow({x:78+orb, y:256+Math.sin(frame*0.042)*5,  size:26, hp:3,  maxHp:3,  wobble:frame*0.05,   type:'normal',   hitFlash:0, rangedTimer:0});
  drawCrow({x:312-orb,y:250+Math.sin(frame*0.042+1)*5,size:20, hp:3,  maxHp:3,  wobble:frame*0.05+1, type:'fast',     hitFlash:0, rangedTimer:0});
  drawCrow({x:195,    y:238+Math.sin(frame*0.042+2)*4, size:36, hp:24, maxHp:24, wobble:frame*0.05+2, type:'tank',     hitFlash:0, rangedTimer:0});

  // メインひよこ
  _ctx.save(); _ctx.translate(_W/2,288+chickBob); _ctx.scale(chickSc,chickSc); drawChick(0,0,78,false); _ctx.restore();
  drawEarth(_W/2,402,36);

  /* ★2026-08-29: トップ画面を他の5本と同じ形に整理した（オーナー指摘「ごちゃごちゃしてる」）。
     ・**ベスト／STAGE／所持コインのパネルを外した**（情報であって操作ではない。
       ベストはゲームオーバー画面、コインはショップと戦闘HUDに出るので、ここには要らない）
     ・図鑑・実績・ショップは**小さいボタン1行**にまとめた（前は2行＋幅いっぱいで主役級に見えていた）
     ・**主役は START だけ**。他5本と同じ「題名 → 1行 → START」の並びになる
     ★game.js のタップ判定も同じ数字にそろえること */

  // STARTボタン（y=496-548）
  var pulse=Math.sin(frame*0.07)*3;
  var glow=0.55+Math.abs(Math.sin(frame*0.07))*0.45;
  var stG=_ctx.createLinearGradient(72,496+pulse,72,552+pulse);
  stG.addColorStop(0,'rgba(70,14,52,0.95)'); stG.addColorStop(1,'rgba(24,6,24,0.95)');
  _ctx.save();
  _ctx.shadowColor='rgba(255,79,195,'+glow.toFixed(2)+')'; _ctx.shadowBlur=18;
  rrectGrd(72,496+pulse,246,52,10,stG,'#FF4FC3',3);
  _ctx.restore();
  _ctx.save();
  _ctx.shadowColor='#FF4FC3'; _ctx.shadowBlur=14;
  _ctx.fillStyle='#FFFFFF'; _ctx.font='bold 25px Orbitron,"Zen Kaku Gothic New",sans-serif';
  _ctx.fillText('▶  START  ◀',_W/2,530+pulse);
  _ctx.restore();

  // 副ボタン3つ（y=568-604）。小さく1行に並べる
  var SUB=[
    {x:34,  w:104, label:'図鑑', col:'rgba(65,227,255,0.7)',  txt:'#8FE9FF'},
    {x:143, w:104, label:'実績', col:'rgba(255,213,79,0.7)',  txt:'#FFD54F'},
    {x:252, w:104, label:'強化', col:'rgba(179,107,255,0.7)', txt:'#C9A8FF'}
  ];
  SUB.forEach(function(b){
    var g=_btnGrd(b.x,568,b.w,36,'','');
    rrectGrd(b.x,568,b.w,36,6,g,b.col,1.5);
    _ctx.fillStyle=b.txt; _ctx.font='bold 13px Orbitron,"Zen Kaku Gothic New",sans-serif';
    _ctx.textAlign='center'; _ctx.fillText(b.label, b.x+b.w/2, 591);
  });

  // ★説明は題名の下の1行に移した（他の5本と同じ並び）。フッターは版の表示だけ残す
  _ctx.fillStyle='rgba(255,255,255,0.28)'; _ctx.font='10px sans-serif';
  _ctx.textAlign='center'; _ctx.fillText('NEON TOWER  v4.0',_W/2,_H-18);
}

// ── Settings & Shop（y範囲メモ：各ボタンy記載） ────────────────────────────
// ショップ購入エリア: y=140+i*106 height=90
// BGM: y=800-840, SE: y=852-892
// 戻る: y=752-798
function drawSettings(frame, bgmOn, seOn) {
  drawBg(frame);
  _ctx.fillStyle='rgba(0,0,12,0.86)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.shadowColor='#AAAAFF'; _ctx.shadowBlur=14;
  _ctx.fillStyle='#AAAAFF'; _ctx.font='bold 24px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('⚙ 設定 & 強化ショップ',_W/2,60);
  _ctx.shadowBlur=0;

  var coins=SaveManager.getCoins();
  // ★コインの絵と文字が重なっていたので、文字幅を測ってから左に並べる（固定値で置かない）
  _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif';
  var cTxt='所持コイン: '+coins;
  var cW=_ctx.measureText(cTxt).width;
  drawCoinIcon(_W/2-cW/2-14,85,10);
  _ctx.fillStyle='#FFD54F'; _ctx.textAlign='left'; _ctx.fillText(cTxt,_W/2-cW/2,90);
  _ctx.textAlign='center';

  // ショップアイテム（最大6個）
  var lvls=SaveManager.getShopLevels();
  SHOP_ITEMS.forEach(function(item,i) {
    var lv=lvls[item.id]||0;
    var maxed=lv>=item.maxLv;
    var cost=maxed?0:item.costs[lv];
    var iy=110+i*112;
    var canAfford=!maxed&&coins>=cost;

    var ig=_btnGrd(18,iy,_W-36,96,
      canAfford?'rgba(20,30,80,0.95)':maxed?'rgba(10,40,10,0.95)':'rgba(30,15,15,0.95)',
      canAfford?'rgba(8,12,50,0.95)':maxed?'rgba(4,20,4,0.95)':'rgba(15,6,6,0.95)');
    rrectGrd(18,iy,_W-36,96,12,ig,
      canAfford?'rgba(80,120,200,0.6)':maxed?'rgba(80,200,80,0.5)':'rgba(120,60,60,0.4)',1.5);

    // アイコン
    _ctx.font='28px sans-serif'; _ctx.textAlign='left'; _ctx.fillText(item.icon,32,iy+44);
    // 名前
    _ctx.fillStyle=maxed?'#88FF88':canAfford?'#FFD700':'#888';
    _ctx.font='bold 15px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='left'; _ctx.fillText(item.name,70,iy+32);
    // 説明
    _ctx.fillStyle='#aaa'; _ctx.font='12px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(item.desc,70,iy+52);
    // レベルドット
    for (var li=0;li<item.maxLv;li++) {
      _ctx.fillStyle=li<lv?'#FFD700':'rgba(255,255,255,0.18)';
      _ctx.beginPath(); _ctx.arc(70+li*14,iy+72,4.5,0,Math.PI*2); _ctx.fill();
    }
    // コスト or MAX
    if (maxed) {
      _ctx.fillStyle='#88FF88'; _ctx.font='bold 13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right'; _ctx.fillText('MAX',_W-28,iy+72);
    } else {
      drawCoinIcon(_W-76,iy+64,8);
      _ctx.fillStyle=canAfford?'#FFD700':'#AA6655'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right'; _ctx.fillText(cost,_W-28,iy+72);
    }
  });

  // BGM/SE (y=790, y=840)
  var bgmG=_btnGrd(18,780,(_W-44)/2,48,bgmOn?'rgba(10,55,10,0.95)':'rgba(48,10,10,0.95)',bgmOn?'rgba(4,33,4,0.95)':'rgba(28,4,4,0.95)');
  rrectGrd(18,780,(_W-44)/2,48,10,bgmG,bgmOn?'rgba(45,165,45,0.55)':'rgba(165,45,45,0.5)',1.5);
  _ctx.fillStyle=bgmOn?'#80F080':'#F08080'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center';
  _ctx.fillText('♪ BGM '+(bgmOn?'ON':'OFF'),18+(_W-44)/4,810);

  var seG=_btnGrd(26+(_W-44)/2,780,(_W-44)/2,48,seOn?'rgba(10,55,10,0.95)':'rgba(48,10,10,0.95)',seOn?'rgba(4,33,4,0.95)':'rgba(28,4,4,0.95)');
  rrectGrd(26+(_W-44)/2,780,(_W-44)/2,48,10,seG,seOn?'rgba(45,165,45,0.55)':'rgba(165,45,45,0.5)',1.5);
  _ctx.fillStyle=seOn?'#80F080':'#F08080';
  _ctx.fillText('♩ SE  '+(seOn?'ON':'OFF'),26+(_W-44)/2+(_W-44)/4,810);

  // 戻る (y=840-888)
  var bk2G=_btnGrd(50,840,_W-100,46,'rgba(22,24,76,0.92)','rgba(9,10,48,0.92)');
  rrectGrd(50,840,_W-100,46,11,bk2G,'rgba(65,85,175,0.56)',1.5);
  _ctx.fillStyle='#AAC0FF'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('← タイトルに戻る',_W/2,869);
}

// ── 図鑑 ──────────────────────────────────────────────────────────────────────
// 戻るボタン: y=790-838
var BESTIARY_LABELS = {
  normal:'ノーマル',fast:'ファスト',ranged:'遠距離',tank:'タンク',ghost:'ゴースト',
  healer:'ヒーラー',bomber:'ボンバー',sprinter:'スプリンター',armored:'装甲',
  regen:'リジェネ',shielded:'シールド',splitter:'分裂',swarm:'スウォーム',
  poison:'ポイズン',stealth:'ステルス',berserker:'バーサーカー',titan:'タイタン',
  leech:'リーチ',necro:'ネクロ',phantom:'ファントム',
  boss_chicken:'ニワトリ大魔王',boss_snake:'巨大ヘビ',boss:'UFOボス'
};
var BESTIARY_DESC = {
  normal:'基本的な敵。特殊能力なし。',
  fast:'移動速度が速い。HPは低め。',
  ranged:'遠距離から弾を発射する。',
  tank:'HPが高く移動が遅い。',
  ghost:'半透明で霞む。すり抜け注意。',
  healer:'周囲の敵を回復する。',
  bomber:'地面で爆発し大ダメージ。',
  sprinter:'突然高速ダッシュする。',
  armored:'ダメージが半減する。',
  regen:'自己回復する。',
  shielded:'シールドで最初の攻撃を吸収。',
  splitter:'死亡時に2体に分裂。',
  swarm:'分裂から生まれる小型敵。',
  poison:'到達時、攻撃速度が低下する。',
  stealth:'定期的に完全透明になる。',
  berserker:'HP低下で加速する。',
  titan:'巨大な超重装甲タンク。',
  leech:'自己回復する吸血鬼。',
  necro:'一度だけ復活する。',
  phantom:'定期的にテレポートする。',
  boss_chicken:'3way弾＋突進＋召喚。',
  boss_snake:'潜伏＋毒スプレー＋なぎ払い。',
  boss:'レーザー＋ミサイル＋回転弾。'
};

function drawBestiary(frame) {
  drawBg(frame);
  // 旧版は rgba(0,0,12,0.86) で空を塗り潰し、暗い地に暗いカードで全部読めなかった。
  // 薄い幕にして夜空を透かす（2026-08-28）。
  _ctx.fillStyle='rgba(6,10,30,0.60)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.shadowColor='#88AAFF'; _ctx.shadowBlur=14;
  _ctx.fillStyle='#BBD4FF'; _ctx.font='bold 24px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('📚 敵図鑑',_W/2,56);
  _ctx.shadowBlur=0;

  var bestiary=SaveManager.getBestiary();
  var types=BESTIARY_TYPES;
  var total=types.length;
  var found=types.filter(function(t){return bestiary[t]>0;}).length;
  _ctx.fillStyle='#9AD4FF'; _ctx.font='13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center';
  _ctx.fillText('撃破済み: '+found+'/'+total,_W/2,78);
  // 収集バー（あと何種いるかが一目で分かる）
  var pbw=_W-120;
  rrect(60,86,pbw,7,3.5,'rgba(0,0,0,0.5)','rgba(90,120,190,0.4)',1);
  if (found>0) {
    var pG2=_ctx.createLinearGradient(60,86,60+pbw,86);
    pG2.addColorStop(0,'#5FC8FF'); pG2.addColorStop(1,'#B98BFF');
    rrectGrd(60,86,pbw*(found/total),7,3.5,pG2,null);
  }

  // 3列グリッド（23種 → 8行）。旧版は rowH=90 で最終行が「戻る」ボタンの下に潜っていた
  var cols=3, rowH=84, startY=100, cardH=76;
  for (var ri=0;ri<types.length;ri++) {
    var type=types[ri];
    var col2=ri%cols, row2=~~(ri/cols);
    var ix=18+col2*(_W-36)/cols, iy=startY+row2*rowH;
    var iw=(_W-36)/cols-6;
    var seen=bestiary[type]>0;

    var bG2=_btnGrd(ix,iy,iw,cardH,seen?'rgba(20,36,80,0.94)':'rgba(16,20,42,0.90)',seen?'rgba(8,16,44,0.94)':'rgba(9,11,26,0.90)');
    rrectGrd(ix,iy,iw,cardH,8,bG2,seen?'rgba(96,150,230,0.75)':'rgba(70,80,120,0.45)',1.5);

    // 敵の姿。未発見は影絵で見せる（旧版は色付きの丸1個だけだった）
    _ctx.save();
    _ctx.translate(ix+iw/2, iy+30);
    if (!seen) _ctx.globalAlpha=0.75;
    drawCrow({ x:0, y:0, size:23, hp:3, maxHp:3, wobble:frame*0.05+ri,
               type:type, hitFlash:0, rangedTimer:0, healTimer:0, regenTimer:0,
               shield:0, maxShield:1, sprintPhase:0, enraged:false, isHidden:false,
               noHpBar:true, silhouette:!seen });
    _ctx.restore();

    _ctx.textAlign='center';
    if (seen) {
      _ctx.fillStyle='#FFD700'; _ctx.font='bold 10px Orbitron,"Zen Kaku Gothic New",sans-serif';
      _ctx.fillText(BESTIARY_LABELS[type]||type, ix+iw/2, iy+60);
      _ctx.fillStyle='#8FA8C8'; _ctx.font='9px Orbitron,"Zen Kaku Gothic New",sans-serif';
      _ctx.fillText('×'+(bestiary[type]||0), ix+iw/2, iy+71);
    } else {
      _ctx.fillStyle='#6B7699'; _ctx.font='bold 11px Orbitron,"Zen Kaku Gothic New",sans-serif';
      _ctx.fillText('？？？', ix+iw/2, iy+62);
    }
  }

  // 戻る (y=790-838)
  var bkG2=_btnGrd(50,790,_W-100,46,'rgba(22,24,76,0.92)','rgba(9,10,48,0.92)');
  rrectGrd(50,790,_W-100,46,11,bkG2,'rgba(65,85,175,0.56)',1.5);
  _ctx.fillStyle='#AAC0FF'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('← タイトルに戻る',_W/2,819);
}

// ── 実績 ──────────────────────────────────────────────────────────────────────
// 戻る: y=780-828
function drawAchievements(frame) {
  drawBg(frame);
  _ctx.fillStyle='rgba(0,0,12,0.86)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=14;
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 24px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('🏆 実績',_W/2,56);
  _ctx.shadowBlur=0;

  var ach=SaveManager.getAchievements();
  var done=ACHIEVEMENT_DEFS.filter(function(d){return ach[d.id];}).length;
  _ctx.fillStyle='#FFCC66'; _ctx.font='13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center';
  _ctx.fillText('達成済み: '+done+'/'+ACHIEVEMENT_DEFS.length,_W/2,78);

  ACHIEVEMENT_DEFS.forEach(function(def,i) {
    var achieved=!!ach[def.id];
    // ★2026-08-29: 実績が11件になり、**最後の1件が「タイトルに戻る」の下に潜っていた**
    //   （96 + 10×66 + 58 = 814 に対して、ボタンの上端は 780）。
    //   行の間隔を 66→61、高さを 58→54 に詰めて、最終行の下端を 760 にした。
    var ay=96+i*61;
    var ag=_btnGrd(18,ay,_W-36,54,
      achieved?'rgba(30,24,5,0.95)':'rgba(12,12,30,0.95)',
      achieved?'rgba(15,12,2,0.95)':'rgba(6,6,18,0.95)');
    rrectGrd(18,ay,_W-36,54,8,ag,achieved?'rgba(255,213,79,0.75)':'rgba(70,80,130,0.35)',1.5);

    _ctx.globalAlpha=achieved?1:0.35;
    _ctx.font='21px sans-serif'; _ctx.textAlign='left'; _ctx.fillText(def.icon,32,ay+35);
    _ctx.fillStyle=achieved?'#FFD54F':'#8891B8'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(def.name,64,ay+24);
    _ctx.fillStyle=achieved?'#CCAA44':'#5A6088'; _ctx.font='11px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(def.desc,64,ay+43);
    if (achieved) {
      // ★コインの絵（半径8）と「+40」が2pxだけ重なっていたので、幅を測って離す
      _ctx.font='bold 12px Orbitron,"Zen Kaku Gothic New",sans-serif';
      var rTxt='+'+def.reward, rW=_ctx.measureText(rTxt).width;
      drawCoinIcon(_W-24-rW-13,ay+27,8);
      _ctx.fillStyle='#FFD54F'; _ctx.textAlign='right'; _ctx.fillText(rTxt,_W-24,ay+32);
    }
    _ctx.globalAlpha=1;
  });

  var bkG3=_btnGrd(50,780,_W-100,46,'rgba(22,24,76,0.92)','rgba(9,10,48,0.92)');
  rrectGrd(50,780,_W-100,46,8,bkG3,'rgba(65,227,255,0.7)',2);
  _ctx.fillStyle='#8FE9FF'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('← タイトルに戻る',_W/2,809);
}

// ── 実績ポップアップ ─────────────────────────────────────────────────────────
function drawAchievementPopup(def, timer, maxTimer) {
  if (!def) return;
  var alpha=timer>maxTimer*0.8 ? (timer-maxTimer*0.8)/(maxTimer*0.2) :
             timer<maxTimer*0.2 ? timer/(maxTimer*0.2) : 1.0;
  alpha=Math.min(1,alpha);
  _ctx.save(); _ctx.globalAlpha=alpha;
  var py=_H-200;
  rrect(28,py,_W-56,72,14,'rgba(20,16,4,0.96)','rgba(200,160,40,0.8)',2.5);
  _ctx.font='26px sans-serif'; _ctx.textAlign='left'; _ctx.fillText(def.icon,46,py+44);
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('実績解除: '+def.name,84,py+28);
  _ctx.fillStyle='#CCAA44'; _ctx.font='12px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(def.desc,84,py+48);
  drawCoinIcon(_W-64,py+36,9);
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right'; _ctx.fillText('+'+def.reward,_W-38,py+41);
  _ctx.restore();
}

// ── How To ───────────────────────────────────────────────────────────────────
function drawHowTo(frame) {
  drawBg(frame);
  _ctx.fillStyle='rgba(0,0,10,0.84)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=12;
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 26px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('あそびかた',_W/2,78);
  _ctx.shadowBlur=0;
  var rows=[
    ['👆','画面を押しっぱなしで連続発射！'],
    ['🌍','地球のHPが0になるとゲームオーバー'],
    ['◀▶','◀▶ボタンかスワイプでレーン移動！'],
    ['⬆️','LvUP→フィールドにアイテムドロップ！'],
    ['⚠️','赤い警告列が出たら別レーンへ逃げろ！'],
    ['🏰','強化でタワーを設置して自動攻撃！'],
    ['💀','ボスは全20種！各ステージ固有の強敵！'],
    ['🏆','全20ステージをクリアせよ！'],
  ];
  rows.forEach(function(row,i) {
    var rG=_btnGrd(28,102+i*80,334,66,'rgba(12,12,44,0.92)','rgba(6,6,28,0.92)');
    rrectGrd(28,102+i*80,334,66,10,rG,'rgba(50,60,100,0.5)',1.5);
    _ctx.font='26px sans-serif'; _ctx.textAlign='left'; _ctx.fillStyle='#fff'; _ctx.fillText(row[0],56,146+i*80);
    _ctx.fillStyle='#dde'; _ctx.font='13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(row[1],96,146+i*80);
  });
  var bkG4=_btnGrd(72,750,246,52,'rgba(28,42,100,0.95)','rgba(12,18,60,0.95)');
  rrectGrd(72,750,246,52,13,bkG4,'rgba(100,160,220,0.6)',2.5);
  _ctx.fillStyle='#AAC0FF'; _ctx.font='bold 18px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('タイトルに戻る',_W/2,782);
}

// ── Level Up ─────────────────────────────────────────────────────────────────
function drawLevelUp(choices, level) {
  _ctx.fillStyle='rgba(0,0,12,0.80)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.textAlign='center';
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=28;
  _ctx.fillStyle='#FFD700'; _ctx.font='bold 38px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('LEVEL UP!',_W/2,172);
  _ctx.shadowBlur=0;
  _ctx.fillStyle='#CC88FF'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('Lv.'+level+' に上がった！',_W/2,200);
  _ctx.fillStyle='rgba(255,200,80,0.85)'; _ctx.font='12px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('⏱ ゲームはスローで継続中',_W/2,222);
  _ctx.fillStyle='#888'; _ctx.font='12px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('強化を1つ選んでください',_W/2,242);

  choices.forEach(function(ch,i) {
    var cy=258+i*184;
    var cG=_btnGrd(20,cy,_W-40,168,'rgba(12,22,65,0.97)','rgba(5,10,40,0.97)');
    rrectGrd(20,cy,_W-40,168,14,cG,'rgba(80,100,200,0.6)',2.5);
    _ctx.fillStyle='rgba(255,255,255,0.07)';
    _ctx.beginPath(); _ctx.moveTo(34,cy+2); _ctx.lineTo(_W-34,cy+2); _ctx.lineTo(_W-34,cy+24); _ctx.lineTo(34,cy+24); _ctx.closePath(); _ctx.fill();
    _ctx.font='36px sans-serif'; _ctx.textAlign='center'; _ctx.fillText(ch.icon,_W/2,cy+54);
    _ctx.fillStyle='#FFD700'; _ctx.font='bold 19px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(ch.name,_W/2,cy+90);
    _ctx.fillStyle='#aaa'; _ctx.font='13px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText(ch.desc,_W/2,cy+118);
    _ctx.fillStyle='rgba(255,255,255,0.25)'; _ctx.font='11px sans-serif'; _ctx.fillText('タップして選択',_W/2,cy+146);
  });
}

// ── Pause ────────────────────────────────────────────────────────────────────
function drawPause(stage, wave, score) {
  _ctx.fillStyle='rgba(0,0,0,0.82)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.fillStyle='#fff'; _ctx.font='bold 40px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('PAUSE',_W/2,280);
  _ctx.fillStyle='#666'; _ctx.font='14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('STAGE '+stage+'  WAVE '+wave+'  SCORE '+score,_W/2,316);
  var r1G=_btnGrd(72,358,246,58,'rgba(32,72,180,0.95)','rgba(14,36,110,0.95)');
  rrectGrd(72,358,246,58,14,r1G,'rgba(100,180,220,0.6)',2.5);
  _ctx.fillStyle='#fff'; _ctx.font='bold 20px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('再開する',_W/2,394);
  var r2G=_btnGrd(72,436,246,58,'rgba(130,22,22,0.95)','rgba(80,8,8,0.95)');
  rrectGrd(72,436,246,58,14,r2G,'rgba(220,80,80,0.6)',2.5);
  _ctx.fillStyle='#fff'; _ctx.fillText('最初からやり直す',_W/2,472);
  var r3G=_btnGrd(72,514,246,58,'rgba(20,22,65,0.95)','rgba(8,10,38,0.95)');
  rrectGrd(72,514,246,58,14,r3G,'rgba(60,80,160,0.5)',2);
  _ctx.fillStyle='#AAC0FF'; _ctx.fillText('タイトルへ',_W/2,550);
}

// ── Game Over ─────────────────────────────────────────────────────────────────
function drawGameOver(score, stage, wave, kills, isNewHS, hs, bs, frame, runCoins) {
  // 月は消す（同じ位置に地球を描くので、並ぶと灰色の塊に見える）
  drawBg(frame, 1, true);
  _ctx.fillStyle='rgba(0,0,0,0.80)'; _ctx.fillRect(0,0,_W,_H);
  _ctx.textAlign='center';
  _ctx.shadowColor='#FF2020'; _ctx.shadowBlur=28; _ctx.fillStyle='#FF4444'; _ctx.font='bold 44px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('EARTH CRASH!',_W/2,148); _ctx.shadowBlur=0;
  drawEarth(_W/2,228,36);
  _ctx.strokeStyle='#FF4444'; _ctx.lineWidth=4;
  _ctx.beginPath(); _ctx.moveTo(_W/2-6,193); _ctx.lineTo(_W/2+5,218); _ctx.lineTo(_W/2-10,263); _ctx.stroke();
  if (isNewHS) {
    _ctx.shadowColor='#FFD54F'; _ctx.shadowBlur=14; _ctx.fillStyle='#FFD54F'; _ctx.font='bold 18px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('🏆 NEW HIGH SCORE! 🏆',_W/2,292); _ctx.shadowBlur=0;
  }
  var rows=[
    ['スコア',score],['到達ステージ','STAGE '+stage+' - WAVE '+wave],
    ['撃破数',kills+' 体'],['ベストスコア',hs],['最高クリアST',bs>0?'STAGE '+bs:'---'],
  ];
  rows.forEach(function(row,i) {
    var ry=308+i*42;
    var rG=_btnGrd(44,ry,_W-88,34,'rgba(12,14,36,0.92)','rgba(6,8,22,0.92)');
    rrectGrd(44,ry,_W-88,34,6,rG,'rgba(65,227,255,0.35)',1.5);
    _ctx.fillStyle='#8891B8'; _ctx.font='11px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='left'; _ctx.fillText(row[0],62,ry+21);
    _ctx.fillStyle='#fff'; _ctx.font='bold 14px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right'; _ctx.fillText(row[1],_W-56,ry+21);
  });
  // コイン獲得表示
  if (runCoins > 0) {
    var cy2=520;
    rrect(44,cy2,_W-88,36,8,'rgba(30,24,5,0.90)','rgba(180,140,30,0.6)',1.5);
    drawCoinIcon(64,cy2+18,9); _ctx.fillStyle='#FFD700'; _ctx.font='bold 15px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center';
    _ctx.fillText('コイン +'+runCoins+' 獲得！',_W/2+6,cy2+23);
  }
  // ★2026-08-29: 橙のグラデーションをやめ、ネオン（緑＝進む色）にした
  var cG2=_ctx.createLinearGradient(44,566,44,622);
  cG2.addColorStop(0,'rgba(18,50,20,0.95)'); cG2.addColorStop(1,'rgba(6,20,10,0.95)');
  _ctx.shadowColor='rgba(255,80,30,0.7)'; _ctx.shadowBlur=20;
  rrectGrd(44,566,_W-88,54,10,cG2,'#7CFF4F',3); _ctx.shadowBlur=0;
  _ctx.fillStyle='#fff'; _ctx.font='bold 17px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('▶ STAGE '+stage+' からコンテニュー',_W/2,590);
  _ctx.fillStyle='rgba(160,230,180,0.8)'; _ctx.font='11px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('スコアはリセット',_W/2,608);
  var rG2=_btnGrd(44,630,_W-88,46,'rgba(30,12,12,0.95)','rgba(15,5,5,0.95)');
  rrectGrd(44,630,_W-88,46,8,rG2,'rgba(255,79,195,0.7)',2);
  _ctx.fillStyle='#FF9AD8'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('最初からやり直す',_W/2,659);
  var tG2=_btnGrd(44,686,_W-88,46,'rgba(18,20,60,0.95)','rgba(7,9,34,0.95)');
  rrectGrd(44,686,_W-88,46,8,tG2,'rgba(65,227,255,0.7)',2);
  _ctx.fillStyle='#8FE9FF'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('タイトルへ',_W/2,715);
}

// ── Ending ───────────────────────────────────────────────────────────────────
function drawEnding(score, kills, playFrames, isNewHS, hs, frame, runCoins) {
  var g=_ctx.createLinearGradient(0,0,0,_H);
  g.addColorStop(0,'#001040'); g.addColorStop(1,'#001A08');
  _ctx.fillStyle=g; _ctx.fillRect(0,0,_W,_H);
  for (var i=0;i<70;i++) {
    var sx=(i*141+47)%_W,sy=(i*233+31)%_H;
    _ctx.globalAlpha=(Math.sin(frame*0.04+i)*0.3+0.7)*0.9; _ctx.fillStyle='#fff';
    _ctx.beginPath(); _ctx.arc(sx,sy,1+(i%3)*0.4,0,Math.PI*2); _ctx.fill();
  }
  _ctx.globalAlpha=1;
  [[110,220],[280,200],[195,330]].forEach(function(fw,k) {
    var t=frame*0.04+k*2.1;
    ['#FF4444','#FFD700','#4ECDC4','#FF69B4','#fff','#88FF88'].forEach(function(c2,j) {
      var a2=t+j*(Math.PI*2/6), r2=28*Math.abs(Math.sin(t*0.6));
      _ctx.globalAlpha=Math.max(0,Math.abs(Math.sin(t))); _ctx.shadowColor=c2; _ctx.shadowBlur=6; _ctx.fillStyle=c2;
      _ctx.beginPath(); _ctx.arc(fw[0]+Math.cos(a2)*r2,fw[1]+Math.sin(a2)*r2,3,0,Math.PI*2); _ctx.fill();
    });
  });
  _ctx.globalAlpha=1; _ctx.shadowBlur=0;
  drawEarth(_W/2,180,70); _ctx.fillStyle='#FFD700'; _ctx.font='32px sans-serif'; _ctx.textAlign='center'; _ctx.fillText('🌟',_W/2,104);
  _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=22; _ctx.fillStyle='#FFD700'; _ctx.font='bold 52px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('ALL CLEAR!!',_W/2,292); _ctx.shadowBlur=0;
  drawChick(_W/2,368,58,true); drawChick(_W/2-90,392,34,false,'glasses'); drawChick(_W/2+90,392,34,false,'nurse'); drawChick(_W/2,412,28,false,'helmet');
  if (isNewHS) { _ctx.shadowColor='#FFD700'; _ctx.shadowBlur=12; _ctx.fillStyle='#FFD700'; _ctx.font='bold 18px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('🏆 NEW HIGH SCORE! 🏆',_W/2,452); _ctx.shadowBlur=0; }
  if (runCoins>0) {
    rrect(60,460,_W-120,36,8,'rgba(30,24,5,0.90)','rgba(180,140,30,0.6)',1.5);
    drawCoinIcon(_W/2-55,478,9); _ctx.fillStyle='#FFD700'; _ctx.font='bold 15px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('コイン +'+runCoins+' 獲得！',_W/2+6,483);
  }
  var mins=~~(playFrames/60/60),secs=~~(playFrames/60)%60;
  var timeStr=(mins<10?'0':'')+mins+':'+(secs<10?'0':'')+secs;
  var rows2=[['最終スコア',score],['撃破数',kills+' 体'],['プレイ時間',timeStr]];
  rows2.forEach(function(row,i) {
    var ry=506+i*52;
    var rG=_btnGrd(55,ry,_W-110,44,'rgba(10,12,36,0.88)','rgba(4,6,20,0.88)');
    rrectGrd(55,ry,_W-110,44,8,rG,'rgba(40,55,100,0.4)',1.5);
    _ctx.fillStyle='#777'; _ctx.font='12px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='left'; _ctx.fillText(row[0],76,ry+26);
    _ctx.fillStyle='#fff'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='right'; _ctx.fillText(row[1],_W-70,ry+26);
  });
  _ctx.fillStyle='#B8E8FF'; _ctx.font='bold 16px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.textAlign='center'; _ctx.fillText('THANK YOU FOR PLAYING!',_W/2,670);
  var eG=_ctx.createLinearGradient(55,682,55,736); eG.addColorStop(0,'#3060C0'); eG.addColorStop(1,'#1A3888');
  rrectGrd(55,682,_W-110,54,14,eG,'rgba(100,180,220,0.6)',2.5);
  _ctx.fillStyle='#fff'; _ctx.font='bold 20px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('もう一度プレイ',_W/2,716);
  var e2G=_btnGrd(55,746,_W-110,48,'rgba(20,22,65,0.95)','rgba(8,10,38,0.95)');
  rrectGrd(55,746,_W-110,48,13,e2G,'rgba(60,80,160,0.5)',2);
  _ctx.fillStyle='#AAC0FF'; _ctx.font='bold 18px Orbitron,"Zen Kaku Gothic New",sans-serif'; _ctx.fillText('タイトルへ',_W/2,777);
}
