#!/usr/bin/env python3
"""Video Downloader core.

Usage:
  vdl run video|mp3|transcript URL   Download a video / MP3 / transcript
  vdl link 'videodl://video?url=...'  Same, from a browser-button link
  vdl check-url TEXT                  Print the first http(s) URL in TEXT (exit 1 if none)
  vdl update                          Update yt-dlp, ffmpeg, deno and whisper-cpp
  vdl doctor                          Check that everything is installed
"""

import html
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse
from pathlib import Path

APP_NAME = "Video Downloader"
HOME = Path.home()
SUPPORT = Path(os.environ.get("VDL_SUPPORT", HOME / "Library/Application Support/VideoDownloader"))
OUT_BASE = Path(os.environ.get("VDL_OUT_BASE", HOME / "Downloads"))
OUT_DIRS = {
    "video": OUT_BASE / "Videos",
    "mp3": OUT_BASE / "Audio",
    "transcript": OUT_BASE / "Transcripts",
}
LOG_FILE = Path(os.environ.get("VDL_LOG", HOME / "Library/Logs/VideoDownloader.log"))
WHISPER_MODEL = SUPPORT / "models" / "ggml-large-v3-turbo-q5_0.bin"
UPDATE_STAMP = SUPPORT / ".last-update"
UPDATE_EVERY = 7 * 24 * 3600

# 720p first, then 1080p, then the best below 1080p, then anything at all.
VIDEO_FORMAT = (
    "bv*[height=720]+ba/b[height=720]/"
    "bv*[height=1080]+ba/b[height=1080]/"
    "bv*[height<1080]+ba/b[height<1080]/"
    "bv*+ba/b"
)
# Within a height, prefer H.264 + AAC in MP4 so the file plays in QuickTime and on iPhone.
VIDEO_SORT = ["res:1080", "vcodec:h264", "acodec:aac", "ext:mp4:m4a"]
QUICKTIME_VCODECS = {"h264", "hevc"}
QUICKTIME_ACODECS = {"aac", "mp3", "alac", "ac3", "eac3"}

CAPTION_LANGS = ["fr", "en"]
CAPTION_EXTS = ["vtt", "srt"]


# --------------------------------------------------------------------------- logging / notify

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{os.getpid()}] {msg}\n")


def notify(message, subtitle=None, reveal=None, sound=False):
    """Show a macOS notification. Clicking it reveals `reveal` in Finder."""
    if os.environ.get("VDL_NOTIFY") == "print" or sys.platform != "darwin":
        print(f"[notify] {subtitle or ''} | {message}" + (f" | reveal={reveal}" if reveal else ""))
        return
    tn = shutil.which("terminal-notifier")
    if tn:
        # terminal-notifier treats a leading "-" or "[" specially
        safe = message if not message[:1] in "-[" else "​" + message
        args = [tn, "-title", APP_NAME, "-message", safe, "-group", f"vdl-{os.getpid()}"]
        if subtitle:
            args += ["-subtitle", subtitle]
        if reveal:
            args += ["-execute", f"open -R {shlex.quote(str(reveal))}"]
        if sound:
            args += ["-sound", "default"]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    script = "display notification {} with title {}{}".format(
        _as_str(message), _as_str(APP_NAME), f" subtitle {_as_str(subtitle)}" if subtitle else ""
    )
    subprocess.Popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _as_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


class YDLLogger:
    def debug(self, msg):
        if not msg.startswith("[debug] "):
            log(msg)

    def info(self, msg):
        log(msg)

    def warning(self, msg):
        log("WARNING " + msg)

    def error(self, msg):
        log("ERROR " + msg)


# --------------------------------------------------------------------------- helpers

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def find_url(text):
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(").,;]") if m else None


def parse_link(link):
    """videodl://video?url=ENCODED  ->  ("video", "https://...")"""
    parsed = urllib.parse.urlparse(link.strip())
    mode = (parsed.netloc or parsed.path.strip("/")).lower()
    url = urllib.parse.parse_qs(parsed.query).get("url", [None])[0]
    if mode == "audio":
        mode = "mp3"
    if mode not in OUT_DIRS or not url or not find_url(url):
        raise ValueError(f"Not a valid Video Downloader link: {link!r}")
    return mode, url


