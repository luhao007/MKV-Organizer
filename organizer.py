"""Organize and rename video files."""

import os
import re
import traceback
from formatter import build_filename, normalize_illegal_chars
from parser import detect_anime_episode_numbers, parse_filename
from pathlib import Path
from typing import Callable, Generator, Iterable, Optional

from config import EPISODE_NAME_FILE, LANGUAGES, META_FILES, VIDEO_FORMATS
from media_info import extract_media_info
from models import FileDefinition, FileOrganization, ShowData
from utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# Utility Functions
# ============================================================================


def check_file_type(filename: str, extensions: Iterable[str]) -> bool:
    """Check if file has one of the specified extensions."""
    ext = filename.split(".")[-1].lower()
    return ext in extensions


def _media_name_key(name: str) -> str:
    """Build a case/separator-insensitive key used to match files of one title.

    E.g. "Avengers Infinity War" and "avengers.infinity_war" map to the same
    key, so a subtitle file is grouped with its movie.
    """
    return re.sub(r"[\s._-]+", " ", name).strip().lower()


def iterate_organized_episodes(
    organized: FileOrganization,
) -> Generator[tuple[str, ShowData, str, str, dict[str, FileDefinition]]]:
    """
    Iterate through all episodes in organized file structure.

    Yields:
        Tuple of (show_name, show_data, season, episode, episode_files)
    """
    for show_name, show_data in organized.items():
        if "seasons" not in show_data:
            continue

        seasons = show_data["seasons"]
        for season, season_files in seasons.items():
            for episode, episode_files in season_files.items():
                yield show_name, show_data, season, episode, episode_files


def has_video_file(episode_files: dict[str, FileDefinition]) -> bool:
    """Check if episode has at least one video file."""
    return any(not file_def.is_subtitle for file_def in episode_files.values())


def get_all_episode_files(
    episode_files: dict[str, FileDefinition],
) -> list[FileDefinition]:
    """Get all FileDefinition objects from episode_files dict."""
    return list(episode_files.values())


def get_video_files(episode_files: dict[str, FileDefinition]) -> list[FileDefinition]:
    """Get only video files (non-subtitles) from episode_files."""
    return [f for f in episode_files.values() if not f.is_subtitle]


def get_subtitle_files(
    episode_files: dict[str, FileDefinition],
) -> list[FileDefinition]:
    """Get only subtitle files from episode_files."""
    return [f for f in episode_files.values() if f.is_subtitle]


def extract_identifier_from_organized(
    show_data: ShowData, show_name: str = ""
) -> tuple[str, str, str]:
    """
    Extract identifier, year, and updated show name from show data.

    Returns:
        Tuple of (identifier, year, updated_show_name)
    """
    identifier = ""
    year = ""
    updated_show_name = show_name

    seasons = show_data.get("seasons", {})
    for season_episodes in seasons.values():
        for episode_files in season_episodes.values():
            video_files = get_video_files(episode_files)
            for file_def in video_files:
                if file_def.parsed.imdb_id:
                    identifier = f"{{imdb-{file_def.parsed.imdb_id}}}"
                elif file_def.parsed.tmdb_id:
                    identifier = f"{{tmdb-{file_def.parsed.tmdb_id}}}"
                year = file_def.parsed.year
                break
            if identifier and year:
                break
        if identifier and year:
            break

    return identifier, year, updated_show_name


def apply_to_all_episodes(
    organized: FileOrganization,
    apply_func: Callable[[str, ShowData, str, str, dict[str, FileDefinition]], None],
) -> None:
    """Apply a function to all episodes in organized structure."""
    for (
        show_name,
        show_data,
        season,
        episode,
        episode_files,
    ) in iterate_organized_episodes(organized):
        apply_func(show_name, show_data, season, episode, episode_files)


def build_season_episode_key(season: str, episode: str) -> str:
    """Build the key format for season/episode indexing."""
    return f"{season}|{episode}"


def parse_season_episode_key(key: str) -> tuple[str, str]:
    """Parse season/episode key back into components."""
    parts = key.split("|")
    if len(parts) != 2:
        raise ValueError(f"Invalid season/episode key: {key}")
    return parts[0], parts[1]


# ============================================================================
# File Type Checking
# ============================================================================


def is_video_file(filename: str) -> bool:
    """Check if file is a supported video format."""
    return check_file_type(filename, VIDEO_FORMATS)


def is_subtitle_file(filename: str) -> bool:
    """Check if file is a subtitle file."""
    return check_file_type(filename, ["srt", "ass", "ssa", "sub"])


def get_subtitle_language(filename: str) -> str:
    """
    Extract subtitle language code from filename.

    E.g., "Show.S01E01.chs.srt" -> "chs"
    """
    parts = filename.replace(".srt", "").replace(".ass", "").split(".")
    if len(parts) >= 2:
        potential_lang = parts[-1].lower()
        if potential_lang in LANGUAGES:
            return potential_lang
    return ""


