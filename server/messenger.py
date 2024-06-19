import os
import json
import ecdsa
import base64
import bcrypt
import mysql.connector

from time import time
from time import sleep
from random import random
from hashlib import sha256
from functools import wraps
from threading import Thread
from markdown import markdown
from base64 import b64encode, b85encode


def get_int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


MAX_MESSAGE_LENGTH = 262143
MAX_USERNAME_LENGTH = 255
DELETE_THREAD_TIME = get_int_env('DELETE_THREAD_TIME', 1000 * 3600 * 24 * 365)
DELETE_ACCOUNT_TIME = get_int_env('DELETE_ACCOUNT_TIME', 1000 * 3600 * 24 * 365 * 3)
ACTIVATE_ACCOUNT_TIME = get_int_env('ACTIVATE_ACCOUNT_TIME', 1000 * 60 * 5)
UNSUBSCRIBE_TIMEOUT = get_int_env('UNSUBSCRIBE_TIMEOUT', 1000 * 3600 * 24 * 365)
MAX_SUBSCRIPTIONS_PER_USER = get_int_env('MAX_SUBSCRIPTIONS_PER_USER', 32)

CHANGES_USERNAME_MESSSAGE = "User *%s* has changed its nick to *%s*"
CLOSE_USERNAME_MESSSAGE = "User *%s* has left from the chat"
CREATE_NEW_CHAT_MESSAGE = "User *%s* has created the new chat with name *%s*"
ADD_NEW_USER_MESSAGE = "User *%s* has added the new user *%s*"

DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASS = os.getenv("DATABASE_PASS")
DATABASE_PORT = os.getenv("DATABASE_PORT", "3306")
AES_KEY = os.getenv("AES_KEY", "4ea040749715201f3fb0352b41eea15e5ad969508701eb25401770ff0cefaa97")
RANDOM_DEVICE = os.getenv("RANDOM_DEVICE", "/dev/random")
VAPID_CLAIMS =  {"sub": "mailto:"+os.getenv("mail", "your.email@example.com")}


def generate_vapid_keypair():
    pk = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
    vk = pk.get_verifying_key()
    return {
        'private_key': base64.urlsafe_b64encode(pk.to_string()).decode('utf-8').strip("="),
        'public_key': base64.urlsafe_b64encode(bytearray(b"\x04") + bytearray(vk.to_string())).decode('utf-8').strip("=")
    }


VAPID_KEYS = generate_vapid_keypair()
VAPID_PRIVATE_KEY = VAPID_KEYS['private_key']
VAPID_PUBLIC_KEY = VAPID_KEYS['public_key']


def get_database_connection():
    return mysql.connector.connect(
        host = DATABASE_HOST,
        user = DATABASE_USER,
        password = DATABASE_PASS,
        database = DATABASE_NAME,
        port = DATABASE_PORT)


HASH_VALID_CHARS = set('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~-_+=')
VALIDATE_ACCESS_QUERY = """
        SELECT
            users.id
        FROM
            users
        LEFT JOIN
            account_tokens ON (account_tokens.id = users.account)
        WHERE
            users.hash = %s
        AND
            users.closed = 0
        AND
            (users.account IS NULL OR account_tokens.hash = %s)
        LIMIT 1
        """
        

def my_uuid(use_b85=True):
    hash_fun = b85encode if use_b85 else b64encode
    result = str()
    with open(RANDOM_DEVICE, "rb") as f:
        while len(result) < 64:
            result += hash_fun(sha256(f.read(16*1024)).digest()).decode('utf-8')
    return result[:64]


def random_sleep(_min=0.01, _max=0.1):
    sleep(_min+(_max-_min)*random())


def get_timestamp():
    return round(time()*1000+0.5)


def cursor_provider(fun):

    @wraps(fun)
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


def VALIDATE_ACCESS(cursor, userhash, token):
    cursor.execute(VALIDATE_ACCESS_QUERY, [userhash, token])
    user_id, = cursor.fetchone()
    return user_id


