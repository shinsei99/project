/* 追加ステージを自動で作って、解析器で採点し、条件を満たしたものだけ残す。
 *
 *   node tools/gen-stages.js            10面ぶん探して JS の形で出す（index.html に貼る）
 *   node tools/gen-stages.js --tries 8000
 *
 * なぜ機械に作らせるのか:
 *   手で置いた面は「解けるかどうか」も「難しいかどうか」も分からない。
 *   このゲームは決定論なので、**作ってから総当たりで測って、条件に合う面だけ採る**ほうが確実。
 *   実測（2026-08-28）では 1〜20面の平均が 最短5.8手・勝ち筋率64.5% で、後半ほど軽かった。
 *   そこで追加分は **最短8手以上・勝ち筋率60%未満** を狙う。
 *
 * 見た目の担保（線が交差すると盤面が読めなくなる）:
 *   - マスは「列」に並べる。**つなぐのは隣の列どうしと、同じ列の上下だけ**
 *   - 隣の列は必ず「上から順に」つなぐ（階段状）ので、線は交差しない
 */
const E = require('./engine.js');

const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i >= 0 ? Number(process.argv[i+1]) : dflt;
};
const TRIES = arg('--tries', 6000);

const rnd = n => Math.floor(Math.random()*n);
const pick = a => a[rnd(a.length)];
const shuffle = a => { for (let i=a.length-1;i>0;i--){ const j=rnd(i+1); [a[i],a[j]]=[a[j],a[i]]; } return a; };
const ROWY = { 1:[50], 2:[34,66], 3:[22,50,78] };

function makeLayout(want){
  const lo = want.cols ? want.cols[0] : 6, hi = want.cols ? want.cols[1] : 9;
  const cols = lo + rnd(hi - lo + 1);
  const counts = [];
  for (let c = 0; c < cols; c++){
    if (c === 0) counts.push(1 + rnd(3));        // 入口
    else if (c === cols-1) counts.push(1);       // ゴールの列は1つ
    else counts.push(1 + rnd(3));
  }
  const nodes = [], colIdx = [];
  for (let c = 0; c < cols; c++){
    const ys = ROWY[counts[c]], idx = [];
    for (let r = 0; r < counts[c]; r++){
      idx.push(nodes.length);
      nodes.push([Math.round(5 + c*(90/(cols-1))), ys[r]]);
    }
    colIdx.push(idx);
  }
  const edges = [];
  // 同じ列の上下（ときどき）
  for (const idx of colIdx)
    for (let r = 0; r+1 < idx.length; r++)
      if (Math.random() < 0.45) edges.push([idx[r], idx[r+1]]);
  // 隣の列は階段状に。i か j を進めながらつなぐので線が交差しない
  for (let c = 0; c+1 < colIdx.length; c++){
    const L = colIdx[c], R = colIdx[c+1];
    let i = 0, j = 0;
    edges.push([L[0], R[0]]);
    while (i < L.length-1 || j < R.length-1){
      const canI = i < L.length-1, canJ = j < R.length-1;
      const step = (canI && canJ) ? rnd(3) : (canI ? 0 : 1);
      if (step === 0) i++; else if (step === 1) j++; else { i++; j++; }
      edges.push([L[i], R[j]]);
    }
    // ときどき「もう1本」（階段の内側なので交差しない）
    if (L.length > 1 && R.length > 1 && Math.random() < 0.4)
      edges.push([L[L.length-1], R[R.length-1]]);
  }
  const uniq = new Map();
  for (const [a,b] of edges) uniq.set(E.edgeKey(a,b), [a,b]);
  return { nodes, edges: [...uniq.values()], colIdx };
}

