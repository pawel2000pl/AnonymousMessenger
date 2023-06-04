from cherrypy.process.plugins import SimplePlugin

from threading import Thread
from time import sleep


class BrokenTask(Exception):
    pass


class Task(SimplePlugin):
    
    
    def __init__(self, bus, target, period=600):
        super().__init__(bus)
        self.target = target
        self.period = max(1e-16, period)
        self.broken = False
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
            while True:
                self.target()
                self.sleep(self.period)
        except BrokenTask:
            pass
        
        
    def stop(self):
        self.broken = True
        self.thread.join()
            
