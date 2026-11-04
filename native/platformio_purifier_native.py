"""Scoped native package capture and frozen-resolution checks."""

import base64
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit


@lru_cache(maxsize=1)
def context():
    path = os.environ.get("PLATFORMIO_PURIFIER_CONTEXT")
    return json.loads(Path(path).read_text()) if path else {}


def deny(message="Packages are Nix-resolved; run platformio-purifier lock --update"):
    from platformio.exception import UserSideException

    raise UserSideException(message)


def frozen():
    return context().get("mode") == "frozen"


def deny_if_frozen():
    if frozen():
        deny()


def check_install(manager, spec, force=False):
    if not frozen():
        return
    item = manager.get_package(spec)
    tree = Path(context()["packages"]).resolve()
    if force or not item or not Path(item.path).resolve().is_relative_to(tree):
        deny()


def component(value):
    return (
        isinstance(value, str)
        and value not in (".", "..")
        and re.fullmatch(r"[A-Za-z0-9_.+@ -]+", value)
    )


def record_install(manager, uri, spec, checksum, item):
    state = context()
    if state.get("mode") != "capture":
        return
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        deny("This provider requires public HTTPS package archives")
    metadata = item.metadata.as_dict()
    if metadata["type"] == "platform" and metadata["name"] != "atmelavr":
        deny("This provider currently supports the Arduino AVR platform")
    path = Path(item.path)
    if not component(path.name):
        deny("Unsupported native package directory name")
    if manager.pkg_type == "library":
        relative = path.relative_to(Path(state["libraries"]))
        if len(relative.parts) != 2 or not component(relative.parts[0]):
            deny("This library storage needs an additional provider")
        directory = "libraries/" + relative.parts[0]
    else:
        directory = {"platform": "platforms", "tool": "packages"}[manager.pkg_type]
    archive = Path(manager.compute_download_path(uri, checksum or ""))
    digest = hashlib.sha256(archive.read_bytes()).digest()
    capture = Path(state["capture"])
    capture.mkdir(parents=True, exist_ok=True)
    saved = capture / (digest.hex() + ".archive")
    shutil.copyfile(archive, saved)
    record = dict(
        url=uri,
        hash="sha256-" + base64.b64encode(digest).decode(),
        archive=str(saved),
        directory=directory,
        name=path.name,
        metadata=metadata,
    )
    with (capture / "records.jsonl").open("a") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")


@contextmanager
def working_directory(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def projection(root, config_file):
    from platformio.project.config import ProjectConfig

    fields = (
        "platform",
        "platform_packages",
        "framework",
        "board",
        "lib_deps",
        "lib_ignore",
        "lib_compat_mode",
        "lib_ldf_mode",
        "test_framework",
        "debug_tool",
        "upload_protocol",
        "check_tool",
    )
    with working_directory(root):
        config = ProjectConfig(str(config_file))
        return {
            name: {field: config.get("env:" + name, field) for field in fields}
            for name in sorted(config.envs())
        }


def guard_project():
    if not frozen():
        return
    state = context()
    if projection(state["root"], state["config"]) != state["selection"]:
        deny(
            "PlatformIO dependency selection changed; run platformio-purifier lock --update"
        )
    from platformio import app

    app.set_session_var("custom_project_conf", state["config"])