function makeStage(want){
  const { nodes, edges, colIdx } = makeLayout(want);
  const N = nodes.length;
  const colOf = new Array(N);
  colIdx.forEach((idx,c)=>idx.forEach(n=>{ colOf[n] = c; }));
  const last = colIdx[colIdx.length-1][0];
  const start = pick(colIdx[0]);
  const mid = [].concat(...colIdx.slice(1, colIdx.length-1));
  const free = shuffle(mid.filter(n => n !== start && n !== last));
  if (free.length < 6) return null;

  const st = { name:'?', cat:start, goal:last, robots:[], sofa:[], yarn:[], fish:[], trap:[],
               sw:[], doors:[], catOnly:[], nodes, edges };
  // 敵は入口の列と2列目から（ねこの近くに置くと初手で詰む面になりやすい）
  const robotPool = shuffle([].concat(colIdx[0], colIdx[1] || []).filter(n => n !== start));
  st.robots = robotPool.slice(0, want.robots);
  if (st.robots.length < want.robots) return null;

  let p = 0;
  const take = k => free.slice(p, p += k);
  if (want.sofa) st.sofa = take(1);
  st.yarn = take(want.yarn);
  st.fish = take(want.fish);
  st.trap = take(want.trap);

  // 道に付くギミックは**中ほどの列**の辺だけ。入口やゴールのすぐ脇に置くと、
  // あってもなくても勝負が変わらない「飾り」になる
  const cmax = colIdx.length - 1;
  const midEdges = shuffle(edges.filter(([a,b]) =>
    Math.min(colOf[a],colOf[b]) >= 2 && Math.max(colOf[a],colOf[b]) <= cmax - 1));
  // ★ドアとぬけ道は「そこを塞ぐと遠回りになる辺」に置く。
  //   ただの並行路に置いても勝負が変わらず、飾りにしかならない（実測で全部落ちた）
  const base = dist(st, []);
  const chokes = shuffle(midEdges.filter(e => {
    const d = dist(st, [E.edgeKey(e[0],e[1])]);
    return d < 0 || d >= base + 2;
  }));
  let qc = 0, qm = 0;
  if (want.doors){                                   // ドアは必ず「塞ぐと遠回りになる辺」へ
    st.doors = chokes.slice(qc, qc += want.doors);
    if (st.doors.length < want.doors) return null;
    const swPool = free.slice(p).filter(n => !st.doors.some(e => e.includes(n)));
    if (!swPool.length) return null;
    st.sw = [swPool[0]];
  }
  if (want.catOnly){                                 // ぬけ道も、まずは近道になる辺から
    const used = new Set(st.doors.map(e => E.edgeKey(e[0],e[1])));
    const pool = chokes.filter(e => !used.has(E.edgeKey(e[0],e[1])))
              .concat(midEdges.filter(e => !used.has(E.edgeKey(e[0],e[1]))));
    const seen = new Set();
    st.catOnly = pool.filter(e => {
      const k = E.edgeKey(e[0],e[1]);
      if (seen.has(k)) return false; seen.add(k); return true;
    }).slice(0, want.catOnly);
    if (st.catOnly.length < want.catOnly) return null;
  }
  return st;
}

/* ねこから見た「ゴールまでの距離」。skip で塞いだ辺を除ける（ドア候補さがし用）。 */
function dist(st, skip){
  const N = st.nodes.length, adj = Array.from({length:N},()=>[]);
  const off = new Set(skip || []);
  st.edges.forEach(([a,b])=>{ if (!off.has(E.edgeKey(a,b))){ adj[a].push(b); adj[b].push(a); } });
  const d = new Array(N).fill(-1); d[st.cat] = 0;
  const q = [st.cat];
  for (let i = 0; i < q.length; i++)
    for (const n of adj[q[i]]) if (d[n] < 0){ d[n] = d[q[i]] + 1; q.push(n); }
  return d[st.goal];
}

/* ★ギミックが「効いている」か。飾りで置かれた道具は面白さに寄与しないので落とす。
   - ぬけ道: 取り上げると、最短手数が伸びるか解けなくなること
   - ドア  : スイッチを外す（＝永久に閉じたまま）と、最短手数が伸びるか解けなくなること */
