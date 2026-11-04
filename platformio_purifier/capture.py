import json
import os
from pathlib import Path
import tempfile

from .common import SYSTEMS, run
from .layout import configure


def capture(root, config, companion, update=False):
    if companion.exists() and not update:
        from .runtime import execute

        if execute(
            root,
            config,
            companion,
            [
                "pkg",
                "install",
                "--project-dir",
                str(root),
            ],
        ):
            raise ValueError("Locked PlatformIO configuration failed verification")
        return
    systems = {}
    with tempfile.TemporaryDirectory(prefix="platformio-capture-") as temporary:
        temporary = Path(temporary)
        for system in SYSTEMS:
            state = temporary / system
            observed = state / "observed"
            observed.mkdir(parents=True)
            env = configure(
                root, config, state, state / "invocation", system, capture=observed
            )
            env["PLATFORMIO_WORKSPACE_DIR"] = str(state / "workspace")
            selection_file = state / "selection.json"
            driver = Path(__file__).parent.parent / "native/resolve.py"
            run(
                [
                    os.environ["PLATFORMIO_PURIFIER_PYTHON"],
                    str(driver),
                    os.environ["PLATFORMIO_PURIFIER_BOOTSTRAP"],
                    str(root),
                    str(config),
                    str(selection_file),
                ],
                env=env,
            )
            records = []
            record_file = observed / "records.jsonl"
            if record_file.exists():
                records = [
                    json.loads(line) for line in record_file.read_text().splitlines()
                ]
            selected = {}
            for record in records:
                # The native manager can rename an older installed version when
                # another environment selects a conflicting version.
                directory = state / record["directory"]
                matches = [
                    path
                    for path in directory.iterdir()
                    if (path / ".piopm").exists()
                    and json.loads((path / ".piopm").read_text()) == record["metadata"]
                ]
                if len(matches) != 1:
                    raise ValueError("Native installed package identity is ambiguous")
                record["name"] = matches[0].name
                key = record["directory"] + "/" + record["name"]
                if key in selected and selected[key]["hash"] != record["hash"]:
                    raise ValueError(
                        "Conflicting native package directories need a provider"
                    )
                selected[key] = record
            entries = []
            for index, key in enumerate(sorted(selected)):
                record = selected[key]
                run(["nix", "store", "add-file", record["archive"]])
                entries.append(
                    dict(
                        path="archive-" + str(index),
                        url=record["url"],
                        hash=record["hash"],
                        mirrors=[],
                        platformio={
                            name: record[name]
                            for name in ("directory", "name", "metadata")
                        },
                    )
                )
            systems[system] = dict(
                selection=json.loads(selection_file.read_text()), entries=entries
            )
        candidate = temporary / "platformio-purifier.lock.json"
        candidate.write_text(
            json.dumps(
                dict(
                    version=1,
                    purifier="platformio",
                    sdk=os.environ["PLATFORMIO_PURIFIER_SDK_VERSION"],
                    systems=systems,
                ),
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        # Native replay and a fresh frozen installer must succeed against the
        # actual Nix packages before replacing the user's lock.
        from .runtime import execute

        if execute(
            root,
            config,
            candidate,
            [
                "pkg",
                "install",
                "--project-dir",
                str(root),
            ],
        ):
            raise ValueError("Nix-delivered PlatformIO packages failed verification")
        companion.parent.mkdir(parents=True, exist_ok=True)
        staged = companion.with_name(companion.name + ".tmp")
        staged.write_bytes(candidate.read_bytes())
        staged.replace(companion)
