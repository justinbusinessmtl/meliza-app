-- Video Downloader: a tiny Mac app in front of yt-dlp.
-- • Click the app: downloads the link on your clipboard (Video / MP3 / Transcript).
-- • Browser buttons open videodl://video?url=... links, handled by "on open location".
-- The real work happens in the background, in the `vdl` command next to this app's support files.

on vdlPath()
	return (POSIX path of (path to home folder)) & "Library/Application Support/VideoDownloader/vdl"
end vdlPath

on startInBackground(args)
	do shell script quoted form of vdlPath() & " " & args & " > /dev/null 2>&1 &"
end startInBackground

on run
	set clip to ""
	try
		set clip to (the clipboard as text)
	end try
	set theURL to ""
	try
		set theURL to do shell script quoted form of vdlPath() & " check-url " & quoted form of clip
	end try
	if theURL is "" then
		display dialog "No video link on your clipboard." & return & return & ¬
			"Copy a video link first (⌘C), then click Video Downloader again." & return & return & ¬
			"Tip: the browser buttons are even faster, no copying needed." buttons {"OK"} default button "OK" ¬
			with title "Video Downloader" with icon caution
		return
	end if
	set shown to theURL
	if (length of shown) > 70 then set shown to (text 1 thru 67 of shown) & "…"
	set choice to button returned of (display dialog "What do you want from this link?" & return & return & shown ¬
		buttons {"Transcript", "MP3", "Video"} default button "Video" with title "Video Downloader")
	if choice is "Video" then
		set mode to "video"
	else if choice is "MP3" then
		set mode to "mp3"
	else
		set mode to "transcript"
	end if
	startInBackground("run " & mode & " " & quoted form of theURL)
end run

on open location theLink
	startInBackground("link " & quoted form of theLink)
end open location
