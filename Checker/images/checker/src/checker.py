from globals import *
from docker.types import Mount

def prepare_testee(options: dict, samples: dict) -> str:
    options[MOUNTS] = mounts = options.get(MOUNTS, [])

    docker_tmp = options[DOCKER_TEMP]
    starter_tmp = options[STARTER_TEMP]
    starter_wrk_tmp = path_join(starter_tmp, "wrk")
    os.makedirs(starter_wrk_tmp)
    docker_wrk_tmp = path_join(docker_tmp, "wrk")

    mounts.append(Mount("/usr/src", starter_wrk_tmp, type="bind", read_only=False))

    cmd = ["#!/bin/bash"]
    options["commands"] = cmd
    i = 1
    for sample in samples:
        input_name = "input" + f"{i:03}.txt"
        with open(path_join(starter_wrk_tmp, input_name), "x", newline="\n") as f:
            f.write(sample)
            mounts.append(Mount(path_join("/usr/src", input_name), path_join(docker_wrk_tmp, input_name), type="bind", read_only=True))

        cmd.append("echo \"sample: " + str(i) + "\"")
        cmd_debug(cmd, "ln -sf " + input_name + " input.txt")
        cmd_debug(cmd, "cat input.txt | time --format=\"mem: %M;time: %e\" --output=stats.txt -q timeout " + str(options[TIMEOUT]) + " " + options[CMD] + " >> output.txt")
        cmd.append("retVal=$?")
        cmd.append("cat stats.txt")
        cmd.append("if [ $retVal -ne 0 ]; then")
        cmd.append("  echo \"testee error\"")
        cmd.append("  exit $retVal")
        cmd.append("fi")
        cmd_debug(cmd, "mv output.txt output" + f"{i:03}.txt")
        i += 1

    s = "\n".join(cmd)
    command_filename = "run_testee.sh"
    with open(path_join(starter_tmp, command_filename), "x", newline="\n") as f:
        f.write(s)
        mounts.append(Mount(path_join("/usr/src", command_filename), path_join(docker_tmp, command_filename), type="bind", read_only=True))
    options["command"] = command_filename
    options[READONLY] = True
    
def prepare_checker(options: dict, samples: dict) -> str:
    options[MOUNTS] = mounts = options.get(MOUNTS, [])

    docker_tmp = options[DOCKER_TEMP]
    starter_tmp = options[STARTER_TEMP]
    starter_wrk_tmp = path_join(starter_tmp, "wrk")
    mounts.append(Mount("/usr/src", starter_wrk_tmp, type="bind", read_only=False))
    docker_wrk_tmp = path_join(docker_tmp, "wrk")

    cmd = ["#!/bin/bash"]
    options["commands"] = cmd
    timeout = options.get(TIMEOUT, 360)
    i = 1
    for _ in samples:
        input_name = "input" + f"{i:03}.txt"
        mounts.append(Mount(path_join("/usr/src", input_name), path_join(docker_wrk_tmp, input_name), type="bind", read_only=True))
        output_name = "output" + f"{i:03}.txt"
        mounts.append(Mount(path_join("/usr/src", output_name), path_join(starter_wrk_tmp, output_name), type="bind", read_only=True))

        cmd.append("echo \"sample: " + str(i) + "\"")
        cmd_debug(cmd, "ln -sf " + input_name + " input.txt")
        cmd_debug(cmd, "ln -sf " + output_name + " output.txt")
        cmd_debug(cmd, "timeout " + str(timeout) + " " + options[CMD])
        cmd.append("retVal=$?")
        cmd.append("if [ $retVal -ne 0 ]; then")
        cmd.append("  echo \"checker error\"")
        cmd.append("  exit retVal=$?")
        cmd.append("fi")
        i += 1

    s = "\n".join(cmd)
    command_filename = "run_checker.sh"
    with open(path_join(starter_tmp, command_filename), "x", newline="\n") as f:
        f.write(s)
        mounts.append(Mount(path_join("/usr/src", command_filename), path_join(docker_tmp, command_filename), type="bind", read_only=True))
    options["command"] = command_filename
    options[READONLY] = True

