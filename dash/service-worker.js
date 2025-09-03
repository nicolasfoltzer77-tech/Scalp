self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e =>
  self.registration.unregister().then(() =>
    clients.matchAll().then(cs => cs.forEach(c => c.navigate(c.url)))
  )
);
self.addEventListener('fetch', () => {});
