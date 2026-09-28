# Video Downloader (Mac)

Download a video, its audio as MP3, or its transcript with one click. It works on YouTube and
[over 1,000 other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

| Button | What you get | Saved to |
|---|---|---|
| **⬇ Video** | MP4 at **720p**. No 720p? → **1080p**. Neither? → the best below 1080p. Plays in QuickTime and on iPhone. | `Downloads/Videos` |
| **♪ MP3** | Audio only, best quality MP3 | `Downloads/Audio` |
| **📝 Transcript** | Clean text (`.txt`) | `Downloads/Transcripts` |

Free, no account, nothing uploaded anywhere. Transcripts use the video's captions when they exist (instant).
If a video has no captions, Whisper transcribes it **on your Mac**, which works well in French and English.

---

## Install (once, ~5 minutes)

1. Download this folder to your Mac. On GitHub: **Code → Download ZIP**, then unzip it in Downloads.
2. Open **Terminal** (⌘ Space → type "Terminal" → Enter).
3. Type `bash ` (with a space after it), drag **`install.sh`** from the `video-downloader` folder
   into the Terminal window, and press **Enter**.
4. If it asks for your Mac password, type it (nothing shows while you type; that's normal) and press Enter.

The installer sets up Homebrew and the tools, downloads the Whisper model (~550 MB), puts
**Video Downloader** in Applications and your Dock, then opens a page with the three browser buttons.

5. On that page, drag **⬇ Video**, **♪ MP3** and **📝 Transcript** onto your bookmarks bar
   (show the bar with ⌘⇧B).

## Use it

**Fastest: browser buttons.** On any video page, click **⬇ Video**, **♪ MP3** or **📝 Transcript**.
The first time, your browser asks to open "Video Downloader": click **Allow**. In Chrome, also tick
"Always allow".

**Dock icon.** Copy a video link (⌘C), click **Video Downloader** in the Dock, then press **Enter** for
Video or click **MP3** / **Transcript**.

You get a notification when the download starts and another when it's done. **Click the "Done"
notification to see the file in Finder.** You can start several downloads at once.

## 30-second test checklist

- [ ] Open any YouTube video, click **⬇ Video** → allow the browser prompt → a "Getting the video…" notification appears
- [ ] A few seconds later: "Done ✓". Click it → Finder shows the `.mp4` in `Downloads/Videos`. Open it in QuickTime.
- [ ] Same video, click **♪ MP3** → an `.mp3` appears in `Downloads/Audio`
- [ ] Same video, click **📝 Transcript** → a `.txt` appears in `Downloads/Transcripts`
- [ ] Copy a link, click the Dock icon, press Enter → the video downloads

## If something goes wrong

| Problem | Fix |
|---|---|
| No notifications | System Settings → Notifications → **terminal-notifier** → Allow |
| Safari button does nothing | Safari → Settings → Advanced → tick "Show features for web developers", then Settings → Developer → tick "Allow JavaScript from Smart Search Field" |
| "Something went wrong" | A site changed. Update: open Terminal and run `~/Library/Application\ Support/VideoDownloader/vdl update` (it also updates automatically once a week) |
| "DRM-protected" | Netflix, Disney+, Prime Video etc. encrypt their videos. This can't be downloaded, by design. |
| "Needs you to be signed in" | Private, members-only or age-restricted videos aren't supported. |
| macOS says the app is damaged or can't be opened | Run the installer again. It rebuilds and re-signs the app on your Mac. |
| Anything else | Check everything is installed: `~/Library/Application\ Support/VideoDownloader/vdl doctor`. The log is at `~/Library/Logs/VideoDownloader.log`. |

**Update** anytime by running `install.sh` again. It's safe to re-run.
**Uninstall** with `bash uninstall.sh`. Your downloaded files are kept.

Only download videos you have the right to save (your own content, public-domain or Creative Commons
material, or with the owner's permission).

---

## How it works (for the curious)

```
Browser button ──videodl://video?url=…──┐
                                        ├─▶ Video Downloader.app ──▶ vdl (Python) ──▶ yt-dlp + ffmpeg
Dock icon (clipboard) ──────────────────┘     (AppleScript applet)                   └▶ whisper.cpp (transcripts)
```

- `src/VideoDownloader.applescript`: the app. It shows the Dock dialog, receives `videodl://` links from the
  browser buttons, and starts the engine in the background.
- `src/vdl.py`: the engine.
  - **Video:** format rule `720p → 1080p → best below 1080p → best`, preferring H.264/AAC.
    If a site only offers VP9/AV1, it converts with the Apple Silicon hardware encoder.
  - **MP3:** best audio, converted to MP3 V0.
  - **Transcript:** picks human captions in the spoken language first, then the original auto-captions
    (it never uses machine-translated ones), and falls back to whisper.cpp with the `large-v3-turbo` model.
    It removes the duplicated lines YouTube auto-captions repeat and groups the text into paragraphs.
- `install.sh`: installs Homebrew packages (`python ffmpeg deno whisper-cpp terminal-notifier`), a private
  yt-dlp in `~/Library/Application Support/VideoDownloader/venv`, and the Whisper model, then builds the app
  with `osacompile`, registers the `videodl://` URL scheme and re-signs the app locally.
- `tests/`: offline tests for format selection, caption cleanup and link parsing. Run with
  `python3 -m unittest discover -s tests` (needs `pip install yt-dlp`).
