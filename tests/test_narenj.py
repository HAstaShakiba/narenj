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
                    with self.subTest(file=os.path.basename(src), action=action.id):
                        dst = n.output_path(src, action, kind)
                        trim = (("-ss", "0.2"), ("-t", "0.5")) if action.prompt == "trim" else ((), ())
                        cmd = n.ffmpeg_command(src, kind, action, dst, *trim)
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr[-400:])
                        self.assertGreater(os.path.getsize(dst), 0)


if __name__ == "__main__":
    unittest.main()
