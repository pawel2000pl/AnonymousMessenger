const MESSAGE_SYNC_INTERVAL = 2500;

const messageEditor = document.getElementById('message-editor');
const sendMessageBtn = document.getElementById('send-message-btn');
const messagesList = document.getElementById('messages-list');
const newMessagesLabel = document.getElementById('new-messages-label');

const urlParams = new URLSearchParams(window.location.search);
const userhash = urlParams.get('userhash');

var messageBatch = 32;
var messageLimitOnList = 2*messageBatch-1;
var messageOffset = 0;
var newestTimestamp = 0;
var newestAvailableTimestamp = 0;
var ws = undefined;

const createMessageCloud = function(messageData) {
    let message = document.createElement('div');
    let content = document.createElement('div');
    let header = document.createElement('span');
    let timestamp = document.createElement('span');
    let hr = document.createElement('hr');
    message.data = messageData;
    content.innerHTML = messageData.content;
    content.className = "message-content";
    header.innerText = messageData.username;
    header.className = "message-header " + (messageData.me?"my-message-header":"regular-message-header");
    if (messageData.system)
        header.innerHTML = "<i>System</i>";
    let date = new Date(messageData.timestamp) 
    timestamp.className = "message-timestamp " + (messageData.me?"my-messege-timestamp":"regular-message-timestamp");
    timestamp.innerText = date.toLocaleString();
    message.appendChild(header);
    message.appendChild(hr);
    message.appendChild(content);
    message.appendChild(timestamp);
    message.className = "message-cloud " + (messageData.me?"my-messege":"regular-message");
    return message;
}

const setToArray = function(set) {
    let result = new Array();
    let i=0;
    set.forEach(element => {
        result[i++] = element;
    });
    return result;
}

const addMessages = function(newMessagesList){
    let messageIds = new Set();
    for (let i=0;i<messagesList.children.length;i++) {
        messageIds.add(messagesList.children[i].data.id);
    }
    let count = 0;
    for (let i=0;i<newMessagesList.length;i++) {
        newestTimestamp = Math.max(newestTimestamp, newMessagesList[i].timestamp);
        if (!messageIds.has(newMessagesList[i].id)) {
            if (messagesList.children.length == 0 || messagesList.lastChild.data.timestamp < newMessagesList[i].timestamp) 
                messagesList.appendChild(createMessageCloud(newMessagesList[i]));
            else if (messagesList.firstElementChild.data.timestamp > newMessagesList[i].timestamp)
                messagesList.insertBefore(createMessageCloud(newMessagesList[i]), messagesList.firstElementChild);
            else
                for (let j=1;j<messagesList.children.length;j++)
                    if (messagesList.children[j-1].data.timestamp < newMessagesList[i].timestamp && messagesList.children[j].data.timestamp > newMessagesList[i].timestamp) {
                        messagesList.insertBefore(createMessageCloud(newMessagesList[i]), messagesList.children[j]);
                        break;
                    }
            messageIds.add(newMessagesList[i].id);
            count++;
        }
    }
    newestAvailableTimestamp = newestTimestamp;
    return count;
}

const syncMessages = async function () {
    let messageIds = new Array(messagesList.children.length);
    for (let i=0;i<messagesList.children.length;i++) {
        messageIds[i] = messagesList.children[i].data.id;
    }

    let response = await fetch('/query/get_messages', {
        method: "post",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userhash: userhash,
            limit: messageBatch,
            offset: messageOffset,
            excludeList: messageIds,
            token: localStorage.token??""
        }),
    });

    let result = await response.json();
    if (result['status'] != "ok")
        return -1;

    return addMessages(result.messages);
};

const sendMessage = async function() {
    const message = messageEditor.innerText;
    if (message == "")
        return;
    messageEditor.disabled = "disabled";
    try
    {
        if (ws.readyState == ws.OPEN) {
            ws.send(JSON.stringify({"action": "message", "message": message}));
            messageEditor.innerText = "";
            messageOffset = 0;
            messagesList.scrollTop = messagesList.scrollHeight;
        } else {
            let response = await fetch('/query/send_message', {
                method: "post",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    userhash: userhash,
                    content: message,
                    token: localStorage.token??""
                }),
            });
            let result = await response.json();
            if (result["status"] != "ok")
                alert("Cannot send the message");
            else {
                messageEditor.innerText = "";
                messageOffset = 0;
                messagesList.scrollTop = messagesList.scrollHeight;
            }
        }
    } finally {
        messageEditor.disabled = "";
    }
};

sendMessageBtn.addEventListener('click', sendMessage);

messageEditor.addEventListener('keypress', (event)=>{
    if (event.key == "Enter" && event.shiftKey != true) {
        event.preventDefault();
        sendMessage();
    }
});

const updateMessageList = async function () {
    if (messagesList.scrollTop <= 0) {
        let scrollOffset = messagesList.scrollHeight - messagesList.scrollTop;
        let oldMessageOffset = messageOffset;
        messageOffset += messageBatch;
        let count = await syncMessages();
        if (count <= 0)
            messageOffset = oldMessageOffset
        messagesList.scrollTop = messagesList.scrollHeight - scrollOffset-1;
        while (messagesList.children.length > messageLimitOnList) 
            messagesList.removeChild(messagesList.lastElementChild);
    }

    if (messagesList.scrollTop + messagesList.clientHeight >= messagesList.scrollHeight-1) {
        let last = messagesList.lastElementChild;
        if (messageOffset > 0) {
            messageOffset = Math.max(messageOffset - messageBatch, 0);
            await syncMessages();
        }
        while (messagesList.children.length > messageLimitOnList) 
            messagesList.removeChild(messagesList.firstElementChild);
        messagesList.scrollIntoView(last);
    }
}

const showNewMessagesLabel = function() {
    newMessagesLabel.style.display = newestAvailableTimestamp==newestTimestamp?"none":"";
}

newMessagesLabel.addEventListener('click', async ()=>{
    messageOffset = 0;
    messagesList.innerHTML = "";
    await syncMessages();
    messagesList.scrollTop = messagesList.scrollHeight - messagesList.clientHeight - 1;
});

setInterval(updateMessageList, 300);
setInterval(showNewMessagesLabel, 300);

const connectWS = function () {
    ws = new WebSocket("ws://"+window.location.host+"/ws");
    ws.onopen = ()=>{
        ws.send(JSON.stringify({"action": "subscribe", "userhash": userhash, token: localStorage.token??""}));
        messageOffset = 0;
        syncMessages().then(()=>{messagesList.scrollTop = messagesList.scrollHeight;});
    };
    ws.onmessage = (message)=>{
        msgData = JSON.parse(message.data);
        let playSound = false;
        for (let i=0;i<msgData.length;i++) {
            newestTimestamp = Math.max(newestTimestamp, msgData[i].timestamp);
            playSound = playSound || (!msgData[i].me);
        }
        if (messageOffset == 0) {
            addMessages(msgData);
            if (messagesList.scrollTop >= messagesList.scrollHeight - 3/2*messagesList.clientHeight - 1) {
                messagesList.scrollTop = messagesList.scrollHeight;
                while (messagesList.children.length > messageLimitOnList) 
                    messagesList.removeChild(messagesList.firstElementChild);
            }
        }
        if (playSound) 
            (new Audio('/notification.mp3')).play();
    };
    ws.onclose = ()=>{setTimeout(connectWS, MESSAGE_SYNC_INTERVAL)};
};

window.addEventListener('beforeunload', ()=>{
    ws.onclose = ()=>{};
    ws.close()
});

connectWS();