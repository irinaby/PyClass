from time import sleep
from tkinter import EXCEPTION
import docker
from docker.types import Mount
import os
import tempfile
from datetime import datetime
import threading
import traceback
import uuid

import logging

logger = logging.getLogger("starter")
logging.basicConfig()
logger.setLevel(logging.DEBUG)
logger.info("init")

MAX_CONTAINERS = 5
TESTEE = "testee"
CHECKER = "checker"
DOCKER_TEMP = "docker_temp"
STARTER_TEMP = "starter_temp"

STARTING = "starting"
RUNNING = "running"
REQUEST_ERROR = "request_error"
EXCEPTION = "exception"

def exception_str(e: BaseException) -> str:
    tb = traceback.TracebackException.from_exception(e)
    return str(e) + "\n" + "".join(tb.stack.format())

def path_join(path: str, filename: str) -> str:
    return os.path.join(path, filename).replace("\\", "/")

class TemporaryDirectory:
    def __init__(self, data: dict) -> None:
        self.data = data
        data[DOCKER_TEMP] = os.environ["DOCKER_TEMP"] or "/tmp"
        data[STARTER_TEMP] = os.environ["STARTER_TEMP"] or "/tmp"

        self.tmp = tempfile.TemporaryDirectory(dir=data[STARTER_TEMP])
    def __enter__(self):
        path = self.tmp.__enter__()
        temp_name = os.path.basename(path)
        self.data[STARTER_TEMP] = path_join(self.data[STARTER_TEMP], temp_name)
        self.data[DOCKER_TEMP] = path_join(self.data[DOCKER_TEMP], temp_name)
        return None
    def __exit__(self, exc, value, tb):
        self.tmp.__exit__(exc, value, tb)
    
