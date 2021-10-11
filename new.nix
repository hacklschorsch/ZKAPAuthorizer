let
  sources = import nix/sources.nix;
in
{ pkgs ? import sources.release2015 {}
, pypiData ? sources.pypi-deps-db
, mach-nix ? import sources.mach-nix { inherit pkgs pypiData; }
}:
  let
    providers = {
      _default = "sdist,nixpkgs,wheel";
      tahoe-lafs = "nixpkgs,sdist";
      # not packaged in nixpkgs at all, we can use the binary wheel from
      # pypi though.
      python-challenge-bypass-ristretto = "wheel";
      # Pure python packages that don't build correctly from sdists
      # - patches in nixpkgs that don't apply
      # - missing build dependencies
      platformdirs = "wheel";
      boltons = "wheel";
      klein = "wheel";
      humanize = "wheel";
      chardet = "wheel";
      urllib3 = "wheel";
      zipp = "wheel";
    };
    tahoe-lafs = mach-nix.buildPythonPackage {
      python = "python27";
      pname = "tahoe-lafs";
      version = "1.16.0rc1";
      inherit providers;
      #inherit requirements providers;
      # See https://github.com/DavHau/mach-nix/issues/190
      requirementsExtra = ''
        pyrsistent
        foolscap == 0.13.1
        configparser
        eliot
      '';
      postPatch = ''
        cat > src/allmydata/_version.py <<EOF
        # This _version.py is generated by nix.

        verstr = "$version"
        __version__ = verstr
        EOF
      '';
      src = pkgs.fetchFromGitHub {
        owner = "fenn-cs";
        repo = "tahoe-lafs";
        rev = "f6a96ae3976ee21ad0376f7b6a22fc3d12110dce";
        sha256 = "ZN2V5vH+VqPaBmQXXqyH+vUiqW1YNhz+7LsiNNhA/4g=";
      };
    };
  in
    mach-nix.buildPythonApplication rec {
      python = "python27";
      name = "zero-knowledge-access-pass-authorizer";
      src = ./.;
      inherit providers;
      requirements = builtins.readFile ./requirements/base.txt;
      overridesPre = [
        (
          self: super: {
            inherit tahoe-lafs;
          }
        )
      ];
      format = "setuptools";
      # Record some settings here, so downstream nix files can consume them.
      meta.mach-nix = { inherit python providers; };
    }