def load_episode_name_index(folder: str) -> dict[str, str]:
    """Parse an episode_names.txt file and return a season/episode → title map.

    The file format is:
        Show Name          (line 1)
        S#|E#|Episode Title (subsequent lines)

    Args:
        folder: Path to the folder containing episode_names.txt.

    Returns:
        Dict with key ``"name"`` → show_name and ``"SS|EE"`` → title entries.
        Returns an empty dict if the file doesn't exist.
    """
    index_path = Path(folder) / EPISODE_NAME_FILE
    if not index_path.exists():
        return {}

    index: dict[str, str] = {}
    with index_path.open("r", encoding="utf-8") as file:
        show_name = file.readline().strip()  # First line is show name
        index["name"] = show_name

        for line in file.readlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|", 2)
            if len(parts) != 3:
                continue

            season, episode, title = [part.strip() for part in parts]
            if not season or not episode or not title:
                continue

            key = f"{season}|{episode}"
            index[key] = title

    return index


def write_episode_name_index(
    folder: str,
    organized: FileOrganization,
    skip_folders: Optional[set[str]] = None,
) -> list[str]:
    """
    Write episode_names.txt files for each show folder.

    Args:
        folder: Parent folder (for compatibility, not used directly)
        organized: FileOrganization dict with show data
        skip_folders: Set of show folders to skip (already written by fetch)

    Returns:
        List of paths where episode_names.txt was written
    """
    if skip_folders is None:
        skip_folders = set()

    written_files: list[str] = []

    for show_name, show_data in organized.items():
        if "seasons" not in show_data:
            continue

        show_folder = show_data.get("folder", folder)
        seasons = show_data["seasons"]

        # Skip if already written by fetch
        if show_folder in skip_folders:
            logger.debug(f"Skipping {show_folder} - already written by fetch")
            continue

        mappings: dict[str, str] = {}
        mappings["name"] = show_name

        for season, episodes in seasons.items():
            for episode, episode_files in episodes.items():
                try:
                    primary = get_primary_video_file(episode_files)
                except ValueError:
                    continue

                parsed = primary.parsed
                if not parsed.title:
                    continue

                key = build_season_episode_key(parsed.season, parsed.episode)
                mappings[key] = parsed.title

        if not mappings:
            logger.debug(f"No episode names to write for {show_name}")
            continue

        index_path = Path(show_folder) / EPISODE_NAME_FILE
        if index_path.exists():
            index = load_episode_name_index(show_folder)
            if index == mappings:
                continue
        try:
            with index_path.open("w", encoding="utf-8") as file:
                file.write(show_name)
                file.write("\n")
                for key in sorted(mappings):
                    if key == "name":
                        continue
                    season, episode = parse_season_episode_key(key)
                    file.write(f"{season}|{episode}|{mappings[key]}\n")

            logger.info(f"Exported episode names to: {index_path}")
            written_files.append(str(index_path))
        except Exception as e:
            logger.error(f"Error writing episode_names.txt to {show_folder}: {e}")
            traceback.print_exc()

    return written_files


def apply_episode_names_from_file(
    folder: str,
    organized: FileOrganization,
) -> bool:
    """
    Apply episode names from episode_names.txt file to organized dict.

    Only applies to episodes that don't already have titles.

    Args:
        folder: Path to the show folder containing episode_names.txt
        organized: FileOrganization dict to update

    Returns:
        True if any episode names were applied, False otherwise.
    """
    index = load_episode_name_index(folder)
    if not index or "name" not in index:
        logger.debug(f"No episode names found in {folder}")
        return False

    applied_any = False

    def process_episode(
        show_name: str,
        show_data: ShowData,
        season: str,
        episode: str,
        episode_files: dict[str, FileDefinition],
    ):
        nonlocal applied_any
        for file_def in get_all_episode_files(episode_files):
            if file_def.is_subtitle:
                continue

            # Build key for lookup
            try:
                season_str = str(int(file_def.parsed.season)).zfill(2)
                episode_str = str(int(file_def.parsed.episode)).zfill(2)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid season/episode:"
                    f" {file_def.parsed.season}/{file_def.parsed.episode}"
                )
                continue

            key = build_season_episode_key(season_str, episode_str)

            # Apply episode name if found and not already set
            if key in index and file_def.parsed.title != index[key]:
                file_def.parsed.title = index[key]
                logger.debug(
                    "Applied episode name from file: "
                    f"S{season_str}E{episode_str} - {index[key]}"
                )
                applied_any = True

    apply_to_all_episodes(organized, process_episode)
    return applied_any


