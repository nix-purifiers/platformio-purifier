{ lib }:
{
  src,
  lockFile ? src + "/platformio-purifier.lock.json",
  system ? builtins.currentSystem,
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  systems = data.systems or { };
  selected = if builtins.isAttrs systems then systems.${system} or { } else { };
  entries = selected.entries or [ ];
  component =
    s:
    builtins.isString s
    && builtins.match "[A-Za-z0-9_.+@ -]+" s != null
    && !(builtins.elem s [
      "."
      ".."
    ]);
  directory =
    s:
    builtins.isString s
    && (
      builtins.elem s [
        "platforms"
        "packages"
      ]
      || (
        lib.hasPrefix "libraries/" s
        && builtins.length (lib.splitString "/" s) == 2
        && component (builtins.elemAt (lib.splitString "/" s) 1)
      )
    );
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "platformio"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs selected
    && builtins.isAttrs (selected.selection or null)
    && builtins.isList entries
    && builtins.all (
      entry:
      builtins.isAttrs entry
      && component (entry.path or null)
      && builtins.isString (entry.url or null)
      && lib.hasPrefix "https://" entry.url
      && builtins.isString (entry.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
      && builtins.isList (entry.mirrors or null)
      && builtins.all builtins.isString entry.mirrors
      && builtins.isAttrs (entry.platformio or null)
      && directory (entry.platformio.directory or null)
      && component (entry.platformio.name or null)
      && builtins.isAttrs (entry.platformio.metadata or null)
      && builtins.elem (entry.platformio.metadata.type or null) [
        "platform"
        "tool"
        "library"
      ]
      && builtins.isString (entry.platformio.metadata.name or null)
      && builtins.isString (entry.platformio.metadata.version or null)
      && builtins.isAttrs (entry.platformio.metadata.spec or null)
      && ((entry.platformio.metadata.type != "platform") || entry.platformio.metadata.name == "atmelavr")
    ) entries;
  valid =
    shape
    && builtins.hasAttr system systems
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    &&
      builtins.length (lib.unique (map (e: e.platformio.directory + "/" + e.platformio.name) entries))
      == builtins.length entries;
in
{
  purifier = "platformio";
  inherit data selected entries;
  problems =
    lib.optional (!valid)
      "PlatformIO lock is missing, malformed, or has no closure for this system; run platformio-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
