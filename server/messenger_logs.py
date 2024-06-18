import messenger
import traceback

from time import time
from functools import wraps


MAX_ERROR_LIFETIME = messenger.get_int_env('MAX_ERROR_LIFETIME', 1000 * 3600 * 24 * 30)

DB_COMMANDS = []


def log_error(error):
    if isinstance(error, Exception):
        return log_error(str(error) + "\n\n" + str().join(traceback.TracebackException.from_exception(error).format()))
    global DB_COMMANDS
    DB_COMMANDS.append(("INSERT INTO errors (timestamp, message) VALUES (%s, %s)", [int(time()*1000), str(error)]))


def log_statistic(fun):

    @wraps(fun)
    def decorator(*args, **kwargs):
        global DB_COMMANDS
        t1 = time()
        result = fun(*args, **kwargs)
        t2 = time()
        duration = int(round((t2-t1)*1000))
        short_name = fun.__name__[:16]
        DB_COMMANDS.append(("INSERT INTO statistic_hist (duration, ident, count) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE `count` = `count` + 1", [duration, short_name]))
        return result

    return decorator


def save_logs():

    @messenger.cursor_provider
    def save(cursor):
        global DB_COMMANDS
        for command, params in DB_COMMANDS:
            cursor.execute(command, params)

        cursor.execute("DELETE FROM errors WHERE timestamp < %s", [int(time()*1000) - MAX_ERROR_LIFETIME])
        DB_COMMANDS = []

    if len(DB_COMMANDS) > 0:
        save()