def safe_filename(name, limit=150):
    name = re.sub(r'[\x00-\x1f/\\:*?"<>|]+', " ", name or "untitled")
    name = re.sub(r"\s+", " ", name).strip(" .") or "untitled"
    return name[:limit].rstrip(" .")


def unique_path(path):
    if not path.exists():
        return path
    for i in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def friendly_error(err):
    text = str(err)
    low = text.lower()
    rules = [
        ("drm", "This video is DRM-protected (like Netflix or Disney+), so it can't be downloaded."),
        ("unsupported url", "This link isn't supported. Open the video's own page and try again."),
        ("not a bot", "YouTube wants to confirm you're not a bot. Wait a bit and try again."),
        ("private video", "This video is private."),
        ("sign in", "This video needs you to be signed in (private, members-only or age-restricted)."),
        ("login", "This video needs you to be signed in (private, members-only or age-restricted)."),
        ("members-only", "This video is for channel members only."),
        ("video unavailable", "This video is unavailable (removed, or blocked in your country)."),
        ("is not available", "This video is unavailable (removed, or blocked in your country)."),
        ("http error 404", "The video page wasn't found (404). Check the link."),
        ("live event will begin", "This live stream hasn't started yet."),
        ("ffmpeg", "ffmpeg is missing or broken. Run the installer again."),
    ]
    for needle, message in rules:
        if needle in low:
            return message
    network = ["unable to download webpage", "failed to resolve", "getaddrinfo", "timed out",
               "connection refused", "network is unreachable", "nodename nor servname",
               "connection reset", "temporary failure in name resolution"]
    if any(n in low for n in network):
        return "No internet connection, or the site didn't respond. Try again."
    return "Something went wrong. Try `vdl update`, then retry. Details: ~/Library/Logs/VideoDownloader.log"


def base_opts():
    return {
        "logger": YDLLogger(),
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "noplaylist": True,
        "trim_file_name": 150,
        "outtmpl": "%(title).150B.%(ext)s",
        "retries": 5,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
    }


def final_path(info):
    for d in info.get("requested_downloads") or []:
        if d.get("filepath"):
            return Path(d["filepath"])
    if info.get("filepath"):
        return Path(info["filepath"])
    return None


# --------------------------------------------------------------------------- video / mp3

def ffprobe_codecs(path):
    def probe(stream):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
                 "stream=codec_name", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=60,
            ).stdout.strip().splitlines()
            return out[0].strip() if out else None
        except Exception:
            return None
    return probe("v:0"), probe("a:0")


def make_quicktime_friendly(path):
    """Re-encode only when the codecs won't play in QuickTime (e.g. VP9/AV1/Opus)."""
    vcodec, acodec = ffprobe_codecs(path)
    log(f"codecs: video={vcodec} audio={acodec}")
    v_ok = vcodec is None or vcodec in QUICKTIME_VCODECS
    a_ok = acodec is None or acodec in QUICKTIME_ACODECS
    if v_ok and a_ok and path.suffix.lower() == ".mp4":
        return path
    notify("Converting to a QuickTime-friendly MP4…", subtitle=path.stem)
    tmp = path.with_name(path.stem + ".converting.mp4")
    if sys.platform == "darwin":
        vargs = ["-c:v", "h264_videotoolbox", "-b:v", "5M"]  # Apple Silicon hardware encoder
    else:
        vargs = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(path)]
    cmd += ["-c:v", "copy"] if v_ok else vargs + ["-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "copy"] if a_ok else ["-c:a", "aac", "-b:a", "192k"]
    if vcodec:  # QuickTime needs these tags to recognise the video track
        cmd += ["-tag:v", "hvc1" if v_ok and vcodec == "hevc" else "avc1"]
    cmd += ["-movflags", "+faststart", str(tmp)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and not v_ok and sys.platform == "darwin":
        log("videotoolbox failed, retrying with libx264: " + result.stderr[-500:])
        cmd = [c if c != "h264_videotoolbox" else "libx264" for c in cmd]
        i = cmd.index("-b:v")
        cmd[i:i + 2] = ["-preset", "veryfast", "-crf", "21"]
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log("conversion failed: " + result.stderr[-2000:])
        tmp.unlink(missing_ok=True)
        return path  # keep the original rather than lose the download
    final = path.with_suffix(".mp4")
    path.unlink(missing_ok=True)
    tmp.rename(final)
    return final


def download(mode, url):
    from yt_dlp import YoutubeDL

    outdir = OUT_DIRS[mode]
    outdir.mkdir(parents=True, exist_ok=True)
    opts = base_opts()
    opts["paths"] = {"home": str(outdir), "temp": tempfile.gettempdir()}
    if mode == "video":
        opts.update({
            "format": VIDEO_FORMAT,
            "format_sort": VIDEO_SORT,
            "merge_output_format": "mp4",
        })
    else:
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"},
                {"key": "FFmpegMetadata"},
            ],
        })
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)
    path = final_path(info)
    if path is None or not path.exists():
        raise RuntimeError(f"Download finished but the file wasn't found ({path})")
    if mode == "video":
        path = make_quicktime_friendly(path)
        log(f"format: {info.get('format')}")
    return path, info


