# System
import datetime
import os
import pathlib

# PIP
import flask

# Local
import config
import tasks

app = tasks.flask_app
app_cel = tasks.celery_app

# Load default settings
app.config.update(config.DEFAULT_CONFIG)

# Load local settings
try:
    import config_local
    app.config.update(config_local.CONFIG)
except (ImportError, AttributeError):
    pass


def get_files(target):
    for file in sorted(os.listdir(target)):
        path = os.path.join(target, file)
        if os.path.isfile(path):
            yield (
                os.path.splitext(file)[0]
            )

@app.route("/")
def index():
    sources = get_files(app.config["VIDEO_SOURCE"])
    outputs = get_files(app.config["VIDEO_OUTPUT"])
    running_tasks = app_cel.control.inspect().active()
    if running_tasks:
        for name,host in running_tasks.items():
            for task in host:
                task["time_start"] = datetime.datetime.fromtimestamp(task["time_start"]).strftime('%Y-%m-%d %H:%M:%S')
    else:
        running_tasks = {"": []}
    return flask.render_template("index.html", **locals())

@app.route("/log/<vid_dir>/<video>")
def log(vid_dir, video):
    return flask.render_template("log.html", vid_dir=vid_dir, video=video)

@app.route("/build", methods=['POST'])
def build_video():
    talk_data = {
        "title": "This is a talk",
        "presenter": "A. N. Other"
    }
    result = tasks.build_video.delay(
        str(pathlib.Path.joinpath(app.config["VIDEO_SOURCE"], pathlib.Path(flask.request.form['video']))), 
        talk_data, 
        flask.request.form['start_tc'], 
        flask.request.form['end_tc'],
        out_dir = str(app.config["VIDEO_OUTPUT"]),
        temp_dir = str(app.config["VIDEO_TEMP"])
    )

    return {"result_id": result.id}

@app.get("/tasks")
def view_tasks():
    i = app_cel.control.inspect()
    return flask.jsonify(i.active())


if __name__ == "__main__":
    app.run(debug=True)