def is_access_valid(cursor, userhash, token):
    cursor.execute(f"SELECT COUNT(*) FROM ({VALIDATE_ACCESS_QUERY}) AS tmp", [userhash, token])
    count, = cursor.fetchone()
    return {"status": "ok", "result": count>0}


def add_user_to_account(cursor, userhash, token):
    result = is_access_valid(cursor, userhash, token)
    if result["result"]:
        set_user_to_account(cursor, userhash, token)
    return result


def get_thread_id(cursor, userhash, token=""):
    cursor.execute(f"""
        SELECT
            users.thread
        FROM
            users
        WHERE
            users.id = ({VALIDATE_ACCESS_QUERY})
        LIMIT 1
        """, [userhash, token])
    thread_id, = cursor.fetchone()
    return thread_id


def thread_exists(cursor, thread_id):
    cursor.execute("SELECT COUNT(*) FROM threads WHERE id = %s", [thread_id])
    count, = cursor.fetchone()
    return count > 0


def send_message(cursor, userhash, content, system_message=False, token=""):
    if len(content) == 0:
        return {"status": "error", "message": "NO_CONTENT"}
    if len(content) > MAX_MESSAGE_LENGTH:
        return {"status": "error", "message": "TO_LONG_CONTENT"}
    sysMsg = 1 if system_message else 0
    cursor.execute(f"""
        INSERT INTO messages (user, timestamp, content, is_system)
        SELECT
            id,
            %s,
            AES_ENCRYPT(COMPRESS(%s), %s),
            %s
        FROM
            users
        WHERE
            users.id = ({VALIDATE_ACCESS_QUERY})
        AND
            users.closed = 0
        LIMIT 1
        """, [get_timestamp(), str(content).encode('utf-8'), AES_KEY, sysMsg, userhash, token])
    return {"status": "ok", "message_id": cursor.lastrowid}


def change_username(cursor, userhash, new_username, send_notification=True, token=""):
    if new_username is None or len(new_username) == 0 or len(new_username) > MAX_USERNAME_LENGTH:
        new_username = "User-%d"%round(100000*random())
    user_id = VALIDATE_ACCESS(cursor, userhash, token)
    execute = lambda: cursor.execute("UPDATE users SET username = %s WHERE id = %s", [new_username, user_id])
    if send_notification:
        cursor.execute("SELECT username FROM users WHERE id = %s LIMIT 1", [user_id])
        old_username, = cursor.fetchone()
        execute()
        send_message(cursor, userhash, CHANGES_USERNAME_MESSSAGE%(old_username, new_username))
    else:
        execute()

    return {"status": "ok"}


def remove_unused_threads(cursor):
    cursor.execute("CREATE TEMPORARY TABLE IF NOT EXISTS deleting_threads (id INTEGER)")
    cursor.execute("DELETE FROM deleting_threads")
    cursor.execute("""
        INSERT INTO deleting_threads
        SELECT
            threads.id
        FROM
            threads
        LEFT JOIN
            users ON (users.thread = threads.id)
        LEFT JOIN
            messages ON (messages.user = users.id)
        GROUP BY
            threads.id
        HAVING
            MAX(messages.timestamp) < UNIX_TIMESTAMP() * 1000 - %s
        OR
            MIN(users.closed) = 1
            """, [DELETE_THREAD_TIME])
    cursor.execute("DELETE FROM messages WHERE user IN (SELECT users.id FROM users JOIN deleting_threads ON (users.thread = deleting_threads.id))")
    cursor.execute("DELETE FROM push_notifications WHERE user IN (SELECT users.id FROM deleting_threads JOIN users ON (users.thread = deleting_threads.id))")
    cursor.execute("DELETE FROM users WHERE thread IN (SELECT id FROM deleting_threads)")
    cursor.execute("DELETE FROM threads WHERE id IN (SELECT id FROM deleting_threads)")
    cursor.execute("DELETE FROM deleting_threads")


