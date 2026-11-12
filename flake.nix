{
  description = "Locked, Nix-resolved PlatformIO dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        platformio-purifier = import ./nix/scope.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).platformio-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/platformio-purifier";
          meta.description = "Lock native PlatformIO dependencies";
        };
      });
      lib.platformio-purifier = import ./lib-overlays/default { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.platformio-purifier.buildPlatformioProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = ''test -s "$out/uno/firmware.hex"'';
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