function gimmicksMatter(st, best, loose){
  const worse = (variant) => {
    const a = E.analyse(variant, 60000);
    return a.capped ? false : (a.best === null || a.best > best);
  };
  let catOk = true, doorOk = true;
  if (st.catOnly.length){
    const keys = new Set(st.catOnly.map(e => E.edgeKey(e[0],e[1])));
    catOk = worse({ ...st, catOnly: [], edges: st.edges.filter(e => !keys.has(E.edgeKey(e[0],e[1]))) });
  }
  if (st.doors.length) doorOk = worse({ ...st, sw: [] });
  // 両方のギミックを載せた面で「どちらも効いている」まで求めると、まず見つからない（実測）。
  // その場合はドア（見た目が強いほう）が効いていれば採る
  if (loose && st.catOnly.length && st.doors.length) return doorOk;
  return catOk && doorOk;
}

// 採点。ここを通ったものだけが「配ってよい面」
function ok(a, want){
  if (a.best === null || a.capped) return false;
  if (a.best < want.minBest || a.best > want.maxBest) return false;
  if (a.goodRate > want.maxGood || a.goodRate < 0.3) return false;
  if (a.firstGood < 1 || a.firstAll < 2) return false;
  if (a.states < want.minStates) return false;
  return true;
}

/* ★2026-08-29: 高難度パック（--hard）。
   実測で 1〜30面は「最短6.7手・勝ち筋率61%」＝**打てる手の6割が正解**だった。
   つまり考えれば間違えにくい。歯ごたえを足すため、31面以降は
   **敵4台・最短12手以上・勝ち筋率50%未満**（＝半分以上の手が負け筋）を狙う。 */
const HARD_WANTS = [
  // ★敵4台は捨てた。実測で **398面中 解ける面は3面**（初手で詰む面ばかり）。
  //   台数ではなく「道のりの長さ」と「逃げ道の少なさ」で難しくする。
  //   3台・10〜12列だと 最短11手前後まで伸び、勝ち筋率は最小40%まで落ちる（実測）。
  { tag:'H1 長距離',     cols:[10,12], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:0, doors:0,
    minBest:10, maxBest:16, maxGood:0.58, minStates:90 },
  { tag:'H2 特異点',     cols:[10,12], robots:3, sofa:1, yarn:1, fish:1, trap:2, catOnly:0, doors:0,
    minBest:10, maxBest:16, maxGood:0.56, minStates:90 },
  { tag:'H3 スリット',   cols:[10,12], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:2, doors:0,
    minBest:10, maxBest:16, maxGood:0.56, minStates:100 },
  { tag:'H4 ゲート',     cols:[10,12], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:0, doors:1,
    minBest:10, maxBest:16, maxGood:0.56, minStates:100 },
  { tag:'H5 機雷原',     cols:[10,12], robots:3, sofa:0, yarn:3, fish:1, trap:2, catOnly:0, doors:0,
    minBest:11, maxBest:17, maxGood:0.54, minStates:100 },
  { tag:'H6 特異点帯',   cols:[10,12], robots:3, sofa:1, yarn:1, fish:1, trap:3, catOnly:1, doors:0,
    minBest:11, maxBest:17, maxGood:0.54, minStates:110 },
  { tag:'H7 迷路',       cols:[10,12], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:3, doors:0,
    minBest:11, maxBest:17, maxGood:0.52, minStates:110 },
  { tag:'H8 封鎖',       cols:[10,12], robots:3, sofa:1, yarn:2, fish:1, trap:1, catOnly:1, doors:1,
    minBest:11, maxBest:18, maxGood:0.52, minStates:120, loose:true },
  { tag:'H9 総力戦',     cols:[11,12], robots:3, sofa:1, yarn:2, fish:1, trap:2, catOnly:2, doors:1,
    minBest:12, maxBest:18, maxGood:0.50, minStates:120, loose:true },
  { tag:'H10 最終',      cols:[12,12], robots:3, sofa:1, yarn:2, fish:1, trap:2, catOnly:2, doors:1,
    minBest:12, maxBest:20, maxGood:0.50, minStates:130, loose:true },
];

