import os
import math
import json
import cherrypy
import warnings
import messenger
import itertools
import numpy as np

from time import sleep, time
from scipy.io import wavfile
from threading import Thread, Lock
from messenger_logs import log_error
from ws4py.websocket import WebSocket
from ws4py.messaging import Message, BinaryMessage, TextMessage
from web_socket_module import SUBSCRIBTIONS as message_subscribtions

MAX_STREAM_TIME = messenger.get_int_env('MAX_STREAM_TIME', 43200)
AUDIO_BUFFER_LATENCY = messenger.get_int_env('AUDIO_BUFFER_LATENCY', 120) / 1000
AUDIO_SAMPLE_RATE = messenger.get_int_env('AUDIO_SAMPLE_RATE', 16000)
AUDIO_BUF_SIZE = messenger.get_int_env('AUDIO_BUF_SIZE', 16384)
AUDIO_MAX_CONNECTIONS = messenger.get_int_env('AUDIO_MAX_CONNECTIONS', 64)
AUDIO_STREAM_TIMEOUT = messenger.get_int_env('AUDIO_STREAM_TIMEOUT', 5)

MY_PATH = os.path.dirname(os.path.abspath(__file__)) + "/"
LOW_NOTE_FILENAME = MY_PATH + '../static/low.wav'
HIGH_NOTE_FILENAME = MY_PATH + '../static/high.wav'

AUDIO_THREADS = dict()

def load_wave(filename, level=1.0):
    warnings.simplefilter('ignore', wavfile.WavFileWarning)
    samplerate, data = wavfile.read(filename)
    dest_length = round(data.shape[0] / samplerate * AUDIO_SAMPLE_RATE)
    sample_map = np.linspace(0.5, data.shape[0]-0.5, dest_length, dtype=int)
    data = data[sample_map]
    data_min = np.min(data)
    data_max = np.max(data)
    data = (data - data_min) / (data_max - data_min + 1e-6)
    data = (255 * data - 127) * level
    data[data > 127] = 127
    data[data < -127] = -127
    return np.round(data).astype(np.int8)


LOW_NOTE = load_wave(LOW_NOTE_FILENAME, 0.3)
HIGH_NOTE = load_wave(HIGH_NOTE_FILENAME, 0.3)
NOTIFICATION_LENGTH = LOW_NOTE.shape[0] + HIGH_NOTE.shape[0]
ENTER_NOTIFICATION = lambda: itertools.chain(LOW_NOTE, HIGH_NOTE)
LEAVE_NOTIFICATION = lambda: itertools.chain(HIGH_NOTE, LOW_NOTE)

COMPRESSIONS_MAPS = np.array(tuple([[1] * AUDIO_BUF_SIZE] + [[1 if j % i else 0 for j in range(AUDIO_BUF_SIZE)] for i in np.unique(np.logspace(2, 0, 64, dtype=int))[::-1]]), dtype=np.uint8)
COMPRESSIONS_SIZES = np.array(tuple(tuple(itertools.chain([0], itertools.accumulate(cmap))) for cmap in COMPRESSIONS_MAPS.astype(np.int32)), dtype=np.uint32)

class AudioThread(Thread):

    def __init__(self, first_connection, thread_id):
        super().__init__()
        self.daemon = True
        self.connections = {first_connection}
        self.last_send_time = time()
        self.true_latency = AUDIO_BUFFER_LATENCY
        self.thread_id = thread_id
        AUDIO_THREADS[thread_id] = self
        self.start()


    def send_update_user_list(self, cursor):
        message_ws = message_subscribtions[self.thread_id]
        if len(message_ws) == 0: return
        user_list = [item["username"] for item in messenger.get_users_by_list(cursor, list(set(ws.userhash for ws in AUDIO_THREADS[self.thread_id].connections)))]
        for ws in message_ws:
            txt_msg = TextMessage(json.dumps({"action": "update_voice_chat_list", "user_list": user_list}))
            Thread(target=lambda ws=ws, msg=txt_msg: ws.send(msg)).start()


    def clean_old_connections(self):
        current_time = time()
        for connection in list(self.connections):
            if connection.connectTime < current_time - MAX_STREAM_TIME:
                connection.close()


    def run(self):
        cherrypy.log('Audio thread started: %d'%self.thread_id)
        while len(self.connections):
            connections = list(self.connections)
            try:
                sleep(AUDIO_BUFFER_LATENCY)
                current_time = time()
                dt = current_time - self.last_send_time
                self.last_send_time = current_time
                self.true_latency = dt
                send_size = min(round(dt * AUDIO_SAMPLE_RATE), AUDIO_BUF_SIZE)

                buffer = np.zeros([len(connections), send_size], dtype=np.int32)
                for i, connection in enumerate(connections):
                    connection_buffer = connection.get_buffer_to_send(send_size)
                    if connection_buffer is not None:
                        buffer[i] = connection_buffer

                if not buffer.any():
                    continue
                buffer = np.sum(buffer, axis=0) - buffer
                buffer.clip(-127, 127, out=buffer)
                buffer = buffer.astype(np.int8, copy=False)
                for i, connection in enumerate(connections):
                    if len(connection.buffers_to_send) < 5 and np.sum(np.abs(buffer[i])) != 0:                        
                        connection.buffers_to_send.append(buffer[i].tobytes())
            
            except (KeyboardInterrupt, SystemExit):
                for connection in list(self.connections):
                    connection.close()
                break
            except Exception as err:
                log_error(err)
        
        cherrypy.log('Audio thread stopped: %d'%self.thread_id)
        if self.thread_id in AUDIO_THREADS: AUDIO_THREADS.pop(self.thread_id)


