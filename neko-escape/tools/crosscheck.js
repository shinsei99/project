/* 解析器（node）と本体（index.html）のルールがズレていないか突き合わせる。
 *
 *   node tools/crosscheck.js > /tmp/payload.js
 *   → 出てきた中身を、ブラウザで開いた本体の Console（または Playwright の evaluate）に貼る
 *   → 「一致 N件 / 食い違い 0件」なら、ルールは同じ
 *
 * なぜ要るのか:
 *   ルールが node 側（tools/engine.js）と本体（index.html）の2か所にある。
 *   ズレると **「解析器では解ける面」を配ってしまう**（＝クリアできないステージ）。
 *   ギミックを足したときが一番危ないので、そのたびにこれを流すこと。
 *
 * やっていること:
 *   各ステージで、決まった手順（乱数ではなく、番号から決まる選び方）でねこを動かし、
 *   1手ごとの「ねこ・ロボット・毛糸・穴・さかな・ドア」の状態を node 側で記録する。
 *   同じ手順を本体でも実行して、状態が1つでも違えば食い違いとして出す。
 */
const E = require('./engine.js');
const STAGES = E.parseStages();

const MOVES = 10;                 // 1面あたり何手打つか
const snap = s => [s.cat, s.robots.map(r=>r.node+':'+r.stun).join(','),
                   s.yarn.join(','), s.fish.join(','), s.trap.join(','), s.open ? 1 : 0].join('|');

const plans = [];
STAGES.forEach((st, i) => {
  const G = E.build(st);
  let s = E.startOf(st);
  const moves = [], states = [];
  for (let k = 0; k < MOVES; k++){
    const opts = E.ways(G, s).adj[s.cat];
    // 乱数を使わない選び方（面番号と手数から決める）。本体側でも同じ手を打てる。
    // ★すぐ負ける手は避ける。負けると手順が1手で終わり、毛糸・穴・ドアを通らないため
    const safe = opts.filter(n => E.apply(s, n, G) !== null);
    const use = safe.length ? safe : opts;
    const n = use[(i*7 + k*3 + s.cat) % use.length];
    const r = E.apply(s, n, G);
    moves.push(n);
    if (r === 'WIN'){ states.push('WIN'); break; }
    if (r === null){ states.push('LOSE'); break; }
    s = r; states.push(snap(s));
  }
  plans.push({ i, moves, states });
});

console.log(`/* ▼ここから下を、ブラウザ（本体を開いた状態）の Console に貼る */
(() => {
  const PLANS = ${JSON.stringify(plans)};
  const snap = () => [cat.node, robots.map(r=>r.node+':'+r.stun).join(','),
      [...yarnLeft].sort((a,b)=>a-b).join(','), [...fishLeft].sort((a,b)=>a-b).join(','),
      [...trapLeft].sort((a,b)=>a-b).join(','), doorsOpen ? 1 : 0].join('|');
  const bad = [];
  let checked = 0;
  for (const p of PLANS){
    loadStage(p.i);
    timers.length = 0;                       // 演出の待ち時間を消して、同期で進める
    for (let k = 0; k < p.moves.length; k++){
      const n = p.moves[k], want = p.states[k];
      if (over) break;
      // 本体の onCatMove は演出のあとに続きをやるので、同じ順序を手で組む
      moves++; cat.node = n; cat.x = NX(n); cat.y = NY(n);
      let got;
      if (n === S.goal) got = 'WIN';
      else if (fishLeft.has(n)){ fishLeft.delete(n); got = null; }
      else {
        if (swLeft.has(n)){ swLeft.delete(n); doorsOpen = true; buildAdj(); }
        got = applyRobotTurnNow() === 'LOSE' ? 'LOSE' : null;
      }
      if (got === 'WIN' || got === 'LOSE'){
        checked++;
        if (got !== want) bad.push('Stage' + (p.i+1) + ' ' + k + '手目 ' + got + ' ≠ ' + want);
        break;
      }
      checked++;
      const now = snap();
      if (got === null && want === 'WIN'){ bad.push('Stage' + (p.i+1) + ' ' + k + '手目 さかな継続 ≠ WIN'); break; }
      if (got !== 'WIN' && got !== 'LOSE' && now !== want){
        bad.push('Stage' + (p.i+1) + ' ' + k + '手目\\n  本体: ' + now + '\\n  解析: ' + want);
        break;
      }
    }
  }
  return '突き合わせ ' + checked + '手 / 食い違い ' + bad.length + '件' + (bad.length ? '\\n' + bad.join('\\n') : '');
})()`);
