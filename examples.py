"""
Example usage and testing of the refactored MKV Organizer.

Run this script to see how the new modular structure works:
    python examples.py
"""

from parser import parse_filename


def example_parsing():
    """Example 1: Parsing different filename formats."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Filename Parsing")
    print("=" * 60)

    test_filenames = [
        "Better.Call.Saul.S01E10.Marco.1080p.X265.x265-RARBG.mp4",
        "Air.Crash.Investigations.S01E01.Unlocking.Disaster.(United.Airlines).avi",
        "The.Office.S09E23.Finale.720p.x264-GROUP.mkv",
        "Mayday.S26E10.Mixed.Measures.2160P.CRVE.WEB-DL.H265.DDP.5.1.ENG.FRA-NS225.mkv",
        "Mayday S03E10 Head on Collision 1080p AMZN WEB-DL DD 2 0 H 264-playWEB.mkv",
    ]

    for filename in test_filenames:
        try:
            info = parse_filename(filename)
            print(f"\nFile: {filename}")
            for key, value in info.__dict__.items():
                print(f"  {key}: {value}")
        except ValueError as e:
            print(f"\n✗ {filename}: {e}")


def example_edge_cases():
    """Example 2: Edge cases and error handling."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Edge Cases")
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
    example_edge_cases()

    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("=" * 60 + "\n")
