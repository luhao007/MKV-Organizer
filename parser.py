"""Parse and extract information from video filenames."""

import re
from pathlib import Path
from typing import Iterable, Optional

from config import (
    AUDIO_CODECS,
    CODECS,
    EDITION_PATTERN,
    EXTRA,
    HDR,
    IDENTIFIER_PATTERN,
    LANGUAGES,
    PACKAGE,
    RELEASE_GROUP_PATTERN,
    RESOLUTION_PATTERN,
    SEASON_EPISODE_PATTERN,
    SOURCES,
    SUBTITLE_FORMATS,
    TITLE_METADATA_SUFFIX_PATTERN,
)
from models import ParsedFileInfo
from utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# Extraction Utility Functions (moved from extraction_utils.py)
# ============================================================================


def _extract_through_pattern_base(
    pattern: re.Pattern[str], text: str
) -> tuple[str, str]:
    """Extract a value using the provided regex pattern."""
    match = pattern.search(text)
    if match:
        res = match.group(1)
        left = text[: match.start()].strip(" ._-")
        right = text[match.end() :].strip(" ._-")
        remaining = ".".join([left, right]) if left and right else left or right
        return res, remaining
    return "", text


def _extract_from_list_single(lists: Iterable[str], text: str) -> tuple[str, str]:
    """Extract single value from known lists."""
    pattern_str = "|".join(sorted(map(re.escape, lists), key=len, reverse=True))
    pattern = re.compile(rf"(?i)\b(?P<value>{pattern_str})\b")
    return _extract_through_pattern_base(pattern, text)


def _extract_from_list_repeated(
    lists: Iterable[str], text: str
) -> tuple[list[str], str]:
    """Extract multiple values from known lists."""
    pattern_str = "|".join(sorted(map(re.escape, lists), key=len, reverse=True))
    pattern = re.compile(rf"(?i)\b(?P<value>{pattern_str})\b")

    extracted_list: list[str] = []
    remaining = text
    extracted, remaining = _extract_through_pattern_base(pattern, remaining)
    while extracted:
        if extracted not in extracted_list:
            extracted_list.append(extracted)
        extracted, remaining = _extract_through_pattern_base(pattern, remaining)

    return extracted_list, remaining


# ============================================================================
# Public API
# ============================================================================


def normalize_separators(text: str) -> str:
    """
    Normalize common filename separators to spaces.

    Keeps other punctuation (parentheses, commas) intact.
    E.g., "Better.Call.Saul" -> "Better Call Saul"
    """
    # Replace dots and underscores with spaces
    text = text.replace(".", " ").replace("_", " ")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip("- (")


def strip_noise_prefix(stem: str) -> str:
    """Remove common noise prefixes like 'Rename:' from filenames."""
    return re.sub(
        r"^(?:rename|renamed|download|new)\s*:\s*", "", stem, flags=re.IGNORECASE
    ).strip()


def strip_trailing_metadata(text: str) -> str:
    """Remove trailing metadata tags from extracted titles."""
    if not text:
        return ""

    stripped = text.strip(" ._- ")
    match = TITLE_METADATA_SUFFIX_PATTERN.match(stripped)
    if match:
        return match.group("title").strip(" ._- ")

    return stripped


def extract_release_group(stem: str) -> Optional[str]:
    """
    Extract release group from filename.

    Release groups are typically at the end after a hyphen.
    E.g., "Better.Call.Saul.S01E10.1080p.x265-RARBG" -> "RARBG"
    """
    match = RELEASE_GROUP_PATTERN.search(stem)
    if match:
        return match.group(1)
    return None


def extract_season_episode(text: str) -> tuple[str, str, str, str]:
    """
    Extract season and episode numbers.

    Returns:
        Tuple of (season_str, episode_str, left_text, right_text)
        Season/episode are zero-padded to 2 digits if found.
    """
    match = SEASON_EPISODE_PATTERN.search(text)
    if not match:
        logger.error(f"No season/episode pattern found in filename: {text}")
        raise ValueError("No season/episode pattern found")

    season = match.group("season_s") or match.group("season_x")
    episode = match.group("episode_s") or match.group("episode_x")
    if not season or not episode:
        raise ValueError("No season/episode pattern found")

    left = text[: match.start()]
    right = text[match.end() :]

    return season.zfill(2), episode.zfill(2), left, right


def extract_movie_name(text: str) -> tuple[tuple[str, str], str]:
    """
    Extract movie name and year.

    E.g., "Inception.2010.1080p.x265" -> ("Inception", "2010")
    """
    # The assumption is that all the filename is starting with $MOVIE_NAME.$YEAR.$EXTRA
    # Search the year pattern
    match = re.search(
        r"(?i)(?<!\d)[\.\(]*(19\d{2}|20\d{2})[\.\)]*(?!\d)", text, flags=re.IGNORECASE
    )
    if match:
        year = match.group(1)
        left = text[: match.start()]
        right = text[match.end() :]
        return (left.strip(" ._-"), year), right
    return (text, ""), ""


