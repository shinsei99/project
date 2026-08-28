/* 「ほかのあそび」への切り替え帯。
 *
 * 置き方の考え:
 *   - **アプリを開いたら、いままでどおりネオンブロックス本体が出る**（入口画面を挟まない）。
 *     既存ユーザーの体験を変えないため。掲載名と中身も食い違わない。
 *   - 切り替えは**画面の下**に。ただし遊びの邪魔をしないよう、**既定は細い帯1本**で、
 *     押したときだけ一覧がせり上がる。
 *   - **各ゲームのコードには手を入れない。** このファイルを読み込ませるだけで動く
 *     （本体は `games/_switch.js`、各ゲームは `../_switch.js`）。
 *
 * 進み具合は localStorage に入るが、キーはゲームごとに違うので混ざらない（実測で確認済み:
 * neonblocks_mute / nyanko_ice_* / neko_escape_* / color_gravity_* / cyborg_* / piyo_*）。
 */
(function () {
  var inGame = location.pathname.indexOf('/games/') >= 0;
  var base = inGame ? '../../' : '';
  var here = inGame ? (location.pathname.split('/games/')[1] || '').split('/')[0] : 'blocks';

  // 並びは 3列×2行。上の行＝ネオン系、下の行＝それ以外（オーナー指定）
  var GAMES = [
    { id:'blocks',  name:'ネオンブロックス',   href: base + 'index.html',               color:'#41E3FF' },
    { id:'cyborg',  name:'サイボーグ防衛軍',   href: base + 'games/cyborg/index.html',  color:'#7CFF4F' },
    { id:'piyo',    name:'ひよこ防衛軍',       href: base + 'games/piyo/index.html',    color:'#FF8A3D' },
    { id:'gravity', name:'カラーグラビティ',   href: base + 'games/gravity/index.html', color:'#B36BFF' },
    { id:'ice',     name:'にゃんこアイス',     href: base + 'games/ice/index.html',     color:'#FF4FC3' },
    { id:'escape',  name:'にゃんこ大脱出',     href: base + 'games/escape/index.html',  color:'#FFD54F' }
  ];

  var css = ''
    + '#nbSwitch{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;'
    +   'font:600 12px/1 "Hiragino Maru Gothic ProN","Hiragino Sans",sans-serif;'
    +   'padding-bottom:env(safe-area-inset-bottom);pointer-events:none}'
    + '#nbSwitch *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}'
    + '#nbTab{pointer-events:auto;display:block;margin:0 auto 6px;border:2px solid rgba(65,227,255,.55);'
    +   'background:rgba(10,7,26,.82);color:#9BE9FF;border-radius:999px;padding:6px 14px;'
    +   'box-shadow:0 0 12px rgba(65,227,255,.35);cursor:pointer;font:inherit;backdrop-filter:blur(4px)}'
    // 帯の地は画面いっぱい、中身は中央寄せで幅を抑える（PC・iPad で横に間延びしないように）
    + '#nbList{pointer-events:auto;display:none;gap:8px;padding:10px 12px calc(10px + env(safe-area-inset-bottom));'
    +   'background:rgba(8,5,20,.94);border-top:2px solid rgba(65,227,255,.45);'
    +   'grid-template-columns:repeat(3,minmax(0,1fr));max-width:560px;margin:0 auto;'
    +   'border-left:2px solid rgba(65,227,255,.25);border-right:2px solid rgba(65,227,255,.25);'
    +   'border-radius:14px 14px 0 0}'
    + '#nbSwitch.open #nbList{display:grid}'
    + '#nbSwitch.open #nbTab{margin-bottom:0;border-bottom-left-radius:0;border-bottom-right-radius:0}'
    + '#nbList a{text-decoration:none;color:#EAF6FF;background:rgba(18,12,42,.9);text-align:center;'
    +   'border:2px solid;border-radius:12px;padding:10px 6px;font-size:12px;line-height:1.25}'
    + '#nbList a.cur{opacity:.45;pointer-events:none}';

  function build() {
    if (document.getElementById('nbSwitch')) return;
    var st = document.createElement('style'); st.textContent = css;
    document.head.appendChild(st);

    var box = document.createElement('div'); box.id = 'nbSwitch';
    var tab = document.createElement('button'); tab.id = 'nbTab';
    tab.type = 'button';
    tab.textContent = '▲ ほかのあそび';
    tab.setAttribute('aria-expanded', 'false');

    var list = document.createElement('div'); list.id = 'nbList';
    GAMES.forEach(function (g) {
      var a = document.createElement('a');
      a.href = g.href; a.textContent = g.name;
      a.style.borderColor = g.color;
      a.style.boxShadow = '0 0 10px ' + g.color + '55';
      if (g.id === here) a.className = 'cur';
      list.appendChild(a);
    });

    tab.onclick = function () {
      var open = box.classList.toggle('open');
      tab.textContent = (open ? '▼ とじる' : '▲ ほかのあそび');
      tab.setAttribute('aria-expanded', String(open));
    };
    box.appendChild(tab); box.appendChild(list);
    document.body.appendChild(box);
  }

  if (document.body) build();
  else document.addEventListener('DOMContentLoaded', build);
})();
