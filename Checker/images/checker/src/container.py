from globals import *
import docker

logger = log("container")

def run(task: WrapperInterface, options: dict) -> str:
    mounts = options.get(MOUNTS, [])
    mem_limit = options.get(MEM_LIMIT)
    memswap_limit = options.get(MEMSWAP_LIMIT)
    readonly = options.get(READONLY, False)

    client = docker.from_env()
    kwargs = {
        #"auto_remove": True,
        MOUNTS: mounts,
        MEM_LIMIT: mem_limit,
        MEMSWAP_LIMIT: memswap_limit,
        "pids_limit": -1,
        "tty": False,
        "stdin_open": False,
        READONLY: readonly,
        "entrypoint": ["/bin/bash"],
        "network_disabled": True,
        "working_dir": "/usr/src"
    }
    container = None
    try:
        container = client.containers.create(options["image_name"], command=options["command"], **kwargs)
        logger.info("image: " + options["image_name"] + ", container: " + container.name)
        container.start()

        out = container.logs(
            stdout=True, stderr=True, stream=True, follow=True
        )

        lines = []
        for line in out:
            logger.debug(line.decode("utf-8").rstrip().replace("debug: ", ""))
            lines.append(line.decode("utf-8"))
            task.parse_output(lines)

        container.reload() # обновляет container.attrs
        container_state = container.attrs["State"]
        
        if container_state["OOMKilled"] == True:
            status = "out_of_memory"
        else:
            exitCode = container_state["ExitCode"]

            if exitCode == 0:
                status = SUCCESS
            elif exitCode == 124:
                status = "timeout"
            else:
                status = "error"

        task.parse_output(lines, status)
        return task.status
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

