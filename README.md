# Installation
- Install redis (or other Celery-compatible broker)
- Clone repo
- Create venv
- Install python requirements
- Make the following directories:
  - <install_dir>/static/video/input
  - <install_dir>/static/video/output
  - <install_dir>/temp

# Config
Create config_local.py next to config.py

    import pathlib

    CONFIG = {
        "VIDEO_SOURCE": pathlib.Path("somepath"),
        "VIDEO_OUTPUT": pathlib.Path("someotherpath"),
        "VIDEO_TEMP": pathlib.Path("yetanotherpath")
    }

Any entries you leave out will use defaults.

Rember to configure whatever websever you're using to serve source and output folders under /static/video/source and /static/video/output

# Running
## Development
In seperate consoles/screens/tmux windows, after activating the venv, run each of the following:

    flask run --debug
    Celery -A tasks worker --loglevel INFO

And you should have a server running at localhost:5000

## Production
Use gunicorn or another WSGI server. Make Celery run as a service or something? I dunno, still figuring this bit out