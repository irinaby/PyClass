import docker
from docker.types import Mount
import json
import os
import tempfile

TESTEE = "testee"
CHECKER = "checker"

def parse_output(lines: str) -> dict:
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
    output = []
    for line in lines.splitlines(False):
        if line.startswith("sample: "):
            result["run_samples"] += 1
            result["last_sample"] = int(line[8:])
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
                output.append(line)
    result["output"] = "\n".join(output)
    if result["run_samples"] > 0:
        result["mem_avg"] = result["mem_avg"] / result["run_samples"]
        result["time_avg"] = result["time_avg"] / result["run_samples"]
    return result

def run_mounts(data: dict, mounts: list) -> dict:
    client = docker.from_env()
    kwargs = {
        #"auto_remove": True,
        "mounts": mounts,
        "mem_limit": data["mem_limit"],
        "memswap_limit": 0,
        "pids_limit": -1,
        "tty": False,
        "stdin_open": False,
        "read_only": True,
        "entrypoint": ["bash"],
        "network_disabled": True,
        "working_dir": "/usr/src/"
    }
    container = None
    try:
        container = client.containers.create(data["image_name"], command=["run.sh"], **kwargs)
        print(container.name)
        container.start()

        out = container.logs(
            stdout=True, stderr=True, stream=True, follow=True
        )

        status = container.stats(decode=True, stream=True)
        for stat in status:
            if len(stat["pids_stats"]) == 0:
                container.reload() # обновляет container.attrs
                container_state = container.attrs["State"]
                #print("ExitCode:", container_state["ExitCode"])
                output = b''.join([line for line in out]).decode("utf-8")
                #print(result)
                result = parse_output(output)
                exitCode = container_state["ExitCode"]
                if exitCode == 0:
                    result["result"] = "success"
                elif exitCode == 124:
                    result["result"] = "timeout"
                elif exitCode == 200:
                    result["result"] = "check_error"
                elif exitCode == 224:
                    result["result"] = "check_timeout"
                else:
                    result["result"] = "error"

                if container_state["OOMKilled"] == True:
                    result["result"] = "out_of_memory"
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

def path_join(path: str, filename: str) -> str:
    return os.path.join(path, filename).replace("\\", "/")

def run(data) -> dict:
    mounts = []

    with tempfile.TemporaryDirectory(dir="D:\\Projects\\Docker\\Python\temp") as tmp:
        mounts.append(Mount("/usr/src", tmp, type="bind", read_only=False))

        filename = data["testee_filename"]
        with open(path_join(tmp, filename), "x", newline="\n") as f:
            f.write(data["testee_source"])
            mounts.append(Mount(path_join("/usr/src", filename), path_join(tmp, filename), type="bind", read_only=True))

        filename = data["checker_filename"]
        with open(path_join(tmp, filename), "x", newline="\n") as f:
            f.write(data["checker_source"])
            mounts.append(Mount(path_join("/usr/src", filename), path_join(tmp, filename), type="bind", read_only=True))

        cmd = ["#!/bin/bash"]
        i = 0
        for sample in data["samples"]:
            sample_name = "sample" + f"{i:02}.txt"
            with open(path_join(tmp, sample_name), "x", newline="\n") as f:
                f.write(sample)
                mounts.append(Mount(path_join("/usr/src", sample_name), path_join(tmp, sample_name), type="bind", read_only=True))

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
        with open(path_join(tmp, "run.sh"), "x", newline="\n") as f:
            f.write(s)
            mounts.append(Mount(path_join("/usr/src", "run.sh"), path_join(tmp, "run.sh"), type="bind", read_only=True))
        
        return run_mounts(data, mounts)

def run_python(input: dict) -> dict:
    data = {}
    data["timeout"] = input["timeout"] or 10
    data["image_name"] = "python:latest"
    data["mem_limit"] = input["mem_limit"] or "100m"

    data["testee_filename"] = TESTEE + ".py"
    data["testee_source"] = input["testee"]
    data["testee_cmd"] = "python " + data["testee_filename"]
    data["checker_filename"] = CHECKER + ".py"
    data["checker_source"] = input["checker"]
    data["checker_cmd"] = "python " + data["checker_filename"]
    data["samples"] = input["samples"]

    return run(data)

def test():
    data = {}
    data["testee_filename"] = TESTEE + ".py"
    with open("test_summa_user.py", "r") as f:
        data["testee_source"] = f.read()
    data["testee_cmd"] = "python " + data["testee_filename"]

    data["checker_filename"] = CHECKER + ".py"
    with open("test_summa_check.py", "r") as f:
        data["checker_source"] = f.read()
    data["checker_cmd"] = "python " + data["checker_filename"]

    with open("data.json", "r") as f: 
        data["samples"] = json.load(f)

    data["timeout"] = 2
    data["image_name"] = "python:latest"
    data["mem_limit"] = "100m"

    result = run(data)
    print(result)

try:
    test()
except Exception as e:
    print(e)

