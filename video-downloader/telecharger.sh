#!/bin/bash
# Télécharge une vidéo (720p, sinon 1080p) ou un MP3 dans ~/Downloads.
# Usage : telecharger.sh video|mp3 LIEN
# Lancé en arrière-plan par l'app « Video Downloader ».

DOSSIER="$HOME/Library/Application Support/VideoDownloader"
BIN="${VDL_BIN:-$DOSSIER/bin}"
OUT="${VDL_OUT:-$HOME/Downloads}"
LOG="${VDL_LOG:-$HOME/Library/Logs/VideoDownloader.log}"

mode="$1"
lien="$(printf '%s' "$2" | tr -d '[:space:]')"

notifier() {  # notifier "sous-titre" "message"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'on run argv' \
      -e 'display notification (item 2 of argv) with title "Video Downloader" subtitle (item 1 of argv)' \
      -e 'end run' "$1" "$2" >/dev/null 2>&1
  else
    echo "[$1] $2"
  fi
}

case "$lien" in http://*|https://*) ;; *) notifier "Rien à télécharger" "Ce n'est pas un lien."; exit 1 ;; esac
case "$mode" in video|mp3) ;; *) echo "Usage : $0 video|mp3 LIEN"; exit 2 ;; esac

mkdir -p "$OUT" "$(dirname "$LOG")"
echo "$(date '+%F %T') $mode $lien" >> "$LOG"
notifier "Téléchargement…" "$lien"

args=(--no-playlist --no-progress --ffmpeg-location "$BIN/ffmpeg"
      -P "$OUT" -o "%(title).150B.%(ext)s" --print after_move:filepath)
[[ -x "$BIN/deno" ]] && args+=(--js-runtimes "deno:$BIN/deno")  # requis par YouTube

if [[ "$mode" == video ]]; then
  # 720p, sinon 1080p, sinon le mieux sous 1080p, sinon ce qui existe. H.264 en priorité (QuickTime/iPhone).
  args+=(-f "bv*[height=720]+ba/b[height=720]/bv*[height=1080]+ba/b[height=1080]/bv*[height<1080]+ba/b[height<1080]/bv*+ba/b"
         -S "res:1080,vcodec:h264,acodec:aac,ext:mp4:m4a" --merge-output-format mp4)
else
  args+=(-f "ba/b" -x --audio-format mp3 --audio-quality 0)
fi

erreurs="$(mktemp)"
fichier="$("$BIN/yt-dlp" "${args[@]}" "$lien" 2>"$erreurs" | tail -1)"
cat "$erreurs" >> "$LOG"

if [[ -z "$fichier" || ! -f "$fichier" ]]; then
  e="$(tr '[:upper:]' '[:lower:]' < "$erreurs")"
  if   [[ "$e" == *drm* ]]; then msg="Vidéo protégée (DRM) : impossible à télécharger."
  elif [[ "$e" == *"unsupported url"* ]]; then msg="Ce site ou ce lien n'est pas pris en charge."
  elif [[ "$e" == *"not a bot"* ]]; then msg="YouTube bloque temporairement. Réessaie dans quelques minutes."
  elif [[ "$e" == *"sign in"* || "$e" == *login* || "$e" == *private* ]]; then msg="Cette vidéo demande d'être connecté (privée ou réservée aux membres)."
  elif [[ "$e" == *"unable to download webpage"* || "$e" == *"failed to resolve"* || "$e" == *"timed out"* ]]; then msg="Pas d'internet, ou le site ne répond pas."
  else msg="Échec. Réessaie ; si ça continue, relance install.sh pour mettre à jour."
  fi
  rm -f "$erreurs"
  notifier "Échec ✗" "$msg"
  exit 1
fi
rm -f "$erreurs"

# Si le site n'offre qu'un format que QuickTime ne lit pas (VP9, AV1…), on convertit en H.264.
if [[ "$mode" == video ]] && ! "$BIN/ffmpeg" -hide_banner -i "$fichier" 2>&1 | grep -qE "Video: (h264|hevc)"; then
  notifier "Conversion…" "$(basename "$fichier")"
  tmp="${fichier%.*}.conversion.mp4"
  if "$BIN/ffmpeg" -v error -y -i "$fichier" -c:v h264_videotoolbox -b:v 5M -c:a aac -b:a 192k -tag:v avc1 -movflags +faststart "$tmp" 2>>"$LOG" \
     || "$BIN/ffmpeg" -v error -y -i "$fichier" -c:v libx264 -preset veryfast -crf 21 -c:a aac -b:a 192k -movflags +faststart "$tmp" 2>>"$LOG"; then
    rm -f "$fichier"; fichier="${fichier%.*}.mp4"; mv "$tmp" "$fichier"
  else
    rm -f "$tmp"
  fi
fi

echo "$(date '+%F %T') ok $fichier" >> "$LOG"
notifier "Terminé ✓" "$(basename "$fichier") (dans Téléchargements)"
echo "$fichier"

# Mise à jour de yt-dlp une fois par semaine (les sites changent souvent).
if [[ -n "$(find "$BIN/yt-dlp" -mtime +7 2>/dev/null)" ]]; then
  ("$BIN/yt-dlp" -U >> "$LOG" 2>&1; touch "$BIN/yt-dlp") &
fi
