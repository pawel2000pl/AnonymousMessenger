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
var isNewMessage = false;
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

function realHeigh(el) {
    // Get the DOM Node if you pass in a string
    el = (typeof el === 'string') ? document.querySelector(el) : el; 
  
    var styles = window.getComputedStyle(el);
    var margin = Math.max(parseFloat(styles['marginTop']),
                 parseFloat(styles['marginBottom']));
  
    return Math.ceil(el.offsetHeight + margin);
  }

const addMessages = function(newMessagesList){
    let halfHeight = messagesList.scrollTop + messagesList.scrollHeight/2;
    let currentHeight = 0;
    let halfIndex = 0;
    for (let i=0;i<messagesList.children.length;i++) {
        if (halfHeight <= currentHeight && halfHeight >= currentHeight + realHeigh(messagesList.children[i])) {
            halfIndex = i;
            break;
        }

    }

    let messageIds = new Set();
    for (let i=0;i<messagesList.children.length;i++) {
        messageIds.add(messagesList.children[i].data.id);
    }
    let count = 0;
    let scrollTopOffset = 0;
    for (let i=0;i<newMessagesList.length;i++) {
        if (!messageIds.has(newMessagesList[i].id)) {
            let newCloud = createMessageCloud(newMessagesList[i]);
            if (messagesList.children.length == 0 || messagesList.lastChild.data.timestamp < newMessagesList[i].timestamp) 
                messagesList.appendChild(newCloud);
            else if (messagesList.firstElementChild.data.timestamp > newMessagesList[i].timestamp) {
                messagesList.insertBefore(newCloud, messagesList.firstElementChild);
                scrollTopOffset += realHeigh(newCloud);
            }
            else
                for (let j=1;j<messagesList.children.length;j++)
                    if (messagesList.children[j-1].data.timestamp < newMessagesList[i].timestamp && messagesList.children[j].data.timestamp > newMessagesList[i].timestamp) {
                        messagesList.insertBefore(newCloud, messagesList.children[j]);
                        if (j < halfIndex) {
                            scrollTopOffset += realHeigh(newCloud);
                            halfIndex++;
                        }
                        break;
                    }
            messageIds.add(newMessagesList[i].id);
            count++;
        }
    }
    messagesList.scrollTop += scrollTopOffset;
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
        } else 
            alert("Cannot send the message");
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

const setNewMessageAsReaded = function() {
    if (messagesList.scrollTop >= messagesList.scrollHeight-messagesList.clientHeight-1)
        isNewMessage = false;
};

messagesList.addEventListener('scroll', setNewMessageAsReaded);

const showNewMessagesLabel = function() {
    setNewMessageAsReaded();
    newMessagesLabel.style.display = isNewMessage?"":"none";
}


newMessagesLabel.addEventListener('click', async ()=>{
    messageOffset = 0;
    messagesList.innerHTML = "";
    await syncMessages();
    messagesList.scrollTop = messagesList.scrollHeight - messagesList.clientHeight - 1;
});

var scrollEVents = 0;
messagesList.addEventListener('scroll', async ()=>{
    scrollEVents++;
    await new Promise(r=>setTimeout(r, 300));
    if (--scrollEVents > 0)
        return;
    let id_bookmark = 0;
    let id_direction = 0;
    let need_new = false;
    if (messagesList.children.length > 0) {
        if (messagesList.scrollTop <= 0) {
            id_direction = -1;
            id_bookmark = messagesList.firstElementChild.data.id;
            need_new = true;
        }
        if (messagesList.scrollTop + messagesList.clientHeight >= messagesList.scrollHeight-1) {
            id_direction = 1;
            id_bookmark = messagesList.lastElementChild.data.id;
            need_new = true;
        }
    }

    if (!need_new) 
        return;

    let messageIds = new Array(messagesList.children.length);
    for (let i=0;i<messagesList.children.length;i++) {
        messageIds[i] = messagesList.children[i].data.id;
    }
    let data = {
        action: 'get_messages',
        offset: 0,
        limit: messageBatch,
        excludeList: messageIds,
        id_bookmark: id_bookmark,
        id_direction: id_direction
    };
    ws.send(JSON.stringify(data));
});


setInterval(showNewMessagesLabel, 300);

const connectWS = function () {
    const protocol = window.location.protocol == "http:" ? "ws:" : "wss:";
    ws = new WebSocket(protocol + "//"+window.location.host+"/ws");
    ws.onopen = ()=>{
        ws.send(JSON.stringify({"action": "subscribe", "userhash": userhash, token: localStorage.token??""}));
        messageOffset = 0;
        syncMessages().then(()=>{messagesList.scrollTop = messagesList.scrollHeight;});
    };
    ws.onmessage = (message)=>{
        let data = JSON.parse(message.data);
        let messages = data.messages;
        if (data.action == "new_message") { 
            let playSound = false;
            for (let i=0;i<messages.length;i++) {
                playSound = playSound || (!messages[i].me);
            }
            if (messageOffset == 0) {
                addMessages(messages);
                if (messagesList.scrollTop >= messagesList.scrollHeight - 3/2*messagesList.clientHeight - 1) {
                    messagesList.scrollTop = messagesList.scrollHeight;
                    while (messagesList.children.length > messageLimitOnList) 
                        messagesList.removeChild(messagesList.firstElementChild);
                }
            }
            if (playSound) {
                (new Audio('/notification.mp3')).play();
                isNewMessage = true;
            }
        }
        if (data.action == "ordered_messages") {
            addMessages(messages);
        }
    };
    ws.onclose = ()=>{setTimeout(connectWS, MESSAGE_SYNC_INTERVAL)};
};

window.addEventListener('beforeunload', ()=>{
    ws.onclose = ()=>{};
    ws.close()
});

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
        alert('Acces data is invalid');
        window.location = window.location.origin;
    }
};

ensureAccessIsValid().then(connectWS);