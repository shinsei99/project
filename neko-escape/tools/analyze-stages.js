/* にゃんこ大脱出の全ステージを総当たりで解いて、難易度を数値で出す。
 *
 *   node tools/analyze-stages.js            表を出す
 *   node tools/analyze-stages.js --opt      各面の最短手数を `opt:` の形で出す（★評価に貼る用）
 *
 * なぜ要るのか:
 *   ロボットは毎ターン BFS で最短1マス近づくだけの決定論なので、ゲーム全体が
 *   「解ける有限のパズル」になる。つまり **難しさを感覚ではなく数で言える**。
 *   ステージを足したり触ったりしたら、これを流して次の3つを必ず確かめること。
 *     1. 「解無」が出ていないか（＝詰みステージを配っていないか）
 *     2. 最短手数と勝ち筋率が、置きたい難易度になっているか
 *     3. `opt`（ステージデータに貼ってある最短手数）が実際と合っているか＝★3が取れるか
 *
 * 読み方:
 *   最短手数    … 最善を打ったときのクリア手数
 *   状態数      … その面で到達しうる盤面の数。多いほど考えどころがある
 *   初手(勝/全) … 1手目の選択肢のうち、勝ちが残る手の数
 *   勝ち筋率    … 勝てる盤面全体で「勝ちを保てる手」の割合。**低いほど一手が重い**
 *   一本道率    … 正解が1手しかない盤面の割合
 *   でたらめ勝率 … ランダムに押したときの勝率。低いほど「読み」が要る
 *
 * ★ルールは index.html の写し（tools/engine.js）。ズレ検出は tools/crosscheck.js。
 */
const E = require('./engine.js');

const STAGES = E.parseStages();
const optMode = process.argv.includes('--opt');

const rows = STAGES.map((st, i) => {
  const a = E.analyse(st);
  a.no = i + 1;
  a.randomWin = optMode ? 0 : E.randomWin(st, 3000);
  a.opt = st.opt;
  return a;
});

if (optMode){
  console.log('/* tools/analyze-stages.js --opt が出した最短手数。各ステージの opt: に貼る */');
  console.log(rows.map(r => r.no + ':' + (r.best === null ? 'null' : r.best)).join('  '));
  const ng = rows.filter(r => r.opt !== undefined && r.opt !== r.best);
  console.log(ng.length ? '★ズレている面: ' + ng.map(r => r.no + '(opt=' + r.opt + ' 実際=' + r.best + ')').join(', ')
                        : '★opt はすべて実際の最短手数と一致');
  process.exit(0);
}

console.log('面 名前                 マス 敵 最短 状態数 初手(勝/全) 勝ち筋率 一本道率 でたらめ勝率 opt');
for (const r of rows){
  console.log(
    String(r.no).padStart(2) + '  ' + r.name.padEnd(18) +
    String(r.nodes).padStart(3) + String(r.robots).padStart(3) +
    String(r.best === null ? '解無' : r.best).padStart(5) +
    String(r.states).padStart(8) +
    (r.firstGood + '/' + r.firstAll).padStart(9) +
    (Math.round(r.goodRate*100) + '%').padStart(8) +
    (Math.round(r.tightRate*100) + '%').padStart(8) +
    (Math.round(r.randomWin*1000)/10 + '%').padStart(9) +
    (r.opt === undefined ? '   —' : (r.opt === r.best ? '   ✓' : '  ★' + r.opt)) +
    (r.capped ? '  ※打ち切り' : ''));
}
const part = (from, to) => rows.slice(from, to);
const avg = (rs, f) => Math.round(rs.reduce((a,r)=>a+f(r),0)/rs.length*10)/10;
console.log('\n全体   : 最短' + avg(rows, r=>r.best) + '手 / 勝ち筋率' + avg(rows, r=>r.goodRate*100) +
            '% / でたらめ勝率' + avg(rows, r=>r.randomWin*100) + '%');
if (rows.length > 20){
  console.log('1〜20面: 最短' + avg(part(0,20), r=>r.best) + '手 / 勝ち筋率' + avg(part(0,20), r=>r.goodRate*100) + '%');
  console.log('21面〜 : 最短' + avg(part(20), r=>r.best) + '手 / 勝ち筋率' + avg(part(20), r=>r.goodRate*100) + '%  ← 後半のほうが重いこと');
}
const bad = rows.filter(r => r.best === null);
console.log('解けない面: ' + (bad.length ? bad.map(r=>r.no).join(',') + ' ★配ってはいけない' : 'なし'));
const optNg = rows.filter(r => r.opt !== undefined && r.opt !== r.best);
if (optNg.length) console.log('★opt がズレている面: ' + optNg.map(r=>r.no).join(',') + '（--opt で貼り直す）');
