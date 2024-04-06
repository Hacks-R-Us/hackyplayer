import datetime
import os
from pathlib import Path

from flask import Flask, render_template, request
import flask

import tasks

app = tasks.flask_app
app_cel = tasks.celery_app

def get_files(target):
    for file in sorted(os.listdir(target)):
        path = os.path.join(target, file)
        if os.path.isfile(path):
            yield (
                os.path.splitext(file)[0]
            )

@app.route("/")
def index():
    sources = get_files("static/video/source")
    outputs = get_files("static/video/output")
    running_tasks = app_cel.control.inspect().active()
    for name,host in running_tasks.items():
        for task in host:
            task["time_start"] = datetime.datetime.fromtimestamp(task["time_start"]).strftime('%Y-%m-%d %H:%M:%S')
    return render_template("index.html", **locals())

@app.route("/log/<vid_dir>/<video>")
def log(vid_dir, video):
    return render_template("log.html", vid_dir=vid_dir, video=video)

@app.route("/build", methods=['POST'])
def build_video():
    talk_data = {
        "title": "This is a talk",
        "presenter": "A. N. Other"
    }
    result = tasks.build_video.delay(
        str(Path.joinpath(Path("static/video/source"), Path(request.form['video']))), 
        talk_data, 
        request.form['start_tc'], 
        request.form['end_tc']
    )

    return {"result_id": result.id}

@app.get("/tasks")
def view_tasks():
    i = app_cel.control.inspect()
    return flask.jsonify(i.active())


if __name__ == "__main__":
    app.run(debug=True)