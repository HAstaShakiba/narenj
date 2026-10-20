"""Wheel contents and every ffmpeg wedge, run against small generated media.

Run with: python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import narenj as n  # noqa: E402


class WheelTest(unittest.TestCase):
    def test_no_wheel_has_more_than_eight_wedges(self):
        for ext, kind in n.EXT_KIND.items():
            for mode in n.MODES:
                with self.subTest(ext=ext, mode=mode):
                    self.assertLessEqual(len(n.wheel_items(mode, kind, n.file_ext(f"x.{ext}"))), 8)

    def test_convert_never_offers_the_same_format(self):
        for ext, kind in n.EXT_KIND.items():
            ids = [a.id for a in n.wheel_items(n.CONVERT, kind, n.file_ext(f"x.{ext}"))]
            self.assertNotIn(n.file_ext(f"x.{ext}"), ids)

    def test_gif_offers_nothing_audio(self):
        for mode in (n.CONVERT, n.TOOLS):
            ids = {a.id for a in n.wheel_items(mode, n.VIDEO, "gif")}
            self.assertFalse(ids & n.AUDIO_ONLY_IDS)

    def test_output_path_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "clip.mp4")
            open(src, "w").close()
            mp3 = next(a for a in n.WHEELS[n.CONVERT] if a.id == "mp3")
            first = n.output_path(src, mp3, n.VIDEO)
            open(first, "w").close()
            self.assertNotEqual(first, n.output_path(src, mp3, n.VIDEO))

    def test_wedges_needing_a_missing_encoder_are_hidden(self):
        saved = n._encoders
        try:
            n._encoders = {"libx264", "aac"}  # an ffmpeg without libwebp, libvpx, ...
            ids = [a.id for a in n.wheel_items(n.CONVERT, n.VIDEO, "mkv")]
            self.assertIn("mp4", ids)
            self.assertNotIn("webp", ids)
            self.assertNotIn("webm", ids)
        finally:
            n._encoders = saved

    def test_every_wedge_icon_ships_with_narenj(self):
        for name in set(n.ICONS.values()):
            with self.subTest(icon=name):
                self.assertTrue(os.path.exists(os.path.join(n.APP_DIR, "icons", f"{name}-symbolic.svg")))

    def test_svg_tools_write_png(self):
        rotate = next(a for a in n.WHEELS[n.TOOLS] if a.id == "rotate")
        self.assertTrue(n.output_path("/tmp/icon.svg", rotate, n.IMAGE).endswith(".png"))


@unittest.skipUnless(n.FFMPEG, "ffmpeg is not installed")
class ActionTest(unittest.TestCase):
    """Runs every ffmpeg wedge each sample file's wheels offer."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

        def make(name, *args):
            path = os.path.join(cls.tmp, name)
            subprocess.run([n.FFMPEG, "-v", "error", "-y", *args, path], check=True)
            return path

        cls.samples = [
            make("clip.mp4", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=2",
                 "-f", "lavfi", "-i", "sine=f=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest"),
            make("tone.wav", "-f", "lavfi", "-i", "sine=f=330:duration=2", "-ac", "2"),
            make("alpha.png", "-f", "lavfi", "-i", "color=c=red@0.5:size=301x201,format=rgba", "-frames:v", "1"),
            make("photo.jpg", "-f", "lavfi", "-i", "testsrc=size=301x201", "-frames:v", "1"),
            make("odd.gif", "-f", "lavfi", "-i", "testsrc=size=301x201:rate=10:duration=1"),
        ]
        subtitles = os.path.join(cls.tmp, "subs.srt")
        with open(subtitles, "w") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")
        cls.samples.append(make("subs.mkv", "-i", cls.samples[0], "-i", subtitles, "-map", "0", "-map", "1",
                                "-c", "copy", "-c:s", "srt"))
        cls.wide = make("wide.mp4", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=1",
                        "-f", "lavfi", "-i", "sine=f=220:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest")
        cls.silent = make("silent.mp4", "-f", "lavfi", "-i", "testsrc=size=200x150:rate=25:duration=1",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p")
        svg = os.path.join(cls.tmp, "icon.svg")
        with open(svg, "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="48">'
                    '<circle cx="24" cy="24" r="20" fill="orange"/></svg>')
        cls.samples.append(svg)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_every_wedge(self):
        for src in self.samples:
            kind = n.kind_of(src)
            for mode in (n.CONVERT, n.TOOLS):
                for action in n.wheel_items(mode, kind, n.file_ext(src)):
                    if action.id == "srt" and not n.has_stream(src, "subtitle"):
                        continue  # the app says "No subtitles" instead of running ffmpeg
                    with self.subTest(file=os.path.basename(src), action=action.id):
                        dst = n.output_path(src, action, kind)
                        trim = (("-ss", "0.2"), ("-t", "0.5")) if action.prompt == "trim" else ((), ())
                        cmd = n.ffmpeg_command(src, kind, action, dst, *trim)
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr[-400:])
                        self.assertGreater(os.path.getsize(dst), 0)

    def run_join(self, files, kind):
        join = next(a for a in n.WHEELS[n.ACTIONS] if a.id == "join")
        dst = n.output_path(files[0], join, kind)
        result = subprocess.run(n.join_command(files, kind, dst), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        return dst

    def test_join_videos_of_different_sizes(self):
        dst = self.run_join([self.samples[0], self.wide], n.VIDEO)
        self.assertAlmostEqual(n.probe_duration(dst), 3.0, delta=0.3)
        video = next(s for s in n.probe(dst)["streams"] if s["codec_type"] == "video")
        self.assertEqual((video["width"], video["height"]), (320, 240))

    def test_join_without_audio(self):
        dst = self.run_join([self.samples[0], self.silent], n.VIDEO)
        self.assertFalse(n.has_stream(dst, "audio"))

    def test_join_audio(self):
        dst = self.run_join([self.samples[1], self.samples[1]], n.AUDIO)
        self.assertAlmostEqual(n.probe_duration(dst), 4.0, delta=0.2)

    def test_join_order_is_natural(self):
        self.assertEqual(sorted(["clip10.mp4", "clip2.mp4", "Clip1.mp4"], key=n.natural_key),
                         ["Clip1.mp4", "clip2.mp4", "clip10.mp4"])


if __name__ == "__main__":
    unittest.main()
