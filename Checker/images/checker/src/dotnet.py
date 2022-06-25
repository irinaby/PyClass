from globals import *
from docker.types import Mount

def prepare_build(options: dict, name: str) -> bool:
    language = options[LANGUAGE]
    
    if language == "C#":
        file_ext = ".cs"
    elif language == "F#":
        file_ext = ".fs"
    elif language == "VB":
        file_ext = ".vb"
    else:
        raise Exception('Unknown dotnet language: "' + language + '"')

    options["image_name"] = "dotnet:builder"

    options[MOUNTS] = mounts = []

    cmd = ["#!/bin/bash"]

    docker_tmp = options[DOCKER_TEMP]
    starter_tmp = options[STARTER_TEMP]
    mounts.append(Mount("/usr/src", docker_tmp, type="bind", read_only=False))

    filename = name + file_ext
    with open(path_join(starter_tmp, filename), "x", newline="\n") as f:
        f.write(options[SOURCE])

    cmd_debug(cmd, "dotnet new console -o " + name)
    cmd_debug(cmd, "cp " + filename + " " + name + "/Program" + file_ext)
    cmd_debug(cmd, "dotnet build --configuration Release --no-restore -v q " + name)
    cmd.append("retVal=$?")
    cmd.append("if [ $retVal -ne 0 ]; then")
    cmd.append("  exit $retVal")
    cmd.append("fi")
    cmd.append('echo "debug: build success"')

    options["bin_path"] = name + "/bin/Release/net6.0"
    options[CMD] = "dotnet bin/" + name + ".dll"

    s = "\n".join(cmd)
    command_filename = "build_" + name + ".sh"
    with open(path_join(starter_tmp, command_filename), "x", newline="\n") as f:
        f.write(s)
    options["command"] = command_filename
    
    return True

def prepare_run(options: dict):
    options["image_name"] = "dotnet:runtime"
    options[MEM_LIMIT] = options.get(MEM_LIMIT, "100m")
    options[MEMSWAP_LIMIT] = 0

    options[MOUNTS] = mounts = []

    docker_tmp = options[DOCKER_TEMP]
    mounts.append(Mount("/usr/src/bin", path_join(docker_tmp, options["bin_path"]), type="bind", read_only=True))