import os
import uuid

import docker
from flask import Flask, request

app = Flask(__name__)
client = docker.from_env()


def run_code_in_docker(
    code: str,
    lang: str = "python",
    stdin: str = "",
    version: str = None,
    mem_limit: str = "128m",
    cpu_limit: int = 1,  # need cgroup support
    timeout: int = 5,
):
    code_id = uuid.uuid4()
    if lang == "python":
        image = f"python:{version or 3.9}-slim"
        ext = "py"
        command = f"/bin/sh -c \"timeout {timeout}s /bin/sh -c 'python3 code.{ext} < /stdin.in'\ || echo 'Timeout Error'\""
    elif lang == "c":
        raise NotImplementedError("C is not supported yet")
    elif lang == "cpp":
        raise NotImplementedError("C++ is not supported yet")
    elif lang == "java":
        raise NotImplementedError("Java is not supported yet")
    else:
        raise ValueError("Invalid language")

    # if the image is not available, pull it
    try:
        client.images.get(image)
    except docker.errors.ImageNotFound:
        client.images.pull(image)

    # save code to a tmp file
    code_file = f"/tmp/{code_id}.{ext}"
    with open(code_file, "w") as f:
        f.write(code)

    # save stdin to a tmp file
    stdin_file = f"/tmp/{code_id}.in"
    with open(stdin_file, "w") as f:
        f.write(stdin)

    container_name = f"CodeExecContainer_{code_id}"
    try:
        # worker_id = os.getenv("GUNICORN_WORKER_ID", "0")
        # cpu_start = int(worker_id) * cpu_limit
        # cpu_end = cpu_start + cpu_limit - 1
        # cpuset_cpus = f"{cpu_start}-{cpu_end}" if cpu_limit > 1 else f"{cpu_start}"

        response = client.containers.run(
            image,
            command,
            name=container_name,
            detach=False,
            stderr=True,
            stdout=True,
            remove=True,
            # cpuset_cpus=cpuset_cpus,  # need cgroup support
            mem_limit=mem_limit,
            volumes={
                code_file: {"bind": f"/code.{ext}", "mode": "ro"},
                stdin_file: {"bind": "/stdin.in", "mode": "ro"},
            },
        )

        os.remove(code_file)
        os.remove(stdin_file)
        return response.decode("utf-8")

    except docker.errors.ContainerError as e:
        os.remove(code_file)
        os.remove(stdin_file)
        return e.stderr.decode("utf-8")
    except Exception as e:
        os.remove(code_file)
        os.remove(stdin_file)
        return str(e)


@app.route("/execute", methods=["POST"])
def execute():
    lang = request.json.get("lang", "python")
    version = request.json.get("version", None)
    code = request.json["code"]
    stdin = request.json.get("stdin", "")
    mem_limit = request.json.get("mem_limit", "128m")
    cpu_limit = request.json.get("cpu_limit", 1)
    timeout = request.json.get("timeout", 5)

    try:
        response = run_code_in_docker(
            lang=lang,
            version=version,
            code=code,
            stdin=stdin,
            mem_limit=mem_limit,
            cpu_limit=cpu_limit,
            timeout=timeout,
        )

        return {"output": response}

    except ValueError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5097)