class Runner:
    def __init__(self) -> None:
        self.tasks = {}
        self.lock = threading.Lock()

    def update(self, uid: str, data: dict):
        self.lock.acquire()
        try:
            data["created"] = datetime.now()
            self.tasks[uid] = data
        finally:
            self.lock.release()

    def get(self, uid: str) -> dict:
        self.lock.acquire()
        try:
            return self.tasks.get(uid)
        finally:
            self.lock.release()

    def parse_output(self, lines: list) -> dict:
        #print(lines)
        result = dict(        
            run_samples = 0,
            last_sample = 0,
            output = "",
            time_max = 0,
            time_min = 0,
            time_avg = 0,
            mem_max = 0,
            mem_min = 0,
            mem_avg = 0,
        )
        errors = []
        for line in lines:
            if line.startswith("sample: "):
                result["run_samples"] += 1
                result["last_sample"] = int(line[8:])
                errors = []
            else:
                if line.startswith("mem: "):
                    for p in line.split(";"):
                        if p.startswith("mem: "):
                            mem = int(p[5:])
                            result["mem_max"] = max(result["mem_max"], mem)
                            if result["mem_min"] == 0:
                                result["mem_min"] = mem
                            else:
                                result["mem_min"] = min(result["mem_min"], mem)
                            result["mem_avg"] += mem
                        elif p.startswith("time: "):
                            t = float(p[6:])
                            result["time_max"] = max(result["time_max"], t)
                            if result["time_min"] == 0:
                                result["time_min"] = t
                            else:
                                result["time_min"] = min(result["time_min"], t)
                            result["time_avg"] += t
                else:
                    errors.append(line)
        result["output"] = "\n".join(lines)
        result["errors"] = "\n".join(errors)
        if result["run_samples"] > 0:
            result["mem_avg"] = result["mem_avg"] / result["run_samples"]
            result["time_avg"] = result["time_avg"] / result["run_samples"]
        return result

    def run_container(self, data: dict, mounts: list) -> dict:
        logger.debug(data)
        
        client = docker.from_env()
        kwargs = {
            #"auto_remove": True,
            "mounts": mounts,
            "mem_limit": data["mem_limit"],
            "memswap_limit": 0,
            "pids_limit": -1,
            "tty": False,
            "stdin_open": False,
            #"read_only": True,
            "entrypoint": ["bash"],
            "network_disabled": True,
            "working_dir": "/usr/src"
        }
        container = None
        try:
            container = client.containers.create(data["image_name"], command=["run.sh"], **kwargs)
            logger.info(container.name)
            container.start()

            out = container.logs(
                stdout=True, stderr=True, stream=True, follow=True
            )

            lines = []
            for line in out:
                lines.append(line.decode("utf-8"))
                result = self.parse_output(lines)
                result["result"] = RUNNING
                self.update(data["uid"], result)

            container.reload() # обновляет container.attrs
            container_state = container.attrs["State"]
            #print("ExitCode:", container_state["ExitCode"])
            #print(result)
            result = self.parse_output(lines)
            exitCode = container_state["ExitCode"]
            if exitCode == 0:
                result["result"] = "success"
            elif exitCode == 124:
                result["result"] = "timeout"
            elif exitCode == 200:
                result["result"] = "check_error"
            elif exitCode == 224:
                result["result"] = "check_timeout"
            elif exitCode == 300:
                result["result"] = "build_testee_error"
            elif exitCode == 301:
                result["result"] = "build_checker_error"
            else:
                result["result"] = "error"

            if container_state["OOMKilled"] == True:
                result["result"] = "out_of_memory"

            logger.info("finished: " + data["uid"] + ", " + result["result"])
            self.update(data["uid"], result)
            return result
        finally:
            if not container is None:
                container.reload()
                container_state = container.attrs["State"]
                if container_state["Status"] == "running":
                    container.kill()
                if container_state["Status"] == "created":
                    container.stop()
                container.remove()
        pass

    def prepare_mounts(self, data) -> dict:
        mounts = []

        docker_tmp = data[DOCKER_TEMP]
        starter_tmp = data[STARTER_TEMP]
        mounts.append(Mount("/usr/src", docker_tmp, type="bind", read_only=False))

        filename = data["testee_filename"]
        with open(path_join(starter_tmp, filename), "x", newline="\n") as f:
            f.write(data["testee_source"])
            mounts.append(Mount(path_join("/usr/src", filename), path_join(docker_tmp, filename), type="bind", read_only=True))

        filename = data["checker_filename"]
        with open(path_join(starter_tmp, filename), "x", newline="\n") as f:
            f.write(data["checker_source"])
            mounts.append(Mount(path_join("/usr/src", filename), path_join(docker_tmp, filename), type="bind", read_only=True))

        cmd = data["commands"]
        i = 0
        for sample in data["samples"]:
            sample_name = "sample" + f"{i:02}.txt"
            with open(path_join(starter_tmp, sample_name), "x", newline="\n") as f:
                f.write(sample)
                mounts.append(Mount(path_join("/usr/src", sample_name), path_join(docker_tmp, sample_name), type="bind", read_only=True))

            cmd.append("echo \"sample: " + str(i) + "\"")
            #cmd.append("cp " + sample_name + " input.txt")
            cmd.append("ln -sf " + sample_name + " input.txt")
            cmd.append("cat input.txt | time --format=\"mem: %M;time: %e\" --output=stats.txt -q timeout " + str(data["timeout"]) + " " + data["testee_cmd"] + " >> output.txt")
            cmd.append("retVal=$?")
            cmd.append("cat stats.txt")
            cmd.append("if [ $retVal -ne 0 ]; then")
            cmd.append("  echo \"user error\"")
            cmd.append("  exit $retVal")
            cmd.append("fi")
            #cmd.append("cp " + sample_name + " input.txt")
            cmd.append("timeout " + str(data["timeout"]) + " " + data["checker_cmd"])
            cmd.append("retVal=$?")
            cmd.append("if [ $retVal -eq 124 ]; then")
            cmd.append("  exit 224")
            cmd.append("fi")
            cmd.append("if [ $retVal -ne 0 ]; then")
            cmd.append("  echo \"checker error\"")
            cmd.append("  exit 200")
            cmd.append("fi")
            cmd.append("rm output.txt")
            i += 1

        s = "\n".join(cmd)
        with open(path_join(starter_tmp, "run.sh"), "x", newline="\n") as f:
            f.write(s)
            mounts.append(Mount(path_join("/usr/src", "run.sh"), path_join(docker_tmp, "run.sh"), type="bind", read_only=True))
        
        return self.run_container(data, mounts)

    def init_data(self, input: dict) -> dict:
        data = {}
        data["uid"] = input["uid"]
        data["timeout"] = input.get("timeout", 10)
        data["checker_timeout"] = input.get("checker_timeout", data["timeout"])
        data["mem_limit"] = input.get("mem_limit", "100m")

        data["testee_source"] = input["testee"]
        data["checker_source"] = input["checker"]
        data["samples"] = input["samples"]
        data["commands"] = ["#!/bin/bash"]

        return data

    def run_python(self, input: dict) -> dict:
        data = self.init_data(input)
        data["image_name"] = "python:checker"
        data["testee_filename"] = TESTEE + ".py"
        data["testee_cmd"] = "python " + data["testee_filename"]
        data["checker_filename"] = CHECKER + ".py"
        data["checker_cmd"] = "python " + data["checker_filename"]

        with TemporaryDirectory(data):
            return self.prepare_mounts(data)
        pass

    def run_dotnet(self, input: dict, lang: str, file_ext: str) -> dict:
        data = self.init_data(input)
        data["image_name"] = "dotnet:checker"
        data["testee_filename"] = TESTEE + file_ext
        data["checker_filename"] = CHECKER + file_ext

        with TemporaryDirectory(data):
            cmd = data["commands"]
            testee_prj = TESTEE
            cmd.append("dotnet new console -o " + testee_prj)
            #cmd.append("sleep 1000000")
            cmd.append("cp " + data["testee_filename"] + " " + path_join(testee_prj, "Program" + file_ext))
            cmd.append("dotnet build --no-restore -v q " + testee_prj)
            cmd.append("retVal=$?")
            cmd.append("if [ $retVal -ne 0 ]; then")
            cmd.append("  exit 300")
            cmd.append("fi")
            cmd.append('echo "debug: testee build success"')
            data["testee_cmd"] = "dotnet " + path_join(testee_prj, "bin/Debug/net6.0/" + TESTEE + ".dll")

            checker_prj = CHECKER
            cmd.append("dotnet new console -o " + checker_prj)
            cmd.append("cp " + data["checker_filename"] + " " + path_join(checker_prj, "Program" + file_ext))
            cmd.append("dotnet build --no-restore -v q " + checker_prj)
            cmd.append("retVal=$?")
            cmd.append("if [ $retVal -ne 0 ]; then")
            cmd.append("  exit 301")
            cmd.append("fi")
            cmd.append('echo "debug: checker build success"')
            #cmd.append('sleep 1000000')
            data["checker_cmd"] = "dotnet " + path_join(checker_prj, "bin/Debug/net6.0/" + CHECKER + ".dll")

            return self.prepare_mounts(data)
        pass

    def run_cs(self, input: dict) -> dict:
        return self.run_dotnet(input, "C#", ".cs")
    
    def run_fs(self, input: dict) -> dict:
        return self.run_dotnet(input, "F#", ".fs")

    def run_vb(self, input: dict) -> dict:
        return self.run_dotnet(input, "VB", ".vb")

    def run_safe(self, input: dict):
        try:
            if input["language"] == "python":
                self.run_python(input)
            elif input["language"] == "py":
                self.run_python(input)
            elif input["language"] == "cs":
                self.run_cs(input)
            elif input["language"] == "c#":
                self.run_cs(input)
            elif input["language"] == "f#":
                self.run_fs(input)
            elif input["language"] == "vb":
                self.run_vb(input)
            else:
                self.update(input["uid"], {
                    "result": REQUEST_ERROR,
                    "error": "Unknown language: " + input["language"],
                })
        except Exception as e:
            logger.exception(e)
            self.update(input["uid"], {
                "result": EXCEPTION,
                "error": exception_str(e),
            })

    def run_thread(self, input: dict) -> dict:
        input["result"] = RUNNING
        t = threading.Thread(target=self.run_safe, args=[input])
        t.start()

    def tasks_run(self):
        cnt = 0
        for key in self.tasks:
            task = self.tasks[key]
            if task["result"] == RUNNING:
                cnt += 1
            pass
        pass
        for key in self.tasks:
            task = self.tasks[key]
            if task["result"] == STARTING:
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
            input["uid"] = str(uuid.uuid4())

            input["result"] = STARTING
            input["created"] = datetime.now()
            self.tasks[input["uid"]] = input

            self.tasks_run()
            return input["uid"]
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
                    if (datetime.now() - task["created"]).days < 1:
                        new_tasks[key] = task
                self.tasks = new_tasks

                self.tasks_run()
            finally:
                self.lock.release()
            sleep(1)
        #


runner = Runner()
t = threading.Thread(target=runner.wait)
t.start()

def task_add(input: dict) -> str:
    return runner.add(input)

def task_get(uid: str) -> dict:
    return runner.get(uid)