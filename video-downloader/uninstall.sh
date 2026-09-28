#!/bin/bash
# Removes Video Downloader. Your downloaded files and the Homebrew tools are kept.
set -uo pipefail

for APP in "/Applications/Video Downloader.app" "$HOME/Applications/Video Downloader.app"; do
  if [[ -d "$APP" ]]; then
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -u "$APP" 2>/dev/null
    rm -rf "$APP" && echo "  ✓ removed $APP"
  fi
done
rm -rf "$HOME/Library/Application Support/VideoDownloader" && echo "  ✓ removed engine and Whisper model"
rm -f "$HOME/Library/Logs/VideoDownloader.log"
echo
echo "Done. Remove the Dock icon and the three bookmarks by dragging them away."
echo "Your files in Downloads/Videos, Audio and Transcripts were kept."
echo "To also remove the tools: brew uninstall whisper-cpp deno terminal-notifier ffmpeg"
