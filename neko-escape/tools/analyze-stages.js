/* にゃんこ大脱出の全ステージを総当たりで解いて、難易度を数値で出す。
 *
 *   node tools/analyze-stages.js
 *
 * なぜ要るのか:
 *   ロボットは毎ターン BFS で最短1マス近づくだけの決定論なので、ゲーム全体が
 *   「解ける有限のパズル」になる。つまり **難しさを感覚ではなく数で言える**。
 *   ステージを足したり触ったりしたら、これを流して次の2つを必ず確かめること。
 *     1. 「解無」が出ていないか（＝詰みステージを配っていないか）
 *     2. 最短手数と勝ち筋率が、置きたい難易度になっているか
 *
 * 読み方（2026-08-28 の実測値。全20面の平均は 最短5.8手 / 勝ち筋率64.5%）:
 *   最短手数    … 最善を打ったときのクリア手数。いまは 3〜9手
 *   状態数      … その面で到達しうる盤面の数。多いほど考えどころがある（いまは最大228）
 *   初手(勝/全) … 1手目の選択肢のうち、勝ちが残る手の数
 *   勝ち筋率    … 勝てる盤面全体で「勝ちを保てる手」の割合。**低いほど一手が重い**
 *                 （いちばん厳しいのは 9 挟み撃ち 43% と 10 最後の牙城 47%。
 *                   最終面20は 89% ＝ ほぼどう動いても勝てる＝カーブが効いていない）
 *   一本道率    … 正解が1手しかない盤面の割合
 *   でたらめ勝率 … ランダムに押したときの勝率。低いほど「読み」が要る（平均2.9%）
 *
 * ★ルールは index.html の実装をそのまま写している（BFSの探索順・毛糸/穴の処理順まで）。
 *   index.html 側のルールを変えたら、こちらも同じに直すこと。
 */
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = html.match(/const STAGES = \[([\s\S]*?)\n\];/);
if (!m) { console.error('STAGES を取り出せない'); process.exit(1); }
const STAGES = eval('[' + m[1] + ']');

function build(st){
  const N = st.nodes.length;
  const adj = Array.from({length:N}, ()=>[]);
  st.edges.forEach(([a,b])=>{ adj[a].push(b); adj[b].push(a); });
  return { N, adj, sofa: new Set(st.sofa||[]), goal: st.goal };
}
function bfsStep(from, to, robots, G){
  const blocked = new Set(G.sofa);
  robots.forEach(r => { if (r.node !== from) blocked.add(r.node); });
  if (from === to) return null;
  const prev = new Array(G.N).fill(-2); prev[from] = -1;
  const q = [from]; let qi = 0;
  outer:
  while (qi < q.length){
    const cur = q[qi++];
    for (const nx of G.adj[cur]){
      if (prev[nx] !== -2) continue;
      if (nx !== to && blocked.has(nx)) continue;
      prev[nx] = cur;
      if (nx === to) break outer;
      q.push(nx);
    }
  }
  if (prev[to] === -2) return null;
  let node = to; while (prev[node] !== from) node = prev[node];
  return node;
}
// 状態: {cat, robots:[{node,stun}], yarn:[], fish:[], trap:[]}（すべて猫の手番）
const key = s => s.cat + '|' + s.robots.map(r=>r.node+':'+r.stun).join(',') +
                 '|' + s.yarn.join(',') + '|' + s.fish.join(',') + '|' + s.trap.join(',');

function robotTurn(s, G){
  const robots = s.robots.map(r=>({node:r.node, stun:r.stun}));
  const yarn = new Set(s.yarn), trap = new Set(s.trap);
  let idx = 0;
  while (idx < robots.length){
    const r = robots[idx];
    if (r.stun > 0){ r.stun--; idx++; continue; }
    const next = bfsStep(r.node, s.cat, robots, G);
    if (next !== null) r.node = next;
    if (yarn.has(r.node)){ yarn.delete(r.node); r.stun = 1; idx++; continue; }
    if (r.node === s.cat) return null;                 // 捕獲
    if (trap.has(r.node)){ robots.splice(idx,1); continue; }  // 退場（idxは進めない）
    idx++;
  }
  return { cat:s.cat, robots, yarn:[...yarn].sort((a,b)=>a-b), fish:s.fish, trap:[...trap].sort((a,b)=>a-b) };
}
// 手の結果: 'WIN' / null(負け) / 次の状態
function apply(s, n, G){
  if (n === G.goal) return 'WIN';
  if (s.fish.includes(n))
    return { cat:n, robots:s.robots, yarn:s.yarn, fish:s.fish.filter(f=>f!==n), trap:s.trap };
  return robotTurn({ ...s, cat:n }, G);
}

