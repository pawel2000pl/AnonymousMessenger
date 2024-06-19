"use strict";

const MESSAGE_LIST_SYNC_INTERVAL = 2500;

const chatList = document.getElementById("chat-list");

const updateChatList = async function() {
    let response = await fetch("/query/get_threads_with_token", {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            token: localStorage.token??""
        }),
    });
    let result = await response.json();
    if (result["status"] != "ok") {
        if (result["redirect"] !== undefined)
            window.location = window.location.origin + result["redirect"];
        alert(translate("Cannot download list of chats"));
        return;
    }

    let data = result["result"];
    chatList.innerHTML = "";
    const table = document.createElement('table');
    table.innerHTML = '<tr>'+
        '<th class="chat-list-header translatable">Chat name</th>'+
        '<th class="chat-list-header translatable">Username</th>'+
        '<th class="chat-list-header translatable">Last message time</th>'+
        '<th class="chat-list-header translatable">Unread</th>'+
        '</tr>';
    table.className = "chat-list-table";

    const createCell = function(text) {
        const td = document.createElement('td');
        td.className = 'chat-list-cell';
        td.textContent = text;
        return td;
    };

    for (let i=0;i<data.length;i++) {

        let params = new URLSearchParams();
        params.append('userhash', data[i].userhash);
        const link = window.location.origin + "/messages.html?" + params.toString();

        const tr = document.createElement('tr');
        tr.addEventListener('mouseup', (event)=>{
            if (event.button==0) 
                window.location = link;
            if (event.button==1) 
                window.open(link, '_blank');
        });
        tr.userhash = data[i].userhash;
        tr.className = "class-list-row " + (data[i].unread?"class-list-row-unread":"");
        tr.appendChild(createCell(data[i].thread_name));
        tr.appendChild(createCell(data[i].username));
        tr.appendChild(createCell((new Date(data[i].last_message_timestamp)).toLocaleString()));
        tr.appendChild(createCell(data[i].unread?data[i].unread:" "));
        table.appendChild(tr);
    }
    chatList.appendChild(table);
    translateAll();
};

var ws = undefined;

const connectWsChatList = async function() {
    const protocol = window.location.protocol == "http:" ? "ws:" : "wss:";
    ws = new WebSocket(protocol + "//" + window.location.host + "/ws_multi_lite");
    ws.onopen = ()=>{
        const table = chatList.firstElementChild;
        for (let i=0;i<table.children.length;i++)
            if (table.children[i].userhash)
                ws.send(JSON.stringify({"action": "subscribe", "userhash": table.children[i].userhash, token: localStorage.token??""}));
    };
    ws.onmessage = (message)=>{
        let data = JSON.parse(message.data);
        const table = chatList.firstElementChild;
        if (data.action == "message_readed")
            for (let i=0;i<table.children.length;i++)
                if (table.children[i].userhash == data.userhash) {
                    table.children[i].className = "class-list-row";
                    table.children[i].lastElementChild.textContent = "";
                    break;
                }
        if (data.action == "new_message")
            for (let i=0;i<table.children.length;i++)
                if (table.children[i].userhash == data.userhash) {
                    table.children[i].className = "class-list-row class-list-row-unread";
                    table.children[i].lastElementChild.textContent = 1 + Number(table.children[i].lastElementChild.textContent);
                    break;
                }
    };
    ws.onclose = ()=>{setTimeout(connectWsChatList, MESSAGE_LIST_SYNC_INTERVAL)};
};

permissionChecks.then(async ()=>{
    if (chatList) {
        await updateChatList();
        await connectWsChatList();
    }
});