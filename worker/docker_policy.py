"""Fail closed unless Docker's effective settings match the requested boundary."""

import re

from worker.docker_client import DockerFault

MANAGED = "webguard.runner-v1"
ENV_KEYS = {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256", "HOME", "TMPDIR",
            "PYTHONDONTWRITEBYTECODE", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "WEBGUARD_WALL_SECONDS"}
ENTRYPOINT = ["python", "-I", "/opt/webguard/entrypoint.py"]


def labels(owner, job, run, role):
    return {"io.webguard.managed": MANAGED, "io.webguard.owner": owner,
            "io.webguard.job": job, "io.webguard.run": run, "io.webguard.role": role}


def resource_name(owner, run, role):
    if not all(re.fullmatch(r"[0-9a-f]{32}", value) for value in (owner, run)) or role not in ("stage", "test", "source"):
        raise DockerFault("resource_identity")
    return f"wg-{owner}-{run}-{role}"


def check_daemon(info):
    if (info.get("OSType") != "linux" or info.get("CgroupVersion") != "2"
            or not all(info.get(key) is True for key in
                       ("MemoryLimit", "SwapLimit", "CpuCfsQuota", "PidsLimit"))
            or not any(value.startswith("name=seccomp") and "unconfined" not in value
                       for value in info.get("SecurityOptions", []))):
        raise DockerFault("unsupported_daemon")
    if any(re.search(r"memory|swap|cpu|pid|cgroup|seccomp", warning, re.IGNORECASE)
           for warning in info.get("Warnings") or []):
        raise DockerFault("unsupported_daemon")


def check_image(image, image_id, profile, info, redactor):
    config = image.get("Config") or {}
    expected = {"io.webguard.runner": "1", "io.webguard.python": profile.python_version,
                "io.webguard.profile": profile.digest}
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(info.get("Architecture"), info.get("Architecture"))
    if (image.get("Id") != image_id or image.get("Os") != "linux" or image.get("Architecture") != arch
            or config.get("User") != "10001:10001" or config.get("Entrypoint") != ENTRYPOINT
            or config.get("Cmd") not in (None, []) or config.get("Volumes")
            or config.get("WorkingDir") != "/scratch"
            or any((config.get("Labels") or {}).get(key) != value for key, value in expected.items())):
        raise DockerFault("untrusted_image")
    for value in config.get("Env") or []:
        if value.partition("=")[0] not in ENV_KEYS or redactor.text(value) != value:
            raise DockerFault("image_environment")


def tmpfs_options(mib):
    return f"rw,noexec,nosuid,nodev,size={mib * 1048576},mode=1777"


def create_arguments(image, owner, job, run, role, volume, limits):
    arguments = ["container", "create", "--name", resource_name(owner, run, role),
                 "--pull=never", "--network=none", "--user=10001:10001", "--read-only",
                 "--cap-drop=ALL", "--security-opt=no-new-privileges=true", "--cgroupns=private",
                 "--ipc=private", "--cpus", f"{limits.cpu_millis / 1000:.3f}",
                 "--memory", str(limits.memory_mib * 1048576),
                 "--memory-swap", str(limits.memory_mib * 1048576), "--pids-limit", str(limits.pids),
                 "--shm-size=1048576", "--ulimit=nofile=256:256", "--ulimit=core=0:0",
                 "--log-driver=none", "--workdir=/scratch", "--attach=stdout", "--attach=stderr",
                 "--env", f"WEBGUARD_WALL_SECONDS={limits.wall_seconds}",
                 "--tmpfs", f"/scratch:{tmpfs_options(limits.scratch_mib)}",
                 "--tmpfs", f"/tmp:{tmpfs_options(limits.tmp_mib)}",
                 "--mount", f"type=volume,src={volume},dst=/input,volume-nocopy" +
                 (",readonly" if role == "test" else "")]
    for key, value in labels(owner, job, run, role).items():
        arguments += ["--label", f"{key}={value}"]
    if role == "stage":
        arguments += ["--entrypoint=python", image, "-I", "/opt/webguard/stage.py"]
    else:
        arguments += [image]
    return arguments


def check_volume(document, owner, job, run):
    expected = labels(owner, job, run, "source")
    if (document.get("Name") != resource_name(owner, run, "source")
            or document.get("Driver") != "local" or document.get("Options")
            or any((document.get("Labels") or {}).get(key) != value for key, value in expected.items())):
        raise DockerFault("volume_policy")


