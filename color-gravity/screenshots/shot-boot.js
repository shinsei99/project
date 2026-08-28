/* App Store 用スクリーンショットの「画面づくり」だけを行う細工。
   ゲーム本体の <script> の末尾（requestAnimationFrame(frame) の直前）へ差し込まれるので、
   トップレベルの G / STAGES / init などにそのまま触れる。
   撮影が終わったら差し込みごと捨てるので、配信物には一切残らない。
   使い方は screenshots/shoot.sh を参照。__SHOT__ は Python で置き換わる。

   ★物理は触らない。ここでやるのは「その瞬間の状態を作って止める」だけ。
     止め方は G.mode に 'shot' を入れること（frame() は flying/demo のときしか進めないので、
     絵は描かれ続けるが、星は動かない）。 */
(function shotSetup(){
  var SHOT = '__SHOT__';

  // 全ステージを解放し、★も埋める（選択欄が🔒だらけだと「20面ある」ことが伝わらない）
  function unlockAll(stars){
    G.maxUnlocked = STAGES.length - 1;
    G.stars = {};
    for (var i = 0; i < STAGES.length; i++) G.stars[i] = stars[i % stars.length];
  }
  // sol（正解の発射ベクトル）で n 歩だけ進めた状態を作る。軌跡も残す
  function flyTo(n){
    var st = G.stage;
    var s = { x: st.cannon.x, y: st.cannon.y, vx: st.sol.vx, vy: st.sol.vy, color: new Set(st.start) };
    G.triggered = new Set(); G.trail = [];
    for (var i = 0; i < n; i++){
      stepSim(s, st, G.triggered);
      G.trail.push({ x: s.x, y: s.y, key: keyOf(s.color) });
      if (G.trail.length > 64) G.trail.shift();
    }
    G.star = s;
    G.mode = 'shot';
    syncHUD();
  }

  if (SHOT === 'title'){
    unlockAll([3,3,2,3,1,3,2,3,3,2]);
    hideOverlay();
    init(0);
    showTitle();

  } else if (SHOT === 'aim'){
    // 3面（赤ゲート＋青ゲート＝紫）で引っ張っている最中。予測軌道が出る
    unlockAll([3,3,2,3,1,3,2,3,3,2]);
    init(2);
    G.aim.active = true;
    G.aim.x = G.stage.cannon.x - 118;
    G.aim.y = G.stage.cannon.y + 92;

  } else if (SHOT === 'flight'){
    // 5面（赤・青・黄を通って白へ）。ゲートを2つ抜けたあたりで止める
    unlockAll([3,3,2,3,1,3,2,3,3,2]);
    init(4);
    flyTo(50);          // 3つのゲートを抜けて白になった直後（step 150 だと盤外まで飛んでいた）

  } else if (SHOT === 'clear'){
    unlockAll([3,3,2,3,1,3,2,3,3,2]);
    init(9);
    flyTo(52);
    doWin(false);

  } else if (SHOT === 'stages'){
    // 17面。ブラックホール2つ・ゲート3つ・惑星2つが一度に入る、いちばん賑やかな盤面
    unlockAll([3,3,2,3,1,3,2,3,3,2]);
    init(16);
    G.aim.active = true;
    G.aim.x = G.stage.cannon.x - 10;   // ほぼ真上へ引く＝予測軌道が盤面の中を通る
    G.aim.y = G.stage.cannon.y + 150;
  }
})();
