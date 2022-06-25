from globals import *
from datetime import datetime
import threading

import container
import checker
import dotnet
import python
import gcc

logger = log("task")

class Wrapper(WrapperInterface):
    def __init__(self, options):
        self.lock = threading.Lock()
        self.options = options
        self.created = datetime.now()
        self.status_prefix = ""
        self.status = STARTING
        self.result = {
            STATUS: self.status
        }
        self.statistics = {}
        self.__parse_output = self.parse_run
    
    def select_module(self, options: dict):
        lang = options[LANGUAGE]
        if lang in ["C#", "F#", "VB"]:
            return dotnet
        elif lang in ["py", "python"]:
            return python
        elif lang in ["c"]:
            return gcc
        else:
            raise Exception('Unknown language "' + lang + '"')

    def run_temp(self):
        # testee
        testee_options = self.options[TESTEE]
        module = self.select_module(testee_options)
        logger.debug("-------------------------------------------------")

        # build testee
        self.status_prefix = TESTEE + "_" + BUILD + "_"
        self.status = RUNNING
        logger.debug(self.status_prefix + self.status)
        if module.prepare_build(testee_options, TESTEE):
            self.__parse_output = self.parse_build
            result = container.run(self, testee_options)
            logger.debug(result)
            if result != SUCCESS:
                return

        # run testee samples
        self.status_prefix = TESTEE + "_"
        self.status = RUNNING
        logger.debug("")
        logger.debug(self.status_prefix + self.status)
        module.prepare_run(testee_options)
        checker.prepare_testee(testee_options, self.options[SAMPLES])
        self.__parse_output = self.parse_run
        result = container.run(self, testee_options)
        logger.debug(result)
        if result != SUCCESS:
            return

        # checker
        checker_options = self.options[CHECKER]
        module = self.select_module(checker_options)

        # build checker
        self.status_prefix = CHECKER + "_" + BUILD + "_"
        self.status = RUNNING
        logger.debug("")
        logger.debug(self.status_prefix + self.status)
        if module.prepare_build(checker_options, CHECKER):
            self.__parse_output = self.parse_build
            result = container.run(self, checker_options)
            logger.debug(result)
            if result != SUCCESS:
                return

        # run checker samples
        self.status_prefix = CHECKER + "_"
        self.status = RUNNING
        logger.debug("")
        logger.debug(self.status_prefix + self.status)
        module.prepare_run(checker_options)
        checker.prepare_checker(checker_options, self.options[SAMPLES])
        self.__parse_output = self.parse_check
        result = container.run(self, checker_options)
        logger.debug(result)
        if result != SUCCESS:
            return

    def run(self):
        with TemporaryDirectory(self.options):
            self.options[TESTEE][DOCKER_TEMP] = self.options[DOCKER_TEMP]
            self.options[TESTEE][STARTER_TEMP] = self.options[STARTER_TEMP]
            self.options[CHECKER][DOCKER_TEMP] = self.options[DOCKER_TEMP]
            self.options[CHECKER][STARTER_TEMP] = self.options[STARTER_TEMP]
            self.run_temp()
        logger.debug(self.get())

    def set(self, result: dict, status: str = None):
        self.lock.acquire()
        try:
            self.created = datetime.now()
            self.result = result
            if status:
                self.status = status
        finally:
            self.lock.release()

    def setStatus(self, status: str):
        self.lock.acquire()
        try:
            self.created = datetime.now()
            self.status = status
        finally:
            self.lock.release()

    def get(self):
        self.lock.acquire()
        try:
            self.result[STATUS] = self.status_prefix + self.status
            return self.result
        finally:
            self.lock.release()

    def parse_run(self, lines: list) -> dict:
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
                    pass
                else:
                    if line.startswith("debug: "):
                        pass
                    else:
                        errors.append(line)
                pass # if
            pass # if
        pass # for

        result["output"] = "\n".join(lines).replace("debug: ", "")
        result["errors"] = "\n".join(errors)
        if result["run_samples"] > 0:
            result["mem_avg"] = result["mem_avg"] / result["run_samples"]
            result["time_avg"] = result["time_avg"] / result["run_samples"]

        self.statistics = result
        return result

    def parse_check(self, lines: list) -> dict:
        result = self.statistics
        errors = []
        for line in lines:
            if line.startswith("sample: "):
                result["last_sample"] = int(line[8:])
                errors = []
            else:
                if line.startswith("debug: "):
                    pass
                else:
                    errors.append(line)
            pass # if
        pass # for

        result["output"] = "\n".join(lines).replace("debug: ", "")
        result["errors"] = "\n".join(errors)

        return result

    def parse_build(self, lines: list) -> dict:
        return {
            "output": "\n".join(lines)
        }

    def parse_output(self, lines: list, status: str = None):
        self.set(self.__parse_output(lines), status)
