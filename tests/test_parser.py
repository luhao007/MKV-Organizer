from parser import detect_anime_episode_numbers, parse_filename
from typing import Final, NotRequired, TypedDict

import pytest


class TestScenario(TypedDict):
    filename: str
    expected: dict[str, str | list[str]]
    is_show: NotRequired[bool]  # Default to True


TestScenarios = dict[str, TestScenario]


SEASON_EPISODE_TEST_CASES: Final[TestScenarios] = {
    "sxxeyy_pattern": {
        "filename": "Air.Crash.Investigations.S03E07.avi",
        "is_show": True,
        "expected": {
            "show_name": "Air Crash Investigations",
            "season": "03",
            "episode": "07",
            "title": "",
        },
    },
    "x_pattern": {
        "filename": (
            "Air Crash Investigations  3x07 - Helicopter Down (Helicopter G-TIGK).avi"
        ),
        "is_show": True,
        "expected": {
            "show_name": "Air Crash Investigations",
            "season": "03",
            "episode": "07",
            "title": "Helicopter Down (Helicopter G-TIGK)",
        },
    },
}


@pytest.mark.parametrize("name,case", SEASON_EPISODE_TEST_CASES.items())
def test_patterns(name: str, case: TestScenario):
    parsed = parse_filename(case["filename"], case.get("is_show", True))
    for field, value in case["expected"].items():
        assert getattr(parsed, field) == value


FULL_PARSE_TEST_CASES: Final[TestScenarios] = {
    "full_pattern_1": {
        "filename": "Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4",
        "expected": {
            "show_name": "Better Call Saul",
            "season": "01",
            "episode": "10",
            "title": "Marco",
            "resolution": "1080p",
            "codec": "x265",
            "release_group": "RARBG",
        },
    },
    "full_pattern_2": {
        "filename": (
            "Mayday.S26E10.Mixed.Measures.2160P.CRVE.WEB-DL.H265.DDP.5.1."
            "ENG.FRA-NS225.mkv"
        ),
        "expected": {
            "show_name": "Mayday",
            "season": "26",
            "episode": "10",
            "title": "Mixed Measures",
            "resolution": "2160P",
            "source": "CRVE.WEB-DL",
            "codec": "H265",
            "audio_codecs": ["DDP.5.1"],
            "lang": "ENG.FRA",
            "release_group": "NS225",
        },
    },
    "full_pattern_3": {
        "filename": (
            "Mayday S03E10 Head on Collision 1080p AMZN WEB-DL DD 2 0 H 264-playWEB.mkv"
        ),
        "expected": {
            "show_name": "Mayday",
            "season": "03",
            "episode": "10",
            "title": "Head on Collision",
            "resolution": "1080p",
            "source": "AMZN.WEB-DL",
            "codec": "H.264",
            "audio_codecs": ["DD.2.0"],
            "release_group": "playWEB",
        },
    },
    "full_pattern_4": {
        "filename": (
            "Air.Crash.Investigation.S16E01.Deadly.Silence.(1999.South."
            "Dakota.Learjet.35.Crash).1080p.WEB-DL.H264.DDP-HDCTV.mkv"
        ),
        "expected": {
            "show_name": "Air Crash Investigation",
            "season": "16",
            "episode": "01",
            "title": "Deadly Silence (1999 South Dakota Learjet 35 Crash)",
            "resolution": "1080p",
            "source": "WEB-DL",
            "codec": "H264",
            "audio_codecs": ["DDP"],
            "release_group": "HDCTV",
        },
    },
    "full_pattern_5": {
        "filename": (
            "Air.Crash.Investigation.S01E03.Fire.On.Board.(Swissair.Flight."
            "111).1080p.YTB.WEB-DL.VP9.Opus.mkv"
        ),
        "expected": {
            "show_name": "Air Crash Investigation",
            "season": "01",
            "episode": "03",
            "title": "Fire On Board (Swissair Flight 111)",
            "resolution": "1080p",
            "source": "YTB.WEB-DL",
            "codec": "VP9",
            "audio_codecs": ["Opus"],
        },
    },
    "full_pattern_6": {
        "filename": (
            "Air.Crash.Investigation.S01E03.Fire.On.Board.(Swissair.Flight."
            "111).1080p.YTB.WEB-DL.VP9.Opus.eng.srt"
        ),
        "expected": {
            "show_name": "Air Crash Investigation",
            "season": "01",
            "episode": "03",
            "title": "Fire On Board (Swissair Flight 111)",
            "resolution": "1080p",
            "source": "YTB.WEB-DL",
            "codec": "VP9",
            "audio_codecs": ["Opus"],
            "lang": "eng",
        },
    },
    "full_pattern_7": {
        "filename": (
            "Moon.Knight.S01E06.Gods.and.Monsters.UHD.BluRay.2160p.TrueHD."
            "Atmos.7.1.DV.HEVC.HYBRID.REMUX-FraMeSToR.zh.chs&eng.ass"
        ),
        "expected": {
            "show_name": "Moon Knight",
            "season": "01",
            "episode": "06",
            "title": "Gods and Monsters",
            "source": "UHD.BluRay",
            "package": "REMUX",
            "hdr": "DV.HYBRID",
            "codec": "HEVC",
            "audio_codecs": ["TrueHD.Atmos.7.1"],
            "lang": "zh.chs&eng",
            "release_group": "FraMeSToR",
        },
    },
    "dot_pattern": {
        "filename": (
            "Loki - S01.E04 - The Nexus Event 2160p UHD BDRip DV HDR10 x265 TrueHD"
            " Atmos 7.1-SEV.mkv"
        ),
        "is_show": True,
        "expected": {
            "show_name": "Loki",
            "season": "01",
            "episode": "04",
            "title": "The Nexus Event",
            "resolution": "2160p",
            "source": "BDRip",
            "hdr": "DV.HDR10",
            "codec": "x265",
            "audio_codecs": ["TrueHD.Atmos.7.1"],
        },
    },
    "branket_pattern_1": {
        "filename": (
            "Avengers Infinity War (2018) [Hybrid][Remux-2160p][DV HDR10][TrueHD"
            " Atmos 7.1][HEVC]-FraMeSToR.mkv"
        ),
        "is_show": False,
        "expected": {
            "show_name": "Avengers Infinity War",
            "season": "",
            "episode": "",
            "title": "",
            "source": "",
            "year": "2018",
            "package": "Remux",
            "hdr": "Hybrid.DV.HDR10",
            "codec": "HEVC",
            "audio_codecs": ["TrueHD.Atmos.7.1"],
            "release_group": "FraMeSToR",
        },
    },
    "branket_pattern_2": {
        "filename": (
            "Thor Ragnarok (2017) {imdb-tt3501632} - {edition-IMAX}"
            " [2160p][WEB-DL][HEVC][DV 8.1][TrueHD Atmos 7.1][IMAX"
            " Enhanced]-SiC.mkv"
        ),
        "is_show": False,
        "expected": {
            "show_name": "Thor Ragnarok",
            "edition": "{edition-IMAX}",
            "imdb_id": "tt3501632",
            "year": "2017",
            "hdr": "DV.8.1",
            "codec": "HEVC",
            "audio_codecs": ["TrueHD.Atmos.7.1"],
            "release_group": "SiC",
            "source": "WEB-DL",
            "resolution": "2160p",
            "extras": ["IMAX.Enhanced"],
        },
    },
}