def handle_episode_names(
    folder: str,
    organized: FileOrganization,
    is_show: Optional[bool] = None,
    use_episode_names: bool = True,
    fetch_if_missing: bool = True,
    force_fetch: bool = False,
) -> set[str]:
    """
    Handle episode names for all shows in the organized dict.

    Workflow:
    1. If force_fetch=True, skip to step 4 (fetch from TMDB)
    2. If use_episode_names=True and episode_names.txt exists, apply it
    3. If fetch_if_missing=True and no episode names applied, fetch from TMDB
    4. Fetch from TMDB (if force_fetch=True)

    Args:
        folder: Path to the parent folder
        organized: FileOrganization dict with show folders and seasons
        is_show: Whether this is a show folder (only process if True)
        use_episode_names: Whether to use existing episode_names.txt
        fetch_if_missing: Whether to fetch from TMDB if no episode names found
        force_fetch: Force fetch from TMDB, ignoring existing episode_names.txt

    Returns:
        Set of show folders that had episode_names.txt written by fetch
    """
    # Only process if is_show is True
    if is_show is not None and not is_show:
        logger.debug(f"Skipping episode names for non-show folder")
        return set()

    if not organized:
        logger.debug(f"No organized data")
        return set()

    fetched_folders: set[str] = set()

    # Process each show
    for show_name, show_data in organized.items():
        if "seasons" not in show_data:
            continue

        show_folder = show_data.get("folder", folder)

        need_fetch = False
        # Step 1: Try to use existing episode_names.txt
        if use_episode_names and not force_fetch:
            # Create a temporary organized dict for just this show
            temp_organized = {show_name: show_data}
            index = load_episode_name_index(show_folder)
            if not index:
                need_fetch = fetch_if_missing
            else:
                applied = apply_episode_names_from_file(show_folder, temp_organized)
                if applied:
                    logger.info(f"Applied episode names from file in {show_folder}")
                    continue

        # Step 2: Fetch from TMDB if missing or force_fetch
        if force_fetch or need_fetch:
            from tmdb import fetch_episode_names_for_show

            try:
                logger.info(f"Fetching episode names from TMDB for {show_folder}")
                temp_organized = {show_name: show_data}
                success = fetch_episode_names_for_show(show_folder, temp_organized)
                if success:
                    logger.info(f"Fetched and saved episode names for {show_folder}")
                    fetched_folders.add(show_folder)
                else:
                    logger.warning(
                        f"Could not fetch episode names from TMDB for {show_folder}"
                    )
            except Exception as e:
                logger.error(f"Error fetching episode names: {e}")
                traceback.print_exc()
                if not use_episode_names:
                    # If we couldn't fetch and use_episode_names was False,
                    # try loading from file as fallback
                    logger.info(
                        "Attempting to use existing episode_names.txt as fallback"
                    )
                    temp_organized = {show_name: show_data}
                    apply_episode_names_from_file(show_folder, temp_organized)

    return fetched_folders


