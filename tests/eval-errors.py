import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(repo / "examples/minimal", root)
    lock = root / "platformio-purifier.lock.json"
    original = json.loads(lock.read_text())

    def inspect():
        expression = (
            "let f=builtins.getFlake "
            + json.dumps(str(repo))
            + ";lock=f.lib.platformio-purifier.readLock {src=/. + "
            + json.dumps(str(root))
            + ';system="x86_64-linux";};in {inherit(lock)problems outputs;}'
        )
        return json.loads(
            subprocess.check_output(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                text=True,
            )
        )

    assert inspect()["problems"] == []
    assert inspect()["outputs"]["packages"] == ["default", "environment", "project"]
    (root / "src/main.cpp").write_text("Edited native source\n")
    assert inspect()["problems"] == []
    lock.unlink()
    assert inspect()["problems"]

    def entry(data):
        return data["systems"]["x86_64-linux"]["entries"][0]

    for mutate in [
        lambda d: d.update(purifier="other"),
        lambda d: entry(d).update(path="../escape"),
        lambda d: entry(d).update(hash="invalid"),
        lambda d: entry(d)["platformio"].update(directory="../escape"),
        lambda d: entry(d)["platformio"].update(name="../escape"),
        lambda d: d.update(sdk=None),
        lambda d: d.update(systems={}),
    ]:
        data = copy.deepcopy(original)
        mutate(data)
        lock.write_text(json.dumps(data))
        assert inspect()["problems"]
    lock.write_text(json.dumps(original))
print("PlatformIO lock errors and output names validated without IFD")
