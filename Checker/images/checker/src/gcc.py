from globals import *
from docker.types import Mount

def prepare_build(options: dict, name: str) -> bool:
    language = options[LANGUAGE]
    
    if language == "c":
        file_ext = ".c"
        compiler = "gcc"
    elif language in ["cpp", "c++"]:
        file_ext = ".cpp"
        compiler = "g++"
    else:
        raise Exception('Unknown language: "' + language + '"')

    options["image_name"] = "gcc:builder"

    options[MOUNTS] = mounts = []

    cmd = ["#!/bin/bash"]

    docker_tmp = options[DOCKER_TEMP]
    starter_tmp = options[STARTER_TEMP]
    mounts.append(Mount("/usr/src", docker_tmp, type="bind", read_only=False))

    bin_path = path_join(starter_tmp, name)
    os.makedirs(bin_path)
    filename = "main" + file_ext
    with open(path_join(bin_path, filename), "x", newline="\n") as f:
        f.write(options[SOURCE])

    cmd_debug(cmd, compiler + " -o " + name + "/" + name + " " + name + "/" + filename)
    cmd.append("retVal=$?")
    cmd.append("if [ $retVal -ne 0 ]; then")
    cmd.append("  exit $retVal")
    cmd.append("fi")
    cmd.append('echo "debug: build success"')
    
    options["bin_path"] = name
    options[CMD] = "./bin/" + name

    s = "\n".join(cmd)
    command_filename = "build_" + name + ".sh"
    with open(path_join(starter_tmp, command_filename), "x", newline="\n") as f:
        f.write(s)
    options["command"] = command_filename
    
    return True

def prepare_run(options: dict):
    options["image_name"] = "python:checker"
    options[MEM_LIMIT] = options.get(MEM_LIMIT, "100m")
    options[MEMSWAP_LIMIT] = 0

    options[MOUNTS] = mounts = []

    docker_tmp = options[DOCKER_TEMP]
    mounts.append(Mount("/usr/src/bin", path_join(docker_tmp, options["bin_path"]), type="bind", read_only=True))