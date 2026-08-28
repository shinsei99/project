

/* ══════════════════════════════════════════════════════════════════
 * スクリーンショット撮影専用の起動処理（**一時ビルドにだけ入れる**）
 *
 * シミュレータでは NFC が使えず、Simulator.app のウインドウも開かないので
 * タップを送れない。そこで「アプリ本来の“お試し”のサンプルを入れて、
 * 指定の画面を開いた状態で起動する」ようにし、`simctl io screenshot` で撮る。
 *
 * 出る画面もデータも、実際に使ったときと同じ（アプリ内蔵のサンプルの鍵）。
 * **配信物（www/）には入れない。** 撮り終えたら ios/App/App/public から消す。
 * app.js は type="module" なので、ここは app.js 内部のスコープで動く
 * （showTag / showLending / preview などをそのまま呼べる）。
 * ══════════════════════════════════════════════════════════════════ */
{
  const SHOT = '__SHOT__';
  const fakeTag = uid => ({ uid, records: [], url: '', text: '', fields: {} });
  const tab = id => {
    const b = document.querySelector('nav.tabs button[data-screen=' + id + ']');
    if (b) b.click();
  };
  /* スクロールは main（overflow-y:auto の器）を動かす。
     scrollIntoView だと body ごと動いてヘッダが下がり、上に濃紺の帯が出る */
  const scrollTo = (el, where) => {
    const main = document.querySelector('main');
    const nav = document.querySelector('nav.tabs');
    // タブバーは position:fixed で main の上に重なるので、下端合わせのときはその分よける
    const pad = nav ? nav.getBoundingClientRect().height : 0;
    const m = main.getBoundingClientRect(), e = el.getBoundingClientRect();
    main.scrollTop += (where === 'bottom')
      ? (e.bottom - m.bottom + 12 + pad)
      : (e.top - m.top - 8);
  };

  if (SHOT && !SHOT.startsWith('__')) {
    setTimeout(async () => {
      // ★ヘッダのNFC表示。シミュレータには NFC が無いので「非対応の端末です」と出るが、
      //   対応機種（iPhone 7 以降）では「NFC 利用可」になる。**実機での表示に合わせる**
      $('nfcstate').textContent = 'NFC 利用可';

      // 1) まっさらにしてから、アプリ本来の「サンプルの鍵を入れる」を実行
      ledger = [];
      save(KEY.ledger, ledger);
      $('btn-sample').click();
      await new Promise(r => setTimeout(r, 300));

      if (SHOT === 'read') {
        // かざして鍵が特定された画面（貸出中・貸出先・返却予定が出ている）
        tab('s-read');
        const t = fakeTag('00:02:SA:MP:LE:00:00');
        showTag(t); await showLending(t);
        // 鍵の内容が画面の主役になるよう、読み取りボタンの下までスクロールする
        await new Promise(r => setTimeout(r, 200));
        scrollTo($('lend'), 'top');
      } else if (SHOT === 'lend') {
        // 貸出（貸出先の候補と返却予定が選べる状態）
        tab('s-read');
        const t = fakeTag('00:01:SA:MP:LE:00:00');
        showTag(t); await showLending(t);
        await new Promise(r => setTimeout(r, 200));
        const pick = document.querySelector('#k-picks .pick');
        if (pick) pick.click();
        await new Promise(r => setTimeout(r, 200));
        scrollTo($('lend'), 'top');
      } else if (SHOT === 'list') {
        tab('s-list');
      } else if (SHOT === 'write') {
        tab('s-write');
        $('w-prop').value = '本社ビル';
        $('w-name').value = '4階 応接室';
        $('w-box').value = 'BOX-01';
        $('w-pos').value = '04';
        const row = document.querySelector('#w-keys .keyrow');
        if (row) {
          row.querySelector('.num').value = '10012';
          row.querySelector('.qty').value = '2';
        }
        preview();
      } else if (SHOT === 'server') {
        // サーバー連携（複数人で同じ台帳を共有している状態）
        conf.server = 'http://192.168.1.20:8765';
        conf.token = 'sample-token-for-screenshot';
        conf.org = 'サンプル商事';
        save(KEY.conf, conf);
        $('c-server').value = conf.server;
        showLinkState();
        tab('s-conf');
        // 「✅ ◯◯ と連携中」まで見えるよう、カードの下端を画面の下に合わせる
        setTimeout(() => scrollTo($('c-server').closest('.card'), 'bottom'), 300);
      }
    }, 700);
  }
}
