
const createNewChatBtn = document.getElementById('create-new-chat-btn');
const chatNameInput = document.getElementById('chat-name-input');
const firstUserInput = document.getElementById('first-user-input');
const joinChatBtn = document.getElementById('join-chat-btn');
const userHashInput = document.getElementById('userhash-input');

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
        alert("Error occured");
        return;
    }
    window.location.href = window.location.origin + "/messages.html?userhash="+response.userhash;
});

joinChatBtn.addEventListener('click', async ()=>{
    let userhash = userHashInput.value;
    let response = await fetch('/query/is_token_valid', {
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
        alert('Acces data is invalid');
        return;
    }
    let params = new URLSearchParams();
    params.append('userhash', userhash);
    window.location = window.location.origin + "/messages.html?" + params.toString();
});