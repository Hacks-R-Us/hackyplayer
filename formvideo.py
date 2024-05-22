from pathlib import Path
import subprocess
import datetime
import logging
import math
import os.path
import shutil

logger = logging.getLogger("__name__")

logger.setLevel(logging.DEBUG)

FFMPEG_BIN = "ffmpeg"
IMAGEMAGICK_BIN = "convert"
FRAMERATE = 50

TEMP_DIR = Path("temp/")
OUT_DIR = Path("static/video/output")
LOG_DIR = Path("logs/")

def timecode_split(timecode, framerate = FRAMERATE):
    
    splits = timecode.split(":")
    hours = int(splits[0])
    minutes = int(splits[1])
    seconds = int(splits[2])
    frames = int(splits[3])

    assert hours < 24
    assert minutes < 60
    assert seconds < 60
    assert frames < framerate

    return (hours, minutes, seconds, frames)

def timecode_to_seconds(timecode, framerate = FRAMERATE):
    hours,minutes,seconds,frames = timecode_split(timecode, framerate)

    return (hours * 60 * 60) + (minutes * 60) + (seconds) + (frames/framerate)

def timecode_to_timestamp(timecode, framerate = FRAMERATE):
    hours,minutes,seconds,frames = timecode_split(timecode, framerate)

    return "{:02d}:{:02d}:{:02d}.{:02d}".format(hours, minutes, seconds, int(frames*100/framerate))


def form_video(video, talk, start_tc, end_tc, framerate = FRAMERATE, out_dir = OUT_DIR, temp_dir = TEMP_DIR):

    end_dur = 10
    end_fade = 2

    start_s = timecode_to_seconds(start_tc)
    end_s = timecode_to_seconds(end_tc)

    start_ts = timecode_to_timestamp(start_tc)
    end_ts = timecode_to_timestamp(end_tc)

    fade_offset = end_s - start_s - 1

    start_png = Path.joinpath(Path(temp_dir), Path("start.png"))
    end_png = Path.joinpath(Path(temp_dir), Path("end.png"))

    start_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    try:
        filename = talk["filename"] + "-" + start_timestamp
    except KeyError:
        filename = start_timestamp

    output_file = Path(filename + ".mp4")
    log_file = Path(filename + ".log")
    output_path = Path.joinpath(Path(out_dir), output_file)
    log_path = Path.joinpath(Path(LOG_DIR), log_file)

    start_lt_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1920x1080", "xc:none", 
        "-fill", "blue", "-pointsize", "72", "-annotate", "+70+70", talk["title"], 
        "-fill", "green", "-pointsize", "60", "-annotate", "+70+200", talk["presenter"],
        start_png
    ]

    end_slide_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1920x1080", "xc:orange",
        "-fill", "blue", "-gravity", "center", "-pointsize", "72", "-annotate", "+0-70", talk["title"], 
        "-fill", "green", "-gravity", "center", "-pointsize", "60", "-annotate", "+0+70", talk["presenter"],
        end_png
    ]

    ffmpeg_args = [
        FFMPEG_BIN,
        "-ss", start_ts, "-to", end_ts, "-i", video,
        "-loop", "1", "-framerate", str(framerate), "-i", start_png,
        "-loop", "1", "-framerate", str(framerate), "-i", end_png,
        "-filter_complex", "[0:a]afade=in:d=5,afade=out:st={:.2f}:d=5;[0:v]fade=in:st=0:d=1[v1];[1:v]fade=in:st=3:d=0.4:alpha=1,fade=out:st=13:d=0.4:alpha=1[s2];[v1][s2]overlay=shortest=1,settb=1/{:.2f}[v3];[2:v]trim=start=0:end={:.2f}[e1];[v3][e1]xfade=offset={:.2f}:duration=1,fade=out:st={:.2f}:d={:.2f}".format(fade_offset-3, framerate, end_dur + end_fade, fade_offset, fade_offset + end_dur, end_fade),
        "-c:v", "h264", "-crf", "18", "-g", str(math.floor(framerate/2)), "-flags", "+cgop",
        #"-c:v", "h264_nvenc", "-b:v", "12M",
        "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
        "-r", str(framerate), "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path, "-y"
    ]

    logger.debug(ffmpeg_args)

    with open(log_path, "w+") as error_log:
        subprocess.run(start_lt_args, stderr=error_log)
        subprocess.run(end_slide_args, stderr=error_log)
        subprocess.run(ffmpeg_args, stderr=error_log)

    return str(output_path)

def ingest_video(input_path, output_dir, framerate = FRAMERATE):
    
    start_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    input_file = os.path.basename(input_path)
    output_path = Path.joinpath(Path(output_dir, os.path.splitext(input_file)[0] + ".mp4"))

    ffmpeg_args = [
        FFMPEG_BIN,
        "-i", input_path,
        "-c:v", "h264", "-crf", "18", "-g", str(math.floor(framerate/2)), "-flags", "+cgop",
        #"-c:v", "h264_nvenc", "-b:v", "12M",
        "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
        "-r", str(framerate), "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path, "-y"
    ]

    logger.debug(ffmpeg_args)

    log_file = Path(input_file + start_timestamp + ".log")
    log_path = Path.joinpath(Path(LOG_DIR), log_file)

    with open(log_path, "w+") as error_log:
        subprocess.run(ffmpeg_args, stderr=error_log)

    # Move to processed
    proc_folder = Path.joinpath(Path(os.path.dirname(input_path)), Path("Processed"))
    shutil.move(input_path, str(Path.joinpath(Path(proc_folder), Path(input_file))))

    return str(output_path)

if __name__ == "__main__":
    talk_data = {
        "title": "This is a talk",
        "presenter": "A. N. Other"
    }

    form_video("test3.mp4", talk_data, "00:04:53:16", "00:06:36:04")