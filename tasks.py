import time

import celery

import config
import formvideo

flask_app = config.create_app()
celery_app = flask_app.extensions["celery"]

@celery.shared_task(ignore_result=False)
def long_running_task(iterations):
    result = 0
    for i in range(iterations):
        result += i
        time.sleep(2) 
    return result

@celery.shared_task(ignore_result=False)
def build_video(video_file, talk_data, start_tc, end_tc):
    result = formvideo.form_video(video_file, talk_data, start_tc, end_tc)
    return result