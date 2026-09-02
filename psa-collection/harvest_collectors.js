/*
 * app.collectors.com（PSA My Collection）から全カードの画像URLを集める。
 *
 * PSA公開APIは承認制で403になるため、こちらが実際に使えるルート。
 * ログイン済みブラウザのセッションでサイト内部のtRPC APIを叩くだけなので、
 * 承認も回数制限も不要。
 *
 * 使い方（Safari）:
 *   1. Safari設定 > 詳細 > 「Webデベロッパ用の機能を表示」にチェック
 *      → 開発メニュー > 「Apple EventsからのJavaScriptを許可」にチェック
 *   2. https://app.collectors.com/collection/ を開いてログインしておく
 *   3. osascript でこのファイルを流し込む:
 *
 *      osascript <<'EOF'
 *      set js to read POSIX file "/path/to/harvest_collectors.js" as «class utf8»
 *      tell application "Safari" to do JavaScript js in document 1
 *      EOF
 *
 *   4. window.__h.done が true になったら window.__h.items を取り出す
 *   5. JSONL にして import_from_web.py に渡すと画像が data/images/ に落ちる
 *
 * 対象は既定で全件（["ACTIVE","SOLD"]）。流し込む前に window.__hStatus に
 * ["ACTIVE"] などを入れておけば、その分だけに絞れる。
 * ※ アプリ側の「画像が無いカード」判定は保有・売却を問わないので、
 *   ここを ACTIVE だけにすると売却済みの画像が永久に埋まらない（2026-09-02に判明）。
 *
 * 仕組みのメモ:
 *   collection.list   … cursor は「ページ番号」、pageSize は1ページの件数、
 *                       totalItems に総数。画像URLはここには入っていない（null）。
 *   collection.images … list が返した items をそのまま渡すと、collectibleId をキーに
 *                       {original, large, medium, small, thumbnail} が返る。
 *   入力は {"0": <JSONを16進エンコードした文字列>} という形。
 *   画像の実体は d1htnxwo4o0jhw.cloudfront.net にあり、こちらは認証不要で落とせる。
 */
(function () {
  var STATUS = window.__hStatus || ["ACTIVE", "SOLD"];

  if (window.__h && window.__h.running) return "already running";
  var H = window.__h = { running: true, done: false, error: null, items: [], page: 0, total: null };

  function hex(o) {
    return Array.from(new TextEncoder().encode(JSON.stringify(o)))
      .map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
  }
  function trpc(p, i) {
    var u = "/collection/api/trpc/" + p + "?batch=1&input=" +
      encodeURIComponent(JSON.stringify({ "0": hex(i) }));
    return fetch(u, { credentials: "include" }).then(function (r) {
      if (!r.ok) throw new Error(p + " HTTP " + r.status);
      return r.json();
    }).then(function (j) { return j[0].result.data.json; });
  }

  (async function () {
    try {
      var base = {
        collectibleStatusFilters: STATUS, sortOrder: "DESC",
        sortBy: ["CREATED_DATE"], filters: {}, userSettings: {}
      };
      for (var page = 0; page < 60; page++) {
        var r = await trpc("collection.list", Object.assign({}, base, { cursor: page, pageSize: 50 }));
        var cols = r.collectibles || [];
        if (H.total === null) H.total = r.totalItems;
        if (!cols.length) break;

        var imgs = await trpc("collection.images", {
          items: cols.map(function (c) {
            return {
              collectibleId: c.id, certRefId: c.certRefId || null,
              certNumber: c.certNumber, collectibleType: c.collectibleType,
              gradingCompany: c.gradingCompany, vaultId: c.vaultId
            };
          })
        });

        cols.forEach(function (c) {
          var im = imgs[c.id] || imgs[String(c.id)] || {};
          H.items.push({
            cert: c.certNumber,
            grade: c.gradeValue,
            subject: c.collectibleSubject,
            url: im.large || im.medium || im.original || im.small || im.thumbnail || null,
            orig: im.original || null
          });
        });
        H.page = page + 1;
        if (cols.length < 50) break;
      }
      H.done = true;
    } catch (e) {
      H.error = String((e && e.stack) || e);
      H.done = true;
    } finally {
      H.running = false;
    }
  })();
  return "started";
})();