def delete_old_tokens_accounts(cursor):
    cursor.execute("CREATE TEMPORARY TABLE IF NOT EXISTS hashes_of_valid_tokens (hash LONGTEXT)")
    cursor.execute("DELETE FROM hashes_of_valid_tokens")
    cursor.execute("INSERT INTO hashes_of_valid_tokens SELECT hash FROM valid_tokens")
    cursor.execute("DELETE FROM tokens WHERE hash NOT IN (SELECT hash FROM hashes_of_valid_tokens)")
    cursor.execute("DELETE FROM tokens WHERE account IN (SELECT id FROM accounts WHERE last_login_timestamp < UNIX_TIMESTAMP() * 1000 - %s)", [DELETE_ACCOUNT_TIME])
    cursor.execute("UPDATE users SET account = NULL AND closed = 1 WHERE account IN (SELECT id FROM accounts WHERE last_login_timestamp < UNIX_TIMESTAMP() * 1000 - %s)", [DELETE_ACCOUNT_TIME])
    cursor.execute("DELETE FROM accounts WHERE last_login_timestamp < UNIX_TIMESTAMP() * 1000 - %s", [DELETE_ACCOUNT_TIME])
    cursor.execute("DELETE FROM hashes_of_valid_tokens")


def delete_old_push_notificaions(cursor):
    cursor.execute("CREATE TEMPORARY TABLE IF NOT EXISTS pn_to_delete (id BIGINT)")
    cursor.execute(f"""
        INSERT INTO
            pn_to_delete
        SELECT
            id
        FROM
            push_notifications
        WHERE
            last_derivered_message_timestamp <= (
                SELECT
                    pn.last_derivered_message_timestamp
                FROM
                    push_notifications AS pn
                WHERE
                    pn.user = push_notifications.user
                ORDER BY
                    pn.last_derivered_message_timestamp
                LIMIT 1
                OFFSET {MAX_SUBSCRIPTIONS_PER_USER}
            )
        OR
            last_derivered_message_timestamp < UNIX_TIMESTAMP() * 1000 - {UNSUBSCRIBE_TIMEOUT}
        """)
    cursor.execute("DELETE FROM push_notifications WHERE id IN (SELECT id FROM pn_to_delete)")
    cursor.execute("DELETE FROM pn_to_delete")


def maintain(cursor):
    remove_unused_threads(cursor)
    delete_old_tokens_accounts(cursor)
    delete_old_push_notificaions(cursor)


def can_create_user(cursor, userhash, token=""):
    cursor.execute(f"SELECT can_create FROM users WHERE id = ({VALIDATE_ACCESS_QUERY})", [userhash, token])
    can_create, = cursor.fetchone()
    return {"status": "ok", "result": bool(can_create)}


def close_user(cursor, userhash, token=""):
    user_id = VALIDATE_ACCESS(cursor, userhash, token)
    cursor.execute("SELECT username FROM users WHERE id = %s LIMIT 1", [user_id])
    username, = cursor.fetchone()
    result = send_message(cursor, userhash, CLOSE_USERNAME_MESSSAGE%username, True, token)
    cursor.execute("""
        UPDATE
            users
        SET
            closed = 1,
            account = NULL,
            username =
                (
                    WITH RECURSIVE cte AS
                    (
                        SELECT
                            CONCAT("[deleted] ", u1.username, " #") AS username,
                            0 AS NO
                        FROM
                            users AS u1
                        WHERE
                            u1.id = %s
                        UNION
                        SELECT
                            cte.username,
                            cte.NO+1
                        FROM
                            cte
                        WHERE
                            CONCAT(username, (NO+1)) IN (SELECT u2.username FROM users AS u2)
                    ) SELECT CONCAT(username, (MAX(NO)+1)) FROM cte GROUP BY cte.username
                )
        WHERE
            id = %s
        """, [user_id, user_id])
    return result


def reset_user_hash(cursor, userhash, token=""):
    user_id = VALIDATE_ACCESS(cursor, userhash, token)
    for i in range(256):
        try:
            new_userhash = my_uuid()
            cursor.execute("UPDATE users SET hash = %s WHERE id = %s", [new_userhash, user_id])
            break
        except mysql.connector.IntegrityError as _:
            pass
    if i == 255:
        return {"status": "error", "message": "Cannot set the hash"}
    return {"status": "ok", "userhash": new_userhash}


