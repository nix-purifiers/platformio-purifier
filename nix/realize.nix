{
  root,
  lockFile,
  sdk,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope = import ./scope.nix {
    inherit pkgs nixpkgsSrc;
    purifierSrc = /. + "@purifier@";
  };
  lock = import ../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } {
    src = /. + root;
    lockFile = /. + lockFile;
    system = pkgs.stdenv.hostPlatform.system;
  };
  environment = scope.callPackage ../pkgs/build-platformio-project/environment.nix { } { inherit lock; };
in
pkgs.writeText "platformio-environment-profile.json" (
  builtins.toJSON {
    output = environment.output;
    sdk = builtins.storePath sdk;
  }
)
