const CACHE_NAME = 'traceability-app-cache-v1';
const URLS_TO_CACHE = [
  '/',
  '/ontvangst',
  '/productie',
  '/verzending',
  '/rapport',
  '/beheer/klanten',
  '/beheer/producten',
  '/beheer/leveranciers'
];

// Install the service worker and cache the main pages
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(URLS_TO_CACHE);
      })
  );
});

// Serve cached content when offline
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        // Not in cache - fetch from network
        return fetch(event.request);
      }
    )
  );
});