@pytest.mark.parametrize("name,case", FULL_PARSE_TEST_CASES.items())
def test_full_filename_patterns(name: str, case: TestScenario):
    parsed = parse_filename(case["filename"], case.get("is_show", True))
    for field, value in case["expected"].items():
        assert getattr(parsed, field) == value


# ============================================================================
# Anime parsing
# ============================================================================


ANIME_PARSE_TEST_CASES: Final[TestScenarios] = {
    "main_example": {
        "filename": "Detective Conan - 0123 [1080p][Multiple Subtitle][FDB1F25C].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Detective Conan",
            "season": "01",
            "episode": "0123",
            "title": "",
            "resolution": "1080p",
        },
    },
    "subtitle_language": {
        "filename": "Detective Conan - 0125 [1080p][DDP 5.1][FDB1F25C].chs.srt",
        "is_show": True,
        "expected": {
            "show_name": "Detective Conan",
            "season": "01",
            "episode": "0125",
            "title": "",
            "resolution": "1080p",
            "audio_codecs": ["DDP.5.1"],
            "lang": "chs",
        },
    },
    "keeps_episode_title": {
        "filename": "Show Name - 0002 - The Episode Title [1080p][HEVC].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Show Name",
            "season": "01",
            "episode": "0002",
            "title": "The Episode Title",
            "resolution": "1080p",
            "codec": "HEVC",
        },
    },
    "dot_style_no_brackets": {
        "filename": "Show.Name.0003.1080p.x265.mkv",
        "is_show": True,
        "expected": {
            "show_name": "Show Name",
            "season": "01",
            "episode": "0003",
            "title": "",
            "resolution": "1080p",
            "codec": "x265",
        },
    },
    "parenthesized_resolution": {
        "filename": "[SubsPlease] Detective Conan - 0004 (1080p) [deadbeef].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Detective Conan",
            "season": "01",
            "episode": "0004",
            "title": "",
            "resolution": "1080p",
        },
    },
    "pads_short_number_to_4_digits": {
        "filename": "Show - 123 [1080p].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Show",
            "season": "01",
            "episode": "0123",
            "title": "",
        },
    },
    "explicit_sxxe_uses_actual_marker": {
        "filename": "Show Name - S01E0005 [1080p][HEVC].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Show Name",
            "season": "01",
            "episode": "0005",
            "title": "",
            "resolution": "1080p",
            "codec": "HEVC",
        },
    },
}


