# Installation
- Install redis (or other Celery-compatible broker)
- Install ffmpeg and imagemagick
- Clone repo
- Pick an adventure
  - Lix (or Nix)
    - `nix-shell -A shell`
  - Manual
    - Install ffmpeg and imagemagick
    - Install https://github.com/trummerschlunk/master_me as a LADSPA plugin (or make sure it's on your `LADSPA_PATH`)
    - Run `poetry install`
- Make the following directories:
  - <install_dir>/static/video/input
  - <install_dir>/static/video/output
  - <install_dir>/temp

# Config

Use environment variables, prefixed with `FLASK_`. Flask supports automatically parsing values as JSON, which can be useful for specifying some settings.

```
FLASK_VIDEO_SOURCE=somepath
FLASK_WATCHFOLDERS='[{"FULLPATH":"/store/emf/2024/video/input","NAME":"input","OUTPUT_DIR":"/store/emf/2024/video/source"}]'
```

Any entries you leave out will use defaults.

Rember to configure whatever websever you're using to serve source and output folders under /static/video/source and /static/video/output

# Running
## Development
In seperate consoles/screens/tmux windows, run each of the following - if you
installed manually, prefix with `poetry run`; if you used Lix/Nix, run inside
the `nix-shell -A shell`:

    flask --app hackyplayer.app run --debug
    celery -A hackyplayer.tasks worker --loglevel INFO

And you should have a server running at localhost:5000

## Production
Use gunicorn or another WSGI server. Make Celery run as a service or something? I dunno, still figuring this bit out
