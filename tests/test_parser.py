import unittest
from parser import parse_filename


class TestParserSeasonEpisodePatterns(unittest.TestCase):
    def test_sxxeyy_pattern(self):
        parsed = parse_filename("Air.Crash.Investigations.S03E07.avi")

        self.assertEqual(parsed.show_name, "Air Crash Investigations")
        self.assertEqual(parsed.season, "03")
        self.assertEqual(parsed.episode, "07")
        self.assertEqual(parsed.title, "")

    def test_x_pattern(self):
        parsed = parse_filename(
            "Air Crash Investigations  3x07 - Helicopter Down (Helicopter G-TIGK).avi"
        )

        self.assertEqual(parsed.show_name, "Air Crash Investigations")
        self.assertEqual(parsed.season, "03")
        self.assertEqual(parsed.episode, "07")
        self.assertEqual(parsed.title, "Helicopter Down (Helicopter G-TIGK)")


class TestParser(unittest.TestCase):
    def test_full_pattern_1(self):
        parsed = parse_filename("Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4")

        self.assertEqual(parsed.show_name, "Better Call Saul")
        self.assertEqual(parsed.season, "01")
        self.assertEqual(parsed.episode, "10")
        self.assertEqual(parsed.title, "Marco")
        self.assertEqual(parsed.resolution, "1080p")
        self.assertEqual(parsed.codec, "x265")
        self.assertEqual(parsed.release_group, "RARBG")

    def test_full_pattern_2(self):
        parsed = parse_filename(
            "Mayday.S26E10.Mixed.Measures.2160P.CRVE.WEB-DL.H265.DDP.5.1.ENG.FRA-NS225.mkv"
        )

        self.assertEqual(parsed.show_name, "Mayday")
        self.assertEqual(parsed.season, "26")
        self.assertEqual(parsed.episode, "10")
        self.assertEqual(parsed.title, "Mixed Measures")
        self.assertEqual(parsed.resolution, "2160P")
        self.assertEqual(parsed.source, "CRVE.WEB-DL")
        self.assertEqual(parsed.codec, "H265")
        self.assertEqual(parsed.audio_codec, "DDP.5.1")
        self.assertEqual(parsed.lang, "ENG.FRA")
        self.assertEqual(parsed.release_group, "NS225")

    def test_full_pattern_3(self):
        parsed = parse_filename(
            "Mayday S03E10 Head on Collision 1080p AMZN WEB-DL DD 2 0 H 264-playWEB.mkv"
        )

        self.assertEqual(parsed.show_name, "Mayday")
        self.assertEqual(parsed.season, "03")
        self.assertEqual(parsed.episode, "10")
        self.assertEqual(parsed.title, "Head on Collision")
        self.assertEqual(parsed.resolution, "1080p")
        self.assertEqual(parsed.source, "AMZN.WEB-DL")
        self.assertEqual(parsed.codec, "H.264")
        self.assertEqual(parsed.audio_codec, "DD.2.0")
        self.assertEqual(parsed.release_group, "playWEB")

    def test_full_pattern_4(self):
        parsed = parse_filename(
            "Air.Crash.Investigation.S16E01.Deadly.Silence.(1999.South.Dakota.Learjet.35.Crash).1080p.WEB-DL.H264.DDP-HDCTV.mkv"
        )

        self.assertEqual(parsed.show_name, "Air Crash Investigation")
        self.assertEqual(parsed.season, "16")
        self.assertEqual(parsed.episode, "01")
        self.assertEqual(
            parsed.title, "Deadly Silence (1999 South Dakota Learjet 35 Crash)"
        )
        self.assertEqual(parsed.resolution, "1080p")
        self.assertEqual(parsed.source, "WEB-DL")
        self.assertEqual(parsed.codec, "H264")
        self.assertEqual(parsed.audio_codec, "DDP")
        self.assertEqual(parsed.release_group, "HDCTV")
