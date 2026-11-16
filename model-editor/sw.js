// Keeps the editor usable offline once it has been opened online. Files are
// fetched fresh when the network answers and served from the cache otherwise.
const CACHE = 'neliel-model-editor-v1';
const FILES = [
  './', './index.html', './editor.js', './core.js', './paint.js', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png',
  '../src/materials.js', '../vendor/three/three.module.min.js',
  '../vendor/three/addons/loaders/GLTFLoader.js', '../vendor/three/addons/utils/BufferGeometryUtils.js',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET' || new URL(request.url).origin !== location.origin) return;
  event.respondWith(fetch(request).then(response => {
    if (response.ok) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(request, copy)); }
    return response;
  }).catch(() => caches.match(request, { ignoreSearch: true }).then(hit => hit ?? Response.error())));
});
