"""Configuration and constants for MKV Organizer."""

import itertools
import logging
import re
from typing import Final

# Supported video formats
VIDEO_FORMATS: Final = ["mkv", "mp4", "avi", "ts", "mpeg", "mpg", "mov", "wmv"]

# lists of known values for various metadata fields, used for more accurate parsing
SUBTITLE_FORMATS: Final = ["srt", "ass", "ssa", "sub", "vtt"]
METADATA_FORMATS: Final = ["nfo", "txt", "info", "jpg", "jpeg", "png"]
LANGUAGES: Final = {"chs", "cht", "chs&eng", "cht&eng", "eng", "fra", "zh", "en"}

CODECS: Final = [
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
    "VP9",
]
CODECS_RENAME_MAPPING = {
    "H265": "HEVC",
    "H.265": "HEVC",
    "x265": "HEVC",
}

HDR: Final = [
    "HDR",
    "HDR10",
    "HDR10Plus",
    "10bit",
    "SDR",
    "8bit",
    "DV",
    "DV.5",
    "DV.7.6",
    "DV.7.6.MEL",
    "DV.7.6.FEL",
    "DV.8.1",
    "DolbyVision",
    "DoVi",
    "HYBRID",  # DoVi falls back to HDR10 if DoVi not supported
]
HDR_RENAME_MAPPING: Final = {"DoVi": "DV", "DolbyVision": "DV", "HDR10": "HDR"}

_WEB_SOURCES: Final = [
    "YTB",  # YouTube
    "AMZN",  # Amazon Prime Video
    "CRVE",  # Crave (Canadian Streaming Service)
    "DSNP",  # Disney+
    "Disney+",  # Disney+ alternative
    "HULU",  # Hulu
    "NF",  # Netflix
    "AppleMusic",  # Apple Music
]
SOURCES: Final = [
    "HDTV",
    "TVRip",
    "WEBDL",
    "WEB.DL",
    "WEB-DL",
    "WEB_DL",
    "WEBRip",
    "UHD.BluRay",
    "BluRay",
    "BDRip",
    "BRRip",
    "DVD",
    "DVDRip",
    "AI",
    "Upscaled",
    "R2SE",
    "R2",
] + list(
    map(
        ".".join,
        itertools.product(_WEB_SOURCES, ["WEB-DL", "WEB.DL", "WEBDL", "WEBRip"]),
    )
)
SOURCE_RENAME_MAPPINGS: Final = {
    "WEB.DL": "WEB-DL",
    "WEBDL": "WEB-DL",
    "WEBRip": "WEB-DL",
    "WEBDL": "WEB-DL",
    "UHD.BluRay": "BluRay",
    "AI": "AI",
    "Upscaled": "AI",
    "R2SE": "AI",
    "R2": "AI",
}

PACKAGE: Final = ["INITIAL", "PROPER", "REPACK", "REMUX", "MULTI"]

_AUDIO_CODECS = [
    "TrueHD.Atmos",
    "TrueHD",
    "DTS-HD.MA",
    "DTS-HD",
    "DTS",
    "DTS-X",
    "DDP.Atmos",
    "DDP",
    "EAC3.Atmos",
    "EAC3",
    "DD",
    "AC3",
    "FLAC",
    "PCM",
    "AAC",
    "MP3",
    "MP2",
    "Opus",
]
_CHANNELS = ["2.0", "5.1", "7.1"]
AUDIO_CODECS: Final = (
    _AUDIO_CODECS
    + list(map(".".join, itertools.product(_AUDIO_CODECS, _CHANNELS)))
    + list(map("".join, itertools.product(_AUDIO_CODECS, _CHANNELS)))
)

EDITIONS: Final = [
    "IMAX",
    "Directors.Cut",
    "Extended.Cut",
    "Extended.Cut.IMAX",
]

EXTRA: Final = ["IMAX.Enhanced"]


# Default filename for stored episode title mappings.
EPISODE_NAME_FILE: Final = "episode_names.txt"

# Separator used to join the names of the episodes contained in one merged
# file, e.g. "Feline Fervor & Action Reaction" for ...S03E01E04....
EPISODE_TITLE_SEPARATOR: Final = " & "

