import cherrypy
import json
import messenger
import os

from web_socket_module import ChatWebSocketHandler, propagate_message
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool

SERVER_CONFIG = \
    {
        "/":
            {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': os.path.dirname(os.path.abspath(__file__)) + '/static',
                'tools.staticdir.index': 'index.html',
            },
        "/query": 
            {            
            },
        "/ws":
            {                    
                'tools.websocket.on': True,
                'tools.websocket.handler_cls': ChatWebSocketHandler
            }
    }


def unpackCherryPyJson(fun):

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
            return json.dumps({"status": "error"}).encode("utf-8")

    return decorator

class Server:
    
    @cherrypy.expose()
    @unpackCherryPyJson
    def index(self):
        return {"Hello": "World"}
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def is_token_valid(self, cursor, userhash, token=""):
        return messenger.is_token_valid(cursor, userhash, token=token)
            
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def send_message(self, cursor, userhash, content, token=""):
        result = messenger.send_message(cursor, userhash, content, token=token)
        if result['status'] == 'ok':
            propagate_message(cursor, messenger.get_thread_id(cursor, userhash, token), result['message_id'])
        return result
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def change_username(self, cursor, userhash, new_username, token=""):
        return messenger.change_username(cursor, userhash, new_username, token=token)
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def close_user(self, cursor, userhash, token=""):
        thread_id = messenger.get_thread_id(cursor, userhash, token)
        result = messenger.close_user(cursor, userhash, token)
        if result['status'] == 'ok':
            propagate_message(cursor, thread_id, result['message_id'])
        return result
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def reset_user_hash(self, cursor, userhash, token=""):
        return messenger.reset_user_hash(cursor, userhash, token)
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def add_user(self, cursor, creator, username, token=""):
        return messenger.add_user(cursor, str(creator), username, token)
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def create_new_thread(self, cursor, name, first_username, token=""):
        return messenger.create_new_thread(cursor, name, first_username, token)
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def get_messages(self, cursor, userhash, offset=0, limit=100, excludeList=[], token=""):
        return messenger.get_messages(cursor, userhash, offset, limit, excludeList, token)


    @cherrypy.expose()
    @unpackCherryPyJson
    @messenger.cursor_provider
    def get_newest_message_timestamp(self, cursor, userhash, token=""):
        return messenger.get_newest_message_timestamp(cursor, userhash, token)


class Root:
    
    @cherrypy.expose()
    def ws(self):
        cherrypy.log("Handler created: %s" % repr(cherrypy.request.ws_handler))


if __name__ == "__main__":
    messenger.init_database()

    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()

    cherrypy.config.update({"server.max_request_body_size": 1024*1024})
    cherrypy.tree.mount(Root(), '/', SERVER_CONFIG)
    cherrypy.tree.mount(Server(), '/query', SERVER_CONFIG)
    
    cherrypy.engine.start()
    cherrypy.engine.block()
