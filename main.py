"""MKV Organizer - Automatically organize and rename video files."""

import argparse
import os

from config import setup_logging
from organizer import organize_files, rename_files
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
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without modifying files (default: True)",
    )
    parser.add_argument(
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
        # Organize files
        organized = organize_files(folder)

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
        rename_files(
            organized,
            dry_run=dry_run,
            include_language=include_language,
        )

        if dry_run:
            logger.info("DRY RUN MODE - No files were actually renamed")
            logger.info("Use --commit to actually rename files")
        else:
            logger.info("Files have been renamed successfully")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    exit(main())
