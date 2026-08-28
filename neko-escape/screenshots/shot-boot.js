/* App Store 用スクリーンショットを撮るための細工。
   screenshots/shoot.sh が www/index.html の boot() の直後にこれを差し込み、
   ios/App/App/public/index.html だけを書き換えてビルドする（配信物の www/ は触らない）。

   ★タップは使わない（このMacのターミナルにアクセシビリティ権限が無く、
     シミュレータへタップを送れない）。代わりに「その画面の状態を直接作る」。 */
setTimeout(function () {
  var shot = '__SHOT__';

  // 撮影中は動きを止める（毎フレームの脈動やまばたきで絵がぶれないように）
  var freeze = function () { clock = 1.2; };

  if (shot === 'title') {
    // タイトルはそのまま。★の見え方を作るため、進み具合だけ入れておく
    save.cleared = 12;
    save.best = { 0:3, 1:4, 2:6, 3:7, 4:6 };
    buildGrid();
    freeze();
  }

  if (shot === 'board') {
    hide('titleScreen'); started = true;
    loadStage(9);                       // Stage 10「最後の牙城」＝ソファ・毛糸・さかな・敵2
    setMsg('となりのマスをタップして、うごこう！');
    freeze();
  }

  if (shot === 'gimmick') {
    hide('titleScreen'); started = true;
    loadStage(27);                      // Stage 28「ぬけ道の めいろ」＝ぬけ道3本・落とし穴・敵3
    setMsg('<b>ぬけ道</b>はねこだけ通れる。ロボットは回り道！');
    freeze();
  }

  if (shot === 'door') {
    hide('titleScreen'); started = true;
    loadStage(21);                      // Stage 22「スイッチと ドア」
    setMsg('スイッチを ふむと <b>ドアが ひらく</b>');
    freeze();
  }

  if (shot === 'clear') {
    hide('titleScreen'); started = true;
    save.cleared = 21;
    loadStage(20);                      // Stage 21 を最短手数でクリアした瞬間を作る
    cat.node = S.goal;
    cat.x = NX(S.goal); cat.y = NY(S.goal);
    moves = STAGES[20].opt;             // ぴったり＝★★★
    win();
    freeze();
  }

  if (shot === 'select') {
    hide('titleScreen'); started = true;
    save.cleared = 24;
    save.best = { 0:3, 1:4, 2:6, 3:6, 4:6, 5:6, 6:5, 7:4, 8:4, 9:8,
                  10:6, 11:6, 12:7, 13:6, 14:6, 15:6, 16:7, 17:9, 18:7, 19:9,
                  20:6, 21:7, 22:8, 23:10 };
    buildGrid();
    show('selScreen');
    freeze();
  }
}, 500);
