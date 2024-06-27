import json
import cherrypy
import messenger
import urllib.parse

from time import time
from threading import Thread
from pywebpush import webpush
from collections import defaultdict
from ws4py.websocket import WebSocket
from ws4py.messaging import Message, TextMessage
from messenger_logs import log_statistic, log_error


SUBSCRIBTIONS = defaultdict(set)
NOTIFY_SUBSCRIBTION = defaultdict(set)
NOTIFY_SUBSCRIBTION_READED = defaultdict(set)
MAX_CONNECTION_TIME = messenger.get_int_env('MAX_CONNECTION_TIME', 7200)


@log_statistic
def propagate_message(cursor, thread_id, message_id):
    msg, userhash = messenger.get_message(cursor, message_id)
    for ws in SUBSCRIBTIONS[thread_id]:
        msg['me'] = userhash == ws.userhash
        txt_msg = TextMessage(json.dumps({"action": "new_message", "messages": [msg]}))
        Thread(target=lambda ws=ws, msg=txt_msg: ws.send(msg)).start()

    for ws, ident in NOTIFY_SUBSCRIBTION[thread_id]:
        txt_msg = TextMessage(json.dumps({"action": "new_message", "userhash": ident}))
        Thread(target=lambda ws=ws, msg=txt_msg: ws.send(msg)).start()

    active_users = set()
    for s in SUBSCRIBTIONS.values():
        active_users.update(o.userhash for o in s)

    push_delivered_successfull = []
    for dest in messenger.push_get_by_thread(cursor, thread_id)['data']:
        if dest['userhash'] == userhash or dest['userhash'] in active_users:
            continue
        try:
            message = {
                'address': '/messages.html?'+urllib.parse.urlencode({'userhash': dest['userhash']}),
                'from': msg['username'],
                'content': msg['content']
            }
            webpush(
                subscription_info=dest['subscription_information'],
                data=json.dumps(message),
                vapid_private_key=dest['vapid_private_key'],
                vapid_claims=messenger.VAPID_CLAIMS
            )
            push_delivered_successfull.append(dest['pn_id'])
        except Exception as e:
            log_error(e)        
    
    messenger.push_update_success(cursor, push_delivered_successfull)
        

propagate_message_with_cursor = messenger.cursor_provider(propagate_message)


def propagate_message_async(thread_id, message_id):
    Thread(lambda tid=thread_id, mid=message_id: propagate_message_with_cursor(tid, mid)).start()


@log_statistic
def propagate_readed(userhash):
    for ws in  NOTIFY_SUBSCRIBTION_READED[userhash]:
        txt_msg = TextMessage(json.dumps({"action": "message_readed", "userhash": userhash}))
        Thread(target=lambda ws=ws, msg=txt_msg:ws.send(msg)).start()


class ChatWebSocketHandler(WebSocket):

    def __init__(self, sock, protocols=None, extensions=None, environ=None, heartbeat_freq=None):
        super().__init__(sock, protocols, extensions, environ, heartbeat_freq)
        self.userhash = ""
        self.token = ""
        self.thread_id = 0
        self.connectTime = time()


    def received_message(self, message: Message):
        try:
            content = json.loads(message.data.decode(message.encoding))
            action = content.get('action', '')
            connection = messenger.get_database_connection()
            cursor = connection.cursor()

            if action == 'subscribe' and len(self.userhash) == 0:
                self.userhash = content.get('userhash', '')
                self.token = content.get('token', '')
                self.thread_id = messenger.get_thread_id(cursor, self.userhash, self.token)
                if self.thread_id is None:
                    self.close()
                    return
                SUBSCRIBTIONS[self.thread_id].add(self)

            if action == 'message':
                text = content.get('message', '')
                sent_result = messenger.send_message(cursor, self.userhash, text, token=self.token)
                connection.commit()
                if sent_result['status'] == "ok":
                    propagate_message(connection.cursor(), self.thread_id, sent_result['message_id'])

            if action == 'set_as_readed':
                messenger.set_user_read(cursor, self.userhash, self.token)
                propagate_readed(self.userhash)
                connection.commit()

            if action == 'get_messages' or action == 'get_newest':
                text = content.get('message', '')
                result = messenger.get_messages(
                    cursor,
                    self.userhash,
                    content.get('offset', 0),
                    content.get('limit', 64),
                    content.get('id_bookmark', 0),
                    content.get('id_direction', 0),
                    content.get('excludeList', []),
                    self.token)
                if result['status'] == 'ok':
                    self.send(TextMessage(json.dumps({"action": "ordered_messages", "newest": action == 'get_newest', "messages": result['messages']})))
        except Exception as err:
            log_error(err)


    def closed(self, code, reason=""):
        try:
            cherrypy.log('Connection %s closed'%self.userhash[:8])
            if self.thread_id in SUBSCRIBTIONS and self in SUBSCRIBTIONS[self.thread_id]:
                SUBSCRIBTIONS[self.thread_id].remove(self)
        except Exception as err:
            log_error(err)


