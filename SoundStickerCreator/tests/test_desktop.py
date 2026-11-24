"""GUI smoke test that runs when a display and FFmpeg are available."""
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from media import Engine


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "requires a display")
@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg")
class DesktopTests(unittest.TestCase):
    def test_generate_preview_and_cleanup(self):
        import tkinter as tk
        from tkinterdnd2 import DND_FILES, TkinterDnD
        from desktop import Editor

        with tempfile.TemporaryDirectory(prefix="sticker-gui-test-") as temp:
            path = Path(temp)
            clip = path/"Video sintético.mp4"
            engine = Engine()
            engine.ff(["-f", "lavfi", "-i", "testsrc2=size=100x80:rate=15",
                       "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1",
                       "-c:v", "libx264", "-c:a", "aac", str(clip)])
            try:
                root = TkinterDnD.Tk()
            except (tk.TclError, RuntimeError) as error:
                self.skipTest(str(error))
            with patch("desktop.SETTINGS", path/"settings.json"):
                editor = Editor(root, engine, DND_FILES)
            root.update()
            try:
                editor.visual.set(str(clip))
                editor.values["duration"].set("0.8")
                editor.generate()
                deadline = time.monotonic()+15
                while editor.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.02)
                self.assertTrue(editor.current(), editor.status.get())
                self.assertTrue(editor.report["animated"])
                self.assertTrue(editor.wave)
                editor.draw_frame(.4)
                editor.draw_wave(.4)
                editor.play()
                root.update_idletasks()
                editor.stop()
                scratch = Path(editor.scratch.name)
                editor.close()
                self.assertFalse(scratch.exists())
            finally:
                if editor.busy:
                    root.destroy()
