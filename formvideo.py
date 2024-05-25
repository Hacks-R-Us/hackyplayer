from pathlib import Path
import subprocess
import datetime
import json
import logging
import math
import os.path
import shutil

logger = logging.getLogger("__name__")

logger.setLevel(logging.DEBUG)

FFMPEG_BIN = "ffmpeg"
IMAGEMAGICK_BIN = "convert"
FRAMERATE = 50
LOUD_LEVEL = -23

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

    start_lt_title_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1860x160", "-background", "#00000000", 
        "-fill", "#f9e200", "-gravity", "southwest", "caption:{}".format(talk["title"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", "#21301850", "-layers", "merge", "+repage",
        "temp/start_title.png"
    ]

    start_lt_pres_arg = [
        IMAGEMAGICK_BIN,
        "-size", "1860x80", "-background", "#00000000",
        "-fill", "#2eadd9", "-gravity", "southwest", "caption:{}".format(talk["presenter"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", "#21301850", "-layers", "merge", "+repage",
        "temp/start_pres.png"
    ]

    end_slide_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1920x1080", "xc:orange",
        "-fill", "blue", "-gravity", "center", "-pointsize", "72", "-annotate", "+0-70", talk["title"], 
        "-fill", "green", "-gravity", "center", "-pointsize", "60", "-annotate", "+0+70", talk["presenter"],
        end_png
    ]

    end_slide_title_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1320x350", "-background", "#00000000", 
        "-fill", "#f9e200", "-gravity", "Center", "caption:{}".format(talk["title"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", "#21301850", "-layers", "merge", "+repage",
        "temp/end_title.png"
    ]

    end_slide_pres_arg = [
        IMAGEMAGICK_BIN,
        "-size", "700x200", "-background", "#00000000",
        "-fill", "#2eadd9", "-gravity", "Center", "caption:{}".format(talk["presenter"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", "#21301850", "-layers", "merge", "+repage",
        "temp/end_pres.png"
    ]

    ffmpeg_loudness_args = [
        FFMPEG_BIN,
        "-ss", start_ts, "-to", end_ts, "-i", video,
        "-filter_complex", "[0:a]afade=in:d=5,afade=out:st={fade_offset3:.2f}:d=5,adelay=8000:all=1,loudnorm=print_format=json".format(fade_offset3 = fade_offset - 3),
        "-f", "null", "-"
    ]

    with open(log_path, "a") as error_log:

        # Build all the text assets
        subprocess.run(start_lt_args, stderr=error_log)
        subprocess.run(start_lt_title_args, stderr=error_log)
        subprocess.run(start_lt_pres_arg, stderr=error_log)
        subprocess.run(end_slide_args, stderr=error_log)
        subprocess.run(end_slide_title_args, stderr=error_log)
        subprocess.run(end_slide_pres_arg, stderr=error_log)

        # First FFmpeg pass for getting loudness stats
        logger.debug(ffmpeg_loudness_args)
        analysis = subprocess.check_output(ffmpeg_loudness_args, stderr=subprocess.STDOUT).decode("utf-8").split("\n")

        json_detect = False
        json_string = ""
        for line in analysis:
            if "[Parsed_loudnorm" in line:
                json_detect = True
                continue
            if json_detect:
                json_string += line
        loud_vals = json.loads(json_string)

        # Run the final build FFmpeg
        ffmpeg_args = [
            FFMPEG_BIN,
            "-ss", start_ts, "-to", end_ts, "-i", video,
            "-loop", "1", "-framerate", str(framerate), "-i", start_png,
            "-stream_loop", "-1", "-r", str(framerate), "-i", "temp/BG_V3.mp4",
            "-loop", "1", "-framerate", str(framerate), "-i", "temp/end_pres.png",
            "-loop", "1", "-framerate", str(framerate), "-i", "temp/end_title.png",
            "-loop", "1", "-framerate", str(framerate), "-i", "temp/sponsor_slide.png",
            "-loop", "1", "-framerate", str(framerate), "-i", "temp/start_pres.png",
            "-loop", "1", "-framerate", str(framerate), "-i", "temp/start_title.png",
            "-filter_complex", ("[0:a]afade=in:d=5,afade=out:st={fade_offset3:.2f}:d=5,adelay=8000:all=1,".format(fade_offset3 = fade_offset - 3) +
                                "loudnorm=I={target:.2f}:TP=-1.5:measured_I={mI}:measured_tp={mTP}:measured_LRA={mLRA}:measured_thresh={mTH}:offset={off}:linear=true:print_format=json[a0];".format(
                                    target = LOUD_LEVEL, 
                                    mI = loud_vals["input_i"],
                                    mTP = loud_vals["input_tp"],
                                    mLRA =  loud_vals["input_lra"],
                                    mTH = loud_vals["input_thresh"],
                                    off = loud_vals["target_offset"]) +
                                "[a0]asplit[a1][a2];" +
                                "[a2]ebur128=peak=true;" +
                                "[2:v]crop=w=1920:h=290,fade=in:st=3:d=0.4:alpha=1,fade=out:st=13:d=0.4:alpha=1[ltb];" +
                                "[0:v]fade=in:st=0:d=1[v1];" +
                                "[6:v]fade=in:st=3:d=0.4:alpha=1,fade=out:st=13:d=0.4:alpha=1[s2];" +
                                "[7:v]fade=in:st=3:d=0.4:alpha=1,fade=out:st=13:d=0.4:alpha=1[s3];" +
                                "[v1][ltb]overlay=y=790:x=0:shortest=1[lt1];" +
                                "[lt1][s2]overlay=y=970:x=30:shortest=1,settb=1/{framerate:.2f}[v3];".format(framerate = framerate) +
                                "[v3][s3]overlay=y=800:x=30:shortest=1,settb=1/{framerate:.2f}[v4];".format(framerate = framerate) +
                                "[2:v]trim=start=0:end={main_end:.2f},settb=1/{framerate:.2f}[e1];".format(framerate = framerate, main_end = end_dur + end_fade) +
                                "[e1][3:v]overlay=shortest=1:x=610:y=560[e2];" +
                                "[e2][4:v]overlay=shortest=1:x=300:y=150[e3];" +
                                "[v4][e3]xfade=offset={eb_start:.2f}:duration=1,fade=out:st={eb_end:.2f}:d={end_fade:.2f}[m1];".format(eb_start = fade_offset, eb_end = fade_offset + end_dur, end_fade = end_fade) +
                                "[5:v][m1]xfade=offset=8:duration=1,fade=in:d=3[p1]"
            ),
            "-map", "[p1]", "-map", "[a1]", "-map_metadata", "-1",
            "-c:v", "h264", "-crf", "16", "-g", str(math.floor(framerate/2)), "-flags", "+cgop",
            "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
            "-r", str(framerate), "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path, "-y"
        ]
        logger.debug(ffmpeg_args)
        subprocess.run(ffmpeg_args, stderr=error_log)

    return str(output_path)

def ingest_video(input_path, output_dir, framerate = FRAMERATE):
    
    start_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    input_file = os.path.basename(input_path)
    output_path = Path.joinpath(Path(output_dir, os.path.splitext(input_file)[0] + ".mp4"))

    ffmpeg_args = [
        FFMPEG_BIN,
        "-i", input_path,
        "-c:v", "h264", "-crf", "12", "-g", str(math.floor(framerate/2)), "-flags", "+cgop",
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
    logging.basicConfig()
    talk_data = {
        "title": "'This is Britain' – British cultural propaganda films of the 1930s-1940s, their creation, and their far-reaching global legacy",
        "presenter": "Sarah Cole"
    }

    #form_video("static/video/stage_a/bbb_50.mp4", talk_data, "00:00:00:00", "00:05:00:00")

    talk_data = {
        "title": "Anatomy 102: Is that normal!?!",
        "presenter": "Kim M"
    }

    form_video("static/video/stage_a/bbb_50.mp4", talk_data, "00:05:00:00", "00:06:00:00")