def organize_files(
    folder: str,
    recursive: bool = False,
    is_show: bool = True,
    is_anime: bool = False,
) -> FileOrganization:
    """
    Scan folder and organize files by show/season/episode.

    Args:
        folder: Path of the folder to scan.
        recursive: Recurse into subdirectories.
        is_show: Whether files should be treated as episodes of a show.
        is_anime: Treat the folder as a single-season anime folder.  Files that
            have no explicit ``SxxExx`` marker get their episode number from the
            consecutive-number pattern detected across the files in the same
            folder (see parser.detect_anime_episode_numbers) and are grouped
            under season "01".

    Returns:
        Dict structure: {
            show_name: {
                'folder': show_folder_path,
                'seasons': {season: {episode: {ext: FileDefinition}}}
            }
        }

    Raises:
        ValueError: If any file cannot be parsed
    """
    logger.debug(f"Scanning folder: {folder}")
    organized: FileOrganization = {}
    parsed_count = 0
    skipped_count = 0

    # In anime mode every file in the same folder belongs to one season and
    # carries a bare (consecutive) episode number.  Detect those numbers once
    # per folder before parsing so they can be passed into parse_filename().
    anime_episodes: dict[str, str] = {}
    if is_anime:
        anime_files: list[str] = []
        for filename in os.listdir(folder):
            full_path = os.path.join(folder, filename)
            if os.path.isdir(full_path):
                continue
            if (
                "." not in filename
                or filename.startswith(".")
                or any(filename.endswith(meta) for meta in META_FILES)
            ):
                continue
            anime_files.append(filename)
        anime_episodes = detect_anime_episode_numbers(anime_files)

    # First pass: collect files from current directory
    for filename in os.listdir(folder):
        full_path = os.path.join(folder, filename)

        # Skip directories in first pass
        if os.path.isdir(full_path):
            logger.debug(f"Entering directory: {filename}")
            if recursive:
                suborganized = organize_files(
                    full_path,
                    recursive=True,
                    is_show=is_show,
                    is_anime=is_anime,
                )
                # Merge subdirectory results
                for show_name, show_data in suborganized.items():
                    if show_name not in organized:
                        organized[show_name] = show_data
                    elif is_show:
                        # Merge seasons for same show
                        organized[show_name]["seasons"].update(show_data["seasons"])
                    elif organized[show_name]["folder"] == show_data["folder"]:
                        # Same movie split over several files/folders merged
                        # during the scan of that folder.
                        organized[show_name]["seasons"].update(show_data["seasons"])
                    else:
                        # Movies: the same name in another folder (e.g. a
                        # two-part release) must not overwrite the first one.
                        unique_name = show_name
                        duplicate = 2
                        while unique_name in organized:
                            unique_name = f"{show_name} ({duplicate})"
                            duplicate += 1
                        organized[unique_name] = show_data
            continue

        if (
            "." not in filename
            or filename.startswith(".")
            or any(filename.endswith(meta) for meta in META_FILES)
        ):
            logger.debug(f"Skipping meta file {filename}")
            continue
        ext = os.path.splitext(filename)[1][1:].lower()  # get extension without dot

        # Try to parse filename
        try:
            if is_anime:
                parsed = parse_filename(
                    filename,
                    is_show=True,
                    is_anime=True,
                    anime_episode=anime_episodes.get(filename, ""),
                )
            else:
                parsed = parse_filename(filename, is_show=is_show)
            parsed_count += 1
        except BaseException as e:
            logger.error(f"Skipping {filename}: {e}")
            traceback.print_exc()
            skipped_count += 1
            continue

        # Create FileDefinition
        file_def = FileDefinition(
            parsed=parsed,
            folder=folder,
            filename=full_path,
        )

        # Detect subtitle
        if is_subtitle_file(filename):
            file_def.is_subtitle = True
            file_def.is_media = False
            file_def.subtitle_lang = get_subtitle_language(filename)
            logger.debug(
                f"Detected subtitle file: {filename} (lang: {file_def.subtitle_lang})"
            )
        elif is_video_file(filename):
            file_def.is_subtitle = False
            file_def.is_media = True
            logger.debug(f"Detected video file: {filename}")

        # Get show name and determine show folder
        show_name = parsed.show_name
        season = parsed.season
        episode = parsed.episode
        ext = parsed.extension

        # Determine show folder path
        file_path = Path(folder)
        if "season" in file_path.name.lower() or file_path.name.startswith("Season"):
            show_folder = str(file_path.parent)
        else:
            show_folder = folder

        logger.debug(f"Organized: {filename} -> {show_name} S{season}E{episode}.{ext}")

        # Initialize show entry if needed
        if is_show:
            # Every file in a show folder belongs to the same show, even when
            # the parsed names differ slightly (e.g. multi-season folders).
            if show_name not in organized:
                for sn, sd in organized.items():
                    if sd["folder"] == show_folder:
                        if not sn:
                            # In case of empty existing show name,
                            # replace with the current one
                            organized[show_name] = sd
                            organized.pop(sn)
                        else:
                            # Just use the existing one
                            show_name = sn
                            parsed.show_name = sn
                        break
                else:
                    organized[show_name] = {
                        "folder": show_folder,
                        "seasons": {},
                    }
            # Ensure folder is set to the deepest show folder
            elif show_folder != folder:
                organized[show_name]["folder"] = show_folder
        else:
            # Movies are standalone files: merge them only with the entry of
            # the same movie in the same folder (so a subtitle file follows its
            # movie), never with a *different* movie that happens to sit in the
            # same folder.
            matching_name = ""
            for sn, sd in organized.items():
                if sd["folder"] != show_folder:
                    continue
                if _media_name_key(sn) == _media_name_key(show_name):
                    matching_name = sn
                    break

            if matching_name:
                show_name = matching_name
                parsed.show_name = matching_name
            else:
                # Keep both entries when the same movie name occurs in another
                # folder (e.g. a two-part release) instead of overwriting it.
                unique_name = show_name
                duplicate = 2
                while unique_name in organized:
                    unique_name = f"{show_name} ({duplicate})"
                    duplicate += 1
                show_name = unique_name
                organized[show_name] = {
                    "folder": show_folder,
                    "seasons": {},
                }

        # Add file to seasons structure
        organized[show_name]["seasons"].setdefault(season, {}).setdefault(episode, {})[
            ext
        ] = file_def

    logger.debug(f"Scan complete: {parsed_count} parsed, {skipped_count} skipped")
    return organized


def get_primary_video_file(episode_files: dict[str, FileDefinition]) -> FileDefinition:
    """
    Get the primary video file for an episode.

    Priority: mkv > mp4 > avi
    """
    for ext in VIDEO_FORMATS:
        if ext in episode_files:
            return episode_files[ext]

    # Fallback: return first non-subtitle file
    for file_def in episode_files.values():
        if not file_def.is_subtitle:
            return file_def

    # Shouldn't reach here if data is valid
    raise ValueError("No video file found in episode")


