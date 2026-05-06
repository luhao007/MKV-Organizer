"""Extract metadata from video files using MediaInfo."""

import traceback
from typing import Optional

from pymediainfo import MediaInfo, Track

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
    240: "240p",
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
    logger.debug(f"Height {height} not in standard mapping, applying guessing")
    if height >= 2100:
        return "2160p"
    elif height >= 1000:
        return "1080p"
    elif height >= 700:
        return "720p"
    elif height >= 500:
        return "576p"
    elif height >= 400:
        return "480p"
    elif height >= 300:
        return "320p"
    else:
        return "240p"


def extract_height(video_track: Track) -> Optional[int]:
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


def guess_video_codec(track: Track) -> str:
    """
    Guess video codec from format/codec fields.

    Common mappings:
    - HEVC / H.265 / hvc1 / hev1 -> x265
    - AVC / H.264 / avc1 -> x264
    - AV1 -> AV1
    - XviD -> XviD
    - DivX -> DivX
    """
    fmt: str = (getattr(track, "format", "") or "").lower()
    fmt_ver: str = (getattr(track, "format_version", "") or "").lower()
    codec: str = (getattr(track, "codec", "") or "").lower()
    codec_id: str = (getattr(track, "codec_id", "") or "").lower()
    codec = codec or codec_id  # Some formats use codec_id instead of codec

    combined = fmt + codec

    # HEVC / H.265 -> x265
    if any(x in combined for x in ["hevc", "hvc1", "hev1", "h.265", "h265"]):
        return "x265"

    # AVC / H.264 -> x264
    if any(x in combined for x in ["avc", "h.264", "h264", "avc1"]):
        return "x264"

    # AV1
    if "av1" in combined:
        return "AV1"

    if any(x in combined for x in ["vp9", "vp-9"]):
        return "VP9"

    # XviD
    if "xvid" in codec or "xvid" in fmt:
        return "XviD"

    # DivX
    if "divx" in codec or "divx" in fmt:
        return "DivX"

    # MPEG-1:
    if "mpeg" in combined and "1" in fmt_ver:
        return "MPEG-1"

    raise ValueError(
        f"Unknown codec for format='{fmt}', format_version='{fmt_ver}', codec='{codec}'"
    )


def guess_audio_codec(track: Track) -> str:
    """
    Guess audio codec from format/codec fields.

    Common mappings:
    - AAC -> AAC
    - AC-3 -> AC3 or DD.5.1
    - E-AC-3 -> DDP
    - DTS / DTS-HD -> DTS
    - FLAC -> FLAC
    - MP3 -> MP3
    - Opus -> Opus
    """
    fmt: str = (getattr(track, "format", "") or "").lower()
    codec: str = (getattr(track, "codec", "") or "").lower()
    codec_id: str = (getattr(track, "codec_id", "") or "").lower()
    codec = codec or codec_id  # Some formats use codec_id instead of codec
    commercial_name: str = (getattr(track, "commercial_name", "") or "").lower()

    def get_channels(track: Track) -> str:
        channels = getattr(track, "channels", 0)
        if not channels:
            return ""

        if channels == 8:
            return "7.1"
        elif channels == 6:
            return "5.1"
        elif channels == 2:
            return "2.0"
        else:
            raise ValueError(f"Unknown AC-3 channel configuration: {channels}")

    if "aac" in fmt:
        return "AAC"
    if any(x in fmt for x in ["ac-3", "ac3"]) or "ac3" in codec:
        channels = get_channels(track)
        # Just use "AC3" if we can't determine channels
        # otherwise use "DD.5.1", "DD.7.1", etc.
        return f"DD.{channels}" if channels else "AC3"
    if any(x in fmt for x in ["e-ac-3", "eac3"]):
        channels = get_channels(track)
        return f"DDP.{channels}" if channels else "DDP"
    if "dts" in fmt or "dts" in codec:
        if commercial_name == "dts-hd master audio":
            return "DTS-HD MA"
        elif "dts-hd" in commercial_name:
            return "DTS-HD"
        else:
            return "DTS"
    if "mlp" in fmt or "truehd" in codec:
        ret = "TrueHD.Atmos" if "Atmos" in commercial_name else "TrueHD"
        channels = get_channels(track)
        return f"{ret}.{channels}" if channels else ret
    if "opus" in fmt or "opus" in codec:
        return "Opus"
    if "flac" in fmt or "flac" in codec:
        return "FLAC"
    if "mpeg audio" in fmt:
        format_profile = (getattr(track, "format_profile", "") or "").lower()
        if "layer 2" in format_profile:
            return "MP2"
        elif "layer 3" in format_profile:
            return "MP3"
        else:
            raise ValueError(f"Unknown MPEG Audio format profile: {format_profile}")

    raise ValueError(f"Unknown audio codec for format='{fmt}', codec='{codec}'")


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
    try:
        codec = guess_video_codec(video_track)
        metadata.codec = codec
        logger.debug(f"Extracted codec: {metadata.codec}")
    except ValueError as e:
        logger.warning(f"Failed to guess video codec for {video_path}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        metadata.codec = ""

    # Extract audio codec from first audio track
    audio_codecs: set[str] = set()
    for audio_track in getattr(media_info, "audio_tracks", []):
        try:
            audio_codec = guess_audio_codec(audio_track)
            logger.debug(f"Extracted audio codec: {audio_codec}")
            audio_codecs.add(audio_codec)
            break  # Use the first audio track's codec
        except ValueError as e:
            logger.warning(f"Failed to guess audio codec for {video_path}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            continue
    if audio_codecs:
        metadata.audio_codec = ".".join(audio_codecs)

    return metadata