@pytest.mark.parametrize(
    "name,case",
    ANIME_PARSE_TEST_CASES.items(),
    ids=ANIME_PARSE_TEST_CASES.keys(),
)
def test_anime_filename_patterns(name: str, case: TestScenario):
    parsed = parse_filename(case["filename"], case.get("is_show", True), is_anime=True)
    for field, value in case["expected"].items():
        assert getattr(parsed, field) == value


def test_anime_fallback_unique_numeric_token():
    """is_anime without an explicit episode falls back to a unique number."""
    parsed = parse_filename("Show - 0042 [1080p].mkv", is_anime=True)
    assert parsed.show_name == "Show"
    assert (parsed.season, parsed.episode) == ("01", "0042")


# ============================================================================
# detect_anime_episode_numbers (folder-level consecutive-number detection)
# ============================================================================


def test_detect_anime_consecutive_folder():
    files = [
        "Detective Conan - 0123 [1080p][Multiple Subtitle][FDB1F25C].mkv",
        "Detective Conan - 0124 [1080p][Multiple Subtitle][AABBCCDD].mkv",
        "Detective Conan - 0125 [1080p][DDP 5.1][11223344].chs.srt",
    ]
    detected = detect_anime_episode_numbers(files)
    assert detected == {files[0]: "0123", files[1]: "0124", files[2]: "0125"}


def test_detect_anime_ignores_constant_metadata_numbers():
    """5.1 / 2.0 channel counts repeat in every file; the episode number is
    the only number that increments, so it must be selected."""
    files = [
        "Show.1081.DDP.5.1.mkv",
        "Show.1082.DDP.5.1.mkv",
        "Show.1083.DDP.5.1.mkv",
    ]
    detected = detect_anime_episode_numbers(files)
    assert detected == {
        files[0]: "1081",
        files[1]: "1082",
        files[2]: "1083",
    }


def test_detect_anime_skips_explicit_sxxe_files():
    files = [
        "Show Name - S01E0005 [1080p][HEVC].mkv",
        "Show Name - 0006 [1080p][HEVC].mkv",
    ]
    detected = detect_anime_episode_numbers(files)
    # The explicitly-marked file is handled by normal show parsing.
    assert files[0] not in detected
    assert detected.get(files[1]) == "0006"


def test_detect_anime_single_file():
    assert detect_anime_episode_numbers(["Show - 0001 [1080p].mkv"]) == {
        "Show - 0001 [1080p].mkv": "0001"
    }


def test_detect_anime_empty_and_undetectable():
    assert detect_anime_episode_numbers([]) == {}
    assert detect_anime_episode_numbers(["Some Show.mkv"]) == {}


# ============================================================================
# Identifier ({imdb-...} / {tmdb-...}) handling
# ============================================================================


IDENTIFIER_TEST_CASES: Final[TestScenarios] = {
    "style2_tmdb_in_show_name": {
        "filename": "Detective Conan {tmdb-30983} S01E0001 [1080p][HEVC].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Detective Conan",
            "season": "01",
            "episode": "0001",
            "tmdb_id": 30983,
        },
    },
    "style2_imdb_in_show_name": {
        "filename": "Better Call Saul {imdb-tt0903747} S01E01 [1080p].mkv",
        "is_show": True,
        "expected": {
            "show_name": "Better Call Saul",
            "season": "01",
            "episode": "01",
            "imdb_id": "tt0903747",
        },
    },
    "style1_tmdb_after_marker": {
        "filename": "Detective.Conan.S01E0001.{tmdb-30983}.1080p.mkv",
        "is_show": True,
        "expected": {
            "show_name": "Detective Conan",
            "episode": "0001",
            "tmdb_id": 30983,
        },
    },
    "style1_imdb_after_marker": {
        "filename": "Better.Call.Saul.S01E01.{imdb-tt0903747}.1080p.mkv",
        "is_show": True,
        "expected": {
            "show_name": "Better Call Saul",
            "episode": "01",
            "imdb_id": "tt0903747",
        },
    },
    "tmdb_in_movie_name_region": {
        "filename": "Detective Conan {tmdb-30983} (2020) [1080p].mkv",
        "is_show": False,
        "expected": {
            "show_name": "Detective Conan",
            "year": "2020",
            "tmdb_id": 30983,
        },
    },
}


@pytest.mark.parametrize(
    "name,case", IDENTIFIER_TEST_CASES.items(), ids=IDENTIFIER_TEST_CASES.keys()
)
def test_identifier_is_not_part_of_show_name(name: str, case: TestScenario):
    parsed = parse_filename(case["filename"], case.get("is_show", True))
    for field, value in case["expected"].items():
        assert getattr(parsed, field) == value
    # The id must never leak into the show name.
    assert "{" not in parsed.show_name
    assert "db-" not in parsed.show_name