class NotifyWebSocketHandler(WebSocket):

    def __init__(self, sock, protocols=None, extensions=None, environ=None, heartbeat_freq=None):
        super().__init__(sock, protocols, extensions, environ, heartbeat_freq)
        self.userhash = []
        self.token = ""
        self.thread_id = []
        self.connectTime = time()


    def received_message(self, message: Message):
        try:
            content = json.loads(message.data.decode(message.encoding))
            action = content.get('action', '')
            connection = messenger.get_database_connection()
            cursor = connection.cursor()

            if action == 'subscribe':
                current_hash = content.get('userhash', '')
                self.userhash.append(current_hash)
                self.token = content.get('token', '')
                current_thread_id = messenger.get_thread_id(cursor, current_hash, self.token)
                if current_thread_id is None:
                    self.close()
                    return
                self.thread_id.append(current_thread_id)
                NOTIFY_SUBSCRIBTION[current_thread_id].add((self, current_hash))
                NOTIFY_SUBSCRIBTION_READED[current_hash].add(self)
        except Exception as err:
            log_error(err)


    def closed(self, code, reason=""):
        try:
            cherrypy.log('Multi connection %s closed'%self.token[:8])
            for thread_id in self.thread_id:
                for userhash in self.userhash:
                    value = (self, userhash)
                    if thread_id in NOTIFY_SUBSCRIBTION and value in NOTIFY_SUBSCRIBTION[thread_id]:
                        NOTIFY_SUBSCRIBTION[thread_id].remove(value)
            for userhash in self.userhash:
                if self in NOTIFY_SUBSCRIBTION_READED[userhash] and self in NOTIFY_SUBSCRIBTION_READED[userhash]:
                    NOTIFY_SUBSCRIBTION_READED[userhash].remove(self)
        except Exception as err:
            log_error(err)


def clean_old_connections():
    current_time = time()

    for k in list(SUBSCRIBTIONS.keys()):
        for connection in list(SUBSCRIBTIONS[k]):
            if current_time - connection.connectTime > MAX_CONNECTION_TIME:
                SUBSCRIBTIONS[k].remove(connection)
                connection.close()
        if len(SUBSCRIBTIONS[k]) == 0:
            SUBSCRIBTIONS.pop(k)

    for k in list(NOTIFY_SUBSCRIBTION.keys()):
        outdated_connections = set(connection for connection, _ in NOTIFY_SUBSCRIBTION[k] if current_time - connection.connectTime > MAX_CONNECTION_TIME)
        NOTIFY_SUBSCRIBTION[k] = set((connection, hash) for connection, hash in NOTIFY_SUBSCRIBTION[k] if connection not in outdated_connections)
        for connection in outdated_connections:
            connection.close()
        if len(NOTIFY_SUBSCRIBTION[k]) == 0:
            NOTIFY_SUBSCRIBTION.pop(k)

    for k in list(NOTIFY_SUBSCRIBTION_READED.keys()):
        for connection in list(NOTIFY_SUBSCRIBTION_READED[k]):
            if current_time - connection.connectTime > MAX_CONNECTION_TIME:
                NOTIFY_SUBSCRIBTION_READED[k].remove(connection)
                connection.close()
        if len(NOTIFY_SUBSCRIBTION_READED[k]) == 0:
            NOTIFY_SUBSCRIBTION_READED.pop(k)
