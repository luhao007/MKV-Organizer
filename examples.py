"""
Example usage and testing of the refactored MKV Organizer.

Run this script to see how the new modular structure works:
    python examples.py
"""

from formatter import build_filename, format_title
from parser import parse_filename

from media_info import MediaMetadata
from models import ParsedFileInfo


def example_parsing():
    """Example 1: Parsing different filename formats."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Filename Parsing")
    print("=" * 60)

    test_filenames = [
        "Better.Call.Saul.S01E10.Marco.1080p.X265.x265-RARBG.mp4",
        "Air.Crash.Investigations.S01E01.Unlocking.Disaster.(United.Airlines).avi",
        "The.Office.S09E23.Finale.720p.x264-GROUP.mkv",
    ]

    for filename in test_filenames:
        try:
            info = parse_filename(filename)
            print(f"\nFile: {filename}")
            print(f"  Show: {info.show_name}")
            print(f"  Season: S{info.season}, Episode: E{info.episode}")
            print(f"  Title: {info.title}")
            print(f"  Resolution: {info.resolution}")
            print(f"  Codec: {info.codec}")
            print(f"  Group: {info.release_group or '(none)'}")
        except ValueError as e:
            print(f"\n✗ {filename}: {e}")


def example_formatting():
    """Example 2: Title formatting with capitalization."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Title Formatting & Capitalization")
    print("=" * 60)

    test_titles = [
        "the call of duty",
        "unlocking disaster (united airlines, flight 811)",
        "marco - the final confrontation",
        "a tale of two cities",
    ]

    for title in test_titles:
        formatted = format_title(title)
        print(f"\nOriginal: {title}")
        print(f"Formatted: {formatted}")


def example_building_filenames():
    """Example 3: Building standardized filenames."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Building Standardized Filenames")
    print("=" * 60)

    examples = [
        {
            "show_name": "Better Call Saul",
            "season": "01",
            "episode": "10",
            "title": "Marco",
            "resolution": "1080p",
            "codec": "x265",
            "release_group": "RARBG",
        },
        {
            "show_name": "Air Crash Investigations",
            "season": "01",
            "episode": "01",
            "title": "Unlocking Disaster (United Airlines, Flight 811)",
            "resolution": "720p",
            "codec": "x264",
            "release_group": "",
        },
        {
            "show_name": "The Office",
            "season": "09",
            "episode": "23",
            "title": "Finale",
            "resolution": "",  # Will be missing
            "codec": "",  # Will be missing
            "release_group": "GROUP",
        },
    ]

    for i, example in enumerate(examples, 1):
        filename = build_filename(**example)
        print(f"\nExample {i}:")
        print(f"  Input: {example}")
        print(f"  Output: {filename}.mkv")


def example_data_models():
    """Example 4: Using data models for type safety."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Type-Safe Data Models")
    print("=" * 60)

    # Create a ParsedFileInfo instance
    info = ParsedFileInfo(
        show_name="Better Call Saul",
        season="01",
        episode="10",
        title="Marco",
        resolution="1080p",
        codec="x265",
        release_group="RARBG",
        extension="mp4",
        original_filename="Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4",
    )

    print(f"\nParsedFileInfo instance:")
    print(f"  Show: {info.show_name}")
    print(f"  Season/Episode: S{info.season}E{info.episode}")
    print(f"  Title: {info.title}")
    print(f"  Quality: {info.resolution} @ {info.codec}")
    print(f"  Group: {info.release_group}")

    # Create media metadata
    media = MediaMetadata(
        resolution="1080p",
        codec="x265",
    )
    print(f"\nMediaMetadata instance:")
    print(f"  Resolution: {media.resolution}")
    print(f"  Codec: {media.codec}")


def example_edge_cases():
    """Example 5: Edge cases and error handling."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Edge Cases")
    print("=" * 60)

    # Case 1: Duplicate resolution in filename
    try:
        info = parse_filename(
            "Better.Call.Saul.S01E10.Marco.1080p.X265.1080p.x265-RARBG.mp4"
        )
        print(f"\n✓ Handles duplicate resolution:")
        print(f"  File: Better.Call.Saul.S01E10.Marco.1080p.X265.1080p.x265-RARBG.mp4")
        print(f"  Detected: {info.resolution} @ {info.codec}")
    except Exception as e:
        print(f"✗ Failed: {e}")

    # Case 2: No season/episode (should fail gracefully)
    try:
        info = parse_filename("SomeMovie.1080p.x265.mkv")
        print(f"\nFile without S##E##: {info}")
    except ValueError as e:
        print(f"\n✓ Correctly rejects file without season/episode:")
        print(f"  Error: {e}")

    # Case 3: Mixed case input
    try:
        info = parse_filename("better.CALL.saul.s01e10.MARCO.1080P.X265-rarbg.MP4")
        print(f"\n✓ Handles mixed case:")
        print(f"  Show: {info.show_name}")
        print(f"  Resolution: {info.resolution}")
        print(f"  Codec: {info.codec}")
    except Exception as e:
        print(f"✗ Failed: {e}")


if __name__ == "__main__":
    print("\n🎬 MKV Organizer - Refactored Code Examples\n")

    example_parsing()
    example_formatting()
    example_building_filenames()
    example_data_models()
    example_edge_cases()

    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("=" * 60 + "\n")
