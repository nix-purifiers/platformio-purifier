import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .common import load, original_environment, run
from .layout import configure


def realize(root, companion):
    data = load(companion)
    sdk = os.environ["PLATFORMIO_PURIFIER_SDK"]
    home = Path(
        original_environment().get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    )
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    generation = hashlib.sha256(companion.read_bytes() + sdk.encode()).hexdigest()[:20]
    state = home / "platformio-purifier" / key / generation
    state.mkdir(parents=True, exist_ok=True)
    profile = state / "environment-profile"
    if not profile.exists():
        expression = (
            "import "
            + json.dumps(sdk + "/lib/platformio-purifier/nix/realize.nix")
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";sdk="
            + json.dumps(sdk)
            + ";}"
        )
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(profile),
            ]
        )
    manifest = json.loads(Path(json.loads(profile.read_text())["output"]).read_text())
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared PlatformIO SDK differs from the lock")
    return state, data, manifest


def execute(root, config, companion, args):
    state, data, manifest = realize(root, companion)
    with tempfile.TemporaryDirectory(prefix="invocation-", dir=state) as temporary:
        env = configure(
            root,
            config,
            state / "session",
            Path(temporary),
            os.environ["PLATFORMIO_PURIFIER_SYSTEM"],
            packages=manifest["packages"],
            selection=manifest["selection"],
        )
        env.update(
            PLATFORMIO_PURIFIER_PROJECT=str(root),
            PLATFORMIO_PURIFIER_LOCK=str(companion),
            PLATFORMIO_PURIFIER_CONFIG=str(config),
        )
        return subprocess.call([os.environ["PLATFORMIO_PURIFIER_CORE"], *args], env=env)
