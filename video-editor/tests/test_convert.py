"""실제 ffmpeg로 짧은 샘플 영상을 만들어 변환 결과를 검증한다."""

import shutil
import tempfile
import unittest
from pathlib import Path

import subprocess

from video_editor.cli import main
from video_editor.commands import NoChangesError, build_command
from video_editor.options import EditSpec, parse_fps, parse_resolution
from video_editor.probe import probe


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg 필요")
class ConvertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.src = cls.tmp / "src.mp4"  # 640x360, 25fps, 48kHz, 1초
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=1",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.src)],
            check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_cli(self, name, *args):
        out = self.tmp / name
        code = main(["convert", str(self.src), "-o", str(out), "-y", *args])
        self.assertEqual(code, 0)
        return probe(out)

    def test_source_is_as_expected(self):
        info = probe(self.src)
        self.assertEqual((info.width, info.height, info.sample_rate), (640, 360, 48000))
        self.assertEqual(info.fps, 25)

    def test_resolution_height_only_keeps_aspect(self):
        info = self.run_cli("a.mp4", "-r", "180p")
        self.assertEqual((info.width, info.height), (320, 180))
        self.assertEqual(info.sample_rate, 48000)
        self.assertEqual(info.audio_codec, "aac")  # 오디오는 그대로 복사

    def test_resolution_contain_pads_to_exact_size(self):
        info = self.run_cli("b.mp4", "-r", "400x400")
        self.assertEqual((info.width, info.height), (400, 400))

    def test_resolution_cover_and_stretch(self):
        for fit in ("cover", "stretch"):
            info = self.run_cli(f"{fit}.mp4", "-r", "400x400", "--fit", fit)
            self.assertEqual((info.width, info.height), (400, 400))

    def test_fps(self):
        info = self.run_cli("c.mp4", "-f", "10")
        self.assertEqual(info.fps, 10)
        self.assertEqual((info.width, info.height), (640, 360))
        self.assertAlmostEqual(info.duration, 1.0, delta=0.15)

    def test_sample_rate_only_copies_video(self):
        info = self.run_cli("d.mp4", "-s", "22050")
        self.assertEqual(info.sample_rate, 22050)
        self.assertEqual((info.width, info.height), (640, 360))
        cmd = build_command(probe(self.src), self.tmp / "x.mp4", EditSpec(sample_rate=22050))
        self.assertIn("copy", cmd)  # -c:v copy

    def test_all_three(self):
        info = self.run_cli("e.mp4", "-r", "320x180", "-f", "15", "-s", "44.1k")
        self.assertEqual((info.width, info.height, info.sample_rate), (320, 180, 44100))
        self.assertEqual(info.fps, 15)

    def test_no_changes(self):
        with self.assertRaises(NoChangesError):
            build_command(probe(self.src), self.tmp / "n.mp4",
                          EditSpec(parse_resolution("640x360"), parse_fps("25"), 48000))

    def test_same_input_output_rejected(self):
        with self.assertRaises(ValueError):
            build_command(probe(self.src), self.src, EditSpec(fps=parse_fps("10")))

    def test_unsupported_extension(self):
        with self.assertRaises(ValueError):
            build_command(probe(self.src), self.tmp / "o.avi", EditSpec(fps=parse_fps("10")))

    def test_existing_output_without_overwrite_fails(self):
        out = self.tmp / "exists.mp4"
        out.write_bytes(b"x")
        self.assertEqual(main(["convert", str(self.src), "-o", str(out), "-f", "10"]), 2)
        self.assertEqual(out.read_bytes(), b"x")

    def test_dry_run_creates_nothing(self):
        out = self.tmp / "dry.mp4"
        self.assertEqual(main(["convert", str(self.src), "-o", str(out), "-f", "10", "--dry-run"]), 0)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
