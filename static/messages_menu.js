
const newUserBtn = document.getElementById('new-user-btn');
const newUserName = document.getElementById('new-user-name');
const generateNewUserDiv = document.getElementById('generate-new-user-div');
const newUserOutput = document.getElementById('new-user-output');
const newUserOutputHref = document.getElementById('new-user-output-href');
const newUserCanCreate = document.getElementById('new-user-can-create');
const changeUserhashBtn = document.getElementById('change-userhash-btn');
const closeUserBtn = document.getElementById('close-user-btn');

newUserBtn.addEventListener('click', async ()=>{
    let response = await fetch('/query/add_user', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            creator: userhash,
            username: newUserName.value,
            can_create: newUserCanCreate.checked,
            token: localStorage.token??""
        }),
    });
    let result = await response.json();
    if (result['status'] == "ok") {
        newUserOutput.value = result['userhash'];
        newUserOutputHref.value = window.location.origin + "/messages.html?userhash="+result['userhash'];
    } else
        alert('Cannot generate the new user');
});

const checkCanCreate = async function() {
    let response = await fetch('/query/can_create_user', {
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
    if (result['status'] == "ok" && result['result']) 
        return;
    generateNewUserDiv.style.display = "none";
};
checkCanCreate();

changeUserhashBtn.addEventListener('click', async ()=>{
    let response = await fetch('/query/reset_user_hash', {
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
    if (result['status'] == "ok") {
        window.location = window.location.origin + "/messages.html?userhash="+result['userhash'];
    } else
        alert('Cannot generate the new user');
});

closeUserBtn.addEventListener('click', async ()=>{
    if (!confirm("Are you sure that you want to leave this chat?"))
        return;
    let response = await fetch('/query/close_user', {
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
    if (result['status'] == "ok") {        
        window.location = window.location.origin;
    } else
        alert('Cannot remove the user');
});