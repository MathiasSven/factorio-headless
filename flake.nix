{
  description = "A factorio server flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      inherit (pkgs) lib stdenv fetchurl writeText runCommand;
      inherit (lib) importJSON mapAttrs' replaceStrings;

      versions = importJSON ./versions.json;

      factorioHeadlessFor =
        version: sha256:
        stdenv.mkDerivation {
          pname = "factorio-headless";
          inherit version;
          src = fetchurl {
            name = "factorio_headless_x64-${version}.tar.xz";
            url = "https://factorio.com/get-download/${version}/headless/linux64";
            inherit sha256;
          };
          preferLocalBuild = true;
          dontBuild = true;
          installPhase = ''
            mkdir -p $out/{bin,share/factorio}
            cp -a data $out/share/factorio
            cp -a bin/x64/factorio $out/bin/factorio
            patchelf \
              --set-interpreter $(cat $NIX_CC/nix-support/dynamic-linker) \
              $out/bin/factorio
          '';
        };

      factorioHeadlessVersions = mapAttrs' (version: sha256: {
        name = replaceStrings [ "." ] [ "_" ] version;
        value = factorioHeadlessFor version sha256;
      }) versions.versions;

      releases = builtins.mapAttrs (
        name: version: self.packages.x86_64-linux.${replaceStrings [ "." ] [ "_" ] version}
      ) versions.releases;
    in
    {
      packages.x86_64-linux = factorioHeadlessVersions // releases // {
        default = self.packages.x86_64-linux.stable;
      };

      checks.x86_64-linux.stable = 
      let
        package = self.packages.x86_64-linux.default;
        configFile = writeText "factorio.conf" ''
          use-system-read-write-data-directories=true
          [path]
          read-data=${package}/share/factorio/data
          write-data=./state_dir
        '';
      in
      runCommand "factorio-headless-stable" {} ''
        ${package}/bin/factorio --config=${configFile} --create ./map.zip
        ${package}/bin/factorio --config=${configFile} --benchmark ./map.zip --benchmark-ticks 1
        touch $out
      '';
    };
}
