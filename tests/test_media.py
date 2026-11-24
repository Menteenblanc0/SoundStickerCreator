from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest

from PIL import Image
from media import Edit, Engine


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="sticker-tests-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.root = Path(cls.workspace.name)
        cls.video = cls.root / "Vídeo [prueba] & archivo.mp4"
        cls.png = cls.root / "Imagen transparente.png"
        cls.wav = cls.root / "Tono 440.wav"
        cls.engine = Engine()
        cls.engine.ff(["-f", "lavfi", "-i", "testsrc2=size=160x96:rate=20",
                       "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
                       "-c:v", "libx264", "-c:a", "aac", str(cls.video)])
        cls.engine.ff(["-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(cls.wav)])
        Image.new("RGBA", (160, 96), (120, 10, 20, 128)).save(cls.png)

    def test_video_to_two_components_and_reimport_webp(self):
        converted = self.root/"video"
        edit = Edit(start=.1, duration=1.4, size=160, fps=12, loop=2)
        report = self.engine.convert(self.video, None, converted, edit)
        self.assertEqual(report["width"], 160)
        self.assertGreater(report["frame_count"], 10)
        self.assertEqual(report["loop"], 2)
        self.assertAlmostEqual(report["audioSeconds"], report["duration_ms"]/1000, delta=.03)
        self.assertTrue((converted/"audio.ogg").exists())
        again = self.engine.convert(converted/"sticker.webp", None, self.root/"reimport", Edit(start=.25, duration=.6))
        self.assertTrue(again["animated"])
        self.assertAlmostEqual(again["duration_ms"]/1000, .6, delta=.15)
        self.assertIsNone(again["audioSeconds"])

    def test_transparency_crop_and_audio_delay(self):
        out = self.root/"delay"
        edit = Edit(duration=1, size=128, delay=.3, crop=(120, 70, 10, 5), fade_out=.1)
        report = self.engine.convert(self.png, self.wav, out, edit)
        self.assertFalse(report["animated"])
        with Image.open(out/"sticker.webp") as image:
            self.assertEqual(image.convert("RGBA").getpixel((0,0))[3], 0)
            self.assertGreater(image.convert("RGBA").getpixel((64,64))[3], 0)
        peaks = self.engine.waveform(out/"audio.ogg")
        self.assertLess(max(peaks[:25]), .03)
        self.assertGreater(max(peaks[60:90]), .05)
        self.assertAlmostEqual(report["audioSeconds"], 1, delta=.03)

    def test_compression_reduces_when_requested(self):
        normal = self.engine.convert(self.video, None, self.root/"high", Edit(duration=.75, quality=90))
        budget = normal["bytes"] * 3 // 4
        reduced = self.engine.convert(self.video, None, self.root/"compact", Edit(duration=.75, quality=90, budget=budget))
        self.assertLessEqual(reduced["bytes"], budget)
        self.assertEqual(normal["frame_count"], reduced["frame_count"])

    def test_failure_leaves_no_partial_output_or_stage(self):
        corrupt = self.root/"corrupta.webp"
        corrupt.write_bytes(b"RIFF\x80\x00\x00\x00WEBP")
        before = set(self.root.iterdir())
        with self.assertRaises(ValueError):
            self.engine.convert(corrupt, None, self.root/"bad", Edit())
        self.assertEqual(set(self.root.iterdir()), before)
        with self.assertRaises(ValueError):
            self.engine.convert(self.video, None, self.root/"bad", Edit(duration=.5, budget=1024))
        self.assertEqual(set(self.root.iterdir()), before)

    def test_bad_formats_and_parameters(self):
        with self.assertRaises(ValueError):
            self.engine.convert(self.wav, None, self.root/"badformat", Edit())
        for edit in (Edit(delay=float("nan")), Edit(crop=(0, 1, 2, 3)), Edit(start=-1)):
            with self.assertRaises(ValueError):
                edit.validate()

    def test_transport_requires_account_opt_in(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root/"app.py"), "receive"], capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"--test-account", result.stderr)
