# System
import pathlib

# PIP
import celery
import flask

DEFAULT_CONFIG = {
    "VIDEO_SOURCES": [
        {
            "DISKDIR": pathlib.Path("static/video/source"),
            "WEBDIR": "source",
            "EXT": [".mp4"],
            "NAME": "Source",
        },
        {
            "DISKDIR": pathlib.Path("static/video/output"),
            "WEBDIR": "output",
            "EXT": [".mp4"],
            "NAME": "Output",
        },
        {
            "DISKDIR": pathlib.Path("static/video/live"),
            "WEBDIR": "live",
            "EXT": [".mpd"],
            "NAME": "Live",
        },
    ],
    "VIDEO_OUTPUT": pathlib.Path("static/video/output"),
    "VIDEO_TEMP": pathlib.Path("temp"),
    "WATCHFOLDERS": [
        {
            "NAME": "input",
            "FULLPATH": pathlib.Path("static/video/input"),
            "OUTPUT_DIR": pathlib.Path("static/video/source"),
        }
    ],
    "CELERY": {
        "broker_url": "redis://localhost",
        "result_backend": "redis://localhost",
        "task_ignore_result": False,
    },
    "LOG_DIR": pathlib.Path("logs"),
}


def celery_init_app(app):
    class FlaskTask(celery.Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = celery.Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


def create_app():
    app = flask.Flask(__name__)

    # Load default settings
    app.config.update(DEFAULT_CONFIG)

    # Load local settings
    try:
        import config_local  # pyright: ignore

        app.config.update(config_local.CONFIG)
    except (ImportError, AttributeError):
        pass

    app.config.from_prefixed_env()
    celery_init_app(app)
    return app
