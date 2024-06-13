from pathlib import Path
import subprocess
import datetime
import json
import logging
import math
import os
import os.path
import shutil
import threading

# Set default logger (is overwritten within certain functions)
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
IMAGEMAGICK_BIN = "convert"
FRAMERATE = 50
LOUD_LEVEL = -23
AAC_ENCODER = "aac"  # or e.g. libfdk_aac

APP_ROOT = Path(".").resolve()
TEMP_DIR = APP_ROOT / "temp"
OUT_DIR = APP_ROOT / "static" / "video" / "output"
LOG_DIR = APP_ROOT / "logs"
RESOURCE_DIR = APP_ROOT / "resources"

FONT_PATH = RESOURCE_DIR / "Raleway.ttf"
BKGD_FILE = RESOURCE_DIR / "BG_V3_LC_Shaded.mp4"
TRANSP_FILE = RESOURCE_DIR / "transparent.png"
LOGO_FILE = RESOURCE_DIR / "logo.svg"
SPONS_FILE = RESOURCE_DIR / "sponsor_slide_rounded.png"

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

class FileLogger():
    def critical(self, *args, **kwargs):
        self.main.critical(*args, **kwargs)
        self.file.critical(*args, **kwargs)

    def exception(self, *args, **kwargs):
        self.main.exception(*args, **kwargs)
        self.file.exception(*args, **kwargs)

    def error(self, *args, **kwargs):
        self.main.error(*args, **kwargs)
        self.file.error(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self.main.warning(*args, **kwargs)
        self.file.warning(*args, **kwargs)    

    def debug(self, *args, **kwargs):
        self.main.debug(*args, **kwargs)
        self.file.debug(*args, **kwargs)        

    def info(self, *args, **kwargs):
        self.main.info(*args, **kwargs)
        self.file.info(*args, **kwargs)

    def __init__(self, request_id, task_log):
        self.main = logging.getLogger(__name__).getChild(str(request_id))
        self.file = logging.getLogger(str(request_id))
        self.file.propagate = False

        file_handler = logging.FileHandler(task_log)
        file_handler.setFormatter(formatter)
        self.file.setLevel(logging.DEBUG)
        self.file.addHandler(file_handler)


def form_video(task, video, talk, start_tc, end_tc, framerate = FRAMERATE, out_dir = OUT_DIR, temp_dir = TEMP_DIR, log_dir = LOG_DIR):

    temp_dir = Path(temp_dir).resolve()
    out_dir = Path(out_dir).resolve()

    video = Path(video)

    working_dir = video.parent

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

    # Generated file names
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
    afade_offset = fade_offset - (afade_out) # When to fade out the main talk audio
    eb_end = fade_offset + end_dur # 
    end_tdur = end_dur + end_fade # Total duration of the endslate, including fade time
    title_end = spn_dur + title_dur
    final_len_s = end_s - start_s + title_end + (end_fade_in/2.)

    lic_text = "This work is licensed under CC BY-SA 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by-sa/4.0/"

    start_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    try:
        filename = talk["filename"] + "-" + start_timestamp
    except KeyError:
        filename = start_timestamp

    job_temp_dir = Path.joinpath(Path(temp_dir), Path(filename))
    job_temp_dir.mkdir(parents=True, exist_ok=True)

    copr_file = Path.joinpath(Path(temp_dir), Path(filename), copr_file)
    spres_file = Path.joinpath(Path(temp_dir), Path(filename), spres_file)
    stalk_file = Path.joinpath(Path(temp_dir), Path(filename), stalk_file)

    output_file = Path(filename + ".mp4")
    output_path = Path.joinpath(Path(out_dir), output_file)

    # Setup log paths
    job_log_dir = Path.joinpath(Path(log_dir), Path(str(task.request.id)))
    job_log_dir.mkdir(parents=True, exist_ok=True)
    build_log = Path.joinpath(job_log_dir, Path("main_build.log"))
    loud_log = Path.joinpath(job_log_dir, Path("loudness_analysis.log"))
    task_log = Path.joinpath(job_log_dir, Path(filename + ".log"))

    # And set up the logger
    logger = FileLogger(task.request.id, task_log)

    start_title_args = [
        IMAGEMAGICK_BIN, 
        "-size", "1800x300", "-background", "#00000000", 
        "-fill", col_talk, "-gravity", "center", "-font", str(FONT_PATH), "caption:{}".format(talk["title"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", col_bkg, "-layers", "merge", "+repage",
        stalk_file
    ]

    start_pres_arg = [
        IMAGEMAGICK_BIN,
        "-size", "1800x256", "-background", "#00000000",
        "-fill", col_pres, "-gravity", "center", "-font", str(FONT_PATH), "caption:{}".format(talk["presenter"]),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", col_bkg, "-layers", "merge", "+repage",
        spres_file
    ]

    copyright_args = [
        IMAGEMAGICK_BIN,
        "-size", "1000x256", "-background", "#00000000",
        "-fill", "#2eadd9", "-gravity", "east", "-font", str(FONT_PATH), "caption:{}".format(lic_text),
        "(", "+clone", "-shadow", "500x2+0+0", ")", "+swap", "-background", col_bkg, "-layers", "merge", "+repage",
        copr_file
    ]

    # Build all the text assets
    logger.info("Building text assets.")
    task.update_state(state="Building text assets")
    subprocess.check_output(start_title_args)
    subprocess.check_output(start_pres_arg)
    subprocess.check_output(copyright_args)

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
        "-ss", start_ts, "-to", end_ts, "-i", video.name, #0
        "-stream_loop", "-1", "-r", str(framerate), "-i", BKGD_FILE, #1
        "-loop", "1", "-framerate", str(framerate), "-i", TRANSP_FILE, #2
        "-loop", "1", "-framerate", str(framerate), "-i", spres_file, #3
        "-loop", "1", "-framerate", str(framerate), "-i", stalk_file, #4
        "-width", "850", "-height", "380", "-keep_ar", "1", "-loop", "1", "-framerate", str(framerate), "-i", LOGO_FILE, #5
        "-loop", "1", "-framerate", str(framerate), "-i", SPONS_FILE, #6
        "-loop", "1", "-framerate", str(framerate), "-i", copr_file, #7
        "-filter_complex", ("[0:a]afade=in:d={in_:.2f},afade=out:st={out_st:.2f}:d={out:.2f},adelay={title_end:.2f}:all=1,".format(in_ = afade_in, out = afade_out, out_st = afade_offset, spn_dur = spn_dur, title_end = title_end * 1000) +
                            # "volume=volume=1.9," +  # C3VOC were using this for GPN; do we need to boost the volume by 2x?
                            "ladspa=f=master_me-ladspa:p=master_me:controls=c1=-16|c22=21|c59=-3[a1];" +
                            f"[0:v]settb=AVTB,fps={framerate:.2f},format=yuv420p[main];" +
                            f"[1:v]settb=AVTB,fps={framerate:.2f},format=yuv420p[bg];" +
                            f"[2:v]settb=AVTB,fps={framerate:.2f},format=yuva420p[tp];" +
                            f"[3:v]settb=AVTB,fps={framerate:.2f},format=yuva420p[slide-pres];" +
                            f"[4:v]settb=AVTB,fps={framerate:.2f},format=yuva420p[slide-title];" +
                            f"[5:v]settb=AVTB,fps={framerate:.2f},format=yuva420p[logo];" +
                            f"[6:v]settb=AVTB,fps={framerate:.2f},format=yuva420p[slide-spons];" +
                            f"[7:v]settb=AVTB,fps={framerate:.2f},format=yuva420p[slide-copyright];" +
                            "[logo]split[l1][l2];" +
                            "[bg]split[bg1][bg2];" +
                            "[tp][slide-pres]overlay=x=60:y=640:shortest=1[s2];" +
                            "[s2][slide-title]overlay=x=60:y=320:shortest=1[s3];" +
                            "[s3][l1]overlay=shortest=1[s4];" +
                            f"[slide-spons][s4]xfade=offset={spn_dur:.2f}:duration={spn_fade_out:.2f}[s5];" +
                            f"[bg1]trim=start=0:end={title_end:.2f}[bg3];" +
                            "[bg3][s5]overlay[s6];" +       
                            "[bg2][l2]overlay[e1];" +
                            f"[e1][slide-copyright]overlay=x=870:y=70:shortest=1,trim=start=0:end={end_tdur:.2f}[e2];" +
                            "[main][e2]xfade=offset={eb_start:.2f}:duration=1,fade=out:st={eb_end:.2f}:d={end_fade:.2f}[m2];".format(eb_start = fade_offset, eb_end = eb_end, end_fade = end_fade) +
                            "[s6][m2]xfade=offset={title_end:.2f}:duration={title_fade_out:.2f},fade=in:d={spn_fade_in:.2f}[p1]".format(title_fade_out = title_fade_out, title_end = title_end, spn_fade_in = spn_fade_in)
                            
        ),
        "-map", "[p1]:v", "-map", "[a1]:a", "-map_metadata", "-1",
        *metadata,
        "-c:v", "h264", "-crf", "16", "-g", str(math.floor(framerate/2)), "-flags", "+cgop",
        "-c:a", AAC_ENCODER, "-ac", "2", "-ar", "48000", "-b:a", "128k",
        "-r", str(framerate), "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path, "-y"
    ]
    logger.info("Running main build.")
    logger.debug("'" + ("' '".join(str(f).replace("'", "'\"'\"'") for f in ffmpeg_args)) + "'")
    task.update_state(state="Running main build", meta={"current": 0, "total": final_len_s})
    with open(build_log, "a") as error_log:
        for current_s in _run_ffmpeg(ffmpeg_args, stderr=error_log, cwd=working_dir):
            current_s = min(current_s, final_len_s)
            task.update_state(state="Running main build", meta={"current": current_s, "total": final_len_s})
    logger.info("Completed main build.")

    return str(output_path)

def _run_ffmpeg(ffmpeg_args, **kwargs):
    ffmpeg_args = list(ffmpeg_args)
    pipe_r_fd, pipe_w_fd = os.pipe()
    pipe_r = os.fdopen(pipe_r_fd, "rb", buffering=0)
    ffmpeg_args += ["-progress", f"pipe:{pipe_w_fd}"]
    with subprocess.Popen(ffmpeg_args, pass_fds=[pipe_w_fd], **kwargs) as proc:
        os.close(pipe_w_fd)
        threading.Thread(target=_close_on_exit, args=[proc, pipe_r]).start()
        for ln in pipe_r:
            ln = ln.strip().decode('utf-8')
            if '=' not in ln:
                continue
            key, _, value = ln.partition('=')
            if key != 'out_time_us' or value == 'N/A':
                continue
            try:
                yield int(value) / 1000000.
            except ValueError:
                logger.warning('Invalid out_time_us from ffmpeg: %s', ln)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=ffmpeg_args)

def _close_on_exit(proc, f):
    proc.wait()
    f.close()

def ingest_video(task, input_path, output_dir, framerate = FRAMERATE, log_dir = LOG_DIR):
    
    start_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    input_file = os.path.basename(input_path)
    output_path = Path.joinpath(Path(output_dir, os.path.splitext(input_file)[0] + ".mp4"))

    # ffprobe to see how long this is...
    ffprobe_args = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        input_path,
    ]
    ffprobe_result = subprocess.check_output(ffprobe_args)
    ffprobe_result_dict = json.loads(ffprobe_result)
    final_len_s = float(ffprobe_result_dict['format']['duration'])

    ffmpeg_args = [
        FFMPEG_BIN,
        "-i", input_path,
        "-vf", "bwdif",
        "-filter_complex", '[0:a]channelsplit=channels=FL+FR,join=inputs=2:channel_layout=stereo[a]',
        "-map", "0:v", "-map", "[a]",
        "-c:v", "h264", "-crf", "12", "-g", str(math.floor(framerate/2)), "-flags", "+cgop", "-s", "1920x1080",
        #"-c:v", "h264_nvenc", "-b:v", "12M",
        "-c:a", AAC_ENCODER, "-ac", "2", "-ar", "48000", "-b:a", "128k",
        "-r", str(framerate), "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path, "-y"
    ]

    logger.debug(ffmpeg_args)

    log_file = Path(input_file + start_timestamp + ".log")
    log_path = Path.joinpath(Path(log_dir), log_file)

    with open(log_path, "w+") as error_log:
        for current_s in _run_ffmpeg(ffmpeg_args, stderr=error_log):
            current_s = min(current_s, final_len_s)
            task.update_state(state="Ingesting...", meta={"current": current_s, "total": final_len_s})

    # Move to processed
    proc_folder = Path.joinpath(Path(os.path.dirname(input_path)), Path("Processed"))
    shutil.move(input_path, str(Path.joinpath(Path(proc_folder), Path(input_file))))

    return str(output_path)

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    class Object(object):
        pass

    task = Object()
    task.request = Object()
    task.request.id = 1
    talk_data = {
        "title": "'This is Britain' – British cultural propaganda films of the 1930s-1940s, their creation, and their far-reaching global legacy",
        "presenter": "Sarah Cole"
    }

    #form_video("static/video/stage_a/bbb_50.mp4", talk_data, "00:00:00:00", "00:05:00:00")

    talk_data = {
        "title": "Anatomy 102: Is that normal!?!",
        "presenter": "Kim M"
    }

    form_video(task, "static/video/source/bbb_50.mp4", talk_data, "00:05:05:00", "00:05:20:00")