def set_user_to_account(cursor, userhash, token):
    cursor.execute("UPDATE users SET account = (SELECT id FROM account_tokens WHERE hash = %s LIMIT 1) WHERE users.account IS NULL AND users.hash = %s", [token, userhash])
    return {"status": "ok"}


def add_user(cursor, create_on, username: str = None, can_create=True, token=""):
    send_notification = False
    creator_username = ""
    thread_id = -1
    if isinstance(create_on, int):
        thread_id = create_on
    else:
        cursor.execute(f"SELECT thread, closed, username, can_create FROM users WHERE id = ({VALIDATE_ACCESS_QUERY}) LIMIT 1", [str(create_on), token])
        thread_id, closed, creator_username, creator_can_create = cursor.fetchone()
        send_notification = True
        if closed:
            return {"status": "error", "message": "User is closed"}
        if not creator_can_create:
            return {"status": "error", "message": "User cannot create a new user"}
    cursor.execute("SELECT COUNT(*) FROM users WHERE thread = %s AND username = %s", [thread_id, username])
    count, = cursor.fetchone()
    if count > 0:
        return {"status": "error", "message": "User already exists"}
    for i in range(256):
        try:
            userhash = my_uuid()
            cursor.execute("INSERT INTO users (username, thread, hash, can_create) VALUES (%s, %s, %s, %s)", [username, thread_id, userhash, int(bool(can_create))])
            break
        except mysql.connector.IntegrityError as _:
            pass
    else:
        return {"status": "error", "message": "Cannot set the hash"}
    result = {"status": "ok", "userhash": userhash}
    if send_notification:
        result.update(send_message(cursor, create_on, ADD_NEW_USER_MESSAGE%(creator_username, username), True, token))
    return result


def create_new_thread(cursor, name, first_username, token=""):
    cursor.execute("INSERT INTO threads (name) VALUES (%s)", [str(name)])
    thread_id = cursor.lastrowid
    result = add_user(cursor, int(thread_id), first_username, True)
    if result["status"] == "ok":
        if len(token) > 0:
            set_user_to_account(cursor, result["userhash"], token)
        result.update(send_message(cursor, result["userhash"], CREATE_NEW_CHAT_MESSAGE%(first_username, name), True, token))
    return result


def get_message(cursor, message_id):
    cursor.execute("""
        SELECT
            messages.id,
            CASE messages.is_system WHEN 1 THEN "SYSTEM" ELSE users.username END,
            CASE messages.is_system WHEN 1 THEN "__SYSTEM_HASH__" ELSE users.hash END AS hash,
            messages.timestamp,
            UNCOMPRESS(AES_DECRYPT(messages.content, %s)),
            messages.is_system
        FROM
            messages
        LEFT JOIN
            users ON (messages.user = users.id)
        WHERE
            messages.id = %s
        LIMIT 1
        """, [AES_KEY, message_id])
    id, username, userhash, timestamp, content, system  = cursor.fetchone()
    return {"id": id, "username": username, "timestamp": timestamp, "content": markdown(content.decode('utf-8')).replace("\n", "<br>"), "system": bool(system)}, userhash


def set_user_read(cursor, userhash, token=""):
    cursor.execute(f"UPDATE users SET last_read_time = %s WHERE id = ({VALIDATE_ACCESS_QUERY})", [get_timestamp(), userhash, token])
    return {"status": "ok"}


