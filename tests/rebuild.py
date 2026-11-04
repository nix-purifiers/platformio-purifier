from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
subprocess.run(
    [
        "nix",
        "build",
        "--rebuild",
        "--no-link",
        "--expr",
        "(builtins.getFlake "
        + __import__("json").dumps(str(repo))
        + ").checks."
        + system
        + ".environment.packages",
        "--impure",
    ],
    check=True,
)
print("Native PlatformIO package replay and binary patching rebuilt identically")
