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

def get_files(target, ext_filter = []):
    for file in sorted(os.listdir(target)):
        path = os.path.join(target, file)
        if os.path.isfile(path):
            if os.path.splitext(file)[1] in ext_filter or ext_filter == []:
                yield (
                    os.path.splitext(file)[0]
                )

@app.route("/")
def index():
    sources = get_files(app.config["VIDEO_SOURCE"], ext_filter = [".mp4"])
    outputs = get_files(app.config["VIDEO_OUTPUT"], ext_filter = [".mp4"])
    live = get_files(app.config["VIDEO_LIVE"], ext_filter = [".mpd"])
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
    if vid_dir == "live":
        vid_type = "dash"
        vid_ext = "mpd"
    else:
        vid_type = "mp4"
        vid_ext = "mp4"
    return flask.render_template("log.html", **locals())

@app.route("/build", methods=['POST'])
def build_video():

    talk_data = {
        "title": flask.request.form['title'],
        "presenter": flask.request.form['presenter']
    }
    vid_dir = pathlib.Path(flask.request.form['video']).parts[0]
    vid = pathlib.Path(flask.request.form['video']).parts[1]
    result = tasks.build_video.delay(
        str(pathlib.Path.joinpath(app.config["VIDEO_{}".format(vid_dir).upper()], vid)), 
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