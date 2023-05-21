import cherrypy
import messenger
import json

from collections import defaultdict
from ws4py.websocket import WebSocket
from ws4py.messaging import TextMessage

SUBSCRIBTIONS = defaultdict(set)

def propagate_message(cursor, thread_id, message_id):
    msg, userhash = messenger.get_message(cursor, message_id)
    for ws in SUBSCRIBTIONS[thread_id]:
        msg['me'] = userhash == ws.userhash
        ws.send(TextMessage(json.dumps([msg])))

class ChatWebSocketHandler(WebSocket):
    
    def __init__(self, sock, protocols=None, extensions=None, environ=None, heartbeat_freq=None):
        super().__init__(sock, protocols, extensions, environ, heartbeat_freq)
        self.userhash = ""
        self.token = ""
        self.thread_id = ""
    
    def received_message(self, message: TextMessage):
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
            if sent_result['status'] == "ok":
                propagate_message(cursor, self.thread_id, sent_result['message_id'])
            connection.commit()
                                   

    def closed(self, code, reason=""):
        cherrypy.log('Connection %s closed'%self.userhash)
        SUBSCRIBTIONS[self.thread_id].remove(self)
        