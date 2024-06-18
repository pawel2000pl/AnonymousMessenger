const urlParams = new URLSearchParams(window.location.search);
const userhash = urlParams.get('userhash');

const ensureAccessIsValid = async function() {
    let response = await fetch('/query/is_access_valid', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userhash: userhash,
            token: localStorage.token??""
        }),
    });
    let result = await response.json();
    if (result['status'] != "ok" || (!result['result'])) {
        await translatorPromise;
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Acces data is invalid'));
        window.location = window.location.origin;
    }
};


const checkToken = async function() {
    if (localStorage.token == undefined || localStorage.token == "")
        return;
    let response = await fetch('/query/activity', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            token: localStorage.token??""
        }),
    });
    let result = await response.json();
    if (result['status'] != "ok" || result['result'] == false) {
        localStorage.token = "";
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate("Logged out"));
        window.location = window.location.origin;
    }
};

var permissionChecks = checkToken(false);
setInterval(checkToken, 90000);