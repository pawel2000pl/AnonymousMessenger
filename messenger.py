import sqlite3

from hashlib import sha224
from random import random
from time import time
from markdown import markdown

DATABASE_FILENAME = "/tmp/database.db"

MAX_MESSAGE_LENGTH = 262143
MAX_USERNAME_LENGTH = 255

CHANGES_USERNAME_MESSSAGE = "User %s has changed its nick to %s"
CLOSE_USERNAME_MESSSAGE = "User %s has left from the chat"

TOKEN_HASH_VALID_CHARS = set("qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM1234567890-_+=")
VALIDATE_TOKEN_QUERY = """
        SELECT 
            users.id 
        FROM 
            users 
        LEFT JOIN 
            account_tokens ON (account_tokens.id = users.account)
        WHERE
            users.hash = ?
        AND
            users.closed = 0
        AND
            (users.account IS NULL OR account_tokens.hash = ?)
        LIMIT 1
        """   
VALIDATE_TOKEN_QUERY_INLINE = VALIDATE_TOKEN_QUERY.replace('?', '"%s"')

        
def remove_unsafe_chars(test):
    return str().join(c for c in str(test) if c in TOKEN_HASH_VALID_CHARS)


def insert_inline_token_query(userhash, token):
    return VALIDATE_TOKEN_QUERY_INLINE%(remove_unsafe_chars(userhash), remove_unsafe_chars(token))


def get_database_connection():
    return sqlite3.connect(DATABASE_FILENAME)
    
    
def my_uuid():
    with open("/dev/random", "rb") as f:        
        return sha224(f.read(64*1024)).hexdigest()
    

def get_timestamp():
    return round(time()*1000+0.5)
    
    
def cursor_provider(fun):
    
    def decorator(*args, **kwargs):
        connection = get_database_connection()
        try:
            cursor = connection.cursor()
            result = fun(*args, cursor=cursor, **kwargs)
            connection.commit()
            return result
        except Exception as err:
            connection.rollback()
            raise err
    
    return decorator
    

@cursor_provider    
def init_database(cursor, SCHEMA_FILENAME = "initdb.sql"):
    with open(SCHEMA_FILENAME) as f:
        cursor.executescript(f.read())
        
        
def validate_token(cursor, userhash, token):
    cursor.execute(VALIDATE_TOKEN_QUERY, [userhash, token])    
    user_id, = cursor.fetchone()
    return user_id


def is_token_valid(cursor, userhash, token):
    cursor.execute(f"SELECT COUNT(*) FROM ({VALIDATE_TOKEN_QUERY}) AS tmp", [userhash, token])    
    count, = cursor.fetchone()
    return {"status": "ok", "result": count>0}
        

def get_thread_id(cursor, userhash, token=""):
    cursor.execute(f"""
        SELECT 
            threads.id
        FROM 
            threads
        JOIN 
            users ON (users.thread = threads.id)
        WHERE 
            users.id = ({VALIDATE_TOKEN_QUERY})
        LIMIT 1
        """, [userhash, token])
    thread_id, = cursor.fetchone()
    return thread_id
    
    
def send_message(cursor, userhash, content, systemMessage=False, token=""):
    if len(content) == 0:
        return {"status": "error", "message": "NO_CONTENT"}
    if len(content) > MAX_MESSAGE_LENGTH:
        return {"status": "error", "message": "TO_LONG_CONTENT"}
    sysMsg = 1 if systemMessage else 0
    cursor.execute(f"""
        INSERT INTO messages (user, timestamp, content, system)
        SELECT
            id,
            ?, 
            ?, 
            ? 
        FROM
            users
        WHERE 
        (
                users.id = ({VALIDATE_TOKEN_QUERY}) 
            AND 
                users.closed = 0
        ) OR ?
        LIMIT 1
        """, [get_timestamp(), str(content), sysMsg, userhash, token, sysMsg])
    return {"status": "ok", "message_id": cursor.lastrowid}


def change_username(cursor, userhash, new_username, send_message=True, token=""):
    if new_username is None or len(new_username) == 0 or len(new_username) > MAX_USERNAME_LENGTH:
        new_username = "User-%d"%round(100000*random())    
    user_id = validate_token(cursor, userhash, token)
    execute = lambda: cursor.execute("UPDATE users SET username = ? WHERE id = ?", [new_username, user_id])
    if send_message:
        cursor.execute("SELECT username FROM users WHERE id = ? LIMIT 1", [user_id])
        old_username, = cursor.fetchone()
        execute()
        send_message(cursor, userhash, CHANGES_USERNAME_MESSSAGE%(old_username, new_username))
    else:
        execute()
    
    return {"status": "ok"}
    