def check_container(document, image, owner, job, run, role, volume, limits):
    config, host = document.get("Config") or {}, document.get("HostConfig") or {}
    expected_labels = labels(owner, job, run, role)
    safe_options = {"no-new-privileges", "no-new-privileges=true", "no-new-privileges:true"}
    if (document.get("Name") != "/" + resource_name(owner, run, role)
            or not re.fullmatch(r"[0-9a-f]{64}", document.get("Id", ""))
            or document.get("Image") != image or config.get("User") != "10001:10001"
            or config.get("WorkingDir") != "/scratch" or config.get("Tty") is not False
            or config.get("OpenStdin") is not False
            or any((config.get("Labels") or {}).get(key) != value for key, value in expected_labels.items())
            or host.get("Privileged") is not False or host.get("ReadonlyRootfs") is not True
            or host.get("NetworkMode") != "none" or host.get("PublishAllPorts")
            or host.get("PortBindings") or host.get("Binds") or host.get("VolumesFrom")
            or host.get("Devices") or host.get("DeviceRequests") or host.get("DeviceCgroupRules")
            or host.get("PidMode") not in ("", None) or host.get("IpcMode") != "private"
            or host.get("UTSMode") not in ("", None) or host.get("UsernsMode") == "host"
            or host.get("CgroupnsMode") != "private" or host.get("CapAdd")
            or {item.lower() for item in host.get("CapDrop") or []} != {"all"}
            or not host.get("SecurityOpt") or not set(host["SecurityOpt"]).issubset(safe_options)
            or host.get("Memory") != limits.memory_mib * 1048576
            or host.get("MemorySwap") != limits.memory_mib * 1048576
            or host.get("NanoCpus") != limits.cpu_millis * 1000000
            or host.get("PidsLimit") != limits.pids or host.get("ShmSize") != 1048576
            or host.get("OomKillDisable") is True or host.get("AutoRemove")
            or (host.get("LogConfig") or {}).get("Type") != "none"
            or host.get("Tmpfs") != {"/scratch": tmpfs_options(limits.scratch_mib),
                                      "/tmp": tmpfs_options(limits.tmp_mib)}):
        raise DockerFault("container_policy")
    mounts = host.get("Mounts") or []
    if (len(mounts) != 1 or mounts[0].get("Type") != "volume"
            or mounts[0].get("Source") != volume or mounts[0].get("Target") != "/input"
            or bool(mounts[0].get("ReadOnly")) != (role == "test")
            or not (mounts[0].get("VolumeOptions") or {}).get("NoCopy")):
        raise DockerFault("container_mounts")
    expected_entry = ENTRYPOINT if role == "test" else ["python"]
    expected_cmd = (None, []) if role == "test" else (["-I", "/opt/webguard/stage.py"],)
    if config.get("Entrypoint") != expected_entry or config.get("Cmd") not in expected_cmd:
        raise DockerFault("container_command")
    environment = dict(value.split("=", 1) for value in config.get("Env") or [])
    if (environment.get("WEBGUARD_WALL_SECONDS") != str(limits.wall_seconds)
            or set(environment) - ENV_KEYS):
        raise DockerFault("container_environment")
    actual_mounts = document.get("Mounts") or []
    for mount in actual_mounts:
        if mount.get("Type") == "volume":
            if (mount.get("Name") != volume or mount.get("Destination") != "/input"
                    or mount.get("Driver") != "local" or bool(mount.get("RW")) != (role == "stage")):
                raise DockerFault("effective_mounts")
        elif mount.get("Type") != "tmpfs" or mount.get("Destination") not in ("/tmp", "/scratch"):
            raise DockerFault("effective_mounts")
    if document.get("State", {}).get("Running") and sum(
        mount.get("Type") == "volume" for mount in actual_mounts
    ) != 1:
        raise DockerFault("effective_mounts")
    return {"network": "none", "user": "10001:10001", "read_only_root": True,
            "cap_drop": ["ALL"], "no_new_privileges": True, "host_bind_mounts": False,
            "source_read_only": role == "test", "memory_bytes": host["Memory"],
            "memory_swap_bytes": host["MemorySwap"], "nano_cpus": host["NanoCpus"],
            "pids": host["PidsLimit"], "scratch_bytes": limits.scratch_mib * 1048576,
            "tmp_bytes": limits.tmp_mib * 1048576, "shm_bytes": host["ShmSize"],
            "log_driver": "none"}
