import unittest
from fractions import Fraction

from video_editor.options import parse_fps, parse_resolution, parse_sample_rate


class ParseTests(unittest.TestCase):
    def test_resolution_forms(self):
        self.assertEqual((parse_resolution("1280x720").width, parse_resolution("1280x720").height), (1280, 720))
        self.assertEqual(parse_resolution("720p").height, 720)
        self.assertIsNone(parse_resolution("720p").width)
        self.assertEqual(parse_resolution("4K").height, 2160)
        self.assertEqual(parse_resolution("180p").height, 180)
        self.assertEqual(parse_resolution("640x").width, 640)
        self.assertEqual(parse_resolution("x480").height, 480)

    def test_resolution_invalid(self):
        for bad in ("", "x", "abc", "1281x720", "0p", "0x720", "-2x720"):
            with self.assertRaises(ValueError, msg=bad):
                parse_resolution(bad)

    def test_fps(self):
        self.assertEqual(parse_fps("30"), 30)
        self.assertEqual(parse_fps("30000/1001"), Fraction(30000, 1001))
        self.assertEqual(parse_fps("29.97"), Fraction(2997, 100))
        for bad in ("0", "-1", "abc", "1000", "1/0"):
            with self.assertRaises(ValueError, msg=bad):
                parse_fps(bad)

    def test_sample_rate(self):
        self.assertEqual(parse_sample_rate("44100"), 44100)
        self.assertEqual(parse_sample_rate("44.1k"), 44100)
        self.assertEqual(parse_sample_rate("48K"), 48000)
        for bad in ("abc", "100", "999999"):
            with self.assertRaises(ValueError, msg=bad):
                parse_sample_rate(bad)


if __name__ == "__main__":
    unittest.main()
