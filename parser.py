"""Parse and extract information from video filenames."""

import re
from pathlib import Path
from typing import Optional

from config import (
    CODEC_PATTERN,
    RELEASE_GROUP_PATTERN,
    RESOLUTION_PATTERN,
    SEASON_EPISODE_PATTERN,
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


def extract_season_episode(
    text: str,
) -> tuple[Optional[str], Optional[str], Optional[re.Match[str]]]:
    """
    Extract season and episode numbers.

    Returns:
        Tuple of (season_str, episode_str, match_object)
        Season/episode are zero-padded to 2 digits if found.
    """
    match = SEASON_EPISODE_PATTERN.search(text)
    if not match:
        return None, None, None

    season = match.group("season").zfill(2)
    episode = match.group("episode").zfill(2)
    return season, episode, match


def extract_resolution(text: str) -> Optional[str]:
    """Extract resolution (e.g., 1080p, 720p)."""
    match = RESOLUTION_PATTERN.search(text)
    if match:
        return match.group("res").lower()
    return None


def extract_codec(text: str) -> Optional[str]:
    """Extract video codec (e.g., x265, x264, AV1)."""
    match = CODEC_PATTERN.search(text)
    if match:
        return match.group("codec")
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

    path = Path(filename)
    stem = path.stem
    extension = path.suffix.lstrip(".").lower()

    # Try to extract release group first (usually at the end)
    release_group = extract_release_group(stem)
    if release_group:
        logger.debug(f"Found release group: {release_group}")
        stem_without_group = stem[: -(len(release_group) + 1)]
    else:
        stem_without_group = stem

    # Extract season and episode
    season, episode, se_match = extract_season_episode(stem_without_group)
    if not season or not episode or not se_match:
        logger.debug(f"No SxxEyy pattern found in: {filename}")
        raise ValueError(f"Cannot find SxxEyy pattern in {filename}")

    logger.debug(f"Found season: {season}, episode: {episode}")

    # Extract show name (everything before SxxEyy)
    left_text = stem_without_group[: se_match.start()].strip(" ._-")
    show_name = normalize_separators(left_text)

    # Extract title (everything after SxxEyy)
    right_text = stem_without_group[se_match.end() :].strip(" ._-")
    title = normalize_separators(right_text)

    # Extract resolution and codec
    resolution = extract_resolution(stem_without_group)
    codec = extract_codec(stem_without_group)

    logger.debug(
        f"Extracted: show={show_name}, title={title}, "
        f"resolution={resolution}, codec={codec}"
    )

    return ParsedFileInfo(
        show_name=show_name,
        season=season,
        episode=episode,
        title=title,
        resolution=resolution or "",
        codec=codec or "",
        release_group=release_group or "",
        extension=extension,
        original_filename=filename,
    )