def fill_missing_metadata(
    files: Iterable[FileDefinition],
    force_use_media_info: bool = False,
) -> None:
    """
    Fill missing metadata fields from the primary video file's MediaInfo data.

    If metadata fields (resolution, codec, HDR, audio_codecs, source) are
    missing from parsed info, they are extracted from the media file and
    propagated to all files in the episode group.

    Args:
        files: Iterable of FileDefinition objects for one episode.
        force_use_media_info: If True, re-extract MediaInfo even if fields exist.
    """
    # Find primary video file
    primary = None
    for file_def in files:
        if file_def.is_media:
            primary = file_def
            break

    if not primary:
        return

    # Extract media info if any key is missing
    if force_use_media_info or (
        not primary.parsed.resolution
        or not primary.parsed.codec
        or not primary.parsed.audio_codecs
        or not primary.parsed.hdr
    ):
        if not force_use_media_info:
            logger.info(
                f"Extracting media info for primary video: {primary.filename} \nCurrent"
                f" parsed: resolution={primary.parsed.resolution},"
                f" codec={primary.parsed.codec},"
                f" audio_codec={primary.parsed.audio_codecs}"
            )
            print(primary.parsed)
        if not primary.media:
            primary.media = extract_media_info(primary.filename)

        def fill_missing(field: str):
            if not getattr(primary.media, field):
                return

            setattr(primary.parsed, field, getattr(primary.media, field))

        fill_missing("source")
        fill_missing("resolution")
        fill_missing("codec")
        fill_missing("hdr")
        fill_missing("audio_codecs")

    # Fill in missing data from primary video
    for file_def in files:
        file_def.parsed.show_name = primary.parsed.show_name
        file_def.parsed.year = primary.parsed.year
        file_def.parsed.title = primary.parsed.title
        file_def.parsed.resolution = primary.parsed.resolution
        file_def.parsed.hdr = primary.parsed.hdr
        file_def.parsed.codec = primary.parsed.codec
        file_def.parsed.audio_codecs = primary.parsed.audio_codecs
        file_def.parsed.edition = primary.parsed.edition
        file_def.parsed.source = primary.parsed.source
        file_def.parsed.package = primary.parsed.package
        file_def.parsed.release_group = primary.parsed.release_group
        file_def.parsed.imdb_id = primary.parsed.imdb_id
        file_def.parsed.tmdb_id = primary.parsed.tmdb_id


def find_best_audio_codec(audio_codecs: Iterable[str] | None) -> str:
    """
    Select the highest-quality audio codec from a list.

    Priority order (highest first):
    TrueHD > DTS-X > Atmos > DTS > FLAC > DDP > DD > AC3 > AAC.

    Args:
        audio_codecs: Iterable of audio codec strings (may be None).

    Returns:
        The best single codec string, or a comma-joined fallback.
    """
    if not audio_codecs:
        return ""

    # Return the best audio codec if we have multiple
    best_codecs = [
        "TrueHD",
        "DTS-X",
        "Atmos",
        "DTS",
        "FLAC",
        "DDP",
        "EAC3",
        "DD",
        "AC3",
        "AAC",
    ]

    for best_codec in best_codecs:
        for codec in audio_codecs:
            if best_codec in codec:
                return codec
    return ", ".join(audio_codecs)


def build_new_filename(
    file_def: FileDefinition,
    include_language: bool = True,
    style: int = 1,
    include_identifier: bool = True,
    anime: bool = False,
    anime_with_season: bool = False,
) -> str:
    """
    Build new filename for a file.

    For subtitles, appends language code: "Show.S01E01.Title.chs.srt"

    Args:
        file_def: The file to build a name for.
        include_language: If True, append the language to subtitle files.
        style: 1 (dots) or 2 (spaces + brackets).
        include_identifier: If True, embed the known IMDb/TMDB id in the name
            (e.g. ``{tmdb-12345}``).  Set to False for clean names without the
            id; the id is still parsed & used for TMDB lookups.
        anime: If True, treat the file as single-season anime.
        anime_with_season: Only used when ``anime`` is True.  If True the
            ``SxxExx`` marker is written (e.g. ``S01E0123``); if False (the
            default) only the episode number is written.
    """
    parsed = file_def.parsed
    identifier = ""
    if include_identifier:
        if parsed.imdb_id:
            identifier = f"{{imdb-{parsed.imdb_id}}}"
        elif parsed.tmdb_id:
            identifier = f"{{tmdb-{parsed.tmdb_id}}}"

    # Build base filename
    base = build_filename(
        style=style,
        show_name=parsed.show_name,
        season=parsed.season,
        episode=parsed.episode,
        title=parsed.title,
        year=parsed.year,
        edition=parsed.edition,
        identifier=identifier,
        resolution=parsed.resolution,
        source=parsed.source,
        package=parsed.package,
        codec=parsed.codec,
        hdr=parsed.hdr,
        audio_codec=find_best_audio_codec(parsed.audio_codecs),
        lang=parsed.lang if include_language and not file_def.is_subtitle else "",
        extras=parsed.extras,
        release_group=parsed.release_group,
        anime=anime,
        anime_with_season=anime_with_season,
    )

    if parsed.extension == "thumb.jpg":
        return f"{base}-thumb.jpg"
    elif file_def.is_subtitle and parsed.lang:
        return f"{base}.{parsed.lang}.{parsed.extension}"
    elif parsed.extension in ["op", "ed"]:
        return f".{base}.fg.{parsed.extension}"
    else:
        return f"{base}.{parsed.extension}"


