#!/bin/bash
# Télécharge des vidéos (720p, sinon 1080p) ou seulement le son en MP3, dans ~/Downloads.
# Usage : telecharger.sh video|mp3 "LIEN [LIEN …]"   (un ou plusieurs liens, séparés par des espaces)
# Lancé en arrière-plan par l'app « Video Downloader ».

DOSSIER="$HOME/Library/Application Support/VideoDownloader"
BIN="${VDL_BIN:-$DOSSIER/bin}"
OUT="${VDL_OUT:-$HOME/Downloads}"
LOG="${VDL_LOG:-$HOME/Library/Logs/VideoDownloader.log}"

mode="$1"
# Tous les liens trouvés dans le texte collé (espaces, retours à la ligne… peu importe)
liens=()
while IFS= read -r l; do
  [[ " ${liens[*]} " == *" $l "* ]] || liens+=("$l")
done < <(printf '%s\n' "$2" | grep -oE 'https?://[^[:space:]"<>]+')

notifier() {  # notifier "sous-titre" "message"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'on run argv' \
      -e 'display notification (item 2 of argv) with title "Video Downloader" subtitle (item 1 of argv)' \
      -e 'end run' "$1" "$2" >/dev/null 2>&1
  else
    echo "[$1] $2" >&2
  fi
}

case "$mode" in video|mp3) ;; *) echo "Usage : $0 video|mp3 \"LIEN [LIEN …]\""; exit 2 ;; esac
if (( ${#liens[@]} == 0 )); then notifier "Rien à télécharger" "Ce n'est pas un lien."; exit 1; fi

mkdir -p "$OUT" "$(dirname "$LOG")"
quoi=$([[ "$mode" == mp3 ]] && echo "MP3" || echo "vidéo")
if (( ${#liens[@]} > 1 )); then
  notifier "Téléchargement…" "${#liens[@]} liens en $quoi"
else
  notifier "Téléchargement…" "${liens[0]}"
fi

args=(--no-playlist --no-progress --ffmpeg-location "$BIN/ffmpeg"
      -P "$OUT" -o "%(title).150B.%(ext)s" --print after_move:filepath)
[[ -x "$BIN/deno" ]] && args+=(--js-runtimes "deno:$BIN/deno")  # requis par YouTube

if [[ "$mode" == video ]]; then
  # 720p, sinon 1080p, sinon le mieux sous 1080p, sinon ce qui existe. H.264 en priorité (QuickTime/iPhone).
  args+=(-f "bv*[height=720]+ba/b[height=720]/bv*[height=1080]+ba/b[height=1080]/bv*[height<1080]+ba/b[height<1080]/bv*+ba/b"
         -S "res:1080,vcodec:h264,acodec:aac,ext:mp4:m4a" --merge-output-format mp4)
else
  # Seulement le son, en MP3 meilleure qualité
  args+=(-f "ba/b" -x --audio-format mp3 --audio-quality 0)
fi

message_erreur() {  # traduit l'erreur de yt-dlp en français simple
  local e; e="$(tr '[:upper:]' '[:lower:]' < "$1")"
  if   [[ "$e" == *drm* ]]; then echo "Vidéo protégée (DRM) : impossible à télécharger."
  elif [[ "$e" == *"unsupported url"* ]]; then echo "Ce site ou ce lien n'est pas pris en charge."
  elif [[ "$e" == *"not a bot"* ]]; then echo "YouTube bloque temporairement. Réessaie dans quelques minutes."
  elif [[ "$e" == *"sign in"* || "$e" == *login* || "$e" == *private* ]]; then echo "Cette vidéo demande d'être connecté (privée ou réservée aux membres)."
  elif [[ "$e" == *"unable to download webpage"* || "$e" == *"failed to resolve"* || "$e" == *"timed out"* ]]; then echo "Pas d'internet, ou le site ne répond pas."
  else echo "Échec. Réessaie ; si ça continue, relance install.sh pour mettre à jour."
  fi
}

# Si le site n'offre qu'un format que QuickTime ne lit pas (VP9, AV1…), on convertit en H.264.
rendre_compatible() {
  local fichier="$1" tmp
  if "$BIN/ffmpeg" -hide_banner -i "$fichier" 2>&1 | grep -qE "Video: (h264|hevc)"; then
    echo "$fichier"; return
  fi
  notifier "Conversion…" "$(basename "$fichier")"
  tmp="${fichier%.*}.conversion.mp4"
  if "$BIN/ffmpeg" -v error -y -i "$fichier" -c:v h264_videotoolbox -b:v 5M -c:a aac -b:a 192k -tag:v avc1 -movflags +faststart "$tmp" 2>>"$LOG" \
     || "$BIN/ffmpeg" -v error -y -i "$fichier" -c:v libx264 -preset veryfast -crf 21 -c:a aac -b:a 192k -movflags +faststart "$tmp" 2>>"$LOG"; then
    rm -f "$fichier"; mv "$tmp" "${fichier%.*}.mp4"; echo "${fichier%.*}.mp4"
  else
    rm -f "$tmp"; echo "$fichier"
  fi
}

reussis=0; rates=0
for lien in "${liens[@]}"; do
  echo "$(date '+%F %T') $mode $lien" >> "$LOG"
  erreurs="$(mktemp)"
  fichier="$("$BIN/yt-dlp" "${args[@]}" "$lien" 2>"$erreurs" | tail -1)"
  cat "$erreurs" >> "$LOG"
  if [[ -z "$fichier" || ! -f "$fichier" ]]; then
    rates=$((rates + 1))
    notifier "Échec ✗" "$(message_erreur "$erreurs")"
    rm -f "$erreurs"
    continue
  fi
  rm -f "$erreurs"
  [[ "$mode" == video ]] && fichier="$(rendre_compatible "$fichier")"
  reussis=$((reussis + 1))
  echo "$(date '+%F %T') ok $fichier" >> "$LOG"
  notifier "Terminé ✓" "$(basename "$fichier") (dans Téléchargements)"
  echo "$fichier"
done

if (( ${#liens[@]} > 1 )); then
  resume="$reussis sur ${#liens[@]} téléchargé(s) dans Téléchargements"
  (( rates > 0 )) && resume="$resume, $rates en échec"
  notifier "Tout est fini" "$resume"
fi

# Mise à jour de yt-dlp une fois par semaine (les sites changent souvent).
if [[ -n "$(find "$BIN/yt-dlp" -mtime +7 2>/dev/null)" ]]; then
  ("$BIN/yt-dlp" -U >> "$LOG" 2>&1; touch "$BIN/yt-dlp") &
fi

(( reussis > 0 ))
