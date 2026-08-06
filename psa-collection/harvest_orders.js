/*
 * psacard.com（PSA My Orders）から「グレーディング申請」を取得する。
 * ログイン済みブラウザのセッションでサイト内部 tRPC API を叩くだけ（承認・制限なし）。
 *
 * 2段構え:
 *   1) orders.list                … 申請オーダー一覧（status: Processing/Shipped/Completed）
 *      input {"orderFilters":{"start":0,"pageLength":100,"sort":"Arrived","sortOrder":"desc","location":"US"}}
 *   2) orders.get（進行中の各オーダー）… カード明細
 *      input {"submissionNumber":"<sub>","orderNumber":"<no>"}
 *      返り: specReviewResults[]（certNo/specDescription=カード名/lineNumber）,
 *            images{certID -> [{imageSide:1=表/2=裏, thumbnail/small/medium/large}]},
 *            orderProgressSteps[]（Arrived→OrderPrep→ResearchAndID→Grading→Assembly→QACheck→GradesReady→Completed）
 *   ※ 入力エンコードは base64（app.collectors.com は16進で別物）。
 *   ※ 画像は d1htnxwo4o0jhw.cloudfront.net（認証不要）。
 *
 * 使い方: update_orders.sh から osascript 経由で流し込む。
 *   window.__ord.done が true になったら window.__ord.data を取り出す。
 *   data = { totalCount, orders:[...], cards:[ {orderNumber,submissionNumber,service,
 *            currentStep, certID, certNo, name, line, front, back} ] }（cards=進行中のみ）
 */
(function () {
  window.__ord = { done: false };
  function b64(o) { return btoa(JSON.stringify(o)); }
  function trpc(proc, input) {
    var u = "/api/grading/trpc/" + proc + "?batch=1&input=" +
      encodeURIComponent(JSON.stringify({ "0": b64(input) }));
    return fetch(u, { credentials: "include" }).then(function (r) {
      if (!r.ok) throw new Error(proc + " HTTP " + r.status);
      return r.json();
    }).then(function (j) { return j[0].result.data.json; });
  }

  (async function () {
    try {
      var list = await trpc("orders.list", {
        orderFilters: { start: 0, pageLength: 100, sort: "Arrived", sortOrder: "desc", location: "US" }
      });
      var orders = list.orders || [];
      var inProg = orders.filter(function (o) { return o.status === "Processing"; });
      var cards = [];
      for (var i = 0; i < inProg.length; i++) {
        var o = inProg[i];
        var det = await trpc("orders.get", {
          submissionNumber: String(o.submissionNumber), orderNumber: String(o.orderNumber)
        });
        var steps = det.orderProgressSteps || [];
        var cur = null;
        for (var s = 0; s < steps.length; s++) { if (!steps[s].completed) { cur = steps[s].step; break; } }
        var imgs = det.images || {};
        (det.specReviewResults || []).forEach(function (it) {
          var arr = imgs[it.certID] || imgs[String(it.certID)] || [];
          var front = null, back = null;
          arr.forEach(function (im) {
            if (im.imageSide === 1 && !front) front = im.thumbnail || im.small || im.medium;
            if (im.imageSide === 2 && !back) back = im.thumbnail || im.small || im.medium;
          });
          cards.push({
            orderNumber: o.orderNumber, submissionNumber: o.submissionNumber,
            service: o.service, currentStep: cur,
            certID: it.certID, certNo: it.certNo, name: it.specDescription,
            line: it.lineNumber, front: front, back: back
          });
        });
      }
      window.__ord = { done: true, data: { totalCount: list.totalCount, orders: orders, cards: cards } };
    } catch (e) {
      window.__ord = { done: true, error: String((e && e.stack) || e) };
    }
  })();
  return "started";
})();
