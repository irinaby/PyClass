import traceback
import os
import logging
import tempfile

LOG_LEVEL = logging.DEBUG

UID = "uid"
MOUNTS = "mounts"
MEM_LIMIT = "mem_limit"
MEMSWAP_LIMIT = "memswap_limit"
READONLY = "read_only"
TIMEOUT = "timeout"
LANGUAGE = "language"
CMD = "cmd"

STATUS = "status"
RESULT = "result"
SOURCE = "source"
TESTEE = "testee"
CHECKER = "checker"
SAMPLES = "samples"
DOCKER_TEMP = "docker_temp"
STARTER_TEMP = "starter_temp"

# Results:
STARTING = "starting"
RUNNING = "running"
REQUEST_ERROR = "request_error"
EXCEPTION = "exception"
BUILD = "build"
CHECKING = "checking"
SUCCESS = "success"

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


class WrapperInterface:
    def set(self, result: dict, status: str = None):
        pass

    def setStatus(self, status: str):
        pass

    def get(self):
        pass

    def parse_output(self, lines: list, status: str):
        pass


def log(name):
    logger = logging.getLogger(name)
    logging.basicConfig()
    logger.setLevel(LOG_LEVEL)
    return logger


def exception_str(e: BaseException) -> str:
    tb = traceback.TracebackException.from_exception(e)
    return str(e) + "\n" + "".join(tb.stack.format())

def path_join(path: str, filename: str) -> str:
    return os.path.join(path, filename).replace("\\", "/")

def cmd_debug(cmd: list, command: str):
    cmd.append('echo "debug: ' + command.replace('"', '\\"') + '"')
    cmd.append(command)

