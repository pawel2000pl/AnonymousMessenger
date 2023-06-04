import messenger

from time import time
from functools import wraps


MAX_ERROR_LIFETIME = 1000 * 3600 * 24 * 30
MAX_STATISTIC_LIFETIME = 1000 * 3600 * 24 * 30

DB_COMMANDS = []


def log_error(error):
    global DB_COMMANDS
    DB_COMMANDS.append(("INSERT INTO errors (timestamp, message) VALUES (%s, %s)", [int(time()*1000), str(error)]))        


def log_statistic(fun):
    
    @wraps(fun)
    def decorator(*args, **kwargs):
        global DB_COMMANDS
        t1 = time()
        result = fun(*args, **kwargs)
        t2 = time()        
        DB_COMMANDS.append(("INSERT INTO statistics (timestamp, time, ident) VALUES (%s, %s, %s)", [int(t1*1000), (t2-t1)*1000, fun.__name__[:16]]))        
        return result
    
    return decorator


def save_logs():
    
    @messenger.cursor_provider
    def save(cursor):
        global DB_COMMANDS
        for command, params in DB_COMMANDS:
            cursor.execute(command, params)
            
        cursor.execute("DELETE FROM errors WHERE timestamp < %s", [int(time()*1000) - MAX_ERROR_LIFETIME])
        cursor.execute("DELETE FROM statistics WHERE timestamp < %s", [int(time()*1000) - MAX_ERROR_LIFETIME])
        
        DB_COMMANDS = []
    
    if len(DB_COMMANDS) > 0:
        save()