function analyse(st, si){
  const G = build(st);
  const start = { cat:st.cat, robots:(st.robots||[]).map(n=>({node:n,stun:0})),
                  yarn:[...(st.yarn||[])].sort((a,b)=>a-b), fish:[...(st.fish||[])].sort((a,b)=>a-b),
                  trap:[...(st.trap||[])].sort((a,b)=>a-b) };
  // 1) 到達できる状態を全部並べる
  const states = new Map();               // key -> {s, moves:[{n, to:key|'WIN'|'LOSE'}]}
  const queue = [start]; states.set(key(start), {s:start, moves:null});
  let capped = false;
  while (queue.length){
    if (states.size > 400000){ capped = true; break; }
    const s = queue.shift(); const k = key(s);
    const moves = [];
    for (const n of G.adj[s.cat]){
      const r = apply(s, n, G);
      if (r === 'WIN'){ moves.push({n, to:'WIN'}); continue; }
      if (r === null){ moves.push({n, to:'LOSE'}); continue; }
      const rk = key(r);
      if (!states.has(rk)){ states.set(rk, {s:r, moves:null}); queue.push(r); }
      moves.push({n, to:rk});
    }
    states.get(k).moves = moves;
  }
  // 2) 勝てる状態と最短手数（WINから逆向きBFS）
  const dist = new Map();
  const rev = new Map();                  // key -> [親key]
  for (const [k, v] of states){
    if (!v.moves) continue;
    for (const mv of v.moves){
      if (mv.to === 'WIN'){ if (!dist.has(k)) dist.set(k, 1); }
      else if (mv.to !== 'LOSE'){
        if (!rev.has(mv.to)) rev.set(mv.to, []);
        rev.get(mv.to).push(k);
      }
    }
  }
  let frontier = [...dist.keys()];
  while (frontier.length){
    const next = [];
    for (const k of frontier)
      for (const p of (rev.get(k) || []))
        if (!dist.has(p)){ dist.set(p, dist.get(k) + 1); next.push(p); }
    frontier = next;
  }
  const sk = key(start);
  const best = dist.get(sk);

  // 3) 「一手まちがえたら詰む」度合い: 勝てる状態で、勝ちを保てる手の割合
  let sumMoves = 0, sumGood = 0, tight = 0, winnable = 0;
  for (const [k, v] of states){
    if (!dist.has(k) || !v.moves) continue;
    winnable++;
    const good = v.moves.filter(mv => mv.to === 'WIN' || (mv.to !== 'LOSE' && dist.has(mv.to))).length;
    sumMoves += v.moves.length; sumGood += good;
    if (good === 1) tight++;
  }
  // 4) でたらめに押したときの勝率（子どもが適当に触った場合の目安）
  let wins = 0, TRY = 4000;
  for (let t = 0; t < TRY; t++){
    let s = start, steps = 0;
    while (steps++ < 60){
      const opts = G.adj[s.cat];
      const r = apply(s, opts[(Math.random()*opts.length)|0], G);
      if (r === 'WIN'){ wins++; break; }
      if (r === null) break;
      s = r;
    }
  }
  const firstGood = states.get(sk).moves.filter(mv => mv.to === 'WIN' || (mv.to !== 'LOSE' && dist.has(mv.to))).length;
  return {
    no: si+1, name: st.name, nodes: st.nodes.length, robots: (st.robots||[]).length,
    best: best === undefined ? null : best,
    states: states.size, capped,
    firstGood, firstAll: states.get(sk).moves.length,
    goodRate: sumMoves ? sumGood/sumMoves : 0,
    tightRate: winnable ? tight/winnable : 0,
    randomWin: wins/TRY,
  };
}

const rows = STAGES.map(analyse);
console.log('面 名前                 マス 敵 最短 状態数 初手(勝/全) 勝ち筋率 一本道率 でたらめ勝率');
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
    (r.capped ? '  ※打ち切り' : ''));
}
const avg = f => Math.round(rows.reduce((a,r)=>a+f(r),0)/rows.length*10)/10;
console.log('\n平均: 最短' + avg(r=>r.best) + '手 / 勝ち筋率' + avg(r=>r.goodRate*100) + '% / でたらめ勝率' + avg(r=>r.randomWin*100) + '%');
console.log('解けない面: ' + (rows.filter(r=>r.best===null).map(r=>r.no).join(',') || 'なし'));
