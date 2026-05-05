"""Parse and extract information from video filenames."""

import re
from pathlib import Path
from typing import Optional

from config import (
    AUDIO_CODEC_PATTERN,
    CODEC_PATTERN,
    LANGUAGE_PATTERN,
    RELEASE_GROUP_PATTERN,
    RESOLUTION_PATTERN,
    SEASON_EPISODE_PATTERN,
    SOURCE_PATTERN,
    TITLE_METADATA_SUFFIX_PATTERN,
)
from models import ParsedFileInfo
from utils import get_logger

logger = get_logger(__name__)


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
    return text.strip()


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
        raise ValueError("No season/episode pattern found")

    season = match.group("season_s") or match.group("season_x")
    episode = match.group("episode_s") or match.group("episode_x")
    if not season or not episode:
        raise ValueError("No season/episode pattern found")

    left = text[: match.start()]
    right = text[match.end() :]

    return season.zfill(2), episode.zfill(2), left, right


def extract_through_pattern(pattern: re.Pattern[str], text: str) -> tuple[str, str]:
    """Extract a value using the provided regex pattern."""
    match = pattern.search(text)
    if match:
        res = match.group(1)
        left = text[: match.start()].strip(" ._-")
        right = text[match.end() :].strip(" ._-")
        remaining = ".".join([left, right]) if left and right else left or right
        return res, remaining
    return "", text


def extract_resolution(text: str) -> Optional[str]:
    """Extract resolution (e.g., 1080p, 720p)."""
    match = RESOLUTION_PATTERN.search(text)
    if match:
        return match.group("res").lower()
    return None


def parse_filename(filename: str) -> ParsedFileInfo:
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
    filename = filename.replace(" ", ".")

    path = Path(filename)
    stem = path.stem
    extension = path.suffix.lstrip(".").lower()

    # Remove common noise prefixes that are not part of the title
    stem = strip_noise_prefix(stem)

    # Try to extract release group first (usually at the end)
    release_group, stem = extract_through_pattern(RELEASE_GROUP_PATTERN, stem)

    # Extract season and episode
    season, episode, show_name, unparsed = extract_season_episode(stem)
    logger.debug(f"Found season: {season}, episode: {episode}")

    # Extract show name (everything before SxxEyy)
    show_name = normalize_separators(show_name)

    # Extract resolution
    resolution, unparsed = extract_through_pattern(RESOLUTION_PATTERN, unparsed)

    # Extract codec
    codec, unparsed = extract_through_pattern(CODEC_PATTERN, unparsed)

    # Extract source
    source, unparsed = extract_through_pattern(SOURCE_PATTERN, unparsed)

    # Extract audio codec
    audio_codec, unparsed = extract_through_pattern(AUDIO_CODEC_PATTERN, unparsed)

    # Extract language
    lang, unparsed = extract_through_pattern(LANGUAGE_PATTERN, unparsed)

    # Extract title directly
    title = strip_trailing_metadata(unparsed)
    unparsed = unparsed.replace(title, "").strip(" ._-")
    title = normalize_separators(title)

    logger.debug(
        f"Extracted: show={show_name}, title={title}, resolution={resolution},"
        f" codec={codec}, source={source}, audio_codec={audio_codec}, lang={lang},"
        f" extra={unparsed}"
    )

    return ParsedFileInfo(
        show_name=show_name,
        season=season,
        episode=episode,
        title=title,
        resolution=resolution,
        codec=codec,
        audio_codec=audio_codec,
        lang=lang,
        extra=unparsed,
        release_group=release_group or "",
        extension=extension,
        original_filename=filename,
        source=source or "",
    )