def rename_files(
    organized: FileOrganization,
    dry_run: bool = True,
    include_language: bool = True,
    style: int = 1,
    force_use_media_info: bool = False,
    include_identifier: bool = True,
    anime: bool = False,
    anime_with_season: bool = False,
) -> int:
    """
    Rename all files according to standardized naming scheme.

    Args:
        organized: FileOrganization structure from organize_files()
        dry_run: If True, only log what would be done; don't actually rename
        include_language: If True, append language code to subtitle files
        include_identifier: If True, embed the known IMDb/TMDB id in names
        anime: If True, write single-season anime names
        anime_with_season: Only used when ``anime`` is True.  If True the
            ``SxxExx`` marker is written; if False (the default) only the
            episode number is written
    """
    ren_count = 0

    def process_episode(
        show_name: str,
        show_data: ShowData,
        season: str,
        episode: str,
        episode_files: dict[str, FileDefinition],
    ):
        nonlocal ren_count
        if not has_video_file(episode_files):
            logger.debug(f"Skipping episode with no video file")
            return

        # Fill missing metadata from primary video
        all_files = get_all_episode_files(episode_files)
        fill_missing_metadata(all_files, force_use_media_info)

        # Rename each file
        for file_def in all_files:
            logger.debug(f"Processing file: {file_def.filename}")
            new_filename = build_new_filename(
                file_def,
                include_language,
                style,
                include_identifier=include_identifier,
                anime=anime,
                anime_with_season=anime_with_season,
            )
            logger.debug(
                f"Generated new filename: {new_filename} for {file_def.filename}"
            )
            new_path = os.path.join(file_def.folder, new_filename)

            if new_path != file_def.filename:
                logger.info(f"Rename: {Path(file_def.filename).name} -> {new_filename}")
                ren_count += 1

                if not dry_run:
                    try:
                        os.rename(file_def.filename, new_path)
                    except OSError as e:
                        logger.error(f"Failed to rename {file_def.filename}: {e}")

    apply_to_all_episodes(organized, process_episode)
    return ren_count


def check_missing(
    organized: FileOrganization,
    episode_name_index: dict[str, str],
):
    """
    Check for missing episodes by comparing organized files against an episode index.

    Logs the show name and any episodes present in the index but absent from
    the organized structure.

    Args:
        organized: FileOrganization structure from organize_files().
        episode_name_index: Dict from load_episode_name_index() with expected episodes.
    """
    missing: set[str] = episode_name_index.keys() - set(["name"])

    def process_episode(
        show_name: str,
        show_data: ShowData,
        season: str,
        episode: str,
        episode_files: dict[str, FileDefinition],
    ):
        for file_def in get_all_episode_files(episode_files):
            if not file_def.is_subtitle:
                key = build_season_episode_key(season, episode)
                missing.discard(key)

    apply_to_all_episodes(organized, process_episode)

    for show_name in organized.keys():
        logger.info(f"Show Name: {show_name}")
        if missing:
            logger.info(f"Missing episodes: {sorted(missing)}")
        else:
            logger.info("No missing episodes detected")


def check_low_resolution(
    organized: FileOrganization,
    resolution_threshold: int = 1080,
):
    """
    Check for episodes with resolution below a given threshold.

    Logs the show name and any episodes whose resolution is lower than the
    threshold (default: 1080p).

    Args:
        organized: FileOrganization structure from organize_files().
        resolution_threshold: Minimum acceptable vertical resolution (e.g., 1080).
    """
    low_res: dict[str, str] = {}

    def process_episode(
        show_name: str,
        show_data: ShowData,
        season: str,
        episode: str,
        episode_files: dict[str, FileDefinition],
    ):
        for file_def in get_all_episode_files(episode_files):
            if not file_def.is_subtitle:
                key = build_season_episode_key(season, episode)
                res = file_def.parsed.resolution
                if res and int(res[:-1]) < resolution_threshold:
                    low_res[key] = res

    apply_to_all_episodes(organized, process_episode)

    for show_name in organized.keys():
        logger.info(f"Show Name: {show_name}")
        if low_res:
            logger.info(f"Episodes with low resolution: {low_res}")
        else:
            logger.info("No episodes with low resolution detected")