# --------------------------------------------------------------------------- transcripts

TIME_RE = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
TAG_RE = re.compile(r"<[^>]*>")


def _seconds(stamp):
    m = TIME_RE.search(stamp)
    if not m:
        return 0.0
    h, mnt, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_cues(text):
    """Parse WebVTT or SRT into [(start, end, [lines])].

    Line-based on purpose: YouTube auto-captions put a line holding a single space
    inside cues, so only a truly empty line ends a cue.
    """
    cues, current = [], None
    lines = text.replace("﻿", "").splitlines()
    for i, line in enumerate(lines):
        if "-->" in line:
            start_s, end_s = line.split("-->", 1)
            current = (_seconds(start_s), _seconds((end_s.split() or [""])[0]), [])
            cues.append(current)
        elif line == "":
            current = None
        elif current is not None:
            if line.strip().isdigit() and i + 1 < len(lines) and "-->" in lines[i + 1]:
                continue  # SRT cue number
            clean = html.unescape(TAG_RE.sub("", line))
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                current[2].append(clean)
    return [c for c in cues if c[2]]


def dedupe_cues(cues):
    """Remove the rolling duplicate lines of auto-captions. Returns [(start, end, text)]."""
    out = []
    recent = []
    for start, end, lines in cues:
        for line in lines:
            if line in recent:
                continue
            out.append([start, end, line])
            recent = (recent + [line])[-3:]
    # make end times sane (auto-captions overlap)
    for i in range(len(out) - 1):
        nxt = out[i + 1][0]
        if nxt > out[i][0]:
            out[i][1] = min(out[i][1], nxt)
    return [tuple(x) for x in out]


def to_paragraphs(entries):
    paragraphs, current, words, prev_end = [], [], 0, None
    for start, end, text in entries:
        gap = start - prev_end if prev_end is not None else 0
        ends_sentence = bool(current) and current[-1].rstrip().endswith((".", "!", "?", "…"))
        if current and (gap > 2.5 or words > 120 or (words > 70 and ends_sentence)):
            paragraphs.append(" ".join(current))
            current, words = [], 0
        current.append(text)
        words += len(text.split())
        prev_end = end
    if current:
        paragraphs.append(" ".join(current))
    return [re.sub(r"\s+", " ", p).strip() for p in paragraphs]


