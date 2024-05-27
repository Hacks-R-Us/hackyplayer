from pathlib import Path
import subprocess
import datetime
import json
import logging
import math
import os.path
import shutil

logger = logging.getLogger(__name__)

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

    # Timing information
    end_dur = 10 # How long to hold the endslate for
    end_fade_in = 2
    end_fade = 2 # Fade out time on endslate
    afade_in = 3 # Talk audio fade in duration
    afade_out = 3 # Talk audio fade out duration
    spn_dur = 3 # Sponsor slide hold duration
    spn_fade_in = 0.4 # Sponsor slide fade-in duration
    spn_fade_out = 0.4 # Sponsor slide cross-fade out duration
    title_dur = 2 # How long to hold the title card
    title_fade_out = 0.4 # Title card into program duration
    main_fade_out = 0.4 # Main program into endboard duration

    # Colour and design information
    col_talk = "#f9e200"
    col_pres = "#2eadd9"
    col_bkg = "#00000000" #"#21301850"

    # Resource files
    bkgd_file = "resources/BG_V3.mp4"
    transp_file = "resources/transparent.png"
    logo_file = "resources/logo.svg"
    spons_file = "resources/sponsor_slide_rounded.png"

    # Generated files paths
    copr_file = "copyright.png"
    spres_file = "start_pres.png"
    stalk_file = "start_title.png"

    # Convert start and end to some other forms
    start_s = timecode_to_seconds(start_tc)
    end_s = timecode_to_seconds(end_tc)
    start_ts = timecode_to_timestamp(start_tc)
    end_ts = timecode_to_timestamp(end_tc)

    # Calculate some other reused variables
    fade_offset = end_s - start_s - (end_fade_in/2.)
    afade_offset = fade_offset - (afade_out/2.) # When to fade out the main talk audio
    eb_end = fade_offset + end_dur # 
    end_tdur = end_dur + end_fade # Total duration of the endslate, including fade time
    title_end = spn_dur + title_dur

    lic_text = "This work is licensed under CC BY-SA 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by-sa/4.0/"

    start_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    try:
        filename = talk["filename"] + "-" + start_timestamp
    except KeyError:
        filename = start_timestamp

    Path.joinpath(Path(temp_dir), Path(filename)).mkdir(parents=True, exist_ok=True)

    copr_file = Path.joinpath(Path(temp_dir), Path(filename), copr_file)
    spres_file = Path.joinpath(Path(temp_dir), Path(filename), spres_file)
    stalk_file = Path.joinpath(Path(temp_dir), Path(filename), stalk_file)

    output_file = Path(filename + ".mp4")
    log_file = Path(filename + ".log")
    output_path = Path.joinpath(Path(out_dir), output_file)
    log_path = Path.joinpath(Path(LOG_DIR), log_file)

    start_title_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1800x300", "-background", "#00000000", 
        "-fill", col_talk, "-gravity", "center", "caption:{}".format(talk["title"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", col_bkg, "-layers", "merge", "+repage",
        stalk_file
    ]

    start_pres_arg = [
        IMAGEMAGICK_BIN,
        "-size", "1800x256", "-background", "#00000000",
        "-fill", col_pres, "-gravity", "center", "caption:{}".format(talk["presenter"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", col_bkg, "-layers", "merge", "+repage",
        spres_file
    ]

    copyright_args = [
        IMAGEMAGICK_BIN,
        "-size", "1000x256", "-background", "#00000000",
        "-fill", "#2eadd9", "-gravity", "east", "caption:{}".format(lic_text),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", col_bkg, "-layers", "merge", "+repage",
        copr_file
    ]

    ffmpeg_loudness_args = [
        FFMPEG_BIN,
        "-ss", start_ts, "-to", end_ts, "-i", video,
        "-filter_complex", "[0:a]afade=in:d={in_:.2f},afade=out:st={out_st:.2f}:d={out:.2f},loudnorm=print_format=json".format(in_ = afade_in, out = afade_out, out_st = afade_offset),
        "-f", "null", "-"
    ]

    with open(log_path, "a") as error_log:

        # Build all the text assets
        logger.info("Building text assets")
        subprocess.run(start_title_args)
        subprocess.run(start_pres_arg)
        subprocess.run(copyright_args)

        # First FFmpeg pass for getting loudness stats
        logger.info("Detecting loudness information")
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

        # Build file metadata list
        metadata = [
            "-metadata", "title={}".format(talk["title"]),
            "-metadata", "artist={}".format(talk["presenter"]),
            "-metadata", "year=2024",
        ]

        try:
            metadata.extend(("-metadata", "synopsis={}".format(talk["description"])))
        except KeyError:
            pass

        # Run the final build FFmpeg
        ffmpeg_args = [
            FFMPEG_BIN,
            "-ss", start_ts, "-to", end_ts, "-i", video, #0
            "-stream_loop", "-1", "-r", str(framerate), "-i", bkgd_file, #1
            "-loop", "1", "-framerate", str(framerate), "-i", transp_file, #2
            "-loop", "1", "-framerate", str(framerate), "-i", spres_file, #3
            "-loop", "1", "-framerate", str(framerate), "-i", stalk_file, #4
            "-loop", "1", "-framerate", str(framerate), "-i", logo_file, #5
            "-loop", "1", "-framerate", str(framerate), "-i", spons_file, #6
            "-loop", "1", "-framerate", str(framerate), "-i", copr_file, #7
            "-filter_complex", ("[0:a]afade=in:d={in_:.2f},afade=out:st={out_st:.2f}:d={out:.2f},adelay={title_end:.2f}:all=1,".format(in_ = afade_in, out = afade_out, out_st = afade_offset, spn_dur = spn_dur, title_end = title_end * 1000) +
                                "loudnorm=I={target:.2f}:TP=-1.5:measured_I={mI}:measured_tp={mTP}:measured_LRA={mLRA}:measured_thresh={mTH}:offset={off}:linear=true:print_format=json[a1];".format(
                                    target = LOUD_LEVEL, 
                                    mI = loud_vals["input_i"],
                                    mTP = loud_vals["input_tp"],
                                    mLRA =  loud_vals["input_lra"],
                                    mTH = loud_vals["input_thresh"],
                                    off = loud_vals["target_offset"]) +
                                "[5:v]split[l1][l2];" +
                                "[1:v]settb=1/{framerate:.2f},split[bg1][bg2];".format(framerate = framerate) +
                                "[0:v]settb=1/{framerate:.2f}[m1];".format(framerate = framerate) +
                                "[2:v][3:v]overlay=x=60:y=640:shortest=1[s2];" +
                                "[s2][4:v]overlay=x=60:y=320:shortest=1[s3];" +
                                "[s3][l1]overlay=shortest=1[s4];" +
                                "[6:v][s4]xfade=offset={spn_dur:.2f}:duration={spn_fade_out:.2f}[s5];".format(spn_dur = spn_dur, spn_fade_out = spn_fade_out) +
                                "[bg1]trim=start=0:end={title_end:.2f}[bg3];".format(title_end = title_end) +
                                "[bg3][s5]overlay[s6];" +       
                                "[bg2][l2]overlay[e1];" +
                                "[e1][7:v]overlay=x=870:y=70:shortest=1,trim=start=0:end={end_tdur:.2f}[e2];".format(end_tdur = end_tdur) +
                                "[m1][e2]xfade=offset={eb_start:.2f}:duration=1,fade=out:st={eb_end:.2f}:d={end_fade:.2f}[m2];".format(eb_start = fade_offset, eb_end = eb_end, end_fade = end_fade) +
                                "[s6][m2]xfade=offset={title_end:.2f}:duration={title_fade_out:.2f},fade=in:d={spn_fade_in:.2f}[p1]".format(title_fade_out = title_fade_out, title_end = title_end, spn_fade_in = spn_fade_in)
                                
            ),
            "-map", "[p1]", "-map", "[a1]", "-map_metadata", "-1",
            *metadata,
            "-c:v", "h264", "-crf", "16", "-g", str(math.floor(framerate/2)), "-flags", "+cgop",
            "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
            "-r", str(framerate), "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path, "-y"
        ]
        logger.info("Running main build")
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
        "-c:v", "h264", "-crf", "12", "-g", str(math.floor(framerate/2)), "-flags", "+cgop", "-s", "1920x1080",
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

    form_video("static/video/stage_a/bbb_50.mp4", talk_data, "00:05:05:00", "00:05:20:00")