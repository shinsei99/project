/**
 * かんたんな service worker。
 * ・アプリの殻（HTML/JS/CSS）は「まずネット、だめならキャッシュ」＝更新を取りこぼさない
 * ・データは localStorage にあるので、ここでは同期もアップロードもしない
 * キャッシュ名の版を上げると、古いキャッシュは activate で消える。
 */
const CACHE = 'growth-app-v1'
const CORE = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return
  e.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone()
        caches.open(CACHE).then((c) => c.put(req, copy))
        return res
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
  )
})