const NORMAL_WANTS = [
  // 21〜22面は新ギミックの紹介。やさしめ（手数は短め・勝ち筋率はゆるく）
  { tag:'ぬけ道・紹介',   cols:[6,8],  robots:2, sofa:1, yarn:0, fish:1, trap:0, catOnly:1, doors:0,
    minBest:6, maxBest:9, maxGood:0.72, minStates:60 },
  { tag:'スイッチ・紹介', cols:[6,8],  robots:2, sofa:0, yarn:1, fish:0, trap:0, catOnly:0, doors:1,
    minBest:6, maxBest:9, maxGood:0.72, minStates:60 },
  // 23面以降が本番。★列を増やして道のりを長くし、最短8手以上・勝ち筋率65%未満を狙う
  { tag:'ぬけ道',       cols:[9,10], robots:3, sofa:1, yarn:1, fish:1, trap:0, catOnly:2, doors:0,
    minBest:8, maxBest:13, maxGood:0.65, minStates:100 },
  { tag:'スイッチ',     cols:[9,10], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:0, doors:1,
    minBest:8, maxBest:13, maxGood:0.65, minStates:100 },
  { tag:'穴と毛糸',     cols:[9,10], robots:3, sofa:0, yarn:2, fish:1, trap:2, catOnly:0, doors:0,
    minBest:8, maxBest:13, maxGood:0.63, minStates:100 },
  { tag:'ぬけ道と穴',   cols:[9,10], robots:3, sofa:1, yarn:1, fish:0, trap:2, catOnly:2, doors:0,
    minBest:8, maxBest:13, maxGood:0.62, minStates:100 },
  { tag:'スイッチと穴', cols:[9,10], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:1, doors:1,
    minBest:9, maxBest:14, maxGood:0.62, minStates:100, loose:true },
  { tag:'総力戦',       cols:[9,10], robots:3, sofa:1, yarn:2, fish:1, trap:1, catOnly:1, doors:1,
    minBest:9, maxBest:14, maxGood:0.60, minStates:100, loose:true },
  { tag:'ぬけ道の迷路', cols:[9,10], robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:3, doors:0,
    minBest:9, maxBest:14, maxGood:0.60, minStates:120 },
  { tag:'最終',         cols:[10,10],robots:3, sofa:1, yarn:1, fish:1, trap:2, catOnly:2, doors:1,
    minBest:10, maxBest:16, maxGood:0.60, minStates:120, loose:true },
];

/* 候補の良さ。**最初に見つかったものを採らない**（当たり外れが大きい）。
   同じ試行回数でも、条件を通った中から良いものを選ぶほうが面がそろう。
   良い面 = 手数が長い ＆ 一手が重い（勝ち筋率が低い）＆ 考えどころが多い（状態数） */
const score = a => a.best*1.5 + (0.70 - a.goodRate)*20 + Math.min(a.states, 600)/300;

/* --hard2 … --hard で見つからなかった型（ゲート・特異点だらけ・総力戦・最終）を
   条件をゆるめて拾い直すための組。**条件を緩めたことは採った面の実測値で分かる**ので、
   ゆるめた事実は SESSION_LOG に残すこと。 */
