import time

import celery

import config
import formvideo

flask_app = config.create_app()
celery_app = flask_app.extensions["celery"]

@celery.shared_task(ignore_result=False)
def build_video(*args, **kwargs):
    result = formvideo.form_video(*args, **kwargs)
    return result