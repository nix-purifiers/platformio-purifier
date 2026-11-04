{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.platformio-core;
  core = scope.original.overridePythonAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      ${scope.original.python.interpreter} ${../native/patch-core.py}
      cp ${../native/platformio_purifier_native.py} platformio/platformio_purifier_native.py
    '';
  });
  debugger = pkgs.gdb;
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      platformio = toString scope.original.src;
      debugger = toString scope.debugger.src;
      patch = builtins.hashFile "sha256" ../native/patch-core.py;
      helper = builtins.hashFile "sha256" ../native/platformio_purifier_native.py;
      resolver = builtins.hashFile "sha256" ../native/resolve.py;
      replay = builtins.hashFile "sha256" ../native/replay.py;
    }
  );
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildPlatformioProject = scope.callPackage ./build-project.nix { };
})
