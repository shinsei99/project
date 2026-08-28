/* にゃんこ大脱出のルールを node 側にも1つ持つ（解析・生成・突き合わせで共有する）。
 *
 * ★ここは index.html の実装を写したもの＝**ルールが2か所にある**。
 *   ズレると「解析器では解けるのに実機では解けない面」を配ってしまうので、
 *   触ったら必ず `node tools/crosscheck.js` を流して実機と突き合わせること。
 *
 * 写しているもの（順番も含めて同じにする）:
 *   - ねこ: となりへ1マス → ゴール判定 → おさかな（ターン継続）→ スイッチ → ロボットの番
 *   - ロボット: index順に、毛糸で止まっていれば1回休み、そうでなければ BFS で1マス。
 *              進んだ先が毛糸なら止まる（捕獲判定より先）／ねこと同じマスなら捕獲／
 *              落とし穴なら退場（穴は残る・その位置の添字は進めない）
 *   - 道: ねこ用(adj)とロボット用(radj)は別。ぬけ道はロボットが通れず、
 *        ドアはスイッチを踏むまで誰も通れない
 */
const fs = require('fs');
const path = require('path');

function parseStages(htmlPath){
  const html = fs.readFileSync(htmlPath || path.join(__dirname, '..', 'www', 'index.html'), 'utf8');
  const m = html.match(/const STAGES = \[([\s\S]*?)\n\];/);
  if (!m) throw new Error('index.html から STAGES を取り出せない');
  return eval('[' + m[1] + ']');
}

const edgeKey = (a,b) => a < b ? a + '-' + b : b + '-' + a;

function build(st){
  const N = st.nodes.length;
  const doorSet = new Set((st.doors || []).map(e => edgeKey(e[0],e[1])));
  const onlyCat = new Set((st.catOnly || []).map(e => edgeKey(e[0],e[1])));
  const mk = (open) => {
    const adj = Array.from({length:N}, ()=>[]), radj = Array.from({length:N}, ()=>[]);
    st.edges.forEach(([a,b])=>{
      const k = edgeKey(a,b);
      if (doorSet.has(k) && !open) return;
      adj[a].push(b); adj[b].push(a);
      if (onlyCat.has(k)) return;
      radj[a].push(b); radj[b].push(a);
    });
    return { adj, radj };
  };
  return { N, goal: st.goal, sofa: new Set(st.sofa || []),
           sw: new Set(st.sw || []), closed: mk(false), open: mk(true),
           hasDoors: doorSet.size > 0 };
}
const ways = (G, s) => s.open ? G.open : G.closed;

