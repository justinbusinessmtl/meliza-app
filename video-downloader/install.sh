#!/bin/bash
# Video Downloader: one-time installer for macOS (Apple Silicon or Intel).
# Safe to run again at any time; it updates everything in place.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SUPPORT="$HOME/Library/Application Support/VideoDownloader"
APP_NAME="Video Downloader"
BUNDLE_ID="com.meliza.videodownloader"
MODEL_NAME="ggml-large-v3-turbo-q5_0.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME"

bold() { printf "\n\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  ✓ %s\n" "$*"; }
die()  { printf "\n  ✗ %s\n" "$*" >&2; exit 1; }

[[ "$(uname)" == "Darwin" ]] || die "This installer is for macOS."

bold "1/6  Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$b" ]] && eval "$("$b" shellenv)" && break
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "  Installing Homebrew (it may ask for your Mac password)…"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$b" ]] && eval "$("$b" shellenv)" && break
  done
fi
command -v brew >/dev/null 2>&1 || die "Homebrew didn't install. Install it from https://brew.sh and run this again."
ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"

bold "2/6  Tools (python, ffmpeg, deno, whisper-cpp, terminal-notifier)"
for f in python ffmpeg deno whisper-cpp terminal-notifier; do
  if brew list --formula "$f" >/dev/null 2>&1; then
    brew upgrade "$f" >/dev/null 2>&1 || true
  else
    brew install "$f"
  fi
  ok "$f"
done
PY="$(brew --prefix)/bin/python3"
[[ -x "$PY" ]] || die "Python wasn't found at $PY"

bold "3/6  Download engine (yt-dlp)"
mkdir -p "$SUPPORT/models"
[[ -d "$SUPPORT/venv" ]] || "$PY" -m venv "$SUPPORT/venv"
"$SUPPORT/venv/bin/python" -m pip install -q --upgrade pip
"$SUPPORT/venv/bin/python" -m pip install -q --upgrade "yt-dlp[default]"
cp "$HERE/src/vdl.py" "$SUPPORT/vdl.py"
cp "$HERE/src/vdl" "$SUPPORT/vdl"
chmod +x "$SUPPORT/vdl"
touch "$SUPPORT/.last-update"
ok "yt-dlp $("$SUPPORT/venv/bin/python" -c 'import yt_dlp; print(yt_dlp.version.__version__)')"

bold "4/6  Whisper model for transcripts (~550 MB, one time)"
if [[ -s "$SUPPORT/models/$MODEL_NAME" ]]; then
  ok "already downloaded"
else
  curl -fL --progress-bar -o "$SUPPORT/models/$MODEL_NAME.part" "$MODEL_URL"
  mv "$SUPPORT/models/$MODEL_NAME.part" "$SUPPORT/models/$MODEL_NAME"
  ok "downloaded"
fi

bold "5/6  Building the app"
APPS_DIR="/Applications"
[[ -w "$APPS_DIR" ]] || { APPS_DIR="$HOME/Applications"; mkdir -p "$APPS_DIR"; }
APP="$APPS_DIR/$APP_NAME.app"
rm -rf "$APP"
osacompile -o "$APP" "$HERE/src/VideoDownloader.applescript"
PLIST="$APP/Contents/Info.plist"
pb() { /usr/libexec/PlistBuddy -c "$1" "$PLIST" >/dev/null 2>&1 || true; }
pb "Set :CFBundleIdentifier $BUNDLE_ID"
pb "Add :CFBundleIdentifier string $BUNDLE_ID"
pb "Set :CFBundleName $APP_NAME"
pb "Delete :CFBundleURLTypes"
pb "Add :CFBundleURLTypes array"
pb "Add :CFBundleURLTypes:0 dict"
pb "Add :CFBundleURLTypes:0:CFBundleURLName string $BUNDLE_ID"
pb "Add :CFBundleURLTypes:0:CFBundleURLSchemes array"
pb "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string videodl"
# Custom icon (the compiled asset catalog would override applet.icns, so drop it)
if [[ -f "$HERE/assets/AppIcon.icns" ]]; then
  cp "$HERE/assets/AppIcon.icns" "$APP/Contents/Resources/applet.icns"
  rm -f "$APP/Contents/Resources/Assets.car"
  pb "Delete :CFBundleIconName"
  pb "Set :CFBundleIconFile applet"
fi
# Editing Info.plist invalidates the signature; re-sign locally so macOS accepts it.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
touch "$APP"
ok "$APP"

# Add to the Dock (once)
if ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Video%20Downloader.app"; then
  APP_URL="file://$(echo "$APP" | sed 's/ /%20/g')/"
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$APP_URL</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
  killall Dock || true
  ok "added to your Dock"
fi

mkdir -p "$HOME/Downloads/Videos" "$HOME/Downloads/Audio" "$HOME/Downloads/Transcripts"

bold "6/6  Check"
"$SUPPORT/vdl" doctor || true

bold "Last step: add the browser buttons"
echo "  A page is opening in your browser. Drag the three buttons to your bookmarks bar."
echo "  (Show the bar: Safari ⌘⇧B, Chrome ⌘⇧B)"
open "$HERE/bookmarklets.html"

bold "All set! 🎉"
echo "  • On a video page, click ⬇ Video, ♪ MP3 or 📝 Transcript in your bookmarks bar."
echo "  • Or copy a link and click Video Downloader in your Dock."
echo "  • Files go to Downloads/Videos, Downloads/Audio and Downloads/Transcripts."