def list_files(organized: FileOrganization, is_show: bool = True, to_csv: bool = False):
    """
    List all media files in the organized structure as a table.

    Outputs to the console (via pandas DataFrame) or to ``videos.csv``.

    Args:
        organized: FileOrganization structure from organize_files().
        is_show: If True, include season/episode/title columns; otherwise year.
        to_csv: If True, write output to ``videos.csv`` instead of printing.
    """
    data: list[list[str]] = []

    def process_episode(
        show_name: str,
        show_data: ShowData,
        season: str,
        episode: str,
        episode_files: dict[str, FileDefinition],
    ):
        for file_def in get_all_episode_files(episode_files):
            if not file_def.is_media:
                continue
            parsed = file_def.parsed
            l = [show_name]
            if is_show:
                l += [season, episode, parsed.title]
            else:
                l += [parsed.year]
            l += [
                parsed.resolution,
                parsed.source,
                parsed.package,
                parsed.codec,
                parsed.hdr,
                " / ".join(parsed.audio_codecs) if parsed.audio_codecs else "",
                parsed.release_group,
            ]
            data.append(l)

    apply_to_all_episodes(organized, process_episode)

    if is_show:
        columns = ["Show Name", "Season", "Episode", "Title"]
    else:
        columns = ["Movie Name", "Year"]
    columns += [
        "Resolution",
        "Source",
        "Package",
        "Codec",
        "HDR",
        "Audio Codec",
        "Release Group",
    ]

    if to_csv:
        import csv

        with open("videos.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(data)
        logger.info("'videos.csv' file created")

    else:
        from pandas import DataFrame

        df = DataFrame(data, columns=columns)
        print(df)


# Folder names that carry no information of their own ("1", "CD1", ...).  A
# movie folder without a year is only renamed when its current name is
# meaningless, so a meaningful folder name is never replaced by a bare title.
_NUMBERED_FOLDER_PATTERN = re.compile(
    r"^(?:cd|disc|disk|dvd|part|pt|vol|volume)?[\s._-]*\d+$", re.IGNORECASE
)
_GENERIC_FOLDER_NAMES = {
    "new",
    "new folder",
    "movie",
    "movies",
    "video",
    "videos",
    "media",
    "download",
    "downloads",
    "temp",
    "tmp",
    "untitled",
    "unknown",
    "misc",
    "other",
    "unsorted",
    "to sort",
    "sort",
}


def is_meaningless_folder_name(folder_name: str) -> bool:
    """
    Check if a folder name carries no useful information.

    Useful for deciding whether a movie folder may be renamed after the movie
    itself.  Returns True for bare numbers ("1", "2"), numbered disc/part names
    ("CD1", "Part 2") and generic names ("New folder", "Movies", ...).
    """
    name = folder_name.strip().strip("._- ")
    if not name:
        return True
    if _NUMBERED_FOLDER_PATTERN.match(name):
        return True
    return name.lower() in _GENERIC_FOLDER_NAMES


def build_normalized_folder_name(name: str, year: str, identifier: str) -> str:
    """
    Build a normalized folder name: "Name (Year) {identifier}".

    Empty ``year``/``identifier`` parts are omitted.
    """
    normalized = name
    if year:
        normalized = f"{normalized} ({year})"
    if identifier:
        normalized = f"{normalized} {identifier}"
    return normalize_illegal_chars(normalized)


def extract_movie_info(show_data: ShowData, fallback_name: str) -> tuple[str, str, str]:
    """
    Extract (identifier, year, movie_name) for a movie entry.

    The movie name comes from the first video file (it may have been replaced
    by a title fetched from ``movie.nfo``), the year and identifier from the
    first file that provides them.
    """
    movie_name = fallback_name
    year = ""
    identifier = ""
    first_video = True

    seasons = show_data.get("seasons", {})
    for season_episodes in seasons.values():
        for episode_files in season_episodes.values():
            for file_def in get_video_files(episode_files):
                parsed = file_def.parsed
                if first_video:
                    movie_name = parsed.show_name or fallback_name
                    first_video = False
                if not year:
                    year = parsed.year
                if not identifier:
                    if parsed.imdb_id:
                        identifier = f"{{imdb-{parsed.imdb_id}}}"
                    elif parsed.tmdb_id:
                        identifier = f"{{tmdb-{parsed.tmdb_id}}}"

    return identifier, year, movie_name


def normalize_folders(
    organized: FileOrganization,
    fetch_tmdb: bool = False,
    is_show: bool = True,
    base_folder: str = "",
) -> int:
    """
    Normalize folder names to "Name (Year) {identifier}" format.

    Shows are renamed to "Show Name (Year) {identifier}" (an identifier must be
    known).  Movies are renamed to "Movie Name (Year) {identifier}"; when no
    year is known the folder is only renamed if its current name is generic
    (see ``is_meaningless_folder_name``).

    Args:
        organized: FileOrganization structure from organize_files()
        fetch_tmdb: If True, fetch title/id info from TMDB (and tvshow.nfo /
            movie.nfo) to enrich identifiers, titles and years
        is_show: True when ``organized`` holds TV shows, False for movies
        base_folder: The folder the user scanned.  In movie mode it is never
            renamed so a folder full of loose movies is not renamed after one
            of its movies.

    Returns:
        Number of folders that were renamed
    """
    normalized_count = 0
    base_folder_norm = os.path.normpath(base_folder) if base_folder else ""

    # A folder shared by more than one entry is ambiguous in movie mode (two
    # movies in the same folder) -> leave it alone.
    folder_owners: dict[str, list[str]] = {}
    for owner_name, owner_data in organized.items():
        owner_folder = owner_data.get("folder")
        if owner_folder:
            folder_owners.setdefault(os.path.normpath(owner_folder), []).append(
                owner_name
            )

    for show_name, show_data in organized.items():
        folder = show_data.get("folder")
        if not folder:
            logger.debug(f"No folder found for show: {show_name}")
            continue

        folder_norm = os.path.normpath(folder)

        # Fetch TMDB/nfo info if requested to enrich identifiers and titles
        if fetch_tmdb:
            logger.info(f"Fetching TMDB info for {show_name}")
            if is_show:
                from tmdb import fetch_title_and_ids_for_show

                fetch_title_and_ids_for_show(folder, {show_name: show_data})
            else:
                # Movies are only looked up by an id from movie.nfo / folder
                # name / file name, never by name.
                from tmdb import fetch_title_and_ids_for_movie

                fetch_title_and_ids_for_movie(folder, {show_name: show_data})

        if is_show:
            # Get identifier from the first video file
            identifier, year, folder_label = extract_identifier_from_organized(
                show_data, show_name
            )
            if not identifier:
                logger.debug(
                    f"No identifier found for show: {show_name}, skipping normalization"
                )
                continue
        else:
            # Movies: never rename the scanned folder itself, otherwise the
            # user's movie folder would be renamed after a single movie.
            if base_folder_norm and folder_norm == base_folder_norm:
                logger.info(
                    f"Skipping {folder}: it is the scanned folder itself and is"
                    " never renamed. Point at its parent folder to normalize it."
                )
                continue

            owners = folder_owners.get(folder_norm, [])
            if len(owners) > 1:
                logger.warning(
                    f"Skipping {folder}: it contains multiple movies"
                    f" ({', '.join(sorted(owners))})"
                )
                continue

            identifier, year, folder_label = extract_movie_info(show_data, show_name)

            # Keep an id/year that is already part of the folder name so a
            # re-run does not strip them again.
            if not identifier:
                from tmdb import extract_id_from_folder_name

                folder_id = extract_id_from_folder_name(folder)
                if folder_id:
                    id_type, id_value = folder_id
                    identifier = f"{{{id_type}-{id_value}}}"
            if not year:
                folder_year = re.search(r"\((\d{4})\)", Path(folder).name)
                year = folder_year.group(1) if folder_year else ""

            if not year and not is_meaningless_folder_name(Path(folder).name):
                logger.info(
                    f"Skipping {folder}: no year found and the folder name is not"
                    " generic, so it is left as-is"
                )
                continue

        new_folder_name = build_normalized_folder_name(folder_label, year, identifier)

        # Create normalized folder path
        parent_folder = str(Path(folder).parent)
        new_folder_path = os.path.join(parent_folder, new_folder_name)

        # Check if the folder already has the correct name
        if folder_norm == os.path.normpath(new_folder_path):
            logger.debug(f"Folder already normalized: {folder}")
            continue

        # Check if the new folder already exists
        if os.path.exists(new_folder_path):
            logger.warning(f"Target folder already exists: {new_folder_path}, skipping")
            continue

        # Rename the folder
        try:
            logger.info(f"Normalize folder: {Path(folder).name} -> {new_folder_name}")
            os.rename(folder, new_folder_path)
            normalized_count += 1
            # Update the folder path in the show_data
            show_data["folder"] = new_folder_path
        except OSError as e:
            logger.error(f"Failed to rename folder {folder}: {e}")
            continue

        # Update the paths of all FileDefinitions: the files moved together
        # with the folder, so their full path (used as the rename source later)
        # must be updated too.  Files in subfolders (e.g. "Season 1") keep
        # their position relative to the renamed folder.
        seasons = show_data.get("seasons", {})
        for season_episodes in seasons.values():
            for episode_files in season_episodes.values():
                for file_def in get_all_episode_files(episode_files):
                    relative_folder = os.path.relpath(file_def.folder, folder)
                    file_def.folder = os.path.normpath(
                        os.path.join(new_folder_path, relative_folder)
                    )
                    file_def.filename = os.path.join(
                        file_def.folder, Path(file_def.filename).name
                    )

    return normalized_count
