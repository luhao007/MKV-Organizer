"""MKV Organizer - Automatically organize and rename video files."""

import argparse
import os

from config import setup_logging
from organizer import (
    check_low_resolution,
    check_missing,
    load_episode_name_index,
    organize_files,
    rename_files,
    write_episode_name_index,
)
from utils import get_logger


def main():
    """Main entry point for MKV Organizer."""
    parser = argparse.ArgumentParser(
        description="Organize and rename video files with standardized naming scheme"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        help="Folder containing video files to organize",
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
        action="store_true",
        help="Export parsed episode names to episode_names.txt in the target folder",
    )
    parser.add_argument(
        "-u",
        "--use-episode-names",
        action="store_true",
        help="Use stored episode_names.txt mappings to fill or override parsed titles",
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
    args = parser.parse_args()

    # Setup logging globally for all modules
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)

    # Determine folder
    if args.folder:
        folder = args.folder
    else:
        raise ValueError("No folder specified. Please provide a folder as an argument.")

    # Verify folder exists
    if not os.path.isdir(folder):
        logger.error(f"Folder not found: {folder}")
        return 1

    logger.info(f"Scanning folder: {folder}")

    try:
        # Load existing episode name mappings when requested
        episode_name_index = None
        if args.use_episode_names:
            episode_name_index = load_episode_name_index(folder)

        # Organize files
        organized = organize_files(
            folder,
            recursive=args.recursive,
            episode_name_index=episode_name_index,
        )

        if not organized:
            logger.warning("No video files found to organize")
            return 0

        # Log statistics
        total_episodes = sum(len(eps) for eps in organized.values())
        total_files = sum(
            len(files) for eps in organized.values() for files in eps.values()
        )
        logger.info(f"Found {total_episodes} episodes with {total_files} files")

        # Determine dry_run mode
        dry_run = not args.commit

        # Rename files
        include_language = not args.no_language
        ren_count = rename_files(
            organized,
            dry_run=dry_run,
            include_language=include_language,
        )

        if ren_count:
            if dry_run:
                logger.info(f"DRY RUN MODE - {ren_count} files would be renamed")
                logger.info("Use --commit or -c to actually rename files")
            else:
                logger.info(f"{ren_count} files have been renamed successfully")
        else:
            logger.info("All files are sorted. No files needed to be renamed")

        if args.export_episode_names:
            index_file = write_episode_name_index(folder, organized)
            logger.info(f"Exported episode names to: {index_file}")

        if args.check_missing and episode_name_index is not None:
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
