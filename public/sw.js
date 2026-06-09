self.addEventListener('push', (event) => {
  let data = { title: 'Insignia', body: 'Alert triggered.' };
  try { data = JSON.parse(event.data.text()); } catch {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: 'insignia-alert',
      renotify: true,
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow('/'));
});
