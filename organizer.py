"""Organize and rename video files."""

import os
import traceback
from formatter import build_filename
from parser import parse_filename
from pathlib import Path
from typing import Iterable, Optional

from config import EPISODE_NAME_FILE, LANGUAGES, META_FILES, VIDEO_FORMATS
from media_info import extract_media_info
from models import FileDefinition, FileOrganization
from utils import get_logger

logger = get_logger(__name__)


def is_video_file(filename: str) -> bool:
    """Check if file is a supported video format."""
    ext = filename.split(".")[-1].lower()
    return ext in VIDEO_FORMATS


def is_subtitle_file(filename: str) -> bool:
    """Check if file is a subtitle file."""
    ext = filename.split(".")[-1].lower()
    return ext in ["srt", "ass", "ssa", "sub"]


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

                key = f"{parsed.season}|{parsed.episode}"
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
                    season, episode = key.split("|", 2)
                    file.write(f"{season}|{episode}|{mappings[key]}\n")

            logger.info(f"Exported episode names to: {index_path}")
            written_files.append(str(index_path))
        except Exception as e:
            logger.error(f"Error writing episode_names.txt to {show_folder}: {e}")

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
    for show_data in organized.values():
        if "seasons" not in show_data:
            continue

        seasons = show_data["seasons"]
        for season_files in seasons.values():
            for episode_files in season_files.values():
                for file_def in episode_files.values():
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

                    key = f"{season_str}|{episode_str}"

                    # Apply episode name if found and not already set
                    if key in index and file_def.parsed.title != index[key]:
                        file_def.parsed.title = index[key]
                        logger.debug(
                            "Applied episode name from file: "
                            f"S{season_str}E{episode_str} - {index[key]}"
                        )
                        applied_any = True

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
) -> FileOrganization:
    """
    Scan folder and organize files by show/season/episode.

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
                )
                # Merge subdirectory results
                for show_name, show_data in suborganized.items():
                    if show_name not in organized:
                        organized[show_name] = show_data
                    else:
                        # Merge seasons for same show
                        organized[show_name]["seasons"].update(show_data["seasons"])
            continue

        if "." not in filename:
            logger.debug(f"Skipping file with no extension: {filename}")
            continue
        if any(filename.endswith(meta) for meta in META_FILES):
            continue
        ext = os.path.splitext(filename)[1][1:].lower()  # get extension without dot

        # Try to parse filename
        try:
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
    Fill missing metadata fields from available sources.

    Uses primary video file as source for resolution/codec for all files.
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
        or not primary.parsed.audio_codec
        or not primary.parsed.hdr
    ):
        if not force_use_media_info:
            logger.info(
                f"Extracting media info for primary video: {primary.filename} \nCurrent"
                f" parsed: resolution={primary.parsed.resolution},"
                f" codec={primary.parsed.codec},"
                f" audio_codec={primary.parsed.audio_codec}"
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
        fill_missing("audio_codec")

    # Fill in missing data from primary video
    for file_def in files:
        file_def.parsed.show_name = primary.parsed.show_name
        file_def.parsed.year = primary.parsed.year
        file_def.parsed.title = primary.parsed.title
        file_def.parsed.resolution = primary.parsed.resolution
        file_def.parsed.source = primary.parsed.source
        file_def.parsed.codec = primary.parsed.codec
        file_def.parsed.package = primary.parsed.package
        file_def.parsed.audio_codec = primary.parsed.audio_codec
        file_def.parsed.hdr = primary.parsed.hdr
        file_def.parsed.release_group = primary.parsed.release_group


def build_new_filename(
    file_def: FileDefinition,
    include_language: bool = True,
    style: int = 1,
) -> str:
    """
    Build new filename for a file.

    For subtitles, appends language code: "Show.S01E01.Title.chs.srt"
    """
    parsed = file_def.parsed

    # Build base filename
    base = build_filename(
        style=style,
        show_name=parsed.show_name,
        season=parsed.season,
        episode=parsed.episode,
        title=parsed.title,
        year=parsed.year,
        resolution=parsed.resolution,
        source=parsed.source,
        package=parsed.package,
        codec=parsed.codec,
        hdr=parsed.hdr,
        audio_codec=parsed.audio_codec,
        lang=parsed.lang if include_language and not file_def.is_subtitle else "",
        extra=parsed.extra,
        release_group=parsed.release_group,
    )

    if parsed.extension == "thumb.jpg":
        return f"{base}-thumb.jpg"
    elif file_def.is_subtitle and parsed.lang:
        return f"{base}.{parsed.lang}.{parsed.extension}"
    else:
        return f"{base}.{parsed.extension}"


def rename_files(
    organized: FileOrganization,
    dry_run: bool = True,
    include_language: bool = True,
    style: int = 1,
    force_use_media_info: bool = False,
) -> int:
    """
    Rename all files according to standardized naming scheme.

    Args:
        organized: FileOrganization structure from organize_files()
        dry_run: If True, only log what would be done; don't actually rename
        include_language: If True, append language code to subtitle files
    """
    ren_count = 0

    for show_data in organized.values():
        seasons = show_data["seasons"]
        for season_files in seasons.values():
            for episode_files in season_files.values():
                if not episode_files:
                    continue

                # Get all files for this episode
                all_files = episode_files.values()

                # Check if there's at least one video file
                has_video = any(not f.is_subtitle for f in all_files)
                if not has_video:
                    logger.debug(f"Skipping episode with no video file")
                    continue

                # Fill missing metadata from primary video
                fill_missing_metadata(all_files, force_use_media_info)

                # Rename each file
                for file_def in all_files:
                    logger.debug(f"Processing file: {file_def.filename}")
                    new_filename = build_new_filename(file_def, include_language, style)
                    logger.debug(
                        f"Generated new filename: {new_filename} for"
                        f" {file_def.filename}"
                    )
                    new_path = os.path.join(file_def.folder, new_filename)

                    if new_path != file_def.filename:
                        logger.info(
                            f"Rename: {Path(file_def.filename).name} -> {new_filename}"
                        )
                        ren_count += 1

                        if not dry_run:
                            try:
                                os.rename(file_def.filename, new_path)
                            except OSError as e:
                                logger.error(
                                    f"Failed to rename {file_def.filename}: {e}"
                                )

    return ren_count


def check_missing(
    organized: FileOrganization,
    episode_name_index: dict[str, str],
):
    """
    Check for missing episodes based on organized files.

    Returns:
        list of missing episode identifiers (e.g., "S01E02")
    """
    missing: set[str] = episode_name_index.keys() - set(["name"])
    for show_name, show_data in organized.items():
        if "seasons" not in show_data:
            continue

        seasons = show_data["seasons"]
        for season, episodes in seasons.items():
            for episode, episode_files in episodes.items():
                for file_def in episode_files.values():
                    if not file_def.is_subtitle:
                        key = f"{season}|{episode}"
                        missing.discard(key)

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
    Check for episodes with low resolution based on organized files.

    Returns:
        list of missing episode identifiers (e.g., "S01E02")
    """
    low_res: dict[str, str] = {}
    for show_name, show_data in organized.items():
        seasons = show_data["seasons"]
        for season, episodes in sorted(seasons.items()):
            for episode, episode_files in episodes.items():
                for file_def in episode_files.values():
                    if not file_def.is_subtitle:
                        key = f"{season}|{episode}"
                        res = file_def.parsed.resolution
                        if res and int(res[:-1]) < resolution_threshold:
                            low_res[key] = res

        logger.info(f"Show Name: {show_name}")
        if low_res:
            logger.info(f"Episodes with low resolution: {low_res}")
        else:
            logger.info("No episodes with low resolution detected")


def list_files(organized: FileOrganization, is_show: bool = True, to_csv: bool = False):
    """
    List all files in the organized structure.

    Args:
        organized: FileOrganization structure from organize_files()
    """
    data: list[list[str]] = []
    for show_name, show_data in organized.items():
        seasons = show_data["seasons"]
        for season, episodes in seasons.items():
            for episode, episode_files in episodes.items():
                for file_def in episode_files.values():
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
                        parsed.audio_codec,
                        parsed.release_group,
                    ]
                    data.append(l)

    if is_show:
        columns = ["Show Name", "Season", "Episode", "TItle"]
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
