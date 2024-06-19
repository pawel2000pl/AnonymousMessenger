"use strict";

async function subscribeOnServer(subscribtion) {
    if (!subscribtion)
        return;
    const response = await fetch('/query/push_subscribe', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userhash: userhash,
            token: localStorage.token??"",
            subscription_information: subscribtion
        }),
    });
    const data = await response.json();
    localStorage['push_messages_notification'] = data['hash'];
}

async function unsubscribeThis() {
    if (!localStorage['push_messages_notification'])
        return;
    await fetch('/query/push_unsubscribe', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userhash: userhash,
            token: localStorage.token??"",
            subscription_hash: localStorage['push_messages_notification']
        }),
    });
}

function urlB64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

self.addEventListener('push', function(event) {
  const data = event.data.json();
  self.deseialized = data;

  const title = data.from;
  const options = {
    body: data.content,
    icon: '/static/favicon.svg',
    badge: '/static/favicon.svg'
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(clients.openWindow(self.deseialized.address));
});

self.addEventListener('pushsubscriptionchange', function(event) {
  console.log('[Service Worker]: \'pushsubscriptionchange\' event fired.');
  const applicationServerPublicKey = localStorage.getItem('applicationServerPublicKey');
  const applicationServerKey = urlB64ToUint8Array(applicationServerPublicKey);
  event.waitUntil(
    self.registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: applicationServerKey
    })
    .then(function(newSubscription) {
        unsubscribeThis().finally(()=>{subscribeOnServer(newSubscription)});
    })
  );
});
