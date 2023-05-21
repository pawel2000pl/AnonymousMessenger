
const createNewChatBtn = document.getElementById('create-new-chat-btn');
const chatNameInput = document.getElementById('chat-name-input');
const firstUserInput = document.getElementById('first-user-input');

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