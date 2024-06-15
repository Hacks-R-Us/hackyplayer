# Installation
- Install redis (or other Celery-compatible broker)
- Install ffmpeg and imagemagick
- Clone repo
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
In seperate consoles/screens/tmux windows, run each of the following:

    poetry run flask --app hackyplayer.app run --debug
    celery -A hackyplayer.tasks worker --loglevel INFO

And you should have a server running at localhost:5000

## Production
Use gunicorn or another WSGI server. Make Celery run as a service or something? I dunno, still figuring this bit out