def extract_resolution(text: str) -> Optional[str]:
    """Extract resolution (e.g., 1080p, 720p)."""
    match = RESOLUTION_PATTERN.search(text)
    if match:
        return match.group("res").lower()
    return None


def parse_filename(filename: str, is_show: bool = True) -> ParsedFileInfo:
    """
    Parse a video filename and extract structured information.

    Handles two main patterns:
    1. "Better.Call.Saul.S01E10.Marco.1080p.X265.1080p.x265-RARBG.mp4"
    2. "Air.Crash.Investigations.S01E01 Unlocking Disaster (United Airlines, Flight 811).avi"

    Args:
        filename: The video filename (e.g., "Show.Name.S01E10.Title.1080p.x265-GROUP.mkv")

    Returns:
        ParsedFileInfo with extracted show name, season, episode, title, etc.

    Raises:
        ValueError: If filename doesn't contain season/episode pattern.
    """
    logger.debug(f"Parsing filename: {filename}")
    fn = filename.replace(" ", ".")
    fn = fn.replace("[", "").replace("]-", "-").replace("]", ".")
    fn = fn.replace("..", ".")

    path = Path(fn)
    stem = path.stem
    extension = path.suffix.lstrip(".").lower()

    # Special handling for thumbnail images (e.g., "Show.Name.S01E10-thumb.jpg")
    if extension == "jpg" and stem.lower().endswith("-thumb"):
        extension = "thumb.jpg"
        stem = stem[:-6]  # Remove '-thumb' from the stem for parsing

    # Remove common noise prefixes that are not part of the title
    stem = strip_noise_prefix(stem)

    if extension in SUBTITLE_FORMATS:
        # Extract language tags first (at the end)
        lang, stem = _extract_from_list_repeated(LANGUAGES, stem)
        lang = ".".join(lang)
    else:
        lang = ""

    # Then extract release group (usually at the end after a hyphen)
    release_group, stem = _extract_through_pattern_base(RELEASE_GROUP_PATTERN, stem)

    if is_show:
        # Extract season and episode
        season, episode, show_name, unparsed = extract_season_episode(stem)
        logger.debug(f"Found season: {season}, episode: {episode}")
        year = ""
    else:
        # Grab the year of a movie
        season, episode = "", ""
        (show_name, year), unparsed = extract_movie_name(stem)

    # Extract show name (everything before SxxEyy)
    show_name = normalize_separators(show_name)

    # Extract resolution, codec, source, audio codec, language
    identifier, unparsed = _extract_through_pattern_base(IDENTIFIER_PATTERN, unparsed)
    imdb_id = ""
    tmdb_id = ""
    if identifier.startswith("{imdb-"):
        imdb_id = identifier[6:-1]  # Extract IMDb ID from {imdb-tt1234567}
        tmdb_id = ""
    elif identifier.startswith("{tmdb-"):
        tmdb_id = identifier[6:-1]  # Extract TMDB ID from {tmdb-tv1234567}
        imdb_id = ""

    edition, unparsed = _extract_through_pattern_base(EDITION_PATTERN, unparsed)
    resolution, unparsed = _extract_through_pattern_base(RESOLUTION_PATTERN, unparsed)
    codec, unparsed = _extract_from_list_single(CODECS, unparsed)
    source, unparsed = _extract_from_list_single(SOURCES, unparsed)
    package, unparsed = _extract_from_list_repeated(PACKAGE, unparsed)
    package = ".".join(package)
    hdr, unparsed = _extract_from_list_repeated(HDR, unparsed)
    hdr = ".".join(hdr)
    audio_codecs, unparsed = _extract_from_list_repeated(AUDIO_CODECS, unparsed)
    extras, unparsed = _extract_from_list_repeated(EXTRA, unparsed)

    if extension not in SUBTITLE_FORMATS:
        lang, unparsed = _extract_from_list_repeated(LANGUAGES, unparsed)
        lang = ".".join(lang)

    # Extract title directly
    title = strip_trailing_metadata(unparsed)
    unparsed = unparsed.replace(title, "").strip(" ._-")
    title = normalize_separators(title)

    logger.debug(
        f"Extracted: show={show_name}, title={title}, resolution={resolution},"
        f" codec={codec}, source={source}, package={package}, hdr={hdr},"
        f" audio_codecs={audio_codecs}, lang={lang}, extras={extras},"
        f" extension={extension}, release_group={release_group}, edition={edition}"
    )

    return ParsedFileInfo(
        show_name=show_name,
        season=season,
        episode=episode,
        title=title,
        resolution=resolution,
        codec=codec,
        source=source,
        package=package,
        hdr=hdr,
        audio_codecs=audio_codecs,
        lang=lang,
        extras=extras,
        release_group=release_group or "",
        extension=extension,
        original_filename=filename,
        year=year,
        edition=edition,
        imdb_id=imdb_id,
        tmdb_id=int(tmdb_id) if tmdb_id else 0,
    )
