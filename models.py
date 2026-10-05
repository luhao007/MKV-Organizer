"""Data models for video file information and metadata."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Optional, TypedDict

from config import EPISODE_TITLE_SEPARATOR


@dataclass
class ParsedFileInfo:
    """Parsed information from a video filename."""

    # Basic info
    show_name: str
    season: str
    episode: str
    title: str
    # All episode numbers of a merged (multi-episode) file, primary episode
    # first (e.g. "S03E01E04" -> ["01", "04"]).  ``None``/empty means the file
    # holds exactly one episode (``episode``).
    episodes: list[str] | None = None

    # Media infos
    resolution: str = ""
    codec: str = ""  # x264, x265, AV1, etc.
    hdr: str = ""  # e.g., HDR, 10bit, DV
    audio_codecs: list[str] | None = None  # e.g., DD5.1, DTS-HD.MA

    # Extra info:
    edition: str = ""  # e.g., Director's Cut, Extended Edition
    source: str = ""  # e.g., WEB-DL, HDTV
    package: str = ""  # e.g., PROPER, REPACK
    year: str = ""  # For movies/shows, extracted year
    tmdb_id: int = 0  # TMDB show ID from API lookup
    lang: str = ""  # e.g., chs, eng
    extras: list[str] | None = None  # Any extra info that doesn't fit into other fields
    imdb_id: str = ""  # IMDb ID from API lookup
    release_group: str = ""
    original_filename: str = ""
    extension: str = ""

    @property
    def all_episodes(self) -> list[str]:
        """All episode numbers contained in this file, primary episode first.

        A merged file (``"S03E01E04"``) holds several episodes, a normal file
        exactly one.  Returns an empty list when no episode is known at all
        (e.g. movies).
        """
        if self.episodes:
            return list(self.episodes)
        return [self.episode] if self.episode else []

    @property
    def is_multi_episode(self) -> bool:
        """True when this file contains more than one episode."""
        return len(self.all_episodes) > 1


def join_episode_titles(titles: Iterable[str]) -> str:
    """Combine the episode names of one file into a single title.

    A merged file (e.g. ``S03E01E04``) covers several episodes, so its title is
    the individual episode names joined with ``" & "``
    (``"Feline Fervor & Action Reaction"``).

    Duplicate names are collapsed: when a title that already holds the joined
    name is stored per episode in ``episode_names.txt`` and read back, the join
    stays identical instead of repeating itself.
    """
    unique: list[str] = []
    for title in titles:
        if title and title not in unique:
            unique.append(title)
    return EPISODE_TITLE_SEPARATOR.join(unique)


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
