{ sources ? import ./nix/sources.nix
, pkgs ? import sources.nixpkgs { }
, poetry2nix ? import sources.poetry2nix { inherit pkgs; }
, lib ? pkgs.lib
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
  hackyplayer.dependencyEnv.override {
    app = hackyplayer.overridePythonAttrs (old: {
      postPatch = ''
        ${old.postPatch or ""}

        substituteInPlace hackyplayer/formvideo.py \
          --replace-fail 'FFMPEG_BIN = "ffmpeg"' 'FFMPEG_BIN = "${lib.getExe' pkgs.ffmpeg "ffmpeg"}"' \
          --replace-fail 'IMAGEMAGICK_BIN = "convert"' 'IMAGEMAGICK_BIN = "${lib.getExe' pkgs.imagemagick "convert"}"'
      '';
    });
  }
