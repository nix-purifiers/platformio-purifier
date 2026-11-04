"""Replay the native installers using only already verified Nix archives."""

import json
from pathlib import Path
import runpy
import sys

bootstrap, records_file, output = sys.argv[1:4]
runpy.run_path(bootstrap, run_name="platformio_native_bootstrap")
from platformio.package.manager.platform import PlatformPackageManager
from platformio.package.manager.tool import ToolPackageManager
from platformio.package.manager.library import LibraryPackageManager
from platformio.package.meta import PackageSpec

classes = {
    "platform": PlatformPackageManager,
    "tool": ToolPackageManager,
    "library": LibraryPackageManager,
}
for record in json.loads(Path(records_file).read_text()):
    directory = Path(output) / record["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    manager = classes[record["metadata"]["type"]](package_dir=str(directory))
    item = manager.install_from_uri(
        "file://" + record["archive"], PackageSpec(**record["metadata"]["spec"])
    )
    if (
        item.metadata.as_dict() != record["metadata"]
        or Path(item.path).name != record["name"]
    ):
        raise ValueError("Native package replay differs from the captured lock")
