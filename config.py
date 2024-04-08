# System
import pathlib

# PIP
import celery
import flask

DEFAULT_CONFIG = {
    "VIDEO_SOURCE": pathlib.Path("static/video/source"),
    "VIDEO_OUTPUT": pathlib.Path("static/video/output"),
    "VIDEO_TEMP": pathlib.Path("temp")
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
    app.config.from_mapping(
        CELERY=dict(
            broker_url="redis://localhost",
            result_backend="redis://localhost",
            task_ignore_result=True,
        ),
    )
    app.config.from_prefixed_env()
    celery_init_app(app)
    return app