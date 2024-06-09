# System
import datetime
import json
import os
import pathlib
import urllib

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

app.config["api_route"] = "/api/v1"

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
    files = []
    for source in app.config["VIDEO_SOURCES"]:
        vid_dir = {
            "files": get_files(source["DISKDIR"], ext_filter = source["EXT"]),
            "dir": source["WEBDIR"],
            "name": source["NAME"]
        }
        files.append(vid_dir)

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
    for source in app.config["VIDEO_SOURCES"]:
        if source["WEBDIR"] == vid_dir:
            if ".mp4" in source["EXT"]:
                vid_type = "mp4"
                vid_ext = "mp4"
            if ".mpd" in source["EXT"]:
                vid_type = "dash"
                vid_ext = "mpd"

    #with urllib.request.urlopen("https://www.emfcamp.org/schedule/2024.json") as url:
    #with urllib.request.urlopen("https://www.emfcamp.org/schedule/2022.json") as url:
    with open("talks.json") as url:
        data = json.load(url)
        talks = {}
        for talk in data:
            if talk["type"] == "talk":
                talks[talk["id"]] = {"title": talk["title"], "presenter": talk["speaker"]}
        talks_sorted = dict(sorted(talks.items(), key=lambda k_v: k_v[1]["title"]))
    talks_json = json.dumps(talks_sorted)
    return flask.render_template("log.html", **locals())

@app.route(app.config["api_route"]+"/build", methods=['POST'])
def api_build():

    with open("talks.json") as url:
        data = json.load(url)

    description = None
    for talk in data:
        if talk["id"] == int(flask.request.form['talkid']):
            filename = "{}_{}".format(flask.request.form['talkid'], talk["slug"])
            description = talk["description"]
            break
    else:
        filename = "{}".format(flask.request.form['talkid'])

    talk_data = {
        "title": flask.request.form['title'],
        "presenter": flask.request.form['presenter'],
        "filename": filename,
    }

    if description:
        talk_data["description"] = description

    vid_dir = str(pathlib.Path(flask.request.form['video']).parts[0])
    for source in app.config["VIDEO_SOURCES"]:
        if source["WEBDIR"] == vid_dir:
            vid_dir_path = source["DISKDIR"]
    vid = pathlib.Path(flask.request.form['video']).parts[1]
    result = tasks.build_video.delay(
        str(pathlib.Path.joinpath(vid_dir_path, vid)), 
        talk_data, 
        flask.request.form['start_tc'], 
        flask.request.form['end_tc'],
        out_dir = str(app.config["VIDEO_OUTPUT"]),
        temp_dir = str(app.config["VIDEO_TEMP"])
    )

    return {"result_id": result.id}

@app.route("/watchfolders", methods=["GET"])
def view_watchfolders():
    return flask.render_template("watchfolders.html", **locals())

@app.route("/tasks", methods=["GET"])
def view_tasks():
    return flask.render_template("tasks.html", **locals())

@app.route(app.config["api_route"]+"/tasks", methods=["GET"])
def api_tasks():
    running_tasks = app_cel.control.inspect().active()
    scheduled_tasks = app_cel.control.inspect().reserved()
    result = {"data": []}
    if running_tasks:
        for name,host in running_tasks.items():
            for task in host:
                if task["type"] == "tasks.build_video":
                    state = app_cel.AsyncResult(task["id"])
                    state.ready()
                    result["data"].append({
                        "time_start": datetime.datetime.fromtimestamp(task["time_start"]).strftime('%Y-%m-%d %H:%M:%S'),
                        "id": task["id"],
                        "source": task["args"][0],
                        "title": task["args"][1]["title"],
                        "presenter": task["args"][1]["presenter"],
                        "in_tc": task["args"][2],
                        "out_tc": task["args"][3],
                        "node": task["hostname"],
                        "state": state.state
                    })

    if scheduled_tasks:
        for name,host in scheduled_tasks.items():
            for task in host:
                if task["type"] == "tasks.build_video":
                    state = app_cel.AsyncResult(task["id"])
                    state.ready()
                    result["data"].append({
                        "time_start": None,
                        "id": task["id"],
                        "source": task["args"][0],
                        "title": task["args"][1]["title"],
                        "presenter": task["args"][1]["presenter"],
                        "in_tc": task["args"][2],
                        "out_tc": task["args"][3],
                        "node": task["hostname"],
                        "state": state.state
                    })
    return flask.jsonify(result)

@app.route(app.config["api_route"]+"/watch", methods=["GET"])
def api_watch():
    running_tasks = app_cel.control.inspect().active()
    result = {"data": []}

    for folder in app.config["WATCHFOLDERS"]:
        result["data"].append(
            {
                "time_start": None,
                "id": None,
                "name": str(folder["NAME"]),
                "folder": str(folder["FULLPATH"]),
                "node": None
            }
        )

    if running_tasks:
        for name,host in running_tasks.items():
            for task in host:
                if task["type"] == "tasks.watch_folder":
                    for folder in result["data"]:
                        if folder["folder"] == task["args"][0]:
                            folder["time_start"] = datetime.datetime.fromtimestamp(task["time_start"]).strftime('%Y-%m-%d %H:%M:%S'),
                            folder["id"] = task["id"]
                            folder["folder"] = task["args"][0],
                            folder["node"] = task["hostname"]
    return flask.jsonify(result)

@app.route(app.config["api_route"]+"/watch/<folder>", methods=["DELETE"])
def api_watch_stop(folder=None):
    folder_config = None
    for conf in app.config["WATCHFOLDERS"]:
        if conf["NAME"] == urllib.parse.unquote(folder):
            folder_config = conf
    
    if not folder_config:
        return flask.jsonify({'success':False})
    
    fullpath = folder_config["FULLPATH"]

    for node,tasks in app_cel.control.inspect().active().items():
        for task in tasks:
            if (task["args"][0] == str(fullpath) or folder == None) and task["type"] == "tasks.watch_folder":
                app_cel.control.revoke(task["id"], terminate=True)
    return flask.jsonify({'success':True})

@app.route(app.config["api_route"]+"/watch/<folder>", methods=["PUT"])
def api_watch_start(folder):
    for folder_config in app.config["WATCHFOLDERS"]:
        if folder_config["NAME"] == folder:
            task = tasks.watch_folder.delay(str(folder_config["FULLPATH"]), str(folder_config["OUTPUT_DIR"]))
            result = {
                "data": {
                    "id": task.id
                },
                "success": True
            }
            break
    else:
        result = {
            "success": False
        }
    return flask.jsonify(result)

@app.route(app.config["api_route"]+"/ingest", methods=["GET"])
def api_ingest():
    running_tasks = app_cel.control.inspect().active()
    result = {"data": []}

    if running_tasks:
        for name,host in running_tasks.items():
            for task in host:
                if task["type"] == "tasks.ingest_video":
                    result["data"].append({
                        "time_start": datetime.datetime.fromtimestamp(task["time_start"]).strftime('%Y-%m-%d %H:%M:%S'),
                        "id": task["id"],
                        "input": task["args"][0],
                        "node": task["hostname"]
                    })
    return flask.jsonify(result)

@app.route(app.config["api_route"]+"/ingest/<taskid>", methods=["DELETE"])
def api_ingest_stop(taskid=None):

    for node,tasks in app_cel.control.inspect().active().items():
        for task in tasks:
            if task["id"] == taskid and task["type"] == "tasks.ingest_video":
                app_cel.control.revoke(task["id"], terminate=True)
    return flask.jsonify({'success':True})

if __name__ == "__main__":
    app.run(debug=True)