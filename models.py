"""Data models for video file information and metadata."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedFileInfo:
    """Parsed information from a video filename."""

    show_name: str
    season: str
    episode: str
    title: str
    resolution: str = ""
    codec: str = ""  # x264, x265, AV1, etc.
    source: str = ""  # e.g., WEB-DL, HDTV
    extra: str = ""  # Any extra info that doesn't fit into other fields
    release_group: str = ""
    extension: str = ""
    original_filename: str = ""


@dataclass
class MediaMetadata:
    """Metadata extracted from the actual media file."""

    resolution: str = ""
    codec: str = ""
    source: str = ""  # e.g., WEB-DL, HDTV
    extra: str = ""  # Any extra info that doesn't fit into other fields


@dataclass
class FileDefinition:
    """Complete file information for renaming operations."""

    # Parsed filename info
    parsed: ParsedFileInfo

    # File paths
    folder: str
    filename: str  # full path

    # Extracted media info
    media: MediaMetadata = field(default_factory=MediaMetadata)

    # Generated new name
    new_name: Optional[str] = None

    # Whether this is a subtitle file
    is_subtitle: bool = False
    subtitle_lang: str = ""  # e.g., "chs", "eng", "cht&eng"