def _srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def to_srt(entries):
    rows = []
    for i, (start, end, text) in enumerate(entries, 1):
        if end <= start:
            end = start + 1.5
        rows.append(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    return "\n".join(rows)


def pick_caption(info):
    """Choose the best caption track. Returns (lang_key, format_dict, is_auto) or None."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    lang = (info.get("language") or "").split("-")[0].lower()

    def usable(tracks):
        for ext in CAPTION_EXTS:
            for t in tracks or []:
                if t.get("ext") == ext and t.get("url"):
                    return t
        return None

    def first(table, keys):
        for key in keys:
            fmt = usable(table.get(key))
            if fmt:
                return key, fmt
        return None

    def keys_for(table, code):
        exact = [k for k in table if k.lower() == code]
        regional = [k for k in table if k.lower().startswith(code + "-") and not k.endswith("-orig")]
        return exact + regional

    # Order: human captions in the spoken language, then the original auto-captions,
    # then French/English human captions, then any human captions. Auto-captions in
    # other languages are machine translations, so we'd rather run Whisper.
    candidates = []
    if lang:
        candidates.append((manual, keys_for(manual, lang), False))
        candidates.append((auto, [f"{lang}-orig"] + keys_for(auto, lang), True))
    else:
        candidates.append((auto, [k for k in auto if k.endswith("-orig")], True))
    for code in CAPTION_LANGS:
        candidates.append((manual, keys_for(manual, code), False))
    candidates.append((manual, list(manual), False))
    for table, keys, is_auto in candidates:
        hit = first(table, keys)
        if hit:
            return hit[0], hit[1], is_auto
    return None


def whisper_binary():
    for name in ("whisper-cli", "whisper-cpp"):
        path = shutil.which(name)
        if path:
            return path
    return None


def whisper_transcribe(url, info, workdir):
    from yt_dlp import YoutubeDL

    binary = whisper_binary()
    if not binary:
        raise RuntimeError("whisper-cpp is not installed. Run the installer again.")
    if not WHISPER_MODEL.exists():
        raise RuntimeError("The Whisper model is missing. Run the installer again.")
    notify("No captions found. Transcribing on your Mac…", subtitle=info.get("title"))
    opts = base_opts()
    opts.update({"format": "bestaudio/best", "paths": {"home": str(workdir)}, "outtmpl": "audio.%(ext)s"})
    with YoutubeDL(opts) as ydl:
        audio_info = ydl.extract_info(url, download=True)
    audio = final_path(audio_info)
    wav = workdir / "audio.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    lang = (info.get("language") or "auto").split("-")[0]
    out_base = workdir / "whisper"
    cmd = [binary, "-m", str(WHISPER_MODEL), "-f", str(wav), "-l", lang, "-osrt", "-of", str(out_base), "-np"]
    log("running: " + " ".join(shlex.quote(c) for c in cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log("whisper failed: " + result.stderr[-2000:])
        raise RuntimeError("Whisper transcription failed")
    return (out_base.with_suffix(".srt")).read_text(encoding="utf-8", errors="replace"), "whisper"


def transcript(url):
    from yt_dlp import YoutubeDL

    outdir = OUT_DIRS["transcript"]
    outdir.mkdir(parents=True, exist_ok=True)
    opts = base_opts()
    opts["skip_download"] = True
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if info.get("_type") == "playlist" and info.get("entries"):
            info = next(e for e in info["entries"] if e)
        raw, source = None, None
        choice = pick_caption(info)
        if choice:
            key, fmt, is_auto = choice
            try:
                raw = ydl.urlopen(fmt["url"]).read().decode("utf-8", errors="replace")
                source = f"{'auto-captions' if is_auto else 'captions'} ({key})"
                if not parse_cues(raw):
                    raw = None
            except Exception as e:  # e.g. the site blocks caption downloads
                log(f"caption download failed ({key}): {e}")
                raw = None
    with tempfile.TemporaryDirectory(prefix="vdl-") as tmp:
        if raw is None:
            raw, source = whisper_transcribe(url, info, Path(tmp))
    entries = dedupe_cues(parse_cues(raw))
    if not entries:
        raise RuntimeError("The transcript came back empty (the video may have no speech).")
    log(f"transcript source: {source}, {len(entries)} lines")
    title = info.get("title") or "transcript"
    base = outdir / safe_filename(title)
    txt_path = unique_path(base.with_suffix(".txt"))
    srt_path = txt_path.with_suffix(".srt")
    header = f"{title}\n{info.get('webpage_url') or url}\n\n"
    txt_path.write_text(header + "\n\n".join(to_paragraphs(entries)) + "\n", encoding="utf-8")
    srt_path.write_text(to_srt(entries), encoding="utf-8")
    return txt_path, info, source


# --------------------------------------------------------------------------- commands

LABELS = {"video": "video", "mp3": "MP3", "transcript": "transcript"}


def run(mode, url):
    url = find_url(url)
    if not url:
        notify("That doesn't look like a link.", subtitle="Nothing to download")
        return 1
    log(f"start {mode}: {url}")
    notify(f"Getting the {LABELS[mode]}…", subtitle=url[:80])
    try:
        if mode == "transcript":
            path, info, source = transcript(url)
            done = f"Saved transcript: {path.name}"
        else:
            path, info = download(mode, url)
            done = f"Saved: {path.name}"
        log(f"done: {path}")
        notify(done + " (click to show)", subtitle="Done ✓", reveal=path, sound=True)
        print(path)
        return 0
    except Exception as e:
        log("FAILED: " + "".join(traceback.format_exception(e)))
        notify(friendly_error(e), subtitle="Download failed ✗", sound=True)
        return 1
    finally:
        maybe_auto_update()


def maybe_auto_update():
    """Refresh yt-dlp in the background once a week, since sites change often."""
    if os.environ.get("VDL_NO_AUTO_UPDATE"):
        return
    try:
        if UPDATE_STAMP.exists() and time.time() - UPDATE_STAMP.stat().st_mtime < UPDATE_EVERY:
            return
        UPDATE_STAMP.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_STAMP.touch()
        log("weekly yt-dlp update")
        with LOG_FILE.open("a") as logf:
            subprocess.Popen([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default]"],
                             stdout=logf, stderr=logf, start_new_session=True)
    except Exception as e:
        log(f"auto-update skipped: {e}")


def update():
    notify("Updating…")
    steps = [[sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"]]
    if shutil.which("brew"):
        steps.append(["brew", "upgrade", "ffmpeg", "deno", "whisper-cpp", "terminal-notifier"])
    ok = True
    for cmd in steps:
        print("→", " ".join(cmd))
        ok = subprocess.run(cmd).returncode == 0 and ok
    UPDATE_STAMP.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_STAMP.touch()
    notify("Up to date ✓" if ok else "Update had errors, see Terminal")
    return 0 if ok else 1


def doctor():
    ok = True

    def check(label, good, fix=""):
        nonlocal ok
        ok = ok and good
        print(f"  {'✓' if good else '✗'} {label}" + ("" if good else f"  → {fix}"))

    try:
        import yt_dlp
        check(f"yt-dlp {yt_dlp.version.__version__}", True)
    except ImportError:
        check("yt-dlp", False, "run install.sh")
    for tool, why in [("ffmpeg", "merging/converting"), ("ffprobe", "codec checks"),
                      ("deno", "YouTube support"), ("terminal-notifier", "clickable notifications")]:
        check(f"{tool} ({why})", bool(shutil.which(tool)), f"brew install {tool.replace('ffprobe', 'ffmpeg')}")
    check("whisper-cpp (transcripts without captions)", bool(whisper_binary()), "brew install whisper-cpp")
    check(f"Whisper model ({WHISPER_MODEL.name})", WHISPER_MODEL.exists(), "run install.sh")
    for mode, d in OUT_DIRS.items():
        print(f"  • {LABELS[mode]} folder: {d}")
    print("All good ✓" if ok else "Some things are missing — run install.sh again.")
    return 0 if ok else 1


def main(argv):
    if len(argv) >= 3 and argv[0] == "run" and argv[1] in OUT_DIRS:
        return run(argv[1], argv[2])
    if len(argv) == 2 and argv[0] == "link":
        try:
            mode, url = parse_link(argv[1])
        except ValueError as e:
            log(str(e))
            notify("That button link looks broken. Re-add the browser buttons.", subtitle="Nothing to download")
            return 1
        return run(mode, url)
    if len(argv) == 2 and argv[0] == "check-url":
        url = find_url(argv[1])
        if url:
            print(url)
            return 0
        return 1
    if argv[:1] == ["update"]:
        return update()
    if argv[:1] == ["doctor"]:
        return doctor()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
