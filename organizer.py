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


def write_episode_name_index(folder: str, organized: FileOrganization) -> str:
    index_path = Path(folder) / EPISODE_NAME_FILE
    mappings: dict[str, str] = {}

    for show_name, seasons in organized.items():
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
                if not show_name:
                    show_name = parsed.show_name

        with index_path.open("w", encoding="utf-8") as file:
            file.write(show_name)
            file.write("\n")
            for key in sorted(mappings):
                season, episode = key.split("|", 2)
                file.write(f"{season}|{episode}|{mappings[key]}\n")

    return str(index_path)


def organize_files(
    folder: str,
    recursive: bool = False,
    episode_name_index: Optional[dict[str, str]] = None,
    is_show: bool = True,
) -> FileOrganization:
    """
    Scan folder and organize files by season/episode.

    Returns:
        Nested dict: {season: {episode: {ext: FileDefinition}}}

    Raises:
        ValueError: If any file cannot be parsed
    """
    logger.debug(f"Scanning folder: {folder}")
    organized: FileOrganization = {}
    parsed_count = 0
    skipped_count = 0

    for filename in os.listdir(folder):
        full_path = os.path.join(folder, filename)

        # Skip directories
        if os.path.isdir(full_path):
            logger.debug(f"Entering directory: {filename}")
            if recursive:
                suborganized = organize_files(
                    full_path,
                    recursive=True,
                    episode_name_index=episode_name_index,
                    is_show=is_show,
                )
                for season, episodes in suborganized.items():
                    organized.setdefault(season, {}).update(episodes)
            continue

        if "." not in filename:
            logger.debug(f"Skipping file with no extension: {filename}")
            continue
        if filename in META_FILES:
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

        if episode_name_index:
            if "name" in episode_name_index:
                parsed.show_name = episode_name_index["name"]
            key = f"{parsed.season}|{parsed.episode}"
            if key in episode_name_index:
                parsed.title = episode_name_index[key]

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

        # Organize by season/episode
        name = parsed.show_name
        season = parsed.season
        episode = parsed.episode
        ext = parsed.extension

        logger.debug(f"Organized: {filename} -> S{season}E{episode}.{ext}")

        organized.setdefault(name, {}).setdefault(season, {}).setdefault(episode, {})[
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
        if not primary.media:
            primary.media = extract_media_info(primary.filename)

        def fill_missing(field: str):
            if not getattr(primary.media, field):
                return

            if not getattr(primary.parsed, field) or force_use_media_info:
                setattr(primary.parsed, field, getattr(primary.media, field))

        fill_missing("source")
        fill_missing("resolution")
        fill_missing("codec")
        fill_missing("hdr")
        fill_missing("audio_codec")

    # Fill in missing data from primary video
    for file_def in files:
        file_def.parsed.resolution = primary.parsed.resolution
        file_def.parsed.source = primary.parsed.source
        file_def.parsed.codec = primary.parsed.codec
        file_def.parsed.audio_codec = primary.parsed.audio_codec
        file_def.parsed.hdr = primary.parsed.hdr


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
        lang=parsed.lang if include_language else "",
        extra=parsed.extra,
        release_group=parsed.release_group,
    )

    if parsed.extension == "thumb.jpg":
        return f"{base}-thumb.jpg"
    elif file_def.is_subtitle:
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

    for _, seasons in organized.items():
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
    for show_name, seasons in organized.items():
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
    for show_name, seasons in organized.items():
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
