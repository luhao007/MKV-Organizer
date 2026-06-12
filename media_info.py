"""Extract metadata from video files using MediaInfo."""

import os
import re
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


# ============================================================================
# Extraction Utility Functions (moved from extraction_utils.py)
# ============================================================================


def _safe_extract_track_attribute(track: Track, field: str, default: str = "") -> str:
    """Safely extract and format track attribute."""
    try:
        info: str | int | list[str | int] | None = getattr(track, field, None)
        if info is None:
            return default
        if isinstance(info, list):
            info = ",".join([str(i) for i in info])
        return str(info).strip().lower()
    except (AttributeError, TypeError, ValueError):
        return default


def _detect_codec_from_formats(
    format_str: str,
    codec_str: str,
    codec_id_str: str,
    format_version: str = "",
    commercial_name: str = "",
) -> Optional[str]:
    """Detect codec type from format/codec/codec_id fields."""
    codec = codec_str or codec_id_str
    combined = format_str + codec

    if any(x in combined for x in ["hevc", "hvc1", "hev1", "h.265", "h265"]):
        return "HEVC"
    if any(x in combined for x in ["avc", "h.264", "h264", "avc1"]):
        return "H264"
    if "av1" in combined:
        return "AV1"
    if any(x in combined for x in ["vp9", "vp-9"]):
        return "VP9"
    if "xvid" in codec or "xvid" in format_str:
        return "XviD"
    if "divx" in codec or "divx" in format_str:
        return "DivX"
    if "mpeg" in combined and "1" in format_version:
        return "MPEG-1"

    return None


def _extract_dolby_vision_profile(
    hdr_format: str,
    hdr_format_profile: str,
    hdr_format_commercial: str,
    hdr_format_compatibility: str,
    other_hdr_format: str,
) -> Optional[str]:
    """Extract Dolby Vision profile from HDR metadata."""
    if "profile" in other_hdr_format:
        dv_profile = re.search(r"profile: (\d{2}\.\d{2})", other_hdr_format)
        if dv_profile:
            return f"DV {dv_profile.group(1)}"

    if (
        "dolby vision" in hdr_format
        or "dolby vision" in hdr_format_commercial
        or "dv" in hdr_format_profile
    ):
        dv_match = re.match(
            r"dv(?:he|h1|av)\.(\d{2})", hdr_format_profile, re.IGNORECASE
        )
        if dv_match:
            profile = int(dv_match.group(1))
            if hdr_format_compatibility.startswith("hdr"):
                compatibility = 1
            elif hdr_format_compatibility.startswith("sdr"):
                compatibility = 2
            elif hdr_format_compatibility.startswith("hlg"):
                compatibility = 4
            elif hdr_format_compatibility.startswith("blu-ray"):
                compatibility = 6
            else:
                compatibility = 0
            if compatibility:
                return f"DV {profile}.{compatibility}"
            else:
                return f"DV {profile}"

        return "DV"

    return None


# ============================================================================
# Public API
# ============================================================================


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


def extract_video_codec(track: Track) -> str:
    """
    Extract video codec from format/codec fields.

    Common mappings:
    - HEVC / H.265 / hvc1 / hev1 -> HEVC
    - AVC / H.264 / avc1 -> H264
    - AV1 -> AV1
    - XviD -> XviD
    - DivX -> DivX
    """
    fmt = _safe_extract_track_attribute(track, "format")
    fmt_ver = _safe_extract_track_attribute(track, "format_version")
    codec = _safe_extract_track_attribute(track, "codec")
    codec_id = _safe_extract_track_attribute(track, "codec_id")

    detected = _detect_codec_from_formats(fmt, codec, codec_id, fmt_ver)
    if detected:
        return detected

    raise ValueError(
        f"Unknown codec for format='{fmt}', format_version='{fmt_ver}', codec='{codec}'"
    )


def extract_hdr(track: Track) -> str:
    """
    Extract HDR format information from MediaInfo track.

    Tries to extract Dolby Vision profile (e.g., "DV 8.1", "DV 7.6") first.
    If DV is not available, checks for HDR10/HLG and returns "HDR".
    Otherwise returns "SDR".

    Returns:
        One of:
        - "DV X.Y" for Dolby Vision content (e.g., "DV 8.1", "DV 7.6")
        - "DV" if Dolby Vision is detected but profile can't be extracted
        - "HDR" for HDR10 / HDR10+ / HLG content
        - "SDR" for standard dynamic range
    """
    hdr_format = _safe_extract_track_attribute(track, "hdr_format")
    hdr_format_commercial = _safe_extract_track_attribute(
        track, "hdr_format_commercial"
    )
    hdr_format_compatibility = _safe_extract_track_attribute(
        track, "hdr_format_compatibility"
    )
    hdr_format_profile = _safe_extract_track_attribute(track, "hdr_format_profile")
    other_hdr_format = _safe_extract_track_attribute(track, "other_hdr_format")

    # Try to extract Dolby Vision profile
    dv_result = _extract_dolby_vision_profile(
        hdr_format,
        hdr_format_profile,
        hdr_format_commercial,
        hdr_format_compatibility,
        other_hdr_format,
    )
    if dv_result:
        return dv_result

    # Check for HDR (HDR10, HDR10+, HLG, SMPTE ST 2086, etc.)
    if "hdr10+" in hdr_format_profile:
        return "HDR Plus"
    elif "hlg" in hdr_format_profile:
        return "HLG"
    elif "hdr" in hdr_format_compatibility or "hdr" in hdr_format_commercial:
        return "HDR"

    return "SDR"