const HARD_WANTS2 = [
  { tag:'H4 ゲート',   cols:[9,11],  robots:3, sofa:1, yarn:1, fish:1, trap:1, catOnly:0, doors:1,
    minBest:9,  maxBest:17, maxGood:0.62, minStates:70, loose:true },
  { tag:'H6 特異点帯', cols:[9,11],  robots:3, sofa:1, yarn:1, fish:1, trap:3, catOnly:0, doors:0,
    minBest:9,  maxBest:17, maxGood:0.62, minStates:70 },
  { tag:'H9 総力戦',   cols:[10,11], robots:3, sofa:1, yarn:2, fish:1, trap:2, catOnly:1, doors:1,
    minBest:10, maxBest:18, maxGood:0.55, minStates:90, loose:true },
  { tag:'H10 最終',    cols:[10,12], robots:3, sofa:1, yarn:2, fish:1, trap:2, catOnly:2, doors:1,
    minBest:11, maxBest:20, maxGood:0.58, minStates:80, loose:true },
];

const WANTS = process.argv.includes('--hard2') ? HARD_WANTS2
            : process.argv.includes('--hard')  ? HARD_WANTS : NORMAL_WANTS;

const found = [];
for (const want0 of WANTS){
  let hit = null;
  // 見つからなければ条件を少しずつ緩める（厳しいまま空席にするより、少し緩い面を置くほうがよい）
  for (let round = 0; round < 3 && !hit; round++){
    const want = { ...want0,
      maxGood: want0.maxGood + round*0.05,
      minStates: Math.round(want0.minStates * (1 - round*0.3)),
      maxBest: want0.maxBest + round*2 };
    for (let tried = 0; tried < TRIES; tried++){
      const st = makeStage(want);
      if (!st) continue;
      // 安い足切り。ドアは開くので「全部開いた状態」の距離を下限に使う（閉じた距離で見ると
      // ドアの面を丸ごと落としてしまう。実際それで最初は0件だった）
      const rough = dist(st, []);
      if (rough < 0 || rough < want.minBest - 3 || rough > want.maxBest) continue;
      const a = E.analyse(st, 60000);
      if (!ok(a, want)) continue;
      if (hit && score(a) <= score(hit.a)) continue;            // 今より良くなければ調べない
      if (!gimmicksMatter(st, a.best, want.loose)) continue;    // 飾りのギミックは採らない
      st.opt = a.best;
      hit = { st, a, tag: want0.tag, round };
    }
  }
  if (!hit){ console.error('★条件に合う面が見つからない: ' + want0.tag + '（' + TRIES + '回×3）'); continue; }
  if (hit.round) console.error('  （' + hit.round + '段階ゆるめて採用）');
  found.push(hit);
  console.error('見つけた: ' + hit.tag + ' … 最短' + hit.a.best + '手 / 勝ち筋率' +
                Math.round(hit.a.goodRate*100) + '% / 状態' + hit.a.states +
                ' / マス' + hit.st.nodes.length + ' / でたらめ' +
                Math.round(E.randomWin(hit.st, 1500)*1000)/10 + '%');
}

// 出力（index.html の STAGES に貼れる形）
const fmt = a => '[' + a.map(v => Array.isArray(v) ? '[' + v.join(',') + ']' : v).join(',') + ']';
console.log('\n/* ここから貼る（名前は人が付けること） */');
for (const f of found){
  const s = f.st;
  const parts = [
    '{ name:"' + f.tag + '", opt:' + s.opt + ', cat:' + s.cat + ', goal:' + s.goal +
      ', robots:' + fmt(s.robots),
    '    sofa:' + fmt(s.sofa) + ', yarn:' + fmt(s.yarn) + ', fish:' + fmt(s.fish) + ', trap:' + fmt(s.trap) +
      (s.sw.length ? ', sw:' + fmt(s.sw) : '') +
      (s.doors.length ? ', doors:' + fmt(s.doors) : '') +
      (s.catOnly.length ? ', catOnly:' + fmt(s.catOnly) : ''),
    '    nodes:' + fmt(s.nodes),
    '    edges:' + fmt(s.edges) + ' },',
  ];
  console.log(parts.join(',\n').replace(/,\n    sofa/, ',\n    sofa'));
}
