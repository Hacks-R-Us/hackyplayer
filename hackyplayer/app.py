import datetime
import json
import os
import pathlib
import urllib.parse

import flask
import requests

from . import tasks

app = tasks.flask_app
app_cel = tasks.celery_app

app.config["api_route"] = "/api/v1"


def get_files(target, ext_filter=[]):
    try:
        for file in sorted(os.listdir(target)):
            path = os.path.join(target, file)
            if os.path.isfile(path):
                if os.path.splitext(file)[1] in ext_filter or ext_filter == []:
                    yield (os.path.splitext(file)[0])
    except FileNotFoundError:
        return None


@app.route("/")
def index():
    files = []
    for source in app.config["VIDEO_SOURCES"]:
        vid_dir = {
            "files": get_files(source["DISKDIR"], ext_filter=source["EXT"]),
            "dir": source["WEBDIR"],
            "name": source["NAME"],
        }
        files.append(vid_dir)

    running_tasks = app_cel.control.inspect().active()
    if running_tasks:
        for name, host in running_tasks.items():
            for task in host:
                task["time_start"] = datetime.datetime.fromtimestamp(
                    task["time_start"]
                ).strftime("%Y-%m-%d %H:%M:%S")
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

    # with urllib.request.urlopen("https://www.emfcamp.org/schedule/2024.json") as url:
    # with urllib.request.urlopen("https://www.emfcamp.org/schedule/2022.json") as url:
    with open(pathlib.Path(__file__).parent / "talks.json") as url:
        data = json.load(url)
        talks = {}
        for talk in data:
            if talk["type"] == "talk":
                talks[talk["id"]] = {
                    "title": talk["title"],
                    "presenter": talk["speaker"],
                }
        talks_sorted = dict(sorted(talks.items(), key=lambda k_v: k_v[1]["title"]))
    talks_json = json.dumps(talks_sorted)
    return flask.render_template("log.html", **locals())


def _update_grist(talk_id, grist_data):
    if "GRIST_TABLE_URL" not in app.config or "GRIST_KEY" not in app.config:
        return
    sess = requests.session()
    sess.headers.update(
        {
            "Authorization": f'Bearer {app.config["GRIST_KEY"]}',
        }
    )

    # Find the right ID
    resp = sess.get(app.config["GRIST_TABLE_URL"])
    resp.raise_for_status()
    for record in resp.json()["records"]:
        if str(record["fields"]["id2"]) == str(talk_id):
            talk_record = record
            break
    else:
        return  # couldn't find it :(

    # Patch
    resp = sess.patch(
        app.config["GRIST_TABLE_URL"],
        headers={"Content-Type": "application/json"},
        json={
            "records": [
                {
                    "id": talk_record["id"],
                    "fields": grist_data,
                }
            ],
        },
    )
    resp.raise_for_status()


@app.route(app.config["api_route"] + "/build", methods=["POST"])
def api_build():
    with open(pathlib.Path(__file__).parent / "talks.json") as url:
        data = json.load(url)

    description = None
    for talk in data:
        if talk["id"] == int(flask.request.form["talkid"]):
            filename = "{}_{}".format(flask.request.form["talkid"], talk["slug"])
            description = talk["description"]
            break
    else:
        filename = "{}".format(flask.request.form["talkid"])

    talk_data = {
        "title": flask.request.form["title"],
        "presenter": flask.request.form["presenter"],
        "filename": filename,
    }

    if description:
        talk_data["description"] = description

    vid_dir = str(pathlib.Path(flask.request.form["video"]).parts[0])
    for source in app.config["VIDEO_SOURCES"]:
        if source["WEBDIR"] == vid_dir:
            vid_dir_path = pathlib.Path(source["DISKDIR"])
            break
    else:
        raise ValueError(f"unknown video dir {vid_dir}")
    vid = pathlib.Path(flask.request.form["video"]).parts[1]
    grist_data = {
        "in_time": flask.request.form["start_tc"],
        "out_time": flask.request.form["end_tc"],
        "Source_file": vid,
    }
    if flask.request.form["talkid"]:
        _update_grist(flask.request.form["talkid"], grist_data)
    result = tasks.build_video.delay(
        str(vid_dir_path / vid),
        talk_data,
        flask.request.form["start_tc"],
        flask.request.form["end_tc"],
        out_dir=str(app.config["VIDEO_OUTPUT"]),
        temp_dir=str(app.config["VIDEO_TEMP"]),
        log_dir=str(app.config["LOG_DIR"]),
    )

    return {"result_id": result.id}


@app.route("/watchfolders", methods=["GET"])
def view_watchfolders():
    return flask.render_template("watchfolders.html", **locals())


@app.route("/tasks", methods=["GET"])
def view_tasks():
    return flask.render_template("tasks.html", **locals())


