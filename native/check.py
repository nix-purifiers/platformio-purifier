import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from platformio_purifier.layout import configure

root, state, manifest_file, binary, config_name, system, output = sys.argv[1:8]
root, state, output = Path(root), Path(state), Path(output)
manifest = json.loads(Path(manifest_file).read_text())
env = configure(
    root,
    root / config_name,
    state / "session",
    state / "invocation",
    system,
    packages=manifest["packages"],
    selection=manifest["selection"],
)
env["PLATFORMIO_BUILD_DIR"] = str(state / "build")
for name in manifest["selection"]:
    subprocess.run(
        [
            binary,
            "run",
            "--project-dir",
            str(root),
            "--project-conf",
            str(root / config_name),
            "--environment",
            name,
        ],
        env=env,
        check=True,
    )
    destination = output / name
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("firmware.elf", "firmware.hex"):
        shutil.copyfile(state / "build" / name / filename, destination / filename)
