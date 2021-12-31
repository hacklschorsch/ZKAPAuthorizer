let
  sources = import nix/sources.nix;
in
{ pkgs ? import sources.release2105 {}
, pypiData ? sources.pypi-deps-db
, mach-nix ? import sources.mach-nix { inherit pkgs pypiData; }
, tahoe-lafs-source ? "tahoe-lafs"
, tahoe-lafs-repo ? sources.${tahoe-lafs-source}
}:
  let
    lib = pkgs.lib;
    python = "python27";
    providers = {
      _default = "sdist,nixpkgs,wheel";
      # mach-nix doesn't provide a good way to depend on mach-nix packages,
      # so we get it as a nixpkgs dependency from an overlay. See below for
      # details.
      tahoe-lafs = "nixpkgs";
      # not packaged in nixpkgs at all, we can use the binary wheel from
      # pypi though.
      python-challenge-bypass-ristretto = "wheel";
      # Pure python packages that don't build correctly from sdists
      # - patches in nixpkgs that don't apply
      boltons = "wheel";
      chardet = "wheel";
      urllib3 = "wheel";
      # - incorrectly detected dependencies due to pbr
      fixtures = "wheel";
      testtools = "wheel";
      traceback2 = "wheel";
      # - Incorrectly merged extras - https://github.com/DavHau/mach-nix/pull/334
      tqdm = "wheel";

      # The version of Klein we get doesn't need / can't have the patch that
      # comes from the nixpkgs derivation mach-nix picks up from 21.05.
      klein = "wheel";
    };
  in
    rec {
      tahoe-lafs = mach-nix.buildPythonPackage rec {
        inherit python providers;
        name = "tahoe-lafs";
        version = "1.17.0";
        # See https://github.com/DavHau/mach-nix/issues/190
        requirementsExtra = ''
          pyrsistent < 0.17
          foolscap == 0.13.1
          configparser
          eliot
        '';
        postPatch = ''
          cat > src/allmydata/_version.py <<EOF
          # This _version.py is generated by nix.

          verstr = "${version}+git-${tahoe-lafs-repo.rev}"
          __version__ = verstr
          EOF
        '';
        src = tahoe-lafs-repo;
      };
      zkapauthorizer = mach-nix.buildPythonApplication rec {
        inherit python providers;
        src = lib.cleanSource ./.;
        # mach-nix does not provide a way to specify dependencies on other
        # mach-nix packages, that incorporates the requirements and overlays
        # of that package.
        # See https://github.com/DavHau/mach-nix/issues/123
        # In particular, we explicitly include the requirements of tahoe-lafs
        # here, and include it in a python package overlay.
        requirementsExtra = tahoe-lafs.requirements;
        overridesPre = [
          (
            self: super: {
              inherit tahoe-lafs;
            }
          )
        ];
        # Record some settings here, so downstream nix files can consume them.
        meta.mach-nix = { inherit python providers; };

        # Annoyingly duplicate the Klein fix from the Tahoe-LAFS expression.
        _.klein.patches = [];
      };

      privatestorage = let
        python-env = mach-nix.mkPython {
          inherit python providers;
          packagesExtra = [ zkapauthorizer tahoe-lafs ];
        };
      in
        # Since we use this derivation in `environment.systemPackages`,
        # we create a derivation that has just the executables we use,
        # to avoid polluting the system PATH with all the executables
        # from our dependencies.
        pkgs.runCommandNoCC "privatestorage" {}
          ''
            mkdir -p $out/bin
            ln -s ${python-env}/bin/tahoe $out/bin
            # Include some tools that are useful for debugging.
            ln -s ${python-env}/bin/flogtool $out/bin
            ln -s ${python-env}/bin/eliot-prettyprint $out/bin
          '';
    }
