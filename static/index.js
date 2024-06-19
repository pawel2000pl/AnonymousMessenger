"use strict";

const createNewChatBtn = document.getElementById('create-new-chat-btn');
const chatNameInput = document.getElementById('chat-name-input');
const firstUserInput = document.getElementById('first-user-input');
const joinChatBtn = document.getElementById('join-chat-btn');
const userHashInput = document.getElementById('userhash-input');
const accountLogin = document.getElementById('account-login');
const accountPassword = document.getElementById('account-password');
const loginBtn = document.getElementById('login-btn');
const registerBtn = document.getElementById('register-btn');
const loginDiv = document.getElementById('login-div');
const chatListDiv = document.getElementById('chat-list-div');
const logOutBtn = document.getElementById('logout-btn');
const resetPasswordDiv = document.getElementById('reset-password-div');
const currentAccountPassword = document.getElementById('current-account-password');
const newAccountPassword = document.getElementById('new-account-password');
const newAccountPassword2 = document.getElementById('new-account-password-2');
const changePasswordBtn = document.getElementById('change-password-btn');
const deleteAccountdBtn = document.getElementById('delete-account-btn');


chatNameInput.addEventListener('keypress', (event)=>{
    if (event.key == "Enter") {
        event.preventDefault();
        firstUserInput.focus();
    }
});


firstUserInput.addEventListener('keypress', (event)=>{
    if (event.key == "Enter") {
        event.preventDefault();
        createNewChatBtn.click();
    }
});


createNewChatBtn.addEventListener('click', async ()=>{
    let response = await fetch('/query/create_new_thread', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
          },
        body: JSON.stringify({
            name: chatNameInput.value,
            first_username: firstUserInput.value,
            token: localStorage.token??""
        }),
    });
    response = await response.json();
    if (response.status != "ok") {
        if (response["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate("Error occured"));
        return;
    }
    let params = new URLSearchParams();
    params.append('userhash', response.userhash);
    window.location.href = window.location.origin + "/messages.html?"+params.toString();
});


userHashInput.addEventListener('keypress', (event)=>{
    if (event.key == "Enter") {
        event.preventDefault();
        joinChatBtn.click();
    }
});


joinChatBtn.addEventListener('click', async ()=>{
    let userhash = userHashInput.value;
    let response = await fetch('/query/add_user_to_account', {
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
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Acces data is invalid'));
        return;
    }
    let params = new URLSearchParams();
    params.append('userhash', userhash);
    window.location = window.location.origin + "/messages.html?" + params.toString();
});


accountLogin.addEventListener('keypress', (event)=>{
    if (event.key == "Enter") {
        event.preventDefault();
        accountPassword.focus();
    }
});


accountPassword.addEventListener('keypress', (event)=>{
    if (event.key == "Enter") {
        event.preventDefault();
        loginBtn.click();
    }
});


loginBtn.addEventListener('click', async ()=>{
    let response = await fetch('/query/login', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            login: accountLogin.value,
            password: accountPassword.value
        }),
    });
    let result = await response.json();
    if (result['status'] != "ok" || (!result['result'])) {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Invalid user and / or password'));
        return;
    }
    localStorage.token = result['token'];
    window.location.href = window.location.origin + "/";
});


changePasswordBtn.addEventListener('click', async ()=>{
    if (newAccountPassword2.value != newAccountPassword.value)
        alert(translate('The passwords are not identical'));
    let response = await fetch('/query/change_password', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            token: localStorage.token??"",
            password: currentAccountPassword.value,
            new_password: newAccountPassword.value,
        }),
    });
    let result = await response.json();
    if (result['status'] != "ok") {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Cannot change the password (check old password)'));
        return;
    }
    alert(translate('Password changed'));
});


deleteAccountdBtn.addEventListener('click', async ()=>{
    if (!confirm(translate('Are you sure that you want to delete your account?')))
        return;
    let response = await fetch('/query/delete_account', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            token: localStorage.token??""
        }),
    });
    let result = await response.json();
    if (result['status'] != "ok") {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Error occured'));
        return;
    }
    window.location = '/';
});


registerBtn.addEventListener('click', async ()=>{
    let response = await fetch('/query/register', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            login: accountLogin.value,
            password: accountPassword.value
        }),
    });
    let result = await response.json();
    if (result['status'] != "ok") {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate('Cannot create the user - try another username'));
        return;
    }
    alert(translate('User created. Login within 5 minutes to confirm the registration'));
});


logOutBtn.addEventListener('click', async ()=>{
    if (localStorage.token == undefined || localStorage.token == "")
        return;
    await fetch('/query/logout', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            token: localStorage.token??""
        }),
    });
    localStorage.token = undefined;
    window.location = window.location.origin;;
});


permissionChecks.then(()=>{
    if (localStorage.token) {
        loginDiv.style.display = "none";
        chatListDiv.style.display = "";
        logOutBtn.style.display = "";
        resetPasswordDiv.style.display = "";
    } else {
        loginDiv.style.display = "";
        chatListDiv.style.display = "none";
        logOutBtn.style.display = "none;";
        resetPasswordDiv.style.display = "none";
    }
});
