{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  cacert,
  gnutar,
  gzip,
  unzip,
  coreutils,
  stdenv,
  original,
  core,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "platformio-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/platformio-purifier"
    cp -r platformio_purifier nix lib-overlays pkgs native "$out/lib/platformio-purifier/"
    install -m755 bin/platformio-purifier "$out/bin/platformio-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/platformio-purifier/nix/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/platformio-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
          gnutar
          gzip
          unzip
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default PLATFORMIO_PURIFIER_GH ${gh}/bin/gh \
      --set PLATFORMIO_PURIFIER_ORIGINAL ${original}/bin/pio \
      --set PLATFORMIO_PURIFIER_CORE ${core}/bin/pio \
      --set PLATFORMIO_PURIFIER_PYTHON ${core.python.interpreter} \
      --set PLATFORMIO_PURIFIER_BOOTSTRAP ${core}/bin/.pio-wrapped \
      --set PLATFORMIO_PURIFIER_SYSTEM ${stdenv.hostPlatform.system} \
      --set PLATFORMIO_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set PLATFORMIO_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/platformio-purifier" "$out/bin/platformio" --add-flags '--native'
    makeWrapper "$out/bin/platformio-purifier" "$out/bin/pio" --add-flags '--native'
  '';
  meta = {
    description = "PlatformIO with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "platformio-purifier";
  };
}
