from data_wrapper import Wrapper
from globals import *
from time import sleep
import os
from datetime import datetime
import threading
import uuid

logger = log("starter")
logger.info("init")

MAX_CONTAINERS = int(os.environ.get("MAX_CONTAINERS", "4"))

class Runner:
    def __init__(self) -> None:
        self.tasks = {}
        self.lock = threading.Lock()

    def get(self, uid: str) -> dict:
        self.lock.acquire()
        try:
            return self.tasks.get(uid)
        finally:
            self.lock.release()

    def run_safe(self, task: Wrapper):
        try:
            task.run()
        except Exception as e:
            logger.exception(e)
            task.set({
                "error": exception_str(e)
            }, EXCEPTION)

    def run_thread(self, task: Wrapper):
        task.status = RUNNING
        t = threading.Thread(target=self.run_safe, args=[task])
        t.start()

    def tasks_run(self):
        cnt = 0
        for key in self.tasks:
            task = self.tasks[key]
            if task.status == RUNNING:
                cnt += 1
            pass
        pass
        for key in self.tasks:
            task = self.tasks[key]
            if task.status == STARTING:
                if cnt < MAX_CONTAINERS:
                    self.run_thread(task)
                    cnt += 1
                else:
                    break
            pass
        pass

    def add(self, input: dict):
        self.lock.acquire()
        try:
            uid = str(uuid.uuid4())

            self.tasks[uid] = Wrapper(input)

            self.tasks_run()
            return uid
        finally:
            self.lock.release()

    def wait(self):
        while True:
            self.lock.acquire()
            try:
                # clear old tasks
                new_tasks = {}
                for key in self.tasks:
                    task = self.tasks[key]
                    if (datetime.now() - task.created).days < 1:
                        new_tasks[key] = task
                self.tasks = new_tasks

                self.tasks_run()
            finally:
                self.lock.release()
            sleep(1)
        pass


runner = Runner()
t = threading.Thread(target=runner.wait)
t.start()

def task_add(input: dict) -> str:
    return runner.add(input)

def task_get(uid: str) -> dict:
    return runner.get(uid)