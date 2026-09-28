"""Offline tests for the Video Downloader engine: python3 -m unittest discover -s tests"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("VDL_LOG", os.path.join(tempfile.gettempdir(), "vdl-test.log"))
os.environ.setdefault("VDL_NOTIFY", "print")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vdl  # noqa: E402

try:
    from yt_dlp import YoutubeDL
except ImportError:  # pragma: no cover
    YoutubeDL = None


def vfmt(fid, height, vcodec="avc1.4d401f", ext="mp4"):
    return {"format_id": fid, "url": f"https://x/{fid}", "ext": ext, "protocol": "https",
            "height": height, "width": height * 16 // 9, "vcodec": vcodec, "acodec": "none", "tbr": height}


def afmt(fid, acodec="mp4a.40.2", ext="m4a", abr=128):
    return {"format_id": fid, "url": f"https://x/{fid}", "ext": ext, "protocol": "https",
            "vcodec": "none", "acodec": acodec, "abr": abr, "tbr": abr}


def progressive(fid, height):
    return {"format_id": fid, "url": f"https://x/{fid}", "ext": "mp4", "protocol": "https",
            "height": height, "width": height * 16 // 9, "vcodec": "avc1", "acodec": "mp4a.40.2"}


@unittest.skipIf(YoutubeDL is None, "yt-dlp not installed")
class FormatSelectionTest(unittest.TestCase):
    def pick(self, formats):
        opts = {"format": vdl.VIDEO_FORMAT, "format_sort": vdl.VIDEO_SORT, "quiet": True,
                "simulate": True, "logger": vdl.YDLLogger()}
        info = {"id": "t", "title": "t", "extractor": "generic", "extractor_key": "Generic",
                "webpage_url": "https://x/t", "formats": formats}
        with YoutubeDL(opts) as ydl:
            result = ydl.process_ie_result(info, download=False)
        return result["format_id"]

    def test_prefers_720_h264_over_vp9_and_1080(self):
        formats = [vfmt("1080", 1080), vfmt("720vp9", 720, "vp09.00.40.08", "webm"),
                   vfmt("720", 720), vfmt("480", 480), afmt("opus", "opus", "webm", 160), afmt("aac")]
        self.assertEqual(self.pick(formats), "720+aac")

    def test_falls_back_to_1080(self):
        formats = [vfmt("2160", 2160), vfmt("1080", 1080), vfmt("480", 480), afmt("aac")]
        self.assertEqual(self.pick(formats), "1080+aac")

    def test_then_best_below_1080(self):
        formats = [vfmt("1440", 1440), vfmt("540", 540), vfmt("360", 360), afmt("aac")]
        self.assertEqual(self.pick(formats), "540+aac")

    def test_then_anything(self):
        formats = [vfmt("2160", 2160), vfmt("1440", 1440), afmt("aac")]
        self.assertEqual(self.pick(formats), "1440+aac")

    def test_progressive_only(self):
        formats = [progressive("p1080", 1080), progressive("p720", 720), progressive("p360", 360)]
        self.assertEqual(self.pick(formats), "p720")


YOUTUBE_AUTO_VTT = """WEBVTT
Kind: captions
Language: fr

00:00:00.160 --> 00:00:02.990 align:start position:0%
 
bonjour<00:00:00.480><c> tout</c><00:00:00.640><c> le</c><00:00:00.800><c> monde</c>

00:00:02.990 --> 00:00:03.000 align:start position:0%
bonjour tout le monde
 

00:00:03.000 --> 00:00:05.270 align:start position:0%
bonjour tout le monde
aujourd'hui<00:00:03.520><c> on</c><00:00:03.760><c> parle</c> &amp; on apprend

00:00:05.270 --> 00:00:05.280 align:start position:0%
aujourd'hui on parle &amp; on apprend
 

00:00:09.000 --> 00:00:11.000 align:start position:0%
aujourd'hui on parle &amp; on apprend
nouvelle<00:00:09.300><c> idée</c>
"""

SRT = """1
00:00:01,000 --> 00:00:02,500
Hello there.

