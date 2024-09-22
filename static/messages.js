"use strict";

const MESSAGE_SYNC_INTERVAL = 2500;

const messageEditor = document.getElementById('message-editor');
const sendMessageBtn = document.getElementById('send-message-btn');
const messagesList = document.getElementById('messages-list');
const newMessagesLabel = document.getElementById('new-messages-label');
const menuButton = document.getElementById('menu-button');
const messagesMenuColumn = document.getElementById('messages-menu-column');

const voiceChatUsersCount = document.getElementById('voice-chat-users-count');
const voiceChatuserList = document.getElementById('voice-chat-users-list');

const notification = new Audio('/notification.ogg');

var messageBatch = 32;
var messageLimitOnList = 2*messageBatch-1;
var messageOffset = 0;
var isNewMessage = false;
var ws = undefined;

menuButton.addEventListener('click', ()=>{
    messagesMenuColumn.style.display = messagesMenuColumn.style.display==""?"none":"";
});

if (window.innerHeight > window.innerWidth)
    menuButton.click();

const sleep = function (ms) {
    return new Promise((resolve)=>setTimeout(resolve, ms));
};

const createMessageCloud = function(messageData) {
    let message = document.createElement('div');
    let content = document.createElement('div');
    let header = document.createElement('span');
    let timestamp = document.createElement('span');
    let hr = document.createElement('hr');
    message.data = messageData;
    content.innerHTML = messageData.content;
    content.className = "message-content";
    header.textContent = messageData.username;
    header.className = "message-header " + (messageData.me?"my-message-header":"regular-message-header");
    if (messageData.system)
        header.innerHTML = "<i>System</i>";
    let date = new Date(messageData.timestamp);
    timestamp.textContent = date.toLocaleString();
    timestamp.className = "message-timestamp " + (messageData.me?"my-messege-timestamp":"regular-message-timestamp");
    message.appendChild(header);
    message.appendChild(hr);
    message.appendChild(content);
    message.appendChild(timestamp);
    message.className = "message-cloud " + (messageData.me?"my-messege":"regular-message");
    return message;
};

const setToArray = function(set) {
    let result = new Array();
    let i=0;
    set.forEach(element => {
        result[i++] = element;
    });
    return result;
};

function realHeight(el) {
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
    for (let i=0;i<messagesList.children.length;i++)
        if (halfHeight <= currentHeight && halfHeight >= currentHeight + realHeight(messagesList.children[i])) {
            halfIndex = i;
            break;
        }

    let messageIds = new Set();
    for (let i=0;i<messagesList.children.length;i++) {
        messageIds.add(messagesList.children[i].data.id);
    }
    let count = 0;
    let scrollTopOffset = 0;
    let addedBefore = 0;
    for (let i=0;i<newMessagesList.length;i++) {
        if (!messageIds.has(newMessagesList[i].id)) {
            let newCloud = createMessageCloud(newMessagesList[i]);
            if (messagesList.children.length == 0 || messagesList.lastChild.data.timestamp < newMessagesList[i].timestamp)
                messagesList.appendChild(newCloud);
            else if (messagesList.firstElementChild.data.timestamp > newMessagesList[i].timestamp) {
                messagesList.insertBefore(newCloud, messagesList.firstElementChild);
                scrollTopOffset += realHeight(newCloud);
                halfIndex++;
                addedBefore++;
            }
            else
                for (let j=1;j<messagesList.children.length;j++)
                    if (messagesList.children[j-1].data.timestamp < newMessagesList[i].timestamp && messagesList.children[j].data.timestamp > newMessagesList[i].timestamp) {
                        messagesList.insertBefore(newCloud, messagesList.children[j]);
                        if (j < halfIndex) {
                            scrollTopOffset += realHeight(newCloud);
                            halfIndex++;
                            addedBefore++;
                        }
                        break;
                    }
            messageIds.add(newMessagesList[i].id);
            count++;
        }
    }
    if (count) {
        if (addedBefore > count/2) {
            while (messagesList.children.length > messageLimitOnList)
                messagesList.removeChild(messagesList.lastElementChild);
        } else {
            while (messagesList.children.length > messageLimitOnList)
                messagesList.removeChild(messagesList.firstChild);
        }
    }
    messagesList.scrollTop += scrollTopOffset;
    return count;
};


const checkWs = async function(trials=50, timeout=100) {
    for (let i=0;i<trials;i++) {
        if (ws.readyState == ws.OPEN)
            return true;
        await sleep(timeout);
    }
    return false;
};


const sendMessage = async function() {
    const message = messageEditor.innerText;
    if (message == "")
        return;
    messageEditor.disabled = "disabled";
    try
    {
        if (await checkWs()) {
            ws.send(JSON.stringify({"action": "message", "message": message}));
            messageEditor.textContent = "";
            messageOffset = 0;
            messagesList.scrollTop = messagesList.scrollHeight;
        } else
            alert(translate("Cannot send the message"));
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
    if (messagesList.scrollTop >= messagesList.scrollHeight-messagesList.clientHeight-1) {
        if (isNewMessage)
            ws.send(JSON.stringify({"action": "set_as_readed"}));
        isNewMessage = false;
    }
};


messagesList.addEventListener('scroll', setNewMessageAsReaded);


const showNewMessagesLabel = function() {
    setNewMessageAsReaded();
    newMessagesLabel.style.display = isNewMessage?"":"none";
};


newMessagesLabel.addEventListener('click', async ()=>{
    messageOffset = 0;
    messagesList.innerHTML = "";
    let data = {
        action: 'get_newest',
        offset: 0,
        limit: messageBatch,
        exclude_list: [],
    };
    ws.send(JSON.stringify(data));
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
        exclude_list: messageIds,
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
        let data = {
            action: 'get_newest',
            offset: 0,
            limit: messageBatch,
            exclude_list: [],
        };
        ws.send(JSON.stringify(data));
    };
    ws.onmessage = (message)=>{
        let data = JSON.parse(message.data);
        let messages = data.messages;
        if (data.action == "new_message") {
            let playSound = false;
            isNewMessage = true;
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
            if (playSound)
                notification.play();
        }
        if (data.action == "ordered_messages") {
            addMessages(messages);
            if (data.newest) {
                messagesList.scrollTop = messagesList.scrollHeight;
                ws.send(JSON.stringify({"action": "set_as_readed"}));
            }
        }
        if (data.action == "update_voice_chat_list") {
            voiceChatUsersCount.textContent = data.user_list.length.toLocaleString();
            voiceChatuserList.innerHTML = "";
            data.user_list.forEach((a_username)=>{
                const li = document.createElement('li');
                li.textContent = a_username;
                voiceChatuserList.appendChild(li);
            });
        }
    };
    ws.onclose = ()=>{setTimeout(connectWS, MESSAGE_SYNC_INTERVAL)};
};


window.addEventListener('beforeunload', ()=>{
    ws.onclose = ()=>{};
    ws.close()
});


permissionChecks.then(ensureAccessIsValid).then(connectWS);