def extract_channels(track: Track) -> str:
    """
    Extract audio channel configuration from a MediaInfo track.

    Converts raw channel counts to standard labels: 8→7.1, 6→5.1, 2→2.0.
    Falls back to counting elements in ``channel_layout`` if ``channels`` is absent.

    Args:
        track: A pymediainfo Track (typically an audio track).

    Returns:
        Channel string (e.g., "7.1", "5.1", "2.0") or "" if unknown.

    Raises:
        ValueError: If the channel count doesn't match a known configuration.
    """
    channels = _safe_extract_track_attribute(
        track, "channels"
    ) or _safe_extract_track_attribute(track, "channel_s")
    if not channels:
        channel_layout = _safe_extract_track_attribute(track, "channel_layout")
        if channel_layout:
            channels = len(channel_layout.split(" "))
        else:
            return ""
    channels = int(channels)

    if channels == 8:
        return "7.1"
    elif channels == 6:
        return "5.1"
    elif channels == 2:
        return "2.0"
    else:
        raise ValueError(f"Unknown AC-3 channel configuration: {channels}")


def extract_audio_codec(track: Track) -> str:
    """
    Guess audio codec from format/codec fields.

    Common mappings:
    - AAC -> AAC
    - AC-3 -> AC3
    - E-AC-3 -> EAC3
    - DTS / DTS-HD -> DTS
    - FLAC -> FLAC
    - MP3 -> MP3
    - Opus -> Opus
    """
    fmt = _safe_extract_track_attribute(track, "format")
    codec = _safe_extract_track_attribute(track, "codec")
    codec_id = _safe_extract_track_attribute(track, "codec_id")
    codec = codec or codec_id  # Some formats use codec_id instead of codec
    commercial_name = _safe_extract_track_attribute(track, "commercial_name")
    fmt_info = _safe_extract_track_attribute(track, "format_info")

    if "aac" in fmt:
        ret = "AAC"
    elif any(x in fmt for x in ["e-ac-3", "eac3"]):
        ret = "EAC3"
        if "atmos" in commercial_name or any(
            x in fmt_info for x in ["JOC", "Joint Object Coding"]
        ):
            ret += ".Atmos"
    elif any(x in fmt for x in ["ac-3", "ac3"]) or "ac3" in codec:
        ret = "DD"
    elif "dts" in fmt or "dts" in codec:
        if "x" in commercial_name:
            ret = "DTS-X"
        elif "hd" in commercial_name:
            ret = "DTS-HD"
            if any(x in commercial_name for x in ["ma", "master audio"]):
                ret += " MA"
        else:
            ret = "DTS"
    elif "mlp" in fmt or "truehd" in codec:
        ret = "TrueHD"
        if "fba" in fmt or "atmos" in commercial_name:
            ret += ".Atmos"
    elif "opus" in fmt or "opus" in codec:
        ret = "Opus"
    elif "flac" in fmt or "flac" in codec:
        ret = "FLAC"
    elif "mpeg audio" in fmt:
        format_profile = (getattr(track, "format_profile", "") or "").lower()
        if "layer 2" in format_profile:
            return "MP2"
        elif "layer 3" in format_profile:
            return "MP3"
        else:
            raise ValueError(f"Unknown MPEG Audio format profile: {format_profile}")
    else:
        raise ValueError(f"Unknown audio codec for format='{fmt}', codec='{codec}'")

    channels = extract_channels(track)
    if channels:
        ret += f".{channels}"
    return ret


def extract_source(track: Track) -> str:
    """
    Extract source media type from a MediaInfo track.

    Detects whether the source is a Blu-ray disc.

    Args:
        track: A pymediainfo Track.

    Returns:
        ``"blu-ray"`` if the source field contains "blu-ray", otherwise ``""``.
    """
    source = _safe_extract_track_attribute(track, "source")
    if "blu-ray" in source:
        return "blu-ray"
    else:
        return ""


def _get_tracks(media_info: MediaInfo, track_type: str) -> list[Track]:
    """
    Get tracks of a specific type from MediaInfo.

    Args:
        media_info: MediaInfo object
        track_type: Type of track to get (e.g., "video", "audio")

    Returns:
        List of Track objects
    """
    return getattr(media_info, track_type + "_tracks", [])


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
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        media_info = MediaInfo.parse(video_path)
    except Exception as e:
        logger.warning(f"Failed to parse MediaInfo for {video_path}: {e}")
        return metadata

    # Extract from video track
    video_tracks = _get_tracks(media_info, "video")
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
        codec = extract_video_codec(video_track)
        metadata.codec = codec
        logger.debug(f"Extracted codec: {metadata.codec}")
    except ValueError as e:
        logger.warning(f"Failed to guess video codec for {video_path}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        metadata.codec = ""

    # Extract HDR format
    try:
        hdr = extract_hdr(video_track)
        metadata.hdr = hdr
        logger.debug(f"Extracted HDR: {metadata.hdr}")
    except Exception as e:
        logger.warning(f"Failed to extract HDR info for {video_path}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")

    # Extract audio codec
    audio_codecs: set[str] = set()
    for audio_track in _get_tracks(media_info, "audio"):
        try:
            audio_codec = extract_audio_codec(audio_track)
            logger.debug(f"Extracted audio codec: {audio_codec}")
            if audio_codec:
                audio_codecs.add(audio_codec)
        except ValueError as e:
            logger.warning(f"Failed to guess audio codec for {video_path}")
            logger.debug(f"Track info: {audio_track.to_data()}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            continue

    metadata.audio_codecs = list(audio_codecs) if audio_codecs else None
    return metadata
