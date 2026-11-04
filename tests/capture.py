import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="platformio-cold-capture-") as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(repo / "examples/minimal", root)
    lock = root / "platformio-purifier.lock.json"
    lock.unlink()
    ambient = Path(temporary) / "ambient-core"
    ambient.mkdir()
    (ambient / "preserve").write_text("untouched")
    env = dict(
        os.environ,
        PLATFORMIO_CORE_DIR=str(ambient),
        XDG_CACHE_HOME=str(Path(temporary) / "cache"),
    )

    def capture(*args, success=True):
        result = subprocess.run(
            [sdk / "bin/platformio-purifier", "lock", "--project", root, *args],
            env=env,
            text=True,
            capture_output=True,
            timeout=1200,
        )
        assert (result.returncode == 0) == success, result
        return result

    capture()
    data = json.loads(lock.read_text())
    assert set(data["systems"]) == {"x86_64-linux", "aarch64-linux"}
    for selected in data["systems"].values():
        names = {
            entry["platformio"]["metadata"]["name"] for entry in selected["entries"]
        }
        assert {
            "atmelavr",
            "toolchain-atmelavr",
            "tool-avrdude",
            "tool-cppcheck",
            "Unity",
            "ArduinoJson",
            "Adafruit GFX Library",
            "Adafruit BusIO",
        } <= names, names
        assert all(
            entry["url"].startswith("https://") and entry["hash"].startswith("sha256-")
            for entry in selected["entries"]
        )
    before = lock.read_bytes()
    capture()
    assert lock.read_bytes() == before
    config = root / "platformio.ini"
    config.write_text(
        config.read_text().replace("ArduinoJson@7.4.3", "ArduinoJson@999.0.0")
    )
    capture("--update", success=False)
    assert lock.read_bytes() == before
    assert list(ambient.iterdir()) == [ambient / "preserve"]
print(
    "Cold native capture, both host closures, stable verification, atomic failure and isolated state passed"
)