def get_messages(cursor, userhash, offset=0, limit=64, id_bookmark=0, id_direction=0, exclude_list=[], token=""):
    id_direction = int(id_direction)
    id_direction = id_direction if abs(id_direction) == 1 else 0
    id_bookmark = int(id_bookmark)
    limit = max(min(int(limit), 256), 0)
    offset = max(0, int(offset))
    exclude_list_str = ", ".join(str(i) if isinstance(i, int) else str(int(i)) for i in exclude_list + ["-1"])
    cursor.execute(f"""
        SELECT *
        FROM
        (
            SELECT
                id,
                sender,
                me,
                timestamp,
                UNCOMPRESS(AES_DECRYPT(content, %s)),
                is_system
            FROM
                messages_view
            WHERE
                init_user_id = ({VALIDATE_ACCESS_QUERY})
            AND
            (
                %s = 0
                OR
                    (id > %s AND %s = 1)
                OR
                    (id < %s AND %s = -1)
            )
            ORDER BY
                id * %s,
                id DESC
            LIMIT {int(limit)}
            OFFSET {int(offset)}
        ) AS subquery
        WHERE
            subquery.id NOT IN ({exclude_list_str})
        """, [AES_KEY, userhash, token, id_direction, id_bookmark, id_direction, id_bookmark, id_direction, id_direction])
    return {"status": "ok", "messages": [{"id": id, "username": username, "me": bool(me), "timestamp": timestamp, "content": markdown(content.decode('utf-8')).replace("\n", "<br>"), "system": bool(system)} for id, username, me, timestamp, content, system in cursor]}


def get_threads_with_token(cursor, token):
    cursor.execute("""
        SELECT
            threads.name,
            users.username AS username,
            users.hash AS hash,
            CAST(SUM(messages_view.timestamp > last_read_time) AS INTEGER) AS unread,
            MAX(messages_view.timestamp) AS last_message_timestamp,
            users.last_read_time AS last_read_time
        FROM
            tokens
        JOIN
            accounts ON (tokens.account = accounts.id)
        JOIN
            users ON (users.account = accounts.id)
        JOIN
            messages_view ON (messages_view.init_user_id = users.id)
        JOIN
            threads ON (users.thread = threads.id)
        WHERE
            tokens.hash = %s
        GROUP BY
            users.id
        ORDER BY
            last_message_timestamp DESC
        """, [token])
    return {"status": "ok", "result": [{"thread_name": thread_name, "username": username, "userhash": userhash, "unread": unread, "last_message_timestamp": last_message_timestamp, "last_read_time": last_read_time} for thread_name, username, userhash, unread, last_message_timestamp, last_read_time in cursor]}


def activity(cursor, token):
    timestamp = get_timestamp()
    cursor.execute("SELECT COUNT(*) FROM valid_tokens WHERE hash = %s", [token])
    count, = cursor.fetchone()
    if count > 0:
        def update_tables(cursor):
            cursor.execute("UPDATE tokens SET last_activity_timestamp = %s WHERE hash = %s", [timestamp, token])
            cursor.execute("UPDATE accounts SET last_login_timestamp = %s WHERE id IN (SELECT account FROM valid_tokens WHERE hash = %s)", [timestamp, token])
        Thread(target=cursor_provider(update_tables)).start()

    return {"status": "ok", "result": count>0}


def change_password(cursor, token, password, new_password):
    cursor.execute("""
        SELECT
            accounts.id AS id,
            accounts.password AS password
        FROM
            tokens
        JOIN
            accounts ON (tokens.account = accounts.id)
        WHERE
            tokens.hash = %s
        LIMIT 1
        """, [token])
    results = cursor.fetchall()
    if len(results) == 0:
        return {"status": "ok", "result": False}
    id, password_hash = results[0]
    if not bcrypt.checkpw(str(password).encode('utf-8'), password_hash.encode('utf-8')):
        return {"status": "ok", "result": False}
    password_hash = bcrypt.hashpw(str(new_password).encode('utf-8'), bcrypt.gensalt(13)).decode('utf-8')
    cursor.execute("UPDATE accounts SET password = %s WHERE id = %s", [password_hash, id])
    return {"status": "ok", "result": True}


