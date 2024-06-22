import os
import json
import cherrypy
import messenger
import numpy as np

from time import sleep, time
from scipy.io import wavfile
from threading import Thread, Lock
from ws4py.websocket import WebSocket
from ws4py.messaging import Message, BinaryMessage, TextMessage

MAX_STREAM_TIME = messenger.get_int_env('MAX_STREAM_TIME', 43200)
AUDIO_BUFFER_LATENCY = messenger.get_int_env('AUDIO_BUFFER_LATENCY', 120) / 1000
AUDIO_SAMPLE_RATE = messenger.get_int_env('AUDIO_SAMPLE_RATE', 16000)
AUDIO_BUF_SIZE = messenger.get_int_env('AUDIO_BUF_SIZE', 16384)
AUDIO_MAX_CONNECTIONS = messenger.get_int_env('AUDIO_MAX_CONNECTIONS', 64)

MY_PATH = os.path.dirname(os.path.abspath(__file__)) + "/"
LOW_NOTE_FILENAME = MY_PATH + '../static/low.wav'
HIGH_NOTE_FILENAME = MY_PATH + '../static/high.wav'

AUDIO_THREADS = dict()

def load_wave(filename, level=1.0):
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
    return list(np.round(data))

LOW_NOTE = load_wave(LOW_NOTE_FILENAME, 0.3)
HIGH_NOTE = load_wave(HIGH_NOTE_FILENAME, 0.3)
ENTER_NOTIFICATION = LOW_NOTE + HIGH_NOTE
LEAVE_NOTIFICATION = HIGH_NOTE + LOW_NOTE

class AudioThread(Thread):

    def __init__(self, first_connection, thread_id):
        super().__init__()
        self.connections = {first_connection}
        self.last_send_time = time()
        self.true_latency = AUDIO_BUFFER_LATENCY
        self.thread_id = thread_id
        AUDIO_THREADS[thread_id] = self
        self.start()


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
                    buffer[i] = connection.get_buffer_to_send(send_size)

                if np.sum(np.abs(buffer)) == 0:
                    continue
                buffer = np.sum(buffer, axis=0) - buffer
                buffer[buffer > 127] = 127
                buffer[buffer < -127] = -127
                buffer[buffer[:, 0] == ord('{'), 0] = ord('{')-1
                buffer = buffer.astype(np.int8)
                for i, connection in enumerate(connections):
                    if len(connection.buffers_to_send) < 5 and np.sum(np.abs(buffer[i])) != 0:                        
                        connection.buffers_to_send.append(buffer[i].tobytes())
            
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
        self.my_thread = None
        self.lock = Lock()
        self.buffer = ENTER_NOTIFICATION.copy()
        self.is_closed = False
        self.buffers_to_send = []
        self.connectTime = time()
        self.thread = Thread(target=self.sending_thread)
        self.thread.start()
        Thread(target=self.timeout_thread).start()


    def timeout_thread(self):
        sleep(15)
        if self.my_thread is None:
            self.close()


    def sending_thread(self):
        while not self.is_closed:
            if len(self.buffers_to_send) == 0:
                sleep(AUDIO_BUFFER_LATENCY)
            else:
                try:
                    buf = self.buffers_to_send.pop(0)
                    self.send(buf, binary=True)                                           
                except (AttributeError, TimeoutError): # raised when connection is already closed
                    self.close()
                    break
                except BrokenPipeError: # raised when connections are closed but because of SIGTERM
                    self.my_thread.connections = set()
                    break
                except Exception as err:
                    log_error(err)


    def received_message(self, message: Message):
        try:
            data = message.data
            connection = messenger.get_database_connection()
            cursor = connection.cursor()

            if data[0] == ord('{'):
                content = json.loads(message.data.decode(message.encoding))
                action = content.get('action', '')
                if action == 'subscribe' and self.my_thread is None:
                    self.userhash = content.get('userhash', '')
                    self.token = content.get('token', '')
                    self.thread_id = messenger.get_thread_id(cursor, self.userhash, self.token)                    
                    if self.thread_id is None:
                        self.close()
                        return
                    if self.thread_id not in AUDIO_THREADS:
                        AUDIO_THREADS[self.thread_id] = AudioThread(self, self.thread_id)
                    self.my_thread = AUDIO_THREADS[self.thread_id]
                    if len(self.my_thread.connections) >= AUDIO_MAX_CONNECTIONS:
                        self.close()
                    else:
                        self.my_thread.connections.add(self)
                        self.send(TextMessage(json.dumps({"sample_rate": AUDIO_SAMPLE_RATE})))
            elif self.my_thread is not None:    
                with self.lock:
                    if len(self.buffer) > 1.618 * AUDIO_SAMPLE_RATE * self.my_thread.true_latency:
                        self.buffer.extend(value for i, value in enumerate(data[:AUDIO_BUF_SIZE-len(self.buffer)]) if i & 15)
                    else:
                        self.buffer.extend(data[:AUDIO_BUF_SIZE-len(self.buffer)])

        except Exception as err:
            log_error(err)


    def get_buffer_to_send(self, send_size):
        if send_size > len(self.buffer):
            return 0
        with self.lock:
            send_buffer = np.array(self.buffer[:send_size], dtype=np.uint8).astype(np.int8)
            self.buffer = self.buffer[send_size:]
        return send_buffer
        

    def closed(self, code, reason=""):
        cherrypy.log('Audio connection %s closed'%self.userhash[:8])
        self.buffer = LEAVE_NOTIFICATION.copy()
        sleep(2 * len(self.buffer) / AUDIO_SAMPLE_RATE)
        if self.my_thread is not None:
            self.my_thread.connections.remove(self)
        self.is_closed = True


def clean_old_audio_connections():
    for thread in list(AUDIO_THREADS.values()):
        thread.clean_old_connections()
