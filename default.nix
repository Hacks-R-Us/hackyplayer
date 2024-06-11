{ sources ? import ./nix/sources.nix
, pkgs ? import sources.nixpkgs { }
, poetry2nix ? import sources.poetry2nix { inherit pkgs; }
}:

let
  hackyplayer = poetry2nix.mkPoetryApplication {
    groups = [ "prod" ];
    projectDir = ./.;
    overrides = poetry2nix.overrides.withDefaults (final: prev: {
      celery-singleton = prev.celery-singleton.overridePythonAttrs (old: {
        postPatch = ''
          substituteInPlace pyproject.toml \
            --replace-fail "poetry.masonry.api" "poetry.core.masonry.api"
        '';
      });
    });
  };
in
  hackyplayer.dependencyEnv
