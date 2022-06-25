from globals import *
from docker.types import Mount

def prepare_build(options: dict, name: str) -> bool:
    starter_tmp = options[STARTER_TEMP]

    bin_path = path_join(starter_tmp, name)
    os.makedirs(bin_path)

    filename = path_join(bin_path, "main.py")
    with open(path_join(starter_tmp, filename), "x", newline="\n") as f:
        f.write(options[SOURCE])

    options["bin_path"] = bin_path
    options[CMD] = "python bin/main.py"

    return False

def prepare_run(options: dict):
    options["image_name"] = "python:checker"
    options[MEM_LIMIT] = options.get(MEM_LIMIT, "100m")
    options[MEMSWAP_LIMIT] = 0

    options[MOUNTS] = mounts = []

    docker_tmp = options[DOCKER_TEMP]
    mounts.append(Mount("/usr/src/bin", path_join(docker_tmp, options["bin_path"]), type="bind", read_only=True))