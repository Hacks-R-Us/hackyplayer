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
  ffmpeg = pkgs.ffmpeg-full;  # we need librsvg support

  fontconfigConf = pkgs.makeFontsConf {
    fontDirectories = [
      (lib.sources.sourceFilesBySuffices ./hackyplayer/resources [ ".ttf" ])
    ];
  };
  ffmpegWrapper = pkgs.writeShellScript "ffmpeg-wrapper" ''
    export FONTCONFIG_FILE="${fontconfigConf}"
    exec "${lib.getExe' ffmpeg "ffmpeg"}" "$@"
  '';
in
  (hackyplayer.dependencyEnv.override {
    app = hackyplayer.overridePythonAttrs (old: {
      postPatch = ''
        ${old.postPatch or ""}

        substituteInPlace hackyplayer/formvideo.py \
          --replace-fail 'FFMPEG_BIN = "ffmpeg"' 'FFMPEG_BIN = "${ffmpegWrapper}"' \
          --replace-fail 'IMAGEMAGICK_BIN = "convert"' 'IMAGEMAGICK_BIN = "${lib.getExe' pkgs.imagemagick "convert"}"' \
          --replace-fail 'APP_ROOT = Path(".")' 'APP_ROOT = Path("${placeholder "out"}/${hackyplayer.python.sitePackages}/hackyplayer")'
      '';
    });
  }) // {
    inherit fontconfigConf ffmpegWrapper;
  }
