"""Use the native resolver, uploader setup, and test-framework selection."""

import json
import os
from pathlib import Path
import runpy
import sys

bootstrap, root, config_file, output = sys.argv[1:5]
runpy.run_path(bootstrap, run_name="platformio_native_bootstrap")
from platformio.__main__ import cli
from platformio import app
from platformio.platform.factory import PlatformFactory
from platformio.project.config import ProjectConfig
from platformio.package.manager.library import LibraryPackageManager
from platformio.package.manager.core import get_core_package_dir
from platformio.package.meta import PackageSpec
from platformio.test.result import TestSuite
from platformio.test.runners.factory import TestRunnerFactory
from platformio.platformio_purifier_native import projection, working_directory

selection = projection(root, config_file)
if not selection:
    raise ValueError("Declare at least one PlatformIO environment")
with working_directory(root):
    app.set_session_var("custom_project_conf", config_file)
    args = ["pkg", "install", "--project-dir", root]
    for environment in selection:
        args += ["--environment", environment]
    cli.main(args=args, standalone_mode=False)
    config = ProjectConfig.get_instance(config_file)
    for environment in selection:
        platform = PlatformFactory.from_env(environment, autoinstall=True)
        platform.configure_project_packages(environment, ["upload", "__test", "debug"])
        platform.install_required_packages()
        runner = TestRunnerFactory.new(TestSuite(environment, "*"), config)
        manager = LibraryPackageManager(
            os.path.join(config.get("platformio", "libdeps_dir"), environment)
        )
        for dependency in runner.EXTRA_LIB_DEPS or []:
            manager.install(dependency)
        for tool in config.get("env:" + environment, "check_tool"):
            name = "tool-" + tool
            overrides = [
                PackageSpec(value)
                for value in config.get("env:" + environment, "platform_packages")
            ]
            spec = next((value for value in overrides if value.name == name), None)
            get_core_package_dir(name, spec=spec)
Path(output).write_text(json.dumps(selection, sort_keys=True, indent=2) + "\n")
