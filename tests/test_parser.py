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


if __name__ == "__main__":
    unittest.main()
