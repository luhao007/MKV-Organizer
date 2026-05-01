"""Extract metadata from video files using MediaInfo."""

from typing import Optional

from pymediainfo import MediaInfo

from models import MediaMetadata
from utils import get_logger

logger = get_logger(__name__)

# Height-to-resolution mapping
HEIGHT_TO_RESOLUTION = {
    2160: "2160p",
    1080: "1080p",
    720: "720p",
    576: "576p",
    480: "480p",
    320: "320p",
}


def get_resolution_from_height(height: int) -> str:
    """
    Convert video height to resolution string.

    Args:
        height: Video height in pixels

    Returns:
        Resolution string (e.g., "1080p")
    """
    if height in HEIGHT_TO_RESOLUTION:
        return HEIGHT_TO_RESOLUTION[height]

    # Intelligent guessing for non-standard heights
    if height >= 2100:
        return "2160p"
    elif height >= 1000:
        return "1080p"
    elif height >= 700:
        return "720p"
    elif height >= 500:
        return "576p"
    else:
        return "480p"


def extract_height(video_track) -> Optional[int]:
    """
    Extract video height from MediaInfo track.

    MediaInfo may store height as 'height', 'sampled_height', or other fields.
    """
    for attr in ["height", "sampled_height"]:
        value = getattr(video_track, attr, None)
        if value is None:
            continue

        # Convert to int if string
        if isinstance(value, str):
            if value.isdigit():
                return int(value)
        elif isinstance(value, (int, float)):
            return int(value)

    return None


def guess_codec_from_format(fmt: str, codec: str) -> str:
    """
    Guess video codec from format/codec fields.

    Common mappings:
    - HEVC / H.265 / hvc1 / hev1 -> x265
    - AVC / H.264 / avc1 -> x264
    - AV1 -> AV1
    - XviD -> XviD
    - DivX -> DivX
    """
    fmt_lower = fmt.lower() if fmt else ""
    codec_lower = codec.lower() if codec else ""

    combined = fmt_lower + codec_lower

    # HEVC / H.265 -> x265
    if any(x in combined for x in ["hevc", "hvc1", "hev1", "h.265", "h265"]):
        return "x265"

    # AVC / H.264 -> x264
    if any(x in combined for x in ["avc", "h.264", "h264", "avc1"]):
        return "x264"

    # AV1
    if "av1" in combined:
        return "AV1"

    # XviD
    if "xvid" in codec_lower:
        return "XviD"

    # DivX
    if "divx" in codec_lower:
        return "DivX"

    # Unknown - return original if available
    return fmt if fmt else ""


def extract_media_info(video_path: str) -> MediaMetadata:
    """
    Extract resolution and codec from video file using MediaInfo.

    Args:
        video_path: Path to the video file

    Returns:
        MediaMetadata with resolution and codec (empty if extraction fails)
    """
    metadata = MediaMetadata()

    logger.debug(f"Extracting media info from: {video_path}")

    try:
        media_info = MediaInfo.parse(video_path)
    except Exception as e:
        logger.warning(f"Failed to parse MediaInfo for {video_path}: {e}")
        return metadata

    # Extract from video track
    video_tracks = getattr(media_info, "video_tracks", [])
    if not video_tracks:
        logger.warning(f"No video tracks found in {video_path}")
        return metadata

    video_track = video_tracks[0]

    # Extract resolution
    height = extract_height(video_track)
    if height:
        metadata.resolution = get_resolution_from_height(height)
        logger.debug(f"Extracted resolution: {metadata.resolution} (height={height})")
    else:
        logger.debug(f"Could not extract video height from {video_path}")

    # Extract codec
    fmt = getattr(video_track, "format", "") or ""
    codec_id = getattr(video_track, "codec_id", "") or ""
    codec_id_hint = getattr(video_track, "codec_id_hint", "") or ""
    codec_field = getattr(video_track, "codec", "") or ""

    codec = guess_codec_from_format(fmt, codec_id or codec_id_hint or codec_field)
    if codec:
        metadata.codec = codec
        logger.debug(f"Extracted codec: {metadata.codec}")
    else:
        logger.debug(f"Could not extract codec from {video_path}")

    return metadata