2
00:00:02,600 --> 00:00:04,000
Nice to <i>meet</i> you.
"""


class TranscriptTest(unittest.TestCase):
    def test_youtube_auto_captions_are_deduped(self):
        entries = vdl.dedupe_cues(vdl.parse_cues(YOUTUBE_AUTO_VTT))
        self.assertEqual([e[2] for e in entries],
                         ["bonjour tout le monde", "aujourd'hui on parle & on apprend", "nouvelle idée"])
        self.assertAlmostEqual(entries[0][0], 0.16)
        self.assertLessEqual(entries[0][1], entries[1][0])

    def test_paragraph_break_on_long_pause(self):
        entries = vdl.dedupe_cues(vdl.parse_cues(YOUTUBE_AUTO_VTT))
        paragraphs = vdl.to_paragraphs(entries)
        self.assertEqual(paragraphs, ["bonjour tout le monde aujourd'hui on parle & on apprend", "nouvelle idée"])

    def test_srt_roundtrip(self):
        entries = vdl.dedupe_cues(vdl.parse_cues(SRT))
        self.assertEqual([e[2] for e in entries], ["Hello there.", "Nice to meet you."])
        srt = vdl.to_srt(entries)
        self.assertIn("00:00:01,000 --> 00:00:02,500\nHello there.", srt)
        self.assertEqual([c[2] for c in vdl.parse_cues(srt)], [["Hello there."], ["Nice to meet you."]])

    def track(self, ext="vtt"):
        return [{"ext": "json3", "url": "u"}, {"ext": ext, "url": "u"}]

    def test_pick_manual_in_spoken_language(self):
        info = {"language": "fr", "subtitles": {"fr": self.track(), "en": self.track()},
                "automatic_captions": {"fr-orig": self.track()}}
        self.assertEqual(vdl.pick_caption(info)[0], "fr")

    def test_pick_original_auto_track(self):
        info = {"language": "fr", "subtitles": {},
                "automatic_captions": {"en": self.track(), "fr": self.track(), "fr-orig": self.track()}}
        key, _, is_auto = vdl.pick_caption(info)
        self.assertEqual((key, is_auto), ("fr-orig", True))

    def test_unknown_language_uses_orig_track(self):
        info = {"subtitles": {}, "automatic_captions": {"de": self.track(), "es-orig": self.track()}}
        self.assertEqual(vdl.pick_caption(info)[0], "es-orig")

    def test_no_translated_auto_captions(self):
        info = {"language": "es", "subtitles": {}, "automatic_captions": {"en": self.track(), "fr": self.track()}}
        self.assertIsNone(vdl.pick_caption(info))

    def test_generic_site_manual_subs(self):
        info = {"subtitles": {"en-US": self.track("srt")}}
        self.assertEqual(vdl.pick_caption(info)[0], "en-US")


class HelpersTest(unittest.TestCase):
    def test_parse_link(self):
        link = "videodl://mp3?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dabc%26t%3D5"
        self.assertEqual(vdl.parse_link(link), ("mp3", "https://www.youtube.com/watch?v=abc&t=5"))
        self.assertEqual(vdl.parse_link("videodl://video?url=https%3A%2F%2Fx.com%2Fa")[0], "video")
        with self.assertRaises(ValueError):
            vdl.parse_link("videodl://delete?url=https%3A%2F%2Fx.com")
        with self.assertRaises(ValueError):
            vdl.parse_link("videodl://video?url=notaurl")

    def test_find_url(self):
        self.assertEqual(vdl.find_url("  https://youtu.be/abc  \n"), "https://youtu.be/abc")
        self.assertEqual(vdl.find_url("see (https://vimeo.com/123)."), "https://vimeo.com/123")
        self.assertIsNone(vdl.find_url("just some text"))

    def test_safe_filename(self):
        self.assertEqual(vdl.safe_filename('A/B: "C"?'), "A B C")
        self.assertEqual(len(vdl.safe_filename("x" * 400)), 150)

    def test_friendly_errors(self):
        self.assertIn("DRM", vdl.friendly_error("ERROR: [generic] This video is DRM protected"))
        self.assertIn("isn't supported", vdl.friendly_error("ERROR: Unsupported URL: https://x"))
        self.assertIn("internet", vdl.friendly_error("Unable to download webpage: <urlopen error>"))
        self.assertIn("vdl update", vdl.friendly_error("weird thing"))


if __name__ == "__main__":
    unittest.main()
