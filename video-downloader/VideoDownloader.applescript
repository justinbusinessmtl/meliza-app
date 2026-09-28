-- Video Downloader : une fenêtre, un lien, Vidéo ou MP3.
on run
	set lien to ""
	try
		set lien to (the clipboard as text)
	end try
	if lien does not start with "http" then set lien to ""
	set rep to display dialog "Lien de la vidéo :" default answer lien ¬
		buttons {"Annuler", "MP3", "Vidéo"} default button "Vidéo" cancel button "Annuler" ¬
		with title "Video Downloader"
	set lien to text returned of rep
	if lien does not start with "http" then
		display alert "Ce n'est pas un lien." message "Copie le lien de la vidéo (il commence par https://), puis réessaie."
		return
	end if
	if button returned of rep is "MP3" then
		set mode to "mp3"
	else
		set mode to "video"
	end if
	set moteur to (POSIX path of (path to home folder)) & "Library/Application Support/VideoDownloader/telecharger.sh"
	do shell script quoted form of moteur & " " & mode & " " & quoted form of lien & " > /dev/null 2>&1 &"
end run