@app.route(app.config["api_route"] + "/tasks", methods=["GET"])
def api_tasks():
    running_tasks = app_cel.control.inspect().active()
    scheduled_tasks = app_cel.control.inspect().reserved()
    result = {"data": []}
    if running_tasks:
        for name, host in running_tasks.items():
            for task in host:
                if task["type"] == tasks.build_video.name:
                    state = app_cel.AsyncResult(task["id"])
                    state.ready()
                    progress = 0
                    if state.info and "current" in state.info and "total" in state.info:
                        progress = (state.info["current"] * 100) / state.info["total"]
                    result["data"].append(
                        {
                            "time_start": datetime.datetime.fromtimestamp(
                                task["time_start"]
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "id": task["id"],
                            "source": task["args"][0],
                            "title": task["args"][1]["title"],
                            "presenter": task["args"][1]["presenter"],
                            "in_tc": task["args"][2],
                            "out_tc": task["args"][3],
                            "node": task["hostname"],
                            "state": state.state,
                            "progress": f"{progress:.1f}%",
                        }
                    )

    if scheduled_tasks:
        for name, host in scheduled_tasks.items():
            for task in host:
                if task["type"] == tasks.build_video.name:
                    state = app_cel.AsyncResult(task["id"])
                    state.ready()
                    result["data"].append(
                        {
                            "time_start": None,
                            "id": task["id"],
                            "source": task["args"][0],
                            "title": task["args"][1]["title"],
                            "presenter": task["args"][1]["presenter"],
                            "in_tc": task["args"][2],
                            "out_tc": task["args"][3],
                            "node": task["hostname"],
                            "state": state.state,
                            "progress": "0%",
                        }
                    )
    return flask.jsonify(result)


@app.route(app.config["api_route"] + "/watch", methods=["GET"])
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
                "node": None,
            }
        )

    if running_tasks:
        for name, host in running_tasks.items():
            for task in host:
                if task["type"] == tasks.watch_folder.name:
                    for folder in result["data"]:
                        if folder["folder"] == task["args"][0]:
                            folder["time_start"] = (
                                datetime.datetime.fromtimestamp(
                                    task["time_start"]
                                ).strftime("%Y-%m-%d %H:%M:%S"),
                            )
                            folder["id"] = task["id"]
                            folder["folder"] = (task["args"][0],)
                            folder["node"] = task["hostname"]
    return flask.jsonify(result)


@app.route(app.config["api_route"] + "/watch/<folder>", methods=["DELETE"])
def api_watch_stop(folder: str):
    folder_config = None
    for conf in app.config["WATCHFOLDERS"]:
        if conf["NAME"] == urllib.parse.unquote(folder):
            folder_config = conf

    if not folder_config:
        return flask.jsonify({"success": False})

    fullpath = folder_config["FULLPATH"]

    for node, running_tasks in app_cel.control.inspect().active().items():
        for task in running_tasks:
            if (task["args"][0] == str(fullpath) or folder is None) and task[
                "type"
            ] == tasks.watch_folder.name:
                app_cel.control.revoke(task["id"], terminate=True)
    return flask.jsonify({"success": True})


@app.route(app.config["api_route"] + "/watch/<folder>", methods=["PUT"])
def api_watch_start(folder):
    for folder_config in app.config["WATCHFOLDERS"]:
        if folder_config["NAME"] == folder:
            task = tasks.watch_folder.delay(
                str(folder_config["FULLPATH"]), str(folder_config["OUTPUT_DIR"])
            )
            result = {"data": {"id": task.id}, "success": True}
            break
    else:
        result = {"success": False}
    return flask.jsonify(result)


@app.route(app.config["api_route"] + "/ingest", methods=["GET"])
def api_ingest():
    running_tasks = app_cel.control.inspect().active()
    result = {"data": []}

    if running_tasks:
        for name, host in running_tasks.items():
            for task in host:
                if task["type"] == tasks.ingest_video.name:
                    state = app_cel.AsyncResult(task["id"])
                    state.ready()
                    progress = 0
                    if state.info and "current" in state.info and "total" in state.info:
                        progress = (state.info["current"] * 100) / state.info["total"]
                    result["data"].append(
                        {
                            "time_start": datetime.datetime.fromtimestamp(
                                task["time_start"]
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "id": task["id"],
                            "input": task["args"][0],
                            "node": task["hostname"],
                            "progress": f"{progress:.1f}%",
                        }
                    )
    return flask.jsonify(result)


@app.route(app.config["api_route"] + "/ingest/<taskid>", methods=["DELETE"])
def api_ingest_stop(taskid=None):
    for node, running_tasks in app_cel.control.inspect().active().items():
        for task in running_tasks:
            if task["id"] == taskid and task["type"] == tasks.ingest_video.name:
                app_cel.control.revoke(task["id"], terminate=True)
    return flask.jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True)
