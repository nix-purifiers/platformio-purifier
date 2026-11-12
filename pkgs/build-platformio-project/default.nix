{
  lib,
  runCommand,
  writeText,
  python3,
  fetchurl,
  fetchgit,
  purifier,
  sdkVersion,
  core,
  debugger,
  analyzer,
  autoPatchelfHook,
  stdenv,
  gnutar,
  gzip,
  ...
}@scope:
{
  src,
  lockFile ? src + "/platformio-purifier.lock.json",
  configFile ? "platformio.ini",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } {
      inherit src lockFile;
      system = stdenv.hostPlatform.system;
    }
  );
  prepared = import ./environment.nix scope { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".pio"
        "result"
        "__pycache__"
      ]);
  };
  driver = lib.fileset.toSource {
    root = ../..;
    fileset = lib.fileset.unions [
      ../../platformio_purifier/common.py
      ../../platformio_purifier/layout.py
      ../../native/check.py
    ];
  };
  project = runCommand "platformio-firmware" { } ''
    cp -r ${source} source
    chmod -R u+w source
    ${python3}/bin/python3 ${driver}/native/check.py "$PWD/source" "$TMPDIR/private" \
      ${prepared.output} ${core}/bin/pio ${lib.escapeShellArg configFile} ${stdenv.hostPlatform.system} "$out"
    ${lib.optionalString doCheck checkCommand}
  '';
  release =
    runCommand "platformio-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/firmware.tar.gz" -C ${project} .
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
