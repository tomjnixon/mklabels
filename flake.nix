{
  description = "mklabels";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-24.11";

    utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
    }:
    utils.lib.eachSystem utils.lib.defaultSystems (
      system:
      let
        pkgs = nixpkgs.legacyPackages."${system}";
        python = pkgs.python3;
        pango = pkgs.pango.out;
        glib = pkgs.glib.out;
        ext = pkgs.stdenv.hostPlatform.extensions.sharedLibrary;
      in
      rec {
        packages.mklabels = python.pkgs.buildPythonApplication rec {
          name = "mklabels";
          pyproject = true;
          src = ./.;
          build-system = [ python.pkgs.setuptools ];
          dependencies = with python.pkgs; [
            cffi
            cairocffi
          ];
          postPatch = ''
            substituteInPlace mklabels/pango_cairo.py \
              --replace-fail pangocairo-1.0 ${pango}/lib/libpangocairo-1.0${ext} \
              --replace-fail pango-1.0 ${pango}/lib/libpango-1.0${ext} \
              --replace-fail gobject-2.0 ${glib}/lib/libgobject-2.0${ext}
          '';

          pythonImportsCheck = [ "mklabels.main" ];
        };

        packages.default = packages.mklabels;

        devShells.mklabels = packages.mklabels.overridePythonAttrs (old: {
          nativeBuildInputs = [
            pkgs.nixfmt-rfc-style
            pkgs.black
            python.pkgs.flake8
          ];
          shellHook = ''
            export LD_LIBRARY_PATH=${
              pkgs.lib.makeLibraryPath [
                pango
                glib
              ]
            }:$LD_LIBRARY_PATH
          '';
        });
        devShells.default = devShells.mklabels;
      }
    );
}
