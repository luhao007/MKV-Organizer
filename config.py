"""Configuration and constants for MKV Organizer."""

import logging
import re
from typing import Final

# Supported video formats
VIDEO_FORMATS: Final = ["mkv", "mp4", "avi"]

# Supported subtitle formats and languages
SUBTITLE_FORMATS: Final = ["srt", "ass", "ssa", "sub"]
KNOWN_LANGUAGES: Final = {"chs", "cht", "chs&eng", "cht&eng", "eng", "zh"}

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

# Match video codec (x264, x265, H.264, HEVC, AV1, XviD, DivX, MPEG-4)
CODEC_PATTERN: Final = re.compile(
    r"(?i)\b(?P<codec>x26[45]|h\.?26[45]|hevc|avc|xvid|divx|mpeg-?4|av1)\b"
)

# For capitalization - split on dots, spaces, underscores, hyphens
WORD_SPLIT_PATTERN: Final = re.compile(r"[.\s_-]+")

# For wrapping parentheses/brackets detection
WRAP_PATTERN: Final = re.compile(r"^([(\[]*)(.*?)([)\]]*)$")

# Stopwords for title capitalization (keep lowercase except first word)
STOPWORDS: Final = {"in", "as", "of", "the", "and", "or", "to", "a", "an"}

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