function bfsStep(from, to, robots, G, s){
  const radj = ways(G, s).radj;
  const blocked = new Set(G.sofa);
  robots.forEach(r => { if (r.node !== from) blocked.add(r.node); });
  if (from === to) return null;
  const prev = new Array(G.N).fill(-2); prev[from] = -1;
  const q = [from]; let qi = 0;
  outer:
  while (qi < q.length){
    const cur = q[qi++];
    for (const nx of radj[cur]){
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

// 状態はいつも「ねこの手番」。open はドアが開いているか
const key = s => s.cat + '|' + s.robots.map(r=>r.node+':'+r.stun).join(',') +
                 '|' + s.yarn.join(',') + '|' + s.fish.join(',') + '|' + s.trap.join(',') +
                 '|' + (s.open ? 1 : 0);

function robotTurn(s, G){
  const robots = s.robots.map(r=>({node:r.node, stun:r.stun}));
  const yarn = new Set(s.yarn), trap = new Set(s.trap);
  let idx = 0;
  while (idx < robots.length){
    const r = robots[idx];
    if (r.stun > 0){ r.stun--; idx++; continue; }
    const next = bfsStep(r.node, s.cat, robots, G, s);
    if (next !== null) r.node = next;
    if (yarn.has(r.node)){ yarn.delete(r.node); r.stun = 1; idx++; continue; }
    if (r.node === s.cat) return null;                          // 捕獲
    if (trap.has(r.node)){ robots.splice(idx,1); continue; }     // 退場（添字は進めない）
    idx++;
  }
  return { cat:s.cat, robots, yarn:[...yarn].sort((a,b)=>a-b),
           fish:s.fish, trap:[...trap].sort((a,b)=>a-b), open:s.open };
}

// 手の結果: 'WIN' / null(負け) / 次の状態
function apply(s, n, G){
  if (n === G.goal) return 'WIN';
  if (s.fish.includes(n))
    return { ...s, cat:n, fish:s.fish.filter(f=>f!==n) };
  let ns = { ...s, cat:n };
  if (G.sw.has(n)) ns.open = true;                              // スイッチ→ドアが開く
  return robotTurn(ns, G);
}

const startOf = (st) => ({
  cat: st.cat,
  robots: (st.robots || []).map(n => ({node:n, stun:0})),
  yarn: [...(st.yarn || [])].sort((a,b)=>a-b),
  fish: [...(st.fish || [])].sort((a,b)=>a-b),
  trap: [...(st.trap || [])].sort((a,b)=>a-b),
  open: false,
});

/* 全状態を並べて、勝てるか・最短何手か・一手の重さを測る。
   cap を超えたら打ち切って capped:true を返す（生成中の変な面で固まらないため）。 */
function analyse(st, cap){
  cap = cap || 200000;
  const G = build(st);
  const start = startOf(st);
  const states = new Map();
  const queue = [start]; states.set(key(start), { s:start, moves:null });
  let capped = false, qi = 0;
  while (qi < queue.length){
    if (states.size > cap){ capped = true; break; }
    const s = queue[qi++], k = key(s);
    const moves = [];
    for (const n of ways(G, s).adj[s.cat]){
      const r = apply(s, n, G);
      if (r === 'WIN'){ moves.push({n, to:'WIN'}); continue; }
      if (r === null){ moves.push({n, to:'LOSE'}); continue; }
      const rk = key(r);
      if (!states.has(rk)){ states.set(rk, { s:r, moves:null }); queue.push(r); }
      moves.push({n, to:rk});
    }
    states.get(k).moves = moves;
  }
  const dist = new Map(), rev = new Map();
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
  let sumMoves = 0, sumGood = 0, tight = 0, winnable = 0;
  for (const [k, v] of states){
    if (!dist.has(k) || !v.moves) continue;
    winnable++;
    const good = v.moves.filter(mv => mv.to === 'WIN' || (mv.to !== 'LOSE' && dist.has(mv.to))).length;
    sumMoves += v.moves.length; sumGood += good;
    if (good === 1) tight++;
  }
  const first = states.get(sk).moves || [];
  const firstGood = first.filter(mv => mv.to === 'WIN' || (mv.to !== 'LOSE' && dist.has(mv.to))).length;
  return {
    name: st.name, nodes: st.nodes.length, robots: (st.robots || []).length,
    best: best === undefined ? null : best, states: states.size, capped,
    firstGood, firstAll: first.length,
    goodRate: sumMoves ? sumGood/sumMoves : 0,
    tightRate: winnable ? tight/winnable : 0,
  };
}

// でたらめに押したときの勝率（子どもが適当に触ったときの目安）
function randomWin(st, tries){
  tries = tries || 3000;
  const G = build(st);
  let wins = 0;
  for (let t = 0; t < tries; t++){
    let s = startOf(st), steps = 0;
    while (steps++ < 60){
      const opts = ways(G, s).adj[s.cat];
      const r = apply(s, opts[(Math.random()*opts.length)|0], G);
      if (r === 'WIN'){ wins++; break; }
      if (r === null) break;
      s = r;
    }
  }
  return wins / tries;
}

module.exports = { parseStages, build, apply, analyse, randomWin, startOf, key, ways, edgeKey };
