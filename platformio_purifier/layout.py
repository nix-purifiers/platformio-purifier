import json
import os
from pathlib import Path

from .common import NATIVE_ENV, SYSTEMS


def alias(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.resolve() != target.resolve():
            raise ValueError("Private PlatformIO package differs from the Nix SDK")
    else:
        path.symlink_to(target, target_is_directory=True)


def configure(
    root, config, state, invocation, system, packages=None, selection=None, capture=None
):
    state.mkdir(parents=True, exist_ok=True)
    invocation.mkdir(parents=True, exist_ok=True)
    if packages is not None:
        packages = Path(packages)
        for namespace in ("platforms", "packages", "libraries"):
            source = packages / namespace
            if not source.exists():
                continue
            if namespace == "libraries":
                for environment in source.iterdir():
                    for item in environment.iterdir():
                        alias(state / namespace / environment.name / item.name, item)
            else:
                for item in source.iterdir():
                    alias(state / namespace / item.name, item)
    env = dict(os.environ)
    if "PLATFORMIO_PURIFIER_ORIGINAL_ENV" not in env:
        env["PLATFORMIO_PURIFIER_ORIGINAL_ENV"] = json.dumps(
            {key: env.get(key) for key in NATIVE_ENV}
        )
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.update(
        PLATFORMIO_CORE_DIR=str(state / "core"),
        PLATFORMIO_PLATFORMS_DIR=str(state / "platforms"),
        PLATFORMIO_PACKAGES_DIR=str(state / "packages"),
        PLATFORMIO_LIBDEPS_DIR=str(state / "libraries"),
        PLATFORMIO_GLOBALLIB_DIR=str(state / "global-libraries"),
        PLATFORMIO_CACHE_DIR=str(state / "cache"),
        PLATFORMIO_SETTING_ENABLE_TELEMETRY="no",
        PLATFORMIO_DISABLE_UPGRADE_CHECK="true",
        PLATFORMIO_SYSTEM_TYPE=SYSTEMS[system],
        PYTHONNOUSERSITE="true",
    )
    context = dict(
        mode="capture" if capture else "frozen",
        root=str(root),
        config=str(config),
        libraries=str(state / "libraries"),
        packages=str(packages) if packages is not None else None,
        selection=selection,
        capture=str(capture) if capture else None,
    )
    context_file = invocation / "context.json"
    context_file.write_text(json.dumps(context))
    env["PLATFORMIO_PURIFIER_CONTEXT"] = str(context_file)
    return env
