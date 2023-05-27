import cherrypy
import json
import messenger
import os

from functools import wraps
from web_socket_module import ChatWebSocketHandler, NotifyWebSocketHandler, propagate_message
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool

MY_PATH = os.path.dirname(os.path.abspath(__file__)) + "/"
STATIC_PATH = MY_PATH + '../static/'
ERROR_RESPONSE = json.dumps({"status": "error"}).encode("utf-8")

SERVER_CONFIG = \
    {
        "/":
            {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': STATIC_PATH,
                'tools.staticdir.index': 'index.html',
            },
        "/query": 
            {            
            },
        "/ws":
            {                    
                'tools.websocket.on': True,
                'tools.websocket.handler_cls': ChatWebSocketHandler
            },        
        "/ws_multi_lite":
            {                    
                'tools.websocket.on': True,
                'tools.websocket.handler_cls': NotifyWebSocketHandler
            },
        '/favicon.ico': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': STATIC_PATH + "favicon.svg"
        }
    }


def unpackCherryPyJson(fun):
    
    @wraps(fun)
    def decorator(*args, **kwargs):
        try:
            params = json.loads(cherrypy.request.body.read().decode("utf-8"))
            if isinstance(params, dict):
                kwargs.update(params)
        except:
            pass
        cherrypy.response.headers['Content-Type'] = 'application/json'
        try:
            return json.dumps(fun(*args, **kwargs)).encode("utf-8")
        except Exception as err:
            cherrypy.log(err)
            return ERROR_RESPONSE

    return decorator

def decorator_pack(fun):
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    @wraps(fun)
    def decorator(*args, **kwargs):
        return fun(*args, **kwargs)
    
    return decorator

class Server:
    
    @cherrypy.expose()
    @unpackCherryPyJson
    def index(self):
        return {"Hello": "World"}
    
    
    @decorator_pack
    def is_access_valid(self, cursor, userhash, token=""):
        return messenger.is_access_valid(cursor, userhash, token=token)
    
    
    @decorator_pack
    def activity(self, cursor, token=""):
        return messenger.activity(cursor, token=token)
            
    
    @decorator_pack
    def send_message(self, cursor, userhash, content, token=""):
        result = messenger.send_message(cursor, userhash, content, token=token)
        if result['status'] == 'ok':
            propagate_message(cursor, messenger.get_thread_id(cursor, userhash, token), result['message_id'])
        return result
    
    
    @decorator_pack
    def change_username(self, cursor, userhash, new_username, token=""):
        return messenger.change_username(cursor, userhash, new_username, token=token)
    
    
    @decorator_pack
    def close_user(self, cursor, userhash, token=""):
        thread_id = messenger.get_thread_id(cursor, userhash, token)
        result = messenger.close_user(cursor, userhash, token)
        if result['status'] == 'ok' and messenger.thread_exists(cursor, thread_id):
            propagate_message(cursor, thread_id, result['message_id'])
        return result
    
    
    @decorator_pack
    def reset_user_hash(self, cursor, userhash, token=""):
        return messenger.reset_user_hash(cursor, userhash, token)
    
    
    @decorator_pack
    def can_create_user(self, cursor, userhash, token=""):
        return messenger.can_create_user(cursor, userhash, token="")
    
    
    @decorator_pack
    def add_user(self, cursor, creator, username, can_create=True, token=""):
        result = messenger.add_user(cursor, str(creator), username, can_create, token)
        if result['status'] == 'ok':
            propagate_message(cursor, messenger.get_thread_id(cursor, creator, token), result['message_id'])
        return result
    
    
    @decorator_pack
    def create_new_thread(self, cursor, name, first_username, token=""):
        return messenger.create_new_thread(cursor, name, first_username, token)
    
    
    @decorator_pack
    def get_messages(self, cursor, userhash, offset=0, limit=100, id_bookmark=0, id_direction=0, excludeList=[], token=""):
        return messenger.get_messages(cursor, userhash, offset, limit, id_bookmark, id_direction, excludeList, token)


class Root:
    
    @cherrypy.expose()
    def ws(self):
        cherrypy.log("Handler created: %s" % repr(cherrypy.request.ws_handler))
        
    @cherrypy.expose()
    def ws_multi_lite(self):
        cherrypy.log("Multi handler created: %s" % repr(cherrypy.request.ws_handler))


if __name__ == "__main__":
    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()

    cherrypy.server.socket_host = "0.0.0.0" 
    cherrypy.server.socket_port = 8080
    if os.getenv("PRODUCTION") == "TRUE":
        cherrypy.config.update({'global': {'environment' : 'production'}})
        cherrypy.log.screen = True
    cherrypy.config.update({"server.max_request_body_size": 1024*1024})
    cherrypy.tree.mount(Root(), '/', SERVER_CONFIG)
    cherrypy.tree.mount(Server(), '/query', SERVER_CONFIG)
    
    cherrypy.engine.start()
    cherrypy.engine.block()
