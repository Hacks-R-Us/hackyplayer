import logging
import os
import pathlib
import signal
import time

import celery
import celery_singleton

import config
import formvideo

logger = logging.getLogger(__name__)

flask_app = config.create_app()
celery_app = flask_app.extensions["celery"]

class ErrSigTerm(Exception):
    pass

@celery.shared_task(ignore_result=False, bind=True)
def build_video(self, *args, **kwargs):
    result = formvideo.form_video(self, *args, **kwargs)
    return result

@celery.shared_task(ignore_result=False)
def ingest_video(input_file, output_dir):
    result = formvideo.ingest_video(input_file, output_dir)
    return result

@celery.shared_task(base=celery_singleton.Singleton, ignore_result=False)
def watch_folder(watch, output_dir="static/video/source"):

    watch = pathlib.Path(watch)

    def stop_running(signum, frame):
        raise ErrSigTerm()

    signal.signal(signal.SIGTERM, stop_running)
    #signal.signal(signal.SIGINT, stop_running)

    logger.info("Starting watchfolder: '%s'", watch)
    i=0

    files = {}
    
    try:
        while True:
            logger.debug("Scanning '%s' for new files", watch)
            old_files = files
            files = {}
            try:
                file_list = [f for f in os.listdir(watch) if os.path.isfile(pathlib.Path.joinpath(watch, f))]
            except FileNotFoundError:
                logger.error("Folder on disk doesn't exist or is inaccessible: %s", watch)
                break
            for video in file_list:
                files[video] = {}
                new_file = files[video]

                stats = os.stat(pathlib.Path.joinpath(watch, pathlib.Path(video)))
                new_file["st_size"] = stats.st_size
                new_file["st_mtime"] = stats.st_mtime
                
                new_file["processing"] = False
                new_file["pass"] = 0
                try:
                    old_file = old_files[video]
                except KeyError:
                    new_file["pass"] = 1
                    continue
                if old_file["processing"]:
                    new_file["processing"] = old_file["processing"]
                    continue
                if old_file["st_size"] == new_file["st_size"] or old_file["st_mtime"] == new_file["st_mtime"]:
                    logger.debug("'%s': same size and mtime, pass %s", video, old_file["pass"] + 1)
                    new_file["pass"] = old_file["pass"] + 1
                if new_file["pass"] >= 3:
                    logger.info("'%s': 3 passes with no changes, starting processing", video)
                    result = ingest_video.delay(str(pathlib.Path.joinpath(watch, pathlib.Path(video))), str(output_dir))
                    new_file["processing"] = result.id
            time.sleep(5)
            i += 1
    except ErrSigTerm:
        logger.info("Stopping watchfolder: '%s'", watch)