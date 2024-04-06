from pathlib import Path
import subprocess
import datetime

FFMPEG_BIN = "ffmpeg"
IMAGEMAGICK_BIN = "convert"
FRAMERATE = 25

TEMP_DIR = Path("temp/")
OUT_DIR = Path("static/video/output")

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


def form_video(video, talk, start_tc, end_tc, framerate = FRAMERATE):

    end_dur = 10
    end_fade = 2

    start_s = timecode_to_seconds(start_tc)
    end_s = timecode_to_seconds(end_tc)

    start_ts = timecode_to_timestamp(start_tc)
    end_ts = timecode_to_timestamp(end_tc)

    fade_offset = end_s - start_s - 1

    start_png = Path.joinpath(TEMP_DIR, Path("start.png"))
    end_png = Path.joinpath(TEMP_DIR, Path("end.png"))

    output_file = Path(datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+ ".mp4")

    output_path = Path.joinpath(OUT_DIR, output_file)

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
        "-c:v", "h264", "-crf", "18", output_path, "-y"
    ]

    print(ffmpeg_args)

    subprocess.run(start_lt_args)
    subprocess.run(end_slide_args)
    subprocess.run(ffmpeg_args)

    return str("foobar")


if __name__ == "__main__":
    talk_data = {
        "title": "This is a talk",
        "presenter": "A. N. Other"
    }

    form_video("test3.mp4", talk_data, "00:04:53:16", "00:06:36:04")