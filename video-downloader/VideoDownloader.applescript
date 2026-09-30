-- Video Downloader : une fenêtre, un ou plusieurs liens, Vidéo ou MP3 (le son seulement).
on sansRetours(t)
	set AppleScript's text item delimiters to {return, linefeed, tab}
	set morceaux to text items of t
	set AppleScript's text item delimiters to " "
	set t to morceaux as text
	set AppleScript's text item delimiters to ""
	return t
end sansRetours

on run
	set liens to ""
	try
		set liens to my sansRetours(the clipboard as text)
	end try
	if liens does not contain "http" then set liens to ""
	set rep to display dialog "Lien(s) de la vidéo :" & return & ¬
		"Tu peux coller plusieurs liens, séparés par un espace." default answer liens ¬
		buttons {"Annuler", "MP3 (son seulement)", "Vidéo"} default button "Vidéo" cancel button "Annuler" ¬
		with title "Video Downloader"
	set liens to text returned of rep
	if liens does not contain "http" then
		display alert "Ce n'est pas un lien." message "Copie le lien de la vidéo (il commence par https://), puis réessaie."
		return
	end if
	if button returned of rep is "Vidéo" then
		set mode to "video"
	else
		set mode to "mp3"
	end if
	set moteur to (POSIX path of (path to home folder)) & "Library/Application Support/VideoDownloader/telecharger.sh"
	do shell script quoted form of moteur & " " & mode & " " & quoted form of liens & " > /dev/null 2>&1 &"
end run
