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

    const createCell = function(link, text) {
        const td = document.createElement('td');
        const a = document.createElement('a');
        td.className = 'chat-list-cell';
        a.innerText = text;
        a.href = link;
        td.appendChild(a);
        return td;
    };

    for (let i=0;i<data.length;i++) {

        let params = new URLSearchParams();
        params.append('userhash', data[i].userhash);
        const link = window.location.origin + "/messages.html?" + params.toString();

        const tr = document.createElement('tr');
        tr.className = "class-list-row " + (data[i].unread?"class-list-row-unread":"");
        tr.appendChild(createCell(link, data[i].thread_name));
        tr.appendChild(createCell(link, data[i].username));
        tr.appendChild(createCell(link, (new Date(data[i].last_message_timestamp)).toLocaleString()));
        tr.appendChild(createCell(link, data[i].unread?data[i].unread:" "));
        table.appendChild(tr);
    }
    chatList.appendChild(table);
    translateAll();
};

permissionChecks.then(()=>{
    if (chatList) {
        updateChatList();
    }
});