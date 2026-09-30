# Video Downloader (Mac)

Télécharge une vidéo ou un MP3 en 2 clics. Ça marche sur YouTube et plus de 1 000 sites.

- **Vidéo** : MP4 en 720p (sinon 1080p), lisible dans QuickTime et sur iPhone
- **MP3** : seulement le son, d'un ou de plusieurs liens à la fois
- Les fichiers arrivent dans **Téléchargements**
- Environ 200 Mo sur ton Mac, sans Homebrew

## Installer (une fois, ~2 minutes)

1. Décompresse le ZIP.
2. Ouvre **Terminal** (⌘ Espace → « Terminal » → Entrée).
3. Tape `bash ` (avec un espace), glisse **install.sh** dans la fenêtre du Terminal, puis appuie sur **Entrée**.

## Utiliser

1. Copie le lien d'une vidéo (⌘C).
2. Clique sur **Video Downloader** dans le Dock. Le lien est déjà rempli.
3. Appuie sur **Entrée** pour la vidéo, ou clique **MP3 (son seulement)** pour n'avoir que le son.

**Plusieurs liens d'un coup** : colle-les dans la fenêtre, séparés par un espace (ou copie-les tous
ensemble avant d'ouvrir l'app). Ils sont téléchargés un après l'autre.

Une notification t'avertit quand c'est terminé.

## Bon à savoir

- **Mise à jour** : l'app se met à jour toute seule chaque semaine. En cas de problème, relance `install.sh`.
- **Vidéos protégées (DRM)** : Netflix, MasterClass, etc. ne peuvent pas être téléchargées.
- **Pas de notification ?** Réglages Système → Notifications → **Éditeur de script** → Autoriser.
- **Désinstaller** : colle ceci dans le Terminal, puis retire l'icône du Dock :
  ```
  rm -rf "/Applications/Video Downloader.app" "$HOME/Library/Application Support/VideoDownloader" "$HOME/Library/Logs/VideoDownloader.log"
  ```

Télécharge seulement des vidéos que tu as le droit de garder (les tiennes, libres de droits, ou avec permission).
