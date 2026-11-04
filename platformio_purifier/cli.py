import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import original_environment, run
from .runtime import execute, realize


def locate(project=None, lock=None, config=None, flags=()):
    selected = project or os.environ.get("PLATFORMIO_PURIFIER_PROJECT")
    selected_config = config or os.environ.get("PLATFORMIO_PURIFIER_CONFIG")
    for index, value in enumerate(flags):
        if value in ("-d", "--project-dir") and index + 1 < len(flags):
            selected = flags[index + 1]
        elif value.startswith("--project-dir="):
            selected = value.split("=", 1)[1]
        elif value in ("-c", "--project-conf") and index + 1 < len(flags):
            selected_config = flags[index + 1]
        elif value.startswith("--project-conf="):
            selected_config = value.split("=", 1)[1]
    root = Path(selected or Path.cwd()).expanduser().resolve()
    if not selected:
        for candidate in (root, *root.parents):
            if (candidate / "platformio.ini").exists() or (
                candidate / "platformio-purifier.lock.json"
            ).exists():
                root = candidate
                break
    config_file = Path(selected_config or "platformio.ini")
    if not config_file.is_absolute():
        config_file = root / config_file
    companion = Path(
        lock
        or os.environ.get(
            "PLATFORMIO_PURIFIER_LOCK", root / "platformio-purifier.lock.json"
        )
    ).resolve()
    return root, config_file.resolve(), companion


def main_impl():
    args = sys.argv[1:]
    if args[:1] == ["--native"]:
        flags = args[1:]
        root, config, companion = locate(flags=flags)
        if not companion.exists():
            print(
                "platformio-purifier: no lockfile; using ordinary impure PlatformIO package resolution",
                file=sys.stderr,
            )
            return subprocess.call(
                [os.environ["PLATFORMIO_PURIFIER_ORIGINAL"], *flags],
                env=original_environment(),
            )
        if any(flag in ("--help", "-h", "--version") for flag in flags):
            return subprocess.call(
                [os.environ["PLATFORMIO_PURIFIER_ORIGINAL"], *flags],
                env=original_environment(),
            )
        return execute(root, config, companion, flags)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--tag", default="v0.1.0")
    opts, rest = parser.parse_known_args(args)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    root, config, companion = locate(opts.project, opts.lock, opts.config)
    if opts.action == "lock":
        capture(root, config, companion, opts.update)
    elif opts.action == "prefetch":
        realize(root, companion)
    elif opts.action == "exec":
        if not rest:
            raise ValueError("Pass a command after --")
        if Path(rest[0]).name in ("pio", "platformio"):
            root, config, companion = locate(root, companion, config, rest[1:])
            return execute(root, config, companion, rest[1:])
        realize(root, companion)
        env = original_environment()
        env.update(
            PLATFORMIO_PURIFIER_PROJECT=str(root),
            PLATFORMIO_PURIFIER_LOCK=str(companion),
            PLATFORMIO_PURIFIER_CONFIG=str(config),
        )
        env["PATH"] = (
            os.environ["PLATFORMIO_PURIFIER_SDK"] + "/bin" + os.pathsep + env["PATH"]
        )
        return subprocess.call(rest, env=env)
    else:
        realize(root, companion)
        expression = (
            "import "
            + json.dumps(
                os.environ["PLATFORMIO_PURIFIER_SDK"]
                + "/lib/platformio-purifier/nix/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";configFile="
            + json.dumps(str(config.relative_to(root)))
            + ";}"
        )
        output = Path(
            run(
                [
                    "nix",
                    "build",
                    "--impure",
                    "--no-link",
                    "--print-out-paths",
                    "--expr",
                    expression,
                ]
            ).strip()
        )
        archive = output / "firmware.tar.gz"
        if opts.action == "bundle":
            print(archive)
        else:
            subprocess.run(
                [
                    os.environ["PLATFORMIO_PURIFIER_GH"],
                    "release",
                    "upload",
                    opts.tag,
                    str(archive),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )
    return 0


def main():
    try:
        raise SystemExit(main_impl())
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print("platformio-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
