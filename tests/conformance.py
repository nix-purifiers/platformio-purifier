import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)

with tempfile.TemporaryDirectory(prefix="platformio proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(repo / "examples/minimal", root)
    poisoned = root / ".pio/libdeps/uno/ArduinoJson/src/ArduinoJson.h"
    poisoned.parent.mkdir(parents=True)
    poisoned.write_text("#error unlocked cache must not load\n")
    ambient = temp / "ambient-core/preserve"
    ambient.parent.mkdir()
    ambient.write_text("existing global state\n")
    env = dict(
        os.environ,
        PLATFORMIO_PURIFIER_PROJECT=str(root),
        PLATFORMIO_CORE_DIR=str(ambient.parent),
        PLATFORMIO_PACKAGES_DIR=str(temp / "poison-packages"),
        XDG_CACHE_HOME=str(temp / "cache"),
        PYTHONPATH="/nonexistent/poison",
    )

    def call(name, *args, success=True, extra=None):
        result = subprocess.run(
            [sdk / "bin" / name, *args],
            cwd=root,
            env=dict(env, **(extra or {})),
            text=True,
            capture_output=True,
            timeout=600,
        )
        assert (result.returncode == 0) == success, result
        return result

    companion = root / "platformio-purifier.lock.json"
    before = companion.read_bytes()
    source = root / "src/main.cpp"
    original = source.read_text()
    hashes = []
    for answer in [42, 43, 42]:
        source.write_text(original.replace("= 42;", "= " + str(answer) + ";"))
        shutil.rmtree(root / ".pio/build", ignore_errors=True)
        call("pio", "run")
        hashes.append(
            hashlib.sha256(
                (root / ".pio/build/uno/firmware.hex").read_bytes()
            ).hexdigest()
        )
    assert hashes[0] == hashes[2] and hashes[0] != hashes[1], hashes
    assert companion.read_bytes() == before
    assert "unlocked cache" in poisoned.read_text()
    assert ambient.read_text() == "existing global state\n"
    call("platformio", "test", "--without-uploading", "--without-testing")
    call("pio", "check", "--skip-packages")
    profiles = list(
        (temp / "cache/platformio-purifier").glob("*/*/environment-profile")
    )
    assert len(profiles) == 1
    profile = profiles[0]
    assert str(sdk) in subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    manifest = json.loads(Path(json.loads(profile.read_text())["output"]).read_text())
    packages = Path(manifest["packages"])
    assert not packages.stat().st_mode & 0o222
    assert manifest["providers"]["avrDebugger"]["package"] == "nixpkgs.gdb"
    assert manifest["providers"]["cppcheck"]["package"] == "nixpkgs.cppcheck"
    persistent = profile.parent / "session/cache/preserve"
    persistent.parent.mkdir(parents=True, exist_ok=True)
    persistent.write_text("private state")
    call("pio", "run")
    assert persistent.read_text() == "private state"
    config = root / "platformio.ini"
    configuration = config.read_text()
    config.write_text(configuration + "build_flags = -DPURIFIER_BODY_EDIT=43\n")
    call("pio", "run")
    config.write_text(configuration.replace("ArduinoJson@7.4.3", "ArduinoJson@7.3.0"))
    assert "selection changed" in call("pio", "run", success=False).stderr
    config.write_text(configuration)
    denied = call(
        "pio", "pkg", "uninstall", "--library", "bblanchon/ArduinoJson", success=False
    )
    assert "Nix-resolved" in denied.stderr + denied.stdout, denied

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"42")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result_file = temp / "child-result.json"
    script = root / "root-command.py"
    script.write_text(
        "import json\nfrom pathlib import Path\nfrom urllib.request import urlopen\nfrom platformio.package.manager.tool import ToolPackageManager\n"
        + "data={'network':urlopen("
        + repr("http://127.0.0.1:" + str(server.server_port) + "/")
        + ").read().decode()}\n"
        + "try:\n ToolPackageManager().install('platformio/purifier-missing-package@1.0.0')\nexcept Exception as error:\n data['guard']=str(error)\n"
        + "Path("
        + repr(str(result_file))
        + ").write_text(json.dumps(data))\n"
    )
    config.write_text(configuration + "extra_scripts = pre:root-command.py\n")
    try:
        call("pio", "run")
        data = json.loads(result_file.read_text())
        assert data["network"] == "42" and "Nix-resolved" in data["guard"], data
    finally:
        server.shutdown()
        server.server_close()
        config.write_text(configuration)
        script.unlink()
    external = temp / "external-lock.json"
    companion.rename(external)
    flags = {"PLATFORMIO_PURIFIER_LOCK": str(external)}
    call("pio", "run", extra=flags)
    archive = Path(call("platformio-purifier", "bundle", extra=flags).stdout.strip())
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as released:
        released.extractall(consumer, filter="data")
    # Native GNU utilities consume the firmware artifact without this adapter.
    toolchain = packages / "packages/toolchain-atmelavr/bin"
    subprocess.run(
        [
            toolchain / "avr-objcopy",
            "-I",
            "ihex",
            "-O",
            "binary",
            consumer / "uno/firmware.hex",
            consumer / "firmware.bin",
        ],
        check=True,
    )
    assert (consumer / "firmware.bin").stat().st_size > 0
    result = subprocess.run(
        [
            toolchain / "avr-gdb",
            "--batch",
            "-nx",
            "-ex",
            'file "' + str(consumer / "uno/firmware.elf") + '"',
            "-ex",
            "info target",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0 and "avr" in result.stdout.lower(), result
    fake = temp / "fake-gh"
    publication = temp / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath("
        + repr(str(publication))
        + ").write_text(json.dumps(sys.argv[1:]))\n"
    )
    fake.chmod(0o755)
    call(
        "platformio-purifier",
        "publish",
        "--tag",
        "v-proof",
        extra=dict(flags, PLATFORMIO_PURIFIER_GH=str(fake)),
    )
    assert json.loads(publication.read_text()) == [
        "release",
        "upload",
        "v-proof",
        str(archive),
        "--clobber",
    ]
    fallback = temp / "fallback"
    fallback.mkdir()
    result = call(
        "pio", "--version", extra={"PLATFORMIO_PURIFIER_PROJECT": str(fallback)}
    )
    assert "ordinary impure" in result.stderr
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/platformio-purifier"),
        PLATFORMIO_PURIFIER_ORIGINAL=str(fake),
        PLATFORMIO_PURIFIER_PROJECT=str(fallback),
    )
    result = subprocess.run(
        ["python3", "-m", "platformio_purifier.cli", "--native"],
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result

print(
    "Native PlatformIO firmware edits, unit compilation, analysis, immutable packages, child guards, networking, firmware consumer, publication and fallback passed"
)
