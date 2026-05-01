"""Organize and rename video files."""

import os
from formatter import build_filename
from parser import parse_filename
from pathlib import Path
from typing import Dict, List

from config import KNOWN_LANGUAGES, VIDEO_FORMATS
from media_info import extract_media_info
from models import FileDefinition
from utils import get_logger

logger = get_logger(__name__)

# Type alias for organization structure
# season -> episode -> extension -> FileDefinition
FileOrganization = Dict[str, Dict[str, Dict[str, FileDefinition]]]


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
        if potential_lang in KNOWN_LANGUAGES:
            return potential_lang
    return ""


def organize_files(folder: str) -> FileOrganization:
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
            logger.debug(f"Skipping directory: {filename}")
            continue

        # Try to parse filename
        try:
            parsed = parse_filename(filename)
            parsed_count += 1
        except ValueError as e:
            logger.debug(f"Skipping {filename}: {e}")
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
            file_def.subtitle_lang = get_subtitle_language(filename)
            logger.debug(
                f"Detected subtitle file: {filename} (lang: {file_def.subtitle_lang})"
            )

        # Extract media info from video files
        if is_video_file(filename):
            file_def.media = extract_media_info(full_path)

        # Organize by season/episode
        season = parsed.season
        episode = parsed.episode
        ext = parsed.extension

        logger.debug(f"Organized: {filename} -> S{season}E{episode}.{ext}")

        organized.setdefault(season, {}).setdefault(episode, {})[ext] = file_def

    logger.debug(f"Scan complete: {parsed_count} parsed, {skipped_count} skipped")
    return organized


def get_all_files_for_episode(
    episode_files: Dict[str, FileDefinition],
) -> List[FileDefinition]:
    """Get all files (video + subtitles) for an episode."""
    return list(episode_files.values())


def get_primary_video_file(episode_files: Dict[str, FileDefinition]) -> FileDefinition:
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


def fill_missing_metadata(files: List[FileDefinition]) -> None:
    """
    Fill missing metadata fields from available sources.

    Uses primary video file as source for resolution/codec for all files.
    """
    # Find primary video file
    primary = None
    for file_def in files:
        if not file_def.is_subtitle and file_def.media:
            primary = file_def
            break

    if not primary:
        return

    # Fill in missing data from primary video
    for file_def in files:
        if not file_def.parsed.resolution and primary.media.resolution:
            file_def.parsed.resolution = primary.media.resolution

        if not file_def.parsed.codec and primary.media.codec:
            file_def.parsed.codec = primary.media.codec


def build_new_filename(
    file_def: FileDefinition,
    include_language: bool = True,
) -> str:
    """
    Build new filename for a file.

    For subtitles, appends language code: "Show.S01E01.Title.chs.srt"
    """
    parsed = file_def.parsed

    # Build base filename
    base = build_filename(
        show_name=parsed.show_name,
        season=parsed.season,
        episode=parsed.episode,
        title=parsed.title,
        resolution=parsed.resolution,
        codec=parsed.codec,
        release_group=parsed.release_group,
    )

    # Add language for subtitle files
    if include_language and file_def.is_subtitle and file_def.subtitle_lang:
        return f"{base}.{file_def.subtitle_lang}.{parsed.extension}"

    return f"{base}.{parsed.extension}"


def rename_files(
    organized: FileOrganization,
    dry_run: bool = True,
    include_language: bool = True,
) -> None:
    """
    Rename all files according to standardized naming scheme.

    Args:
        organized: FileOrganization structure from organize_files()
        dry_run: If True, only log what would be done; don't actually rename
        include_language: If True, append language code to subtitle files
    """
    for season_files in organized.values():
        for episode_files in season_files.values():
            if not episode_files:
                continue

            # Get all files for this episode
            all_files = get_all_files_for_episode(episode_files)

            # Check if there's at least one video file
            has_video = any(not f.is_subtitle for f in all_files)
            if not has_video:
                logger.debug(f"Skipping episode with no video file")
                continue

            # Fill missing metadata from primary video
            fill_missing_metadata(all_files)

            # Rename each file
            for file_def in all_files:
                logger.debug(f"Processing file: {file_def.filename}")
                new_filename = build_new_filename(file_def, include_language)
                logger.debug(
                    f"Generated new filename: {new_filename} for {file_def.filename}"
                )
                new_path = os.path.join(file_def.folder, new_filename)

                if new_path != file_def.filename:
                    logger.info(
                        f"Rename: {Path(file_def.filename).name} -> {new_filename}"
                    )

                    if not dry_run:
                        try:
                            os.rename(file_def.filename, new_path)
                        except OSError as e:
                            logger.error(f"Failed to rename {file_def.filename}: {e}")
