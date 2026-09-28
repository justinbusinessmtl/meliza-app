#!/bin/bash
# Installe « Video Downloader » (version légère, ~200 Mo, sans Homebrew).
# Pour mettre à jour : relance ce script.
set -euo pipefail

ICI="$(cd "$(dirname "$0")" && pwd)"
DOSSIER="$HOME/Library/Application Support/VideoDownloader"
BIN="$DOSSIER/bin"
APP="/Applications/Video Downloader.app"

ok()  { printf "  ✓ %s\n" "$*"; }
die() { printf "\n  ✗ %s\n" "$*" >&2; exit 1; }

[[ "$(uname)" == "Darwin" ]] || die "Ce script est pour Mac."
case "$(uname -m)" in
  arm64)  FF=arm64; DENO=aarch64 ;;
  x86_64) FF=amd64; DENO=x86_64 ;;
  *) die "Mac non reconnu : $(uname -m)" ;;
esac

echo "Installation de Video Downloader…"

# Repart de zéro (supprime aussi l'ancienne version lourde, s'il y en a une)
rm -rf "$DOSSIER"
mkdir -p "$BIN"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "  Téléchargement de yt-dlp…"
curl -fL --progress-bar -o "$BIN/yt-dlp" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
echo "  Téléchargement de ffmpeg…"
curl -fL --progress-bar -o "$TMP/ffmpeg.zip" "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$FF/release/ffmpeg.zip"
unzip -o -q "$TMP/ffmpeg.zip" -d "$BIN"
echo "  Téléchargement de deno (requis par YouTube)…"
curl -fL --progress-bar -o "$TMP/deno.zip" "https://github.com/denoland/deno/releases/latest/download/deno-$DENO-apple-darwin.zip"
unzip -o -q "$TMP/deno.zip" -d "$BIN"
chmod +x "$BIN/yt-dlp" "$BIN/ffmpeg" "$BIN/deno"
for f in yt-dlp ffmpeg deno; do  # les Mac M1+ refusent un programme non signé
  codesign -v "$BIN/$f" >/dev/null 2>&1 || codesign --force --sign - "$BIN/$f" >/dev/null 2>&1 || true
done
ok "yt-dlp $("$BIN/yt-dlp" --version)"
ok "$("$BIN/ffmpeg" -version | head -1 | cut -d' ' -f1-3)"
ok "$("$BIN/deno" --version | head -1)"

cp "$ICI/telecharger.sh" "$DOSSIER/telecharger.sh"
chmod +x "$DOSSIER/telecharger.sh"

rm -rf "$APP"
osacompile -o "$APP" "$ICI/VideoDownloader.applescript"
ok "app installée : $APP"

# Ajoute l'app au Dock (une seule fois)
if ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Video%20Downloader.app"; then
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file:///Applications/Video%20Downloader.app/</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
  killall Dock || true
  ok "ajoutée au Dock"
fi

echo
echo "C'est prêt ! ($(du -sh "$DOSSIER" | cut -f1) utilisés)"
echo "Copie un lien de vidéo, clique sur Video Downloader dans le Dock, puis Vidéo ou MP3."
echo "Les fichiers arrivent dans Téléchargements."
