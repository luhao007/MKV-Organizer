"""Data models for video file information and metadata."""

from dataclasses import dataclass, field
from typing import Optional, TypedDict


@dataclass
class ParsedFileInfo:
    """Parsed information from a video filename."""

    # Basic info
    show_name: str
    season: str
    episode: str
    title: str

    # Media infos
    resolution: str = ""
    codec: str = ""  # x264, x265, AV1, etc.
    source: str = ""  # e.g., WEB-DL, HDTV
    package: str = ""  # e.g., PROPER, REPACK
    hdr: str = ""  # e.g., HDR, 10bit, DV
    audio_codecs: list[str] | None = None  # e.g., DD5.1, DTS-HD.MA
    lang: str = ""  # e.g., chs, eng
    extra: str = ""  # Any extra info that doesn't fit into other fields
    release_group: str = ""
    extension: str = ""
    original_filename: str = ""

    # Extra info:
    year: str = ""  # For movies/shows, extracted year
    tmdb_id: int = 0  # TMDB show ID from API lookup


@dataclass
class MediaMetadata:
    """Metadata extracted from the actual media file."""

    resolution: str = ""
    codec: str = ""
    hdr: str = ""  # e.g., HDR, DV 8.1, SDR
    source: str = ""  # e.g., WEB-DL, HDTV
    audio_codecs: list[str] | None = None  # e.g., DD5.1, DTS-HD.MA
    lang: str = ""  # TODO: placeholder for future, e.g., chs, eng
    extra: str = ""  # TODO: placeholder for future

    def __bool__(self):
        """Return True if any metadata field is populated."""
        # XXX: This will always be True if we parsed any media info
        # as the resolution field will be at least available
        return any(
            [
                self.resolution,
                self.codec,
                self.hdr,
                self.source,
                self.audio_codecs,
                self.lang,
                self.extra,
            ]
        )


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
    is_media: bool = False
    subtitle_lang: str = ""  # e.g., "chs", "eng", "cht&eng"


# Type alias for organization structure
# show_name -> {'folder': show_folder_path, 'seasons': {season -> episode -> ext -> FileDefinition}}
class ShowData(TypedDict):
    folder: str
    seasons: dict[str, dict[str, dict[str, FileDefinition]]]


FileOrganization = dict[str, ShowData]
