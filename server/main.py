import cherrypy
import json
import messenger
import os

from tasks import Task
from messenger_logs import log_error, log_statistic, save_logs
from functools import wraps
from web_socket_module import ChatWebSocketHandler, NotifyWebSocketHandler, propagate_message
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool

MY_PATH = os.path.dirname(os.path.abspath(__file__)) + "/"
STATIC_PATH = MY_PATH + '../static/'
ERROR_RESPONSE = json.dumps({"status": "error"}).encode("utf-8")
TRNASLATES = json.loads(open(STATIC_PATH+"translates.json").read())
LANGUAGES_LIST = list(TRNASLATES.keys())

for k in LANGUAGES_LIST:
    keyList = list(TRNASLATES[k].keys())
    keyList.sort()
    TRNASLATES[k] = {k2: TRNASLATES[k][k2] for k2 in keyList}

with open(STATIC_PATH+"translates.json", "w") as f:
    f.write(json.dumps(TRNASLATES, indent=4))
    
for k in LANGUAGES_LIST:
    TRNASLATES[k]["__supported_languages__"] = LANGUAGES_LIST


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
            log_error(err)
            cherrypy.log(err)
            return ERROR_RESPONSE

    return decorator

def decorator_pack(fun):
    
    @cherrypy.expose()
    @log_statistic
    @unpackCherryPyJson
    @messenger.cursor_provider
    @wraps(fun)
    def decorator(*args, **kwargs):
        return fun(*args, **kwargs)
    
    return decorator

class Server:
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    def get_translations(self, languages="en", *args, **kwargs):
        languages = str(languages).split(";")
        for language in languages:
            if language in TRNASLATES:
                return TRNASLATES[language]
        return TRNASLATES.get("en", dict())
    
    
    @cherrypy.expose()
    @unpackCherryPyJson
    def get_translation_keys(self, *args, **kwargs):
        return LANGUAGES_LIST
    
    
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
        return messenger.can_create_user(cursor, userhash, token=token)
    
    
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


    @decorator_pack
    def get_threads_with_token(self, cursor, token):
        return messenger.get_threads_with_token(cursor, token)


    @decorator_pack
    def login(self, cursor, login, password, no_activity_lifespan=3600, max_lifespan=604800):
        return messenger.login(cursor, login, password, no_activity_lifespan=no_activity_lifespan, max_lifespan=max_lifespan)


    @decorator_pack
    def register(self, cursor, login, password):
        return messenger.register(cursor, login, password)
    

    @decorator_pack
    def logout(self, cursor, token=""):
        return messenger.logout(cursor, token)


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
    cherrypy.config.update({"server.max_request_body_size": 256*1024})
    cherrypy.tree.mount(Root(), '/', SERVER_CONFIG)
    cherrypy.tree.mount(Server(), '/query', SERVER_CONFIG)
    
    log_error("Server started")
    task = Task(cherrypy.engine, save_logs, period=30, init_delay=30, repeat_on_close=True, before_close=lambda: log_error("Server stopped"))
    task.subscribe()
    task = Task(cherrypy.engine, messenger.cursor_provider(messenger.maintain), period=3600, init_delay=10)
    task.subscribe()

    cherrypy.engine.start()
    cherrypy.engine.block()
    