{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  sdkVersion,
  core,
  debugger,
  analyzer,
  autoPatchelfHook,
  stdenv,
  ...
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  archives = purifier.tree (
    {
      name = "platformio-archives";
      inherit
        runCommand
        fetchurl
        fetchgit
        writeText
        python3
        ;
      entries = checked.entries;
    }
    // fetchers
  );
  replay = writeText "platformio-replay.json" (
    builtins.toJSON (
      map (entry: entry.platformio // { archive = "${archives}/${entry.path}"; }) checked.entries
    )
  );
  packages =
    runCommand "platformio-native-packages"
      {
        nativeBuildInputs = [
          autoPatchelfHook
          core.python
        ];
        buildInputs = [ stdenv.cc.cc.lib ];
      }
      ''
        export HOME="$TMPDIR/home" PLATFORMIO_CORE_DIR="$TMPDIR/core"
        export PLATFORMIO_SETTING_ENABLE_TELEMETRY=no PLATFORMIO_DISABLE_UPGRADE_CHECK=true
        mkdir -p "$HOME" "$out"
        ${core.python.interpreter} ${../../native/replay.py} ${core}/bin/.pio-wrapped ${replay} "$out"
        # The registry's old bundled GDB crashes with modern libc. Use the explicit
        # all-target Nix debugger provider; the AVR compiler remains registry GCC.
        if [ -f "$out/packages/toolchain-atmelavr/bin/avr-gdb" ]; then
          rm "$out/packages/toolchain-atmelavr/bin/avr-gdb"
        fi
        if [ -f "$out/packages/tool-cppcheck/cppcheck" ]; then
          rm "$out/packages/tool-cppcheck/cppcheck"
        fi
        patchShebangs "$out"
        autoPatchelf "$out"
        if [ -d "$out/packages/toolchain-atmelavr/bin" ]; then
          ln -s ${lib.getExe debugger} "$out/packages/toolchain-atmelavr/bin/avr-gdb"
        fi
        if [ -d "$out/packages/tool-cppcheck" ]; then
          ln -s ${lib.getExe analyzer} "$out/packages/tool-cppcheck/cppcheck"
        fi
      '';
  output =
    (writeText "platformio-environment.json" (
      builtins.toJSON {
        inherit packages;
        sdk = lock.data.sdk;
        selection = lock.selected.selection;
        providers.cppcheck = {
          package = "nixpkgs.cppcheck";
          version = analyzer.version;
        };
        providers.avrDebugger = {
          package = "nixpkgs.gdb";
          version = debugger.version;
        };
      }
    )).overrideAttrs
      (_: {
        passthru = { inherit packages; };
      });
in
assert lib.assertMsg (
  lock.data.sdk == sdkVersion
) "PlatformIO SDK changed; run platformio-purifier lock --update";
{
  inherit output packages;
}
