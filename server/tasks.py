from cherrypy.process.plugins import SimplePlugin

from threading import Thread
from time import sleep


class BrokenTask(Exception):
    pass


class Task(SimplePlugin):
    
    
    def __init__(self, bus, target, period=600, init_delay=0, repeat_on_close=False, before_close=lambda: None):
        super().__init__(bus)
        self.target = target
        self.period = max(1e-16, period)
        self.broken = False
        self.init_delay = init_delay
        self.repeat_on_close = repeat_on_close
        self.before_close = before_close
        self.thread = Thread(target=self.work)
        
        
    def start(self):
        self.thread.start()
        
        
    def sleep(self, time):
        LOOP_PERIOD = 0.1
        while time > 0:
            sleep(min(LOOP_PERIOD, time))
            time -= LOOP_PERIOD
            if self.broken:
                raise BrokenTask()
            
            
    def work(self):      
        try:  
            self.sleep(self.init_delay)
            while True:
                self.target()
                self.sleep(self.period)
        except BrokenTask:
            pass
        self.before_close()
        if self.repeat_on_close:
            self.target()
        
        
    def stop(self):
        self.broken = True
        self.thread.join()
            
