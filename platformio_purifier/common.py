import json
import os
import subprocess

SYSTEMS = {"x86_64-linux": "linux_x86_64", "aarch64-linux": "linux_aarch64"}
NATIVE_ENV = (
    "PLATFORMIO_CORE_DIR",
    "PLATFORMIO_PLATFORMS_DIR",
    "PLATFORMIO_PACKAGES_DIR",
    "PLATFORMIO_LIBDEPS_DIR",
    "PLATFORMIO_GLOBALLIB_DIR",
    "PLATFORMIO_CACHE_DIR",
    "PLATFORMIO_SETTING_ENABLE_TELEMETRY",
    "PLATFORMIO_DISABLE_UPGRADE_CHECK",
    "PLATFORMIO_SYSTEM_TYPE",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONNOUSERSITE",
)


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stderr or result.stdout)
    return result.stdout


def original_environment():
    env = dict(os.environ)
    for name, value in json.loads(
        env.pop("PLATFORMIO_PURIFIER_ORIGINAL_ENV", "{}")
    ).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    env.pop("PLATFORMIO_PURIFIER_CONTEXT", None)
    return env


def load(companion):
    data = json.loads(companion.read_text())
    if data.get("sdk") != os.environ["PLATFORMIO_PURIFIER_SDK_VERSION"]:
        raise ValueError(
            "PlatformIO SDK changed; run platformio-purifier lock --update"
        )
    system = os.environ["PLATFORMIO_PURIFIER_SYSTEM"]
    if system not in data.get("systems", {}):
        raise ValueError("The PlatformIO lock has no closure for this system")
    return data
