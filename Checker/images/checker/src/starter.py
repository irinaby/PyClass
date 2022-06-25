from sre_constants import SUCCESS
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
LANGUAGE = "language"
RESULT = "result"
UID = "uid"
MEM_LIMIT = "mem_limit"
MOUNTS = "mounts"
TESTEE_CMD = "testee_cmd"
CHECKER_CMD = "checker_cmd"
TESTEE_SOURCE = "testee_source"
CHECKER_SOURCE = "checker_source"
READONLY = "read_only"

TESTEE = "testee"
CHECKER = "checker"
DOCKER_TEMP = "docker_temp"
STARTER_TEMP = "starter_temp"

# Results:
STARTING = "starting"
RUNNING = "running"
REQUEST_ERROR = "request_error"
EXCEPTION = "exception"
SUCCESS = "success"



def exception_str(e: BaseException) -> str:
    tb = traceback.TracebackException.from_exception(e)
    return str(e) + "\n" + "".join(tb.stack.format())

def path_join(path: str, filename: str) -> str:
    return os.path.join(path, filename).replace("\\", "/")

def cmd_debug(cmd: list, command: str):
    cmd.append('echo "debug: ' + command.replace('"', '\\"') + '"')
    cmd.append(command)

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

    def parse_check(self, lines: list) -> dict:
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

    def parse_build(self, lines: list) -> dict:
        return {
            "output": "\n".join(lines)
        }

    def run_container(self, data: dict, parse_output, running_result: str) -> dict:
        mounts = data.get(MOUNTS, [])
        mem_limit = data.get(MEM_LIMIT) or None
        memswap_limit = data.get("memswap_limit") or None
        read_only = data.get(READONLY, False)

        client = docker.from_env()
        kwargs = {
            #"auto_remove": True,
            MOUNTS: mounts,
            MEM_LIMIT: mem_limit,
            "memswap_limit": memswap_limit,
            "pids_limit": -1,
            "tty": False,
            "stdin_open": False,
            READONLY: read_only,
            "entrypoint": ["bash"],
            "network_disabled": True,
            "working_dir": "/usr/src"
        }
        container = None
        try:
            container = client.containers.create(data["image_name"], command=data["command"], **kwargs)
            logger.info("image: " + data["image_name"] + ", container: " + container.name)
            container.start()

            out = container.logs(
                stdout=True, stderr=True, stream=True, follow=True
            )

            lines = []
            for line in out:
                logger.debug(line.decode("utf-8").rstrip())
                lines.append(line.decode("utf-8"))
                result = parse_output(lines)
                result[RESULT] = running_result
                self.update(data[UID], result)

            container.reload() # обновляет container.attrs
            container_state = container.attrs["State"]
            result = parse_output(lines)
            if container_state["OOMKilled"] == True:
                result[RESULT] = "out_of_memory"
            else:
                exitCode = container_state["ExitCode"]

                if exitCode == 0:
                    result[RESULT] = SUCCESS
                elif exitCode == 124:
                    result[RESULT] = "timeout"
                elif exitCode == 200:
                    result[RESULT] = "check_error"
                elif exitCode == 224:
                    result[RESULT] = "check_timeout"
                elif exitCode == 300:
                    result[RESULT] = "build_testee_error"
                elif exitCode == 301:
                    result[RESULT] = "build_checker_error"
                else:
                    result[RESULT] = "error"

            self.update(data[UID], result)
            return result[RESULT]
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

    def run_check(self, data) -> dict:
        data[MOUNTS] = mounts = data.get(MOUNTS, [])

        docker_tmp = data[DOCKER_TEMP]
        starter_tmp = data[STARTER_TEMP]
        wrk_tmp = path_join(starter_tmp, "wrk")
        os.makedirs(wrk_tmp)
        mounts.append(Mount("/usr/src", wrk_tmp, type="bind", read_only=False))

        cmd = ["#!/bin/bash"]
        data["commands"] = cmd
        i = 0
        for sample in data["samples"]:
            sample_name = "sample" + f"{i:02}.txt"
            with open(path_join(starter_tmp, sample_name), "x", newline="\n") as f:
                f.write(sample)
                mounts.append(Mount(path_join("/usr/src", sample_name), path_join(docker_tmp, sample_name), type="bind", read_only=True))

            cmd.append("echo \"sample: " + str(i) + "\"")
            cmd_debug(cmd, "ln -sf " + sample_name + " input.txt")
            cmd_debug(cmd, "cat input.txt | time --format=\"mem: %M;time: %e\" --output=stats.txt -q timeout " + str(data["timeout"]) + " " + data[TESTEE_CMD] + " >> output.txt")
            cmd.append("retVal=$?")
            cmd.append("cat stats.txt")
            cmd.append("if [ $retVal -ne 0 ]; then")
            cmd.append("  echo \"user error\"")
            cmd.append("  exit $retVal")
            cmd.append("fi")
            cmd_debug(cmd, "timeout " + str(data["checker_timeout"]) + " " + data[CHECKER_CMD])
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
        command_filename = "check.sh"
        with open(path_join(starter_tmp, command_filename), "x", newline="\n") as f:
            f.write(s)
            mounts.append(Mount(path_join("/usr/src", command_filename), path_join(docker_tmp, command_filename), type="bind", read_only=True))
        data["command"] = command_filename
        data[READONLY] = True
        return self.run_container(data, self.parse_check, RUNNING)
        
    def init_data(self, input: dict) -> dict:
        data = {}
        data[UID] = input[UID]
        data["timeout"] = input.get("timeout", 10)
        data["checker_timeout"] = input.get("checker_timeout", data["timeout"])
        data[MEM_LIMIT] = input.get(MEM_LIMIT, "100m")

        data[TESTEE_SOURCE] = input["testee"]
        data[CHECKER_SOURCE] = input["checker"]
        data["samples"] = input["samples"]
        data["commands"] = ["#!/bin/bash"]

        return data

    def run_python(self, input: dict) -> dict:
        data = self.init_data(input)
        data["image_name"] = "python:checker"

        with TemporaryDirectory(data):
            docker_tmp = data[DOCKER_TEMP]
            starter_tmp = data[STARTER_TEMP]

            data[MOUNTS] = mounts = []

            filename = TESTEE + ".py"
            with open(path_join(starter_tmp, filename), "x", newline="\n") as f:
                f.write(data[TESTEE_SOURCE])
                mounts.append(Mount(path_join("/usr/src", filename), path_join(docker_tmp, filename), type="bind", read_only=True))
                data[TESTEE_CMD] = "python " + filename

            filename = CHECKER + ".py"
            with open(path_join(starter_tmp, filename), "x", newline="\n") as f:
                f.write(data[CHECKER_SOURCE])
                mounts.append(Mount(path_join("/usr/src", filename), path_join(docker_tmp, filename), type="bind", read_only=True))
                data[CHECKER_CMD] = "python " + filename

            return self.run_check(data)
        pass

    def build_dotnet(self, data: dict, lang, file_ext: str) -> dict:
        data["image_name"] = "dotnet:builder"

        data[MOUNTS] = mounts = []

        cmd = ["#!/bin/bash"]
        data["commands"] = cmd

        docker_tmp = data[DOCKER_TEMP]
        starter_tmp = data[STARTER_TEMP]
        mounts.append(Mount("/usr/src", docker_tmp, type="bind", read_only=False))

        testee_filename = TESTEE + file_ext
        with open(path_join(starter_tmp, testee_filename), "x", newline="\n") as f:
            f.write(data[TESTEE_SOURCE])

        checker_filename = CHECKER + file_ext
        with open(path_join(starter_tmp, checker_filename), "x", newline="\n") as f:
            f.write(data[CHECKER_SOURCE])

        testee_prj = TESTEE
        cmd_debug(cmd, "dotnet new console -o " + testee_prj)
        cmd_debug(cmd, "cp " + testee_filename + " " + path_join(testee_prj, "Program" + file_ext))
        cmd_debug(cmd, "dotnet build --configuration Release --no-restore -v q " + testee_prj)
        cmd.append("retVal=$?")
        cmd.append("if [ $retVal -ne 0 ]; then")
        cmd.append("  exit 300")
        cmd.append("fi")
        cmd.append('echo "debug: testee build success"')
        data["testee_bin"] = path_join(testee_prj, "bin/Release/net6.0")

        checker_prj = CHECKER
        cmd_debug(cmd, "dotnet new console -o " + checker_prj)
        cmd_debug(cmd, "cp " + checker_filename + " " + path_join(checker_prj, "Program" + file_ext))
        cmd_debug(cmd, "dotnet build --configuration Release --no-restore -v q " + checker_prj)
        cmd.append("retVal=$?")
        cmd.append("if [ $retVal -ne 0 ]; then")
        cmd.append("  exit 301")
        cmd.append("fi")
        cmd.append('echo "debug: checker build success"')
        data["checker_bin"] = path_join(checker_prj, "bin/Release/net6.0")

        s = "\n".join(cmd)
        command_filename = "build.sh"
        with open(path_join(starter_tmp, command_filename), "x", newline="\n") as f:
            f.write(s)
        data["command"] = command_filename

        return self.run_container(data, self.parse_build, "build")

    def run_dotnet(self, input: dict, lang: str, file_ext: str):
        data = self.init_data(input)

        with TemporaryDirectory(data):
            data[MEM_LIMIT] = None
            result = self.build_dotnet(data, lang, file_ext)
            logger.debug(result)
            if result == SUCCESS:
                data["image_name"] = "dotnet:runtime"
                data[MEM_LIMIT] = input.get(MEM_LIMIT, "100m")
                docker_tmp = data[DOCKER_TEMP]
                data[MOUNTS] = mounts = []
                mounts.append(Mount(path_join("/usr/src", TESTEE), path_join(docker_tmp, data["testee_bin"]), type="bind", read_only=True))
                data[TESTEE_CMD] = "dotnet " + path_join(TESTEE, TESTEE + ".dll")
                mounts.append(Mount(path_join("/usr/src", CHECKER), path_join(docker_tmp, data["checker_bin"]), type="bind", read_only=True))
                data[CHECKER_CMD] = "dotnet " + path_join(CHECKER, CHECKER + ".dll")
                result = self.run_check(data)
                logger.debug(result)
        pass

    def run_cs(self, input: dict):
        self.run_dotnet(input, "C#", ".cs")
    
    def run_fs(self, input: dict):
        self.run_dotnet(input, "F#", ".fs")

    def run_vb(self, input: dict) -> dict:
        self.run_dotnet(input, "VB", ".vb")

    def run_safe(self, input: dict):
        try:
            if input[LANGUAGE] == "python":
                self.run_python(input)
            elif input[LANGUAGE] == "py":
                self.run_python(input)
            elif input[LANGUAGE] == "cs":
                self.run_cs(input)
            elif input[LANGUAGE] == "c#":
                self.run_cs(input)
            elif input[LANGUAGE] == "f#":
                self.run_fs(input)
            elif input[LANGUAGE] == "vb":
                self.run_vb(input)
            else:
                self.update(input[UID], {
                    RESULT: REQUEST_ERROR,
                    "error": "Unknown language: " + input[LANGUAGE],
                })
        except Exception as e:
            logger.exception(e)
            self.update(input[UID], {
                RESULT: EXCEPTION,
                "error": exception_str(e),
            })

    def run_thread(self, input: dict):
        input[RESULT] = RUNNING
        t = threading.Thread(target=self.run_safe, args=[input])
        t.start()

    def tasks_run(self):
        cnt = 0
        for key in self.tasks:
            task = self.tasks[key]
            if task[RESULT] == RUNNING:
                cnt += 1
            pass
        pass
        for key in self.tasks:
            task = self.tasks[key]
            if task[RESULT] == STARTING:
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
            input[UID] = str(uuid.uuid4())

            input[RESULT] = STARTING
            input["created"] = datetime.now()
            self.tasks[input[UID]] = input

            self.tasks_run()
            return input[UID]
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