def close_user(cursor, userhash, token=""):
    user_id = validate_token(cursor, userhash, token)
    cursor.execute("SELECT username FROM users WHERE id = ? LIMIT 1", [user_id])
    username, = cursor.fetchone()
    result = send_message(cursor, userhash, CLOSE_USERNAME_MESSSAGE%username, True, token)
    cursor.execute("""
        UPDATE 
            users 
        SET 
            closed = 1, 
            username = 
                (
                    WITH RECURSIVE cte AS 
                    (
                        SELECT users.username AS username, 0 AS NO 
                        UNION 
                        SELECT 
                            cte.username, 
                            cte.NO+1 
                        FROM 
                            cte 
                        WHERE 
                            (username || " #" || (NO+1)) IN (SELECT u2.username FROM users AS u2)
                    ) SELECT DISTINCT username || " #" || (MAX(NO)+1) FROM cte
                )
        WHERE 
            id = ?
        """, [user_id])
    cursor.execute("CREATE TEMP TABLE deleting_threads (id INTEGER)")
    cursor.execute("INSERT INTO deleting_threads SELECT id FROM threads WHERE id NOT IN (SELECT DISTINCT thread FROM users WHERE closed = 0)")
    cursor.execute("DELETE FROM messages WHERE user IN (SELECT users.id FROM users JOIN deleting_threads ON (users.thread = deleting_threads.id))")
    cursor.execute("DELETE FROM users WHERE thread IN (SELECT id FROM deleting_threads)")
    cursor.execute("DELETE FROM threads WHERE id IN (SELECT id FROM deleting_threads)")
    cursor.execute("DROP TABLE deleting_threads")
    return result


def reset_user_hash(cursor, userhash, token=""):
    user_id = validate_token(cursor, userhash, token)
    for i in range(256):
        try:
            new_userhash = my_uuid()
            cursor.execute("UPDATE users SET hash = ? WHERE id = ?", [new_userhash, user_id])
            break
        except:
            pass  
    if i == 255:
        return {"status": "error", "message": "Cannot set the hash"}
    return {"status": "ok", "userhash": new_userhash}  


def set_user_to_account(cursor, userhash, token):    
    cursor.execute("UPDATE users SET account = (SELECT id FROM account_tokens WHERE hash = ? LIMIT 1) WHERE users.account IS NULL AND users.hash = ?", [token, userhash])

    
def add_user(cursor, create_on, username: str = None, token=""):
    if isinstance(create_on, int):
        thread_id = create_on
    else:          
        cursor.execute(f"SELECT thread, closed FROM users WHERE id = ({VALIDATE_TOKEN_QUERY}) LIMIT 1", [str(create_on), token])
        thread_id, closed = cursor.fetchone()
        if closed:
            return {"status": "error", "message": "User is closed"}
    for i in range(256):
        try:
            userhash = my_uuid()
            cursor.execute("INSERT INTO users (username, thread, hash) VALUES (?, ?, ?)", [username, thread_id, userhash])
            break
        except:
            pass
    if i == 255:
        return {"status": "error", "message": "Cannot set the hash"}
    return {"status": "ok", "userhash": userhash}


def create_new_thread(cursor, name, first_username, token=""):
    cursor.execute("INSERT INTO threads (name) VALUES (?)", [str(name)])
    thread_id = cursor.lastrowid
    result = add_user(cursor, int(thread_id), first_username)
    if len(token) > 0 and result["status"] == "ok":
        set_user_to_account(cursor, result["userhash"], token)
    return result
    
    
def get_message(cursor, message_id):
    cursor.execute("""
        SELECT 
            messages.id,
            users.username,
            users.hash AS hash,
            messages.timestamp,
            messages.content,
            messages.system
        FROM
            messages
        LEFT JOIN
            users ON (messages.user = users.id)
        WHERE 
            messages.id = ?
        LIMIT 1
        """, [message_id])
    id, username, userhash, timestamp, content, system  = cursor.fetchone()
    return {"id": id, "username": username, "timestamp": timestamp, "content": markdown(content), "system": bool(system)}, userhash
    
def get_messages(cursor, userhash, offset=0, limit=64, excludeList=[], token=""):
    limit = max(min(int(limit), 256), 0)
    offset = max(0, int(offset))
    cursor.execute(f"""
        SELECT 
            messages.id,
            users.username,
            users.hash = init_user.hash AS me,
            messages.timestamp,
            messages.content,
            messages.system
        FROM 
            users AS init_user
        JOIN
            threads ON (init_user.thread = threads.id)
        LEFT JOIN 
            users ON (users.thread = threads.id)
        JOIN
            messages ON (messages.user = users.id)
        WHERE
            init_user.id = ({VALIDATE_TOKEN_QUERY})
        ORDER BY
            messages.id DESC
        LIMIT {int(limit)}
        OFFSET {int(offset)}
        """, [userhash, token])
    
    excludeSet = set(excludeList)
    return {"status": "ok", "messages": [{"id": id, "username": username, "me": bool(me), "timestamp": timestamp, "content": markdown(content), "system": bool(system)} for id, username, me, timestamp, content, system in cursor if id not in excludeSet]}


def get_newest_message_timestamp(cursor, userhash, token):
    cursor.execute(f"""
        SELECT
            MAX(messages.timestamp)
        FROM 
            users AS init_user
        JOIN
            threads ON (init_user.thread = threads.id)
        JOIN 
            users ON (users.thread = threads.id)
        JOIN
            messages ON (messages.user = users.id)
        WHERE
            init_user.id = ({VALIDATE_TOKEN_QUERY})
        """, [userhash, token])
    max_timestamp, = cursor.fetchone()
    return {"status": "ok", "max_timestamp": max_timestamp}
