"""MKV Organizer - Automatically organize and rename video files."""

import argparse
import os
from argparse import BooleanOptionalAction, RawTextHelpFormatter

from config import setup_logging
from organizer import (
    check_low_resolution,
    check_missing,
    handle_episode_names,
    list_files,
    load_episode_name_index,
    organize_files,
    rename_files,
    write_episode_name_index,
)
from utils import get_logger


def main():
    """Main entry point for MKV Organizer."""
    parser = argparse.ArgumentParser(
        description="Organize and rename video files with standardized naming scheme",
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "folder",
        nargs="?",
        help="Folder containing video files to organize",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        default=False,
        help="List all video files in the folder",
    )
    parser.add_argument(
        "--list-csv",
        action="store_true",
        default=False,
        help="List all video files in the folder in CSV format",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without modifying files (default: True)",
    )
    parser.add_argument(
        "-c",
        "--commit",
        action="store_true",
        help="Actually rename files (overrides --dry-run)",
    )
    parser.add_argument(
        "--no-language",
        action="store_true",
        help="Don't include language codes in subtitle filenames",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan subdirectories for video files",
    )
    parser.add_argument(
        "-e",
        "--export-episode-names",
        action=BooleanOptionalAction,
        default=True,
        help="Export parsed episode names to episode_names.txt (default: True)",
    )
    parser.add_argument(
        "-u",
        "--use-episode-names",
        action=BooleanOptionalAction,
        default=True,
        help=(
            "Use stored episode_names.txt mappings to fill or override parsed titles"
            " (default: True)"
        ),
    )
    parser.add_argument(
        "--fetch-if-missing",
        action=BooleanOptionalAction,
        default=True,
        help="Fetch from TMDB if episode_names.txt is missing (default: True)",
    )
    parser.add_argument(
        "--force-fetch",
        action="store_true",
        help="Ignore existing episode_names.txt and force fetch from TMDB",
    )
    parser.add_argument(
        "--check-missing",
        action="store_true",
        help=(
            "Check for episodes in episode_names.txt that are missing from the folder,"
            " must be used with --use-episode-names"
        ),
    )
    parser.add_argument(
        "--check-low-resolution",
        type=int,
        help=(
            "Resolution threshold (e.g. 1080) to check for episodes with low resolution"
        ),
    )
    parser.add_argument(
        "-s",
        "--style",
        type=int,
        default=1,
        help=(
            "Style to be used for the name:\n"
            "  TV Show:\n"
            "    Style 1: Show.Name.SxxExx.Title.META1.META2.[...].mkv\n"
            "    Style 2: Show Name SxxExx (Title) [META1][META2][...].mkv\n"
            "  Movie:\n"
            "    Style 1: Movie.Name.Year.META1.META2.[...].mkv\n"
            "    Style 2: Movie Name (Year) [META1][META2][...].mkv\n"
            "Note: Language will always be split by '.' before extension"
        ),
    )
    parser.add_argument(
        "--show",
        action=BooleanOptionalAction,
        help="Mark the folder as containing TV shows",
    )
    parser.add_argument(
        "-f",
        "--force-use-media-info",
        action="store_true",
        help="Force use media info to rename files",
    )
    args = parser.parse_args()

    # Setup logging globally for all modules
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)

    # Determine folder
    if args.folder:
        folder = args.folder
    else:
        parser.print_help()
        return 0

    # Verify folder exists
    if not os.path.isdir(folder):
        logger.error(f"Folder not found: {folder}")
        return 1

    logger.info(f"Scanning folder: {folder}")

    try:
        # Organize files
        organized = organize_files(
            folder,
            recursive=args.recursive,
            is_show=args.show,
        )

        if not organized:
            logger.warning("No video files found to organize")
            return 0

        # Log statistics
        total_episodes = 0
        total_files = 0
        for show_data in organized.values():
            seasons = show_data["seasons"]
            for episodes in seasons.values():
                total_episodes += len(episodes)
                for episode_files in episodes.values():
                    total_files += len(episode_files)
        logger.info(f"Found {total_episodes} episodes with {total_files} files")

        if args.list:
            list_files(organized, is_show=args.show, to_csv=False)
        if args.list_csv:
            list_files(organized, is_show=args.show, to_csv=True)

        # Handle episode names if this is a TV show folder
        fetched_folders: set[str] = set()
        if args.show:
            fetched_folders = handle_episode_names(
                folder,
                organized,
                is_show=args.show,
                use_episode_names=args.use_episode_names,
                fetch_if_missing=args.fetch_if_missing,
                force_fetch=args.force_fetch,
            )

        # Determine dry_run mode
        if args.commit == True:
            dry_run = False
        elif args.commit == False:
            dry_run = True
        else:
            dry_run = args.dry_run

        # Rename files
        include_language = not args.no_language
        ren_count = rename_files(
            organized,
            dry_run=dry_run,
            include_language=include_language,
            style=args.style,
            force_use_media_info=args.force_use_media_info,
        )

        if ren_count:
            if dry_run:
                logger.info(f"DRY RUN MODE - {ren_count} files would be renamed")
                logger.info("Use --commit or -c to actually rename files")
            else:
                logger.info(f"{ren_count} files have been renamed successfully")
        else:
            logger.info("All files are sorted. No files needed to be renamed")

        if args.export_episode_names and args.show:
            index_files = write_episode_name_index(
                folder, organized, skip_folders=fetched_folders
            )
            if index_files:
                for index_file in index_files:
                    logger.info(f"Exported episode names to: {index_file}")

        if args.check_missing and args.show:
            # Load episode_name_index for check_missing from each show folder
            for show_data in organized.values():
                if "folder" in show_data:
                    show_folder = show_data["folder"]
                    episode_name_index = load_episode_name_index(show_folder)
                    if episode_name_index and "name" in episode_name_index:
                        check_missing(organized, episode_name_index)

        if args.check_low_resolution:
            check_low_resolution(
                organized, resolution_threshold=args.check_low_resolution
            )

        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    exit(main())