class AudioStreamWebSocketHandler(WebSocket):

    def __init__(self, sock, protocols=None, extensions=None, environ=None, heartbeat_freq=None):
        super().__init__(sock, protocols, extensions, environ, heartbeat_freq)
        self.userhash = ""
        self.token = ""
        self.thread_id = 0
        self.lock = Lock()
        self.recv_buffers = [ENTER_NOTIFICATION()]
        self.buffer_length = NOTIFICATION_LENGTH
        self.is_closed = False
        self.buffers_to_send = []
        self.connectTime = time()
        self.thread = Thread(target=self.sending_thread)
        self.thread.start()
        Thread(target=self.timeout_thread).start()


    def timeout_thread(self):
        sleep(AUDIO_STREAM_TIMEOUT)
        if self.thread_id == 0:
            self.close()


    def sending_thread(self):
        while not self.is_closed:
            if len(self.buffers_to_send) == 0:
                sleep(AUDIO_BUFFER_LATENCY)
            else:
                try:
                    buf = self.buffers_to_send.pop(0)
                    self.send(buf, binary=True)        
                except (KeyboardInterrupt, SystemExit):
                    break
                except (AttributeError, TimeoutError):
                    self.close()
                    break
                except BrokenPipeError:
                    AUDIO_THREADS[self.thread_id].connections = set()
                    break
                except Exception as err:
                    log_error(err)


    def received_message(self, message: Message):
        try:
            data = message.data
            if data[0] == ord('{'):
                content = json.loads(message.data.decode(message.encoding))
                action = content.get('action', '')
                if action == 'subscribe' and self.thread_id == 0:
                    self.userhash = content.get('userhash', '')
                    self.token = content.get('token', '')
                    connection = messenger.get_database_connection()
                    cursor = connection.cursor()
                    self.thread_id = messenger.get_thread_id(cursor, self.userhash, self.token)                    
                    if self.thread_id is None:
                        self.close()
                        return
                    if self.thread_id not in AUDIO_THREADS:
                        AudioThread(self, self.thread_id)
                    elif len(AUDIO_THREADS[self.thread_id].connections) >= AUDIO_MAX_CONNECTIONS:
                        self.close()
                    else:
                        AUDIO_THREADS[self.thread_id].connections.add(self)
                    self.send(TextMessage(json.dumps({"sample_rate": AUDIO_SAMPLE_RATE})))
                    AUDIO_THREADS[self.thread_id].send_update_user_list(cursor)

            elif self.thread_id:    
                dest_size = AUDIO_SAMPLE_RATE * AUDIO_THREADS[self.thread_id].true_latency
                with self.lock:
                    add_size = min(AUDIO_BUF_SIZE-self.buffer_length, len(data))
                    compression_index = max(0, int(math.log((1+self.buffer_length) / dest_size, 1.618)))
                    
                    if add_size <= 0 or compression_index >= len(COMPRESSIONS_MAPS):
                        return                    
                    if add_size < len(data):
                        data = itertools.islice(data, add_size)
                    if compression_index > 0:
                        data = itertools.compress(data, COMPRESSIONS_MAPS[compression_index])
                        add_size = COMPRESSIONS_SIZES[compression_index][add_size]

                    self.recv_buffers.append(data)
                    self.buffer_length += add_size
                                       

        except Exception as err:
            log_error(err)


    def get_buffer_to_send(self, send_size):
        with self.lock:
            if send_size > self.buffer_length:
                return None
            self.buffer_length -= send_size
            buffer_iter = itertools.chain.from_iterable(self.recv_buffers) if len(self.recv_buffers) > 1 else self.recv_buffers[0]
            self.recv_buffers = [buffer_iter]
            return np.fromiter(buffer_iter, count=send_size, dtype=np.uint8).astype(np.int8, copy=False)        
        

    def closed(self, code, reason=""):
        cherrypy.log('Audio connection %s closed'%self.userhash[:8])
        self.is_closed = True
        with self.lock:
            self.buffer_length += NOTIFICATION_LENGTH
            self.recv_buffers.append(LEAVE_NOTIFICATION())
        sleep(2 * self.buffer_length / AUDIO_SAMPLE_RATE)
        my_thread = AUDIO_THREADS[self.thread_id]
        if my_thread is not None:
            my_thread.connections.discard(self)
        connection = messenger.get_database_connection()
        my_thread.send_update_user_list(connection.cursor())


def clean_old_audio_connections():
    for thread in list(AUDIO_THREADS.values()):
        thread.clean_old_connections()
