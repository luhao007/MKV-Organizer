"""Configuration and constants for MKV Organizer."""

import logging
import re
from typing import Final

# Supported video formats
VIDEO_FORMATS: Final = ["mkv", "mp4", "avi", "ts", "mpeg", "mpg", "mov", "wmv"]

# Supported subtitle formats and languages
SUBTITLE_FORMATS: Final = ["srt", "ass", "ssa", "sub"]
KNOWN_LANGUAGES: Final = {"chs", "cht", "chs&eng", "cht&eng", "eng", "fra", "zh", "en"}

# Regex Patterns
# ============================================================================

# Match season/episode patterns with separators.
# Supports both: S01E10 and 3x07
# Works with dots, spaces, underscores, hyphens as separators.
SEASON_EPISODE_PATTERN: Final = re.compile(
    r"(?i)(?:^|[.\s_-])(?:"
    r"s(?P<season_s>\d{1,2})e(?P<episode_s>\d{2,3})|"
    r"(?P<season_x>\d{1,2})x(?P<episode_x>\d{2,3})"
    r")(?:$|[.\s_-])"
)

# Match resolution (e.g., 1080p, 720p, 2160p)
RESOLUTION_PATTERN: Final = re.compile(r"(?i)(?<!\d)(?P<res>\d{3,4}p)(?!\d)")

KNOWN_CODECS = [
    "x264",
    "H264",
    "H.264",
    "AVC",
    "x265",
    "H265",
    "H.265",
    "HEVC",
    "AV1",
    "XviD",
    "DivX",
    "MPEG-4",
    "MPEG-1",
    "MPEG-2",
]

_CODEC_PATTERN: Final = "|".join(KNOWN_CODECS)
CODEC_PATTERN: Final = re.compile(rf"(?i)\b(?P<codec>{_CODEC_PATTERN})\b")

KNOWN_SOURCES = [
    "HDTV",
    "TVRip",
    "AMZN.WEB-DL",
    "CRVE.WEB-DL",
    "Disney+.WEB-DL",
    "WEB.DL",
    "WEB-DL",
    "WEBRip",
    "BluRay",
    "BDRip",
    "BRRip",
    "DVD",
    "DVDRip",
]

_SOURCE_PATTERN: Final = "|".join(map(re.escape, KNOWN_SOURCES))
SOURCE_PATTERN: Final = re.compile(rf"(?i)\b(?P<source>{_SOURCE_PATTERN})\b")

KNOWN_AUDIO_CODECS = [
    "AC3",
    "AAC",
    "DD5.1",
    "DD.5.1",
    "DD2.0",
    "DD.2.0",
    "DDP",
    "DDP5.1",
    "DDP.5.1",
    "DTS",
    "DTS-HD",
    "DTS-HD.MA",
    "TrueHD",
    "TrueHD.7.1",
    "Atmos",
]


# 重要：把 codec 先按长度从长到短排序，避免 "DTS" 抢先匹配 "DTS-HD.MA"
_audio_alts = "|".join(
    sorted(map(re.escape, KNOWN_AUDIO_CODECS), key=len, reverse=True)
)

_AUDIO_CODEC_PATTERN: Final = rf"({_audio_alts})(\.({_audio_alts}))*"
AUDIO_CODEC_PATTERN: Final = re.compile(rf"(?i)\b(?P<audio>{_AUDIO_CODEC_PATTERN})\b")

_LANGUAGE_PATTERN: Final = "|".join(KNOWN_LANGUAGES)
_LANGUAGE_PATTERN_REPEATED: Final = rf"({_LANGUAGE_PATTERN})(\.({_LANGUAGE_PATTERN}))*"
LANGUAGE_PATTERN: Final = re.compile(rf"(?i)\b(?P<lang>{_LANGUAGE_PATTERN_REPEATED})\b")

# For capitalization - split on dots, spaces, underscores, hyphens
WORD_SPLIT_PATTERN: Final = re.compile(r"[.\s_-]+")

# For wrapping parentheses/brackets detection
WRAP_PATTERN: Final = re.compile(r"^([(\[]*)(.*?)([)\]]*)$")

# Stopwords for title capitalization (keep lowercase except first word)
STOPWORDS: Final = {"in", "as", "of", "the", "and", "or", "to", "a", "an"}

# Metadata suffixes that are not part of the episode title.
TITLE_METADATA_SUFFIX_PATTERN: Final = re.compile(
    r"(?i)^(?P<title>.*?)(?:[.\s_-]*(?:"
    r"\d{3,4}p|"
    f"{_CODEC_PATTERN}|"
    f"{_SOURCE_PATTERN}|"
    f"{_AUDIO_CODEC_PATTERN}|"
    f"{_LANGUAGE_PATTERN}|"
    r"HDR|HDR10|HDR10\+|"
    r"PROPER|REMUX|REPACK|LIMITED)(?:[.\s_-]*))*$"
)

# Default filename for stored episode title mappings.
EPISODE_NAME_FILE: Final = "episode_names.txt"

# Release group pattern (trailing text after last hyphen)
# E.g., "...-RARBG", "...-DEFLATE", "...-GROUP_NAME"


# Logging Configuration
# ============================================================================


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for the entire application.

    Sets up the root logger level so all child loggers inherit it.
    All loggers use the utils.get_logger() formatter for nice coloring.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Configure root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Set level for all existing loggers (since they use propagate=False)
    for logger_name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


RELEASE_GROUP_PATTERN: Final = re.compile(r"-([A-Za-z0-9][A-Za-z0-9._]{1,30})$")