def login(cursor, login, password, no_activity_lifespan=3600, max_lifespan=604800):
    random_sleep()
    cursor.execute("SELECT id, password FROM accounts WHERE login = %s LIMIT 1", [str(login)])
    try:
        account_id, password_hash, = cursor.fetchone()
    except TypeError as _:
        return {"status": "ok", "result": False}

    if not bcrypt.checkpw(str(password).encode('utf-8'), password_hash.encode('utf-8')):
        return {"status": "ok", "result": False}

    timestamp = get_timestamp()
    for _ in range(256):
        try:
            token = my_uuid()
            cursor.execute("""
                INSERT INTO tokens
                    (hash, account, created_timestamp, last_activity_timestamp, no_activity_lifespan, max_lifespan)
                VALUES
                    (%s, %s, %s, %s, %s, %s)""",
                [token, account_id, timestamp, timestamp, 1000*int(no_activity_lifespan), 1000*int(max_lifespan)])
            break
        except mysql.connector.IntegrityError as _:
            pass
    cursor.execute("UPDATE accounts SET last_login_timestamp = %s WHERE id = %s", [timestamp, account_id])
    return {"status": "ok", "result": True, "token": token}


def logout(cursor, token=""):
    cursor.execute("DELETE FROM tokens WHERE hash = %s", [token])
    return {"status": "ok"}


def register(cursor, login, password):
    password_hash = bcrypt.hashpw(str(password).encode('utf-8'), bcrypt.gensalt(13)).decode('utf-8')
    delete_old_tokens_accounts(cursor)
    try:
        cursor.execute("INSERT INTO accounts (login, password, last_login_timestamp) VALUES (%s, %s, %s)", [str(login), password_hash, get_timestamp() - DELETE_ACCOUNT_TIME + ACTIVATE_ACCOUNT_TIME])
        return {"status": "ok"}
    except mysql.connector.errors.IntegrityError:
        return {"status": "error"}


def delete_account(cursor, token=""):
    cursor.execute("SELECT account FROM valid_tokens WHERE hash = %s LIMIT 1", [token])
    account_id, = cursor.fetchone()
    cursor.execute("SELECT hash FROM users WHERE account = %s", [account_id])
    for userhash, in cursor:
        close_user(cursor, userhash, token)
    cursor.execute("DELETE FROM tokens WHERE account = %s", [account_id])
    cursor.execute("DELETE FROM accounts WHERE id = %s", [account_id])
    return {"status": "ok"}


def push_subscribe(cursor, userhash, token="", subscription_information=dict()):
    user_id = VALIDATE_ACCESS(cursor, userhash, token)
    hash = my_uuid()
    cursor.execute("""
        INSERT INTO push_notifications
            (user, subscription_information, vapid_private_key, last_derivered_message_timestamp, hash)
            VALUES
            (%s, AES_ENCRYPT(%s, %s), AES_ENCRYPT(%s, %s), %s, %s)
        """, [user_id, json.dumps(subscription_information).encode('utf-8'), AES_KEY, VAPID_PRIVATE_KEY.encode('utf-8'), AES_KEY, get_timestamp(), hash])
    return {"status": "ok", "hash": hash}


def push_unsubscribe(cursor, userhash, token="", subscription_hash=""):
    user_id = VALIDATE_ACCESS(cursor, userhash, token)
    cursor.execute("DELETE FROM push_notifications WHERE user = %s AND (%s = '' OR hash = %s)", [user_id, subscription_hash, subscription_hash])
    return {"status": "ok"}


def push_get_by_thread(cursor, thread_id):
    cursor.execute("""
        SELECT
            pn.id,
            users.id,
            users.hash,
            threads.id,
            AES_DECRYPT(pn.subscription_information, %s),
            AES_DECRYPT(pn.vapid_private_key, %s)
        FROM
            push_notifications AS pn
        JOIN
            users ON (pn.user = users.id)
        JOIN
            threads ON (threads.id = users.thread)
        WHERE
            threads.id = %s
        """, [AES_KEY, AES_KEY, thread_id])
    return {"status": "ok", 'data': [{'pn_id': pnid, 'user_id': uid, 'userhash': hash, 'thread_id': tid, 'subscription_information': json.loads(si.decode('utf-8')), 'vapid_private_key': vpk.decode('utf-8')} for pnid, uid, hash, tid, si, vpk in cursor]}


def push_update_success(cursor, id):
    cursor.execute("UPDATE push_notifications SET last_derivered_message_timestamp = %s WHERE id = %s", [get_timestamp(), id])