META_FILES: Final = [
    "banner.jpg",
    "backdrop.jpg",
    "folder.jpg",
    "landscape.jpg",
    "logo.png",
    "movie.nfo",
    "tvshow.nfo",
    "fanart.jpg",
    "season.nfo",
    EPISODE_NAME_FILE,
    "poster.jpg",
    "Thumbs.db",
]

# Regex Patterns
# ============================================================================

# Match season/episode patterns with separators.
# Supports both: S01E10 and 3x07
# Works with dots, spaces, underscores, hyphens as separators.
# A merged (multi-episode) file is *anchored* on its first episode here; the
# remaining episodes are read from the text following the match by
# EPISODE_TAIL_PATTERN (e.g. "S03E01E04" -> season 03, episode 01, tail "E04").
SEASON_EPISODE_PATTERN: Final = re.compile(
    r"(?i)(?:^|[.\s_-])*(?:"
    r"s(?P<season_s>\d{1,2})\.?e(?P<episode_s>\d{2,4})|"
    r"(?P<season_x>\d{1,2})x(?P<episode_x>\d{2,4})"
    r")(?=$|[.\s_-]|[eE]\d)"
)

# Merged / multi-episode markers that directly follow the first episode marker:
#   "E04"        -> exact second episode             (S03E01E04   = eps 1 and 4)
#   "E04E05"     -> exact third/fourth episode       (S01E01E02E03)
#   "-E04"/"-04" -> contiguous range                 (S01E01-E04  = eps 1 to 4)
#
# Every episode number must be a *stand-alone* token and the hyphen of the range
# form may only be followed by spaces, an "e" and digits.  A dotted style
# separator therefore never starts a range: the resolution in
# "S01E0469 - [1080p][H264].mkv" (flattened: "S01E0469.-.1080p.H264.mkv") is
# *not* the range 469-1080.
EPISODE_TAIL_PATTERN: Final = re.compile(
    r"(?i)^(?P<tail>"
    r"-\s*[eE]?\d{2,4}(?![A-Za-z0-9])"
    r"|(?:[.\s_-]*[eE]\d{2,4})+(?![A-Za-z0-9])"
    r")"
)

# Match resolution (e.g., 1080p, 720p, 2160p)
RESOLUTION_PATTERN: Final = re.compile(r"(?i)(?<!\d)(?P<res>\d{3,4}p)(?!\d)")

EDITION_PATTERN: Final = re.compile(
    r"(?i)(?P<edition>\{edition-(" + "|".join(map(re.escape, EDITIONS)) + r")\})"
)

# Identifier braces embedded in filenames, e.g.:
#   "{imdb-tt0903747}"  (IMDb)
#   "{tmdb-30983}"      (raw numeric TMDB id, written by this tool)
#   "{tmdb-tv12345}" / "{imdb-nm1234567}" (prefixed variants, tolerated on read)
IDENTIFIER_PATTERN: Final = re.compile(
    r"(?i)(?P<id>\{(im|tm)db-((tt|nm|tv)\d{7,8}|\d+)\})"
)

# For capitalization - split on dots, spaces, underscores
WORD_SPLIT_PATTERN: Final = re.compile(r"[.\s_]+")

# For wrapping parentheses/brackets detection
WRAP_PATTERN: Final = re.compile(r"^([(\[]*)(.*?)([)\]]*)$")

# Stopwords for title capitalization (keep lowercase except first word)
STOPWORDS: Final = {"in", "as", "of", "the", "and", "or", "to", "a", "an", "at", "for"}

# Some special words that should not be captalized
SPECIALWORDS: Final = [
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "WandaVision",
]

# TODO: Metadata suffixes that are not part of the episode title, and
# not handled by our parser yet.
TITLE_METADATA_SUFFIX_PATTERN: Final = re.compile(
    r"(?i)^(?P<title>.*?)(?:[.\s_-]*(?:\d{3,4}p|UHD|IMAX)(?:[.\s_-]*))*$"
)

# Release group pattern (trailing text after last hyphen)
# E.g., "...-RARBG", "...-DEFLATE", "...-GROUP_NAME"

RELEASE_GROUP_PATTERN: Final = re.compile(r"-([A-Za-z0-9][A-Za-z0-9_]{1,30})$")


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
