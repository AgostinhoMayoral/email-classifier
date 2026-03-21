// Service worker stub - evita 404 de extensões/navegador que buscam /sw.js
// Não implementa cache nem PWA; apenas responde à requisição.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());
