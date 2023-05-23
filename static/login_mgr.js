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
        alert("Login again");
        window.location = window.location.origin;
    }
};

checkToken(false);
setInterval(checkToken, 60000);