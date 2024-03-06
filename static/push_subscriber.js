const subscribeBtn = document.getElementById('subscribe-pn-btn');
const unsubscribeBtn = document.getElementById('unsubscribe-pn-btn');
const unsubscribeAllBtn = document.getElementById('unsubscribe-all-pn-btn');


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


function initializeUI() {

    swRegistration.pushManager.getSubscription()
        .then(function(subscription) {
            isSubscribed = !(subscription === null);

            updateSubscriptionOnServer(subscription);

            if (isSubscribed) {
                console.log('User IS subscribed.');
            } else {
                console.log('User is NOT subscribed.');
            }

            updateBtn();
        });
};


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
    if (data['status'] != 'ok') {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Error occured'));
        return;
    }
    localStorage['push_messages_notification'] = data['hash'];
}


async function unsubscribeThis() {
    if (!localStorage['push_messages_notification'])
        return;
    const response = await fetch('/query/push_unsubscribe', {
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
    const data = await response.json();
    if (data['status'] != 'ok') {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Error occured'));
        return;
    }
}


async function unsubscribeAll() {
    const response = await fetch('/query/push_unsubscribe', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userhash: userhash,
            token: localStorage.token??""
        }),
    });
    const data = await response.json();
    if (data['status'] != 'ok') {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Error occured'));
        return;
    }
}


async function initializePushSubscriber() {

    const applicationServerPublicKey = await fetch('/query/push_public').then((response)=>{return response.json()});
    const applicationServerKey = urlB64ToUint8Array(applicationServerPublicKey);

    const subscribe = async function() {
        let swRegistration = null;

        if ('serviceWorker' in navigator && 'PushManager' in window) {
            await navigator.serviceWorker.register("/pn_service.js")
                .then(function(swReg) {
                    console.log('Service Worker is registered', swReg);
                    swRegistration = swReg;
                })
                .catch(function(error) {
                    console.error('Service Worker Error', error);
                });
        } else {
            console.warn('Push meapplicationServerPublicKeyssaging is not supported');
            alert(translate('Notifications are not supported in this device'));
            pushButton.textContent = 'Push Not Supported';
        }

        swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        }).then(function(subscription) {
            console.log('User is subscribed.');
            unsubscribeThis().then(()=>{subscribeOnServer(subscription)});
        }).catch(function(err) {
            console.log('Failed to subscribe the user: ', err);
        });
    };

    subscribeBtn.onclick = subscribe;
    unsubscribeBtn.onclick = unsubscribeThis;
    unsubscribeAllBtn.onclick = unsubscribeAll;

}


initializePushSubscriber();
