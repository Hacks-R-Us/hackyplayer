{ sources ? import ./nix/sources.nix
, pkgs ? import sources.nixpkgs { }
, poetry2nix ? import sources.poetry2nix { inherit pkgs; }
, lib ? pkgs.lib
}:

let
  hackyplayer' = groups: poetry2nix.mkPoetryApplication {
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
  hackyplayerProd = hackyplayer' [ "prod" ];
  hackyplayerDev = hackyplayer' [ "dev" ];

  ffmpeg = pkgs.ffmpeg_7-full;  # we need librsvg support (-full)

  fontconfigConf = pkgs.makeFontsConf {
    fontDirectories = [
      (lib.sources.sourceFilesBySuffices ./hackyplayer/resources [ ".ttf" ])
    ];
  };
  ffmpegWrapper = pkgs.writeShellScript "ffmpeg-wrapper" ''
    export FONTCONFIG_FILE="${fontconfigConf}"
    export LADSPA_PATH="${lib.getLib pkgs.master_me}/lib/ladspa"
    exec "${lib.getExe' ffmpeg "ffmpeg"}" "$@"
  '';
in
  (hackyplayerProd.dependencyEnv.override {
    app = hackyplayerProd.overridePythonAttrs (old: {
      postPatch = ''
        ${old.postPatch or ""}

        substituteInPlace hackyplayer/formvideo.py \
          --replace-fail 'FFMPEG_BIN = "ffmpeg"' 'FFMPEG_BIN = "${ffmpegWrapper}"' \
          --replace-fail 'FFPROBE_BIN = "ffprobe"' 'FFPROBE_BIN = "${lib.getExe' ffmpeg "ffprobe"}"' \
          --replace-fail 'IMAGEMAGICK_BIN = "convert"' 'IMAGEMAGICK_BIN = "${lib.getExe' pkgs.imagemagick "convert"}"' \
          --replace-fail 'APP_ROOT = Path(".")' 'APP_ROOT = Path("${placeholder "out"}/${hackyplayerProd.python.sitePackages}/hackyplayer")'
      '';
    });
  }) // {
    inherit fontconfigConf ffmpegWrapper ffmpeg;

    shell = pkgs.mkShell {
      packages = [ ffmpeg pkgs.imagemagick ];

      inputsFrom = [ hackyplayerDev ];

      shellHook = ''
        export FONTCONFIG_FILE="${fontconfigConf}"
        export LADSPA_PATH="${lib.getLib pkgs.master_me}/lib/ladspa"
      '';
    };
  }
