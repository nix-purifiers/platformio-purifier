{
  root,
  lockFile,
  configFile ? "platformio.ini",
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope = import ./scope.nix {
    inherit pkgs nixpkgsSrc;
    purifierSrc = /. + "@purifier@";
  };
in
(scope.buildPlatformioProject {
  inherit configFile;
  src = /. + root;
  lockFile = /. + lockFile;
}).release
