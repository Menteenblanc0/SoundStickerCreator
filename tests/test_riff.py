import json
import struct
import unittest
from io import BytesIO
from PIL import Image
from riff import add_pack, chunks, inspect, pack_info


class RiffTests(unittest.TestCase):
    def make_webp(self, animated=False):
        stream = BytesIO()
        first = Image.new("RGBA", (64, 80), (0, 0, 0, 0))
        second = Image.new("RGBA", (64, 80), (100, 0, 0, 128))
        args = dict(save_all=True, append_images=[second], duration=[66, 67], loop=0) if animated else {}
        first.save(stream, "WEBP", **args)
        return stream.getvalue()

    def test_animation_and_padding(self):
        data = self.make_webp(True)
        report = inspect(data+b"test")
        self.assertEqual((64, 80), (report["width"], report["height"]))
        self.assertEqual(report["loop"], 0)
        self.assertEqual(report["frame_count"], 2)
        self.assertEqual(report["duration_ms"], 133)
        self.assertEqual(report["trailing_bytes"], 4)
        self.assertEqual(report["unknown_chunks"], [])
        self.assertEqual(bytes(next(chunks(b"TEST\x01\x00\x00\x00x\x00"))[1]), b"x")

    def test_written_pack_round_trip_and_alpha(self):
        original = self.make_webp()
        metadata = {"sticker-pack-name": "Prueba", "emojis": ["🥰"]}
        edited = add_pack(original, metadata)
        self.assertEqual(inspect(edited)["pack"], metadata)
        self.assertTrue(inspect(edited)["flags"] & 8)
        with Image.open(BytesIO(edited)) as image:
            self.assertEqual(image.convert("RGBA").getpixel((0, 0))[3], 0)

    def test_big_endian_exif_and_legacy_little_endian(self):
        binary = json.dumps({"sticker-pack-name": "test"}).encode()
        for endian, byteorder, offset in ((">", b"MM", 26), ("<", b"II", 22)):
            exif = byteorder + struct.pack(endian+"HIHHHII", 42, 8, 1, 0x5741, 7, len(binary), offset)
            if offset == 26:
                exif += b"\0"*4
            self.assertEqual(pack_info(exif+binary), {"sticker-pack-name": "test"})
            self.assertIsNone(pack_info(exif+binary[:-1]))

    def test_invalid_riff_lengths(self):
        data = self.make_webp()
        for broken in (b"", b"Not RIFF", data[:-1], data[:4]+b"\x01\x00\x00\x00"+data[8:]):
            with self.subTest(length=len(broken)), self.assertRaises(ValueError):
                inspect(broken)
