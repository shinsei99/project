/* App Store 用スクリーンショットの「画面づくり」だけを行う細工。
   ここは www/index.html の IIFE の中に差し込まれる（＝内部の変数に触れる）。
   撮影が終わったら差し込みごと捨てるので、配信物には一切残らない。
   使い方は screenshots/shoot.sh を参照。__SHOT__ は sed で置き換わる。 */
(function shotSetup(){
  var SHOT = '__SHOT__';
  var F = ['vanilla','choco','strawberry','mint','soda','grape'];
  // 指定した並びでコーンを積み直す（下から順）。'r' はレインボー。
  function build(cols){
    cones = [[],[],[],[],[]];
    for (var c=0;c<5;c++){
      var spec = cols[c] || '';
      for (var i=0;i<spec.length;i++){
        var ch = spec[i];
        var flavor = ch === 'r' ? 'rainbow' : F[parseInt(ch,10)];
        cones[c].push(mkIce(flavor, laneX(c), BASEY - i*STEP));
      }
    }
    layout(true);
  }
  function freeze(){ dropTimer = 9999; }   // 撮影中に落ちてこないように

  if (SHOT === 'play'){
    stage = 3; score = 1240; ordersLeft = 4; combo = 2;
    startStage();
    build(['011','2','1220','33','04']);
    order = ['choco','choco','vanilla'];
    nextFlav = 'strawberry';
    selected = 2; layout(true);
    ordersLeft = 4; freeze();

  } else if (SHOT === 'stack'){
    stage = 6; score = 5860; ordersLeft = 3;
    startStage();
    build(['0142','21r0','13','4021','30']);
    order = ['mint','soda','mint'];
    nextFlav = 'rainbow';
    selected = -1; layout(true);
    ordersLeft = 3; freeze();

  } else if (SHOT === 'clear'){
    stage = 4; score = 3300;
    startStage();
    build(['01','23','1','40','2']);
    ordersLeft = 0; stageClear = true; freeze();

  } else if (SHOT === 'gameover'){
    stage = 5; score = 4120;
    startStage();
    build(['0123401','1234012','2340123','3401234','4012340']);
    ordersLeft = 2; gameOver = true; freeze();

  } else if (SHOT === 'start'){
    stage = 1; score = 0;
    startStage();
    build(['00','12','2','34','1']);
    order = ['vanilla','strawberry','choco'];
    nextFlav = 'mint';
    selected = -1; layout(true);
    freeze();
  }
})();
