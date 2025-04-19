{ sources ? import ./nix/sources.nix
, pkgs ? import sources.nixpkgs { }
, lib ? pkgs.lib
, pyproject-nix ? import sources."pyproject.nix" { inherit lib; }
, uv2nix ? import sources.uv2nix { inherit lib pyproject-nix; }
, pyproject-build-systems ? import sources.build-system-pkgs { inherit uv2nix pyproject-nix lib; }
}:

let
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

  overlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel";
  };

  python = pkgs.python3;

  pyprojectOverrides = final: prev: {
    # for build fixups
    hackyplayer = prev.hackyplayer.overrideAttrs (old: {
      postPatch = ''
        ${old.postPatch or ""}

        substituteInPlace hackyplayer/formvideo.py \
          --replace-fail 'FFMPEG_BIN = "ffmpeg"' 'FFMPEG_BIN = "${ffmpegWrapper}"' \
          --replace-fail 'FFPROBE_BIN = "ffprobe"' 'FFPROBE_BIN = "${lib.getExe' ffmpeg "ffprobe"}"' \
          --replace-fail 'IMAGEMAGICK_BIN = "convert"' 'IMAGEMAGICK_BIN = "${lib.getExe' pkgs.imagemagick "convert"}"' \
          --replace-fail 'APP_ROOT = Path(".")' 'APP_ROOT = Path("${placeholder "out"}/${python.sitePackages}/hackyplayer")'
      '';
    });
  };

  pythonSet = (pkgs.callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (lib.composeManyExtensions [
    pyproject-build-systems.default
    overlay
    pyprojectOverrides
  ]);

  hackyplayer = pythonSet.mkVirtualEnv "hackyplayer-env" {
    hackyplayer = [ "prod" ];
  };

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
  hackyplayer // {
    inherit fontconfigConf ffmpegWrapper ffmpeg python workspace;

    shell = let
      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
        members = [ "hackyplayer" ];
      };
      editablePythonSet = pythonSet.overrideScope (
        lib.composeManyExtensions [
          editableOverlay
          (final: prev: {
            hackyplayer = prev.hackyplayer.overrideAttrs (old: {
              src = lib.fileset.toSource {
                root = old.src;
                fileset = lib.fileset.unions [
                  (old.src + "/pyproject.toml")
                  (old.src + "/README.md")
                  (old.src + "/hackyplayer")
                ];
              };
              nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem {
                editables = [];
              };
            });
          })
        ]
      );
      virtualenv = editablePythonSet.mkVirtualEnv "hackyplayer-dev-env" {
        hackyplayer = [ "dev" ];
      };
    in pkgs.mkShell {
      packages = [ ffmpeg pkgs.imagemagick pkgs.uv pkgs.nodejs virtualenv ];

      env = {
        # Don't create venv using uv
        UV_NO_SYNC = "1";

        # Force uv to use Python interpreter from venv
        UV_PYTHON = "${virtualenv}/bin/python";

        # Prevent uv from downloading managed Pythons
        UV_PYTHON_DOWNLOADS = "never";
      };

      shellHook = ''
        export FONTCONFIG_FILE="${fontconfigConf}"
        export LADSPA_PATH="${lib.getLib pkgs.master_me}/lib/ladspa"
        export PYRIGHT_PYTHON_GLOBAL_NODE=true

        unset PYTHONPATH
        export REPO_ROOT=$(git rev-parse --show-toplevel)
      '';
    };
  }
