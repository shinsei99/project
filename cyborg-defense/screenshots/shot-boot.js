/* ── App Store 用スクリーンショットの細工（screenshots/shoot.sh が差し込む） ──
   なぜ要るか: このMacのターミナルには「アクセシビリティ」権限が無く、シミュレータへ
   タップを送れない（simtap.py が使えない）。そこで、**画面の状態をコードで作る**。
   IIFE の中に差し込むので、G / player / enemies などの内部にそのまま触れる。

   ★構図は「撮る直前に作って、そこで止める」こと。
     起動直後に作ると、撮影までの十数秒でゲートも敵も流れて別の絵になる（実際にそうなった）。
     ウェーブ数も update() が G.t から計算し直すので、止めないと 1 に戻る。

   ★配信物には残さない。shoot.sh が撮影後に www/index.html で public/ を上書きする。 */
(function(){
  const SHOT = '__SHOT__';

  function place(type, xr, yr){          // 画面比で敵を置く（乱数だと絵が毎回変わる）
    const m = margin();
    spawnEnemy(m + (W - 2*m) * xr, type);
    const e = enemies[enemies.length-1];
    e.y = H * yr;
    return e;
  }
  function volley(){                     // 発射直後の弾を数発だけ置く（撃っている感じ）
    bullets.length = 0;
    soldierPositions().forEach((p, i) => {
      if (i % 2) return;                 // 全員ぶん置くと弾で画面が埋まる
      bullets.push({ x:p.x, y:p.y - 40 - (i%3)*46, vy:-560, r:4, dmg:player.damage });
    });
    player.flash = 0.06;                 // マズルフラッシュを出したまま止める
  }
  function freeze(){                     // 更新だけ止める（draw() は動き続けるので絵は出る）
    syncHUD();
    G.running = false;
  }

  function setup(){
    if (SHOT === 'title') return;        // タイトルはそのまま撮る

    start();
    G.banner = null;                     // バナーは絵の邪魔になるので消す
    enemies.length = 0; gates.length = 0; hazards.length = 0; shields.length = 0;
    parts.length = 0; texts.length = 0; rings.length = 0;

    if (SHOT === 'gate') {
      G.wave = 4; G.score = 118; G.coins = 41;
      player.soldiers = 6; player.base = 2; player.upR = 1; player.upD = 1; player.damage = 2;
      player.x = W * 0.5;
      spawnGate();
      gates[0].y = H * 0.46;
      gates[0].sections = [GATE.div2(), GATE.mul2(), GATE.sub()];   // 罠に挟まれた ×2 を見せる
      gates[0].active = 1;
      place('grunt', 0.18, 0.16); place('runner', 0.72, 0.10); place('grunt', 0.88, 0.24);
      volley(); freeze();
    }

    if (SHOT === 'battle') {
      G.wave = 6; G.score = 264; G.coins = 73;
      player.soldiers = 12; player.base = 3; player.upR = 2; player.upD = 2; player.damage = 3;
      player.x = W * 0.44;
      place('grunt', 0.22, 0.30); place('grunt', 0.55, 0.20); place('runner', 0.80, 0.36);
      place('brute', 0.34, 0.12); place('grunt', 0.92, 0.16);
      spawnHazard(); hazards[0].x = margin() + (W - 2*margin()) * 0.80; hazards[0].y = H * 0.50;
      burst(W * 0.55, H * 0.24, '#ff6b7a', 14, 110);
      volley(); freeze();
    }

    if (SHOT === 'boss') {
      G.wave = 8; G.score = 402; G.coins = 96;
      player.soldiers = 14; player.base = 4; player.upR = 3; player.upD = 3; player.damage = 4;
      player.x = W * 0.52;
      spawnShield(); G.banner = null;
      shields[0].y = H * 0.20; shields[0].hp = shields[0].maxHp * 0.5;
      place('grunt', 0.30, 0.44); place('runner', 0.66, 0.50);
      volley(); freeze();
    }

    if (SHOT === 'combo') {
      G.wave = 7; G.score = 355; G.coins = 88;
      player.soldiers = 16; player.base = 5; player.upR = 3; player.upD = 4; player.damage = 5;
      player.x = W * 0.5;
      G.combo = 24; G.comboT = 1.6;
      place('grunt', 0.22, 0.34); place('grunt', 0.74, 0.28); place('runner', 0.48, 0.42);
      place('brute', 0.60, 0.16);
      floatText(W * 0.5, H * 0.62, '20 連続  +6◈', '#ffe14d', 17);
      volley(); freeze();
    }

    if (SHOT === 'over') {
      // 背景に戦っていた跡を残す（真っ暗な画面でパネルだけだと寂しい）
      G.wave = 9; G.score = 486; G.coins = 112;
      player.soldiers = 9; player.base = 4; player.upR = 3; player.upD = 3; player.damage = 4;
      player.x = W * 0.5;
      place('grunt', 0.24, 0.26); place('brute', 0.62, 0.18); place('runner', 0.80, 0.34);
      volley();
      BEST = 613;                        // localStorage ではなく変数を直接（読み込みは起動時に済んでいる）
      player.hp = 0; gameOver();
    }
  }

  setTimeout(setup, 9200);               // shoot.sh は 11 秒で撮る。その直前に構図を作る
})();
