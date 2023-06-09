import cherrypy
import messenger
import json

from messenger_logs import log_statistic, log_error
from collections import defaultdict
from ws4py.websocket import WebSocket
from ws4py.messaging import TextMessage
from threading import Thread

SUBSCRIBTIONS = defaultdict(set)
NOTIFY_SUBSCRIBTION = defaultdict(set)
NOTIFY_SUBSCRIBTION_READED = defaultdict(set)

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
        self.thread_id = ""
    
    def received_message(self, message: TextMessage):
        try:
            content = json.loads(message.data.decode(message.encoding))
            action = content.get('action', '')
            connection = messenger.get_database_connection()
            cursor = connection.cursor()
            
            if action == 'subscribe':           
                self.userhash = content.get('userhash', '')
                self.token = content.get('token', '')
                self.thread_id = messenger.get_thread_id(cursor, self.userhash, self.token)
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
            if self.thread_id in SUBSCRIBTIONS:
                SUBSCRIBTIONS[self.thread_id].remove(self)        
        except Exception as err:
            log_error(err)   
        
class NotifyWebSocketHandler(WebSocket):
    
    def __init__(self, sock, protocols=None, extensions=None, environ=None, heartbeat_freq=None):
        super().__init__(sock, protocols, extensions, environ, heartbeat_freq)
        self.userhash = []
        self.token = ""
        self.thread_id = []
        
    def received_message(self, message: TextMessage):
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
                self.thread_id.append(current_thread_id)
                NOTIFY_SUBSCRIBTION[current_thread_id].add((self, current_hash))
                NOTIFY_SUBSCRIBTION_READED[current_hash].add(self)
        except Exception as err:
            log_error(err)   
            
    def closed(self, code, reason=""):
        try:
            cherrypy.log('Multi connection %s closed'%self.token[:8])
            for thread_id in self.thread_id:
                if thread_id in NOTIFY_SUBSCRIBTION:
                    NOTIFY_SUBSCRIBTION[thread_id].remove(self)
            for userhash in self.userhash:
                if self in NOTIFY_SUBSCRIBTION_READED[userhash]:
                    NOTIFY_SUBSCRIBTION_READED[userhash].remove(self)
        except Exception as err:
            log_error(err)   
        