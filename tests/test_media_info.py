"""Unit tests for media_info.py pure functions.

Functions that require actual pymediainfo Track objects or file I/O
are tested with mock Track objects.
"""

# This is a unit test file, private functions are imported and tested directly
# pyright: reportPrivateUsage=false

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from pymediainfo import Track

from media_info import (
    _detect_codec_from_formats,
    _extract_dolby_vision_profile,
    _safe_extract_track_attribute,
    extract_audio_codec,
    extract_channels,
    get_resolution_from_size,
)

# ============================================================================
# get_resolution_from_height
# ============================================================================


class TestGetResolutionFromHeight:
    @pytest.mark.parametrize(
        "height,expected",
        [
            (2160, "2160p"),
            (1080, "1080p"),
            (720, "720p"),
            (576, "576p"),
            (480, "480p"),
            (320, "320p"),
            (240, "240p"),
        ],
    )
    def test_standard_heights(self, height: int, expected: str):
        assert get_resolution_from_size(height) == expected

    @pytest.mark.parametrize(
        "height,expected",
        [
            (2100, "2160p"),
            (3000, "2160p"),
            (1000, "1080p"),
            (1500, "1080p"),
            (700, "720p"),
            (900, "720p"),
            (500, "576p"),
            (600, "576p"),
            (400, "480p"),
            (450, "480p"),
            (300, "320p"),
            (350, "320p"),
            (100, "240p"),
            (200, "240p"),
        ],
    )
    def test_non_standard_heights(self, height: int, expected: str):
        assert get_resolution_from_size(height) == expected


# ============================================================================
# _detect_codec_from_formats
# ============================================================================


class TestDetectCodecFromFormats:
    def test_hevc(self):
        # Function expects lowercase input (as from _safe_extract_track_attribute)
        assert _detect_codec_from_formats("hevc", "", "") == "HEVC"
        assert _detect_codec_from_formats("", "hvc1", "") == "HEVC"
        assert _detect_codec_from_formats("", "", "hev1") == "HEVC"
        assert _detect_codec_from_formats("h.265", "", "") == "HEVC"
        assert _detect_codec_from_formats("h265", "", "") == "HEVC"

    def test_avc(self):
        assert _detect_codec_from_formats("avc", "", "") == "H264"
        assert _detect_codec_from_formats("", "avc1", "") == "H264"
        assert _detect_codec_from_formats("h.264", "", "") == "H264"
        assert _detect_codec_from_formats("h264", "", "") == "H264"

    def test_av1(self):
        assert _detect_codec_from_formats("av1", "", "") == "AV1"

    def test_vp9(self):
        assert _detect_codec_from_formats("vp9", "", "") == "VP9"
        assert _detect_codec_from_formats("vp-9", "", "") == "VP9"

    def test_xvid(self):
        assert _detect_codec_from_formats("", "xvid", "") == "XviD"
        assert _detect_codec_from_formats("xvid", "", "") == "XviD"

    def test_divx(self):
        assert _detect_codec_from_formats("", "divx", "") == "DivX"
        assert _detect_codec_from_formats("divx", "", "") == "DivX"

    def test_mpeg1(self):
        assert (
            _detect_codec_from_formats("mpeg", "", "", format_version="1") == "MPEG-1"
        )

    def test_unknown_returns_none(self):
        assert _detect_codec_from_formats("unknown", "", "") is None

    def test_codec_id_fallback(self):
        """When codec_str is empty, codec_id_str should be used."""
        assert _detect_codec_from_formats("", "", "hvc1") == "HEVC"


# ============================================================================
# _extract_dolby_vision_profile
# ============================================================================


class TestExtractDolbyVisionProfile:
    def test_profile_from_other_hdr_format(self):
        result = _extract_dolby_vision_profile(
            hdr_format="",
            hdr_format_profile="",
            hdr_format_commercial="",
            hdr_format_compatibility="",
            other_hdr_format="profile: 08.01 / ...",
        )
        assert result == "DV 08.01"

    def test_dv_from_hdr_format(self):
        result = _extract_dolby_vision_profile(
            hdr_format="Dolby Vision",
            hdr_format_profile="dvhe.08",
            hdr_format_commercial="Dolby Vision",
            hdr_format_compatibility="hdr10",
            other_hdr_format="",
        )
        assert result == "DV 8.1"

    def test_dv_with_sdr_compatibility(self):
        result = _extract_dolby_vision_profile(
            hdr_format="Dolby Vision",
            hdr_format_profile="dvhe.08",
            hdr_format_commercial="Dolby Vision",
            hdr_format_compatibility="sdr",
            other_hdr_format="",
        )
        assert result == "DV 8.2"

    def test_dv_with_hlg_compatibility(self):
        result = _extract_dolby_vision_profile(
            hdr_format="Dolby Vision",
            hdr_format_profile="dvhe.08",
            hdr_format_commercial="Dolby Vision",
            hdr_format_compatibility="hlg",
            other_hdr_format="",
        )
        assert result == "DV 8.4"

    def test_dv_with_bluray_compatibility(self):
        result = _extract_dolby_vision_profile(
            hdr_format="Dolby Vision",
            hdr_format_profile="dvhe.07",
            hdr_format_commercial="Dolby Vision",
            hdr_format_compatibility="blu-ray",
            other_hdr_format="",
        )
        assert result == "DV 7.6"

    def test_dv_no_compatibility(self):
        result = _extract_dolby_vision_profile(
            hdr_format="Dolby Vision",
            hdr_format_profile="dvhe.05",
            hdr_format_commercial="Dolby Vision",
            hdr_format_compatibility="unknown",
            other_hdr_format="",
        )
        assert result == "DV 5"

    def test_dv_from_commercial_name(self):
        result = _extract_dolby_vision_profile(
            hdr_format="",
            hdr_format_profile="dv",
            hdr_format_commercial="Dolby Vision",
            hdr_format_compatibility="",
            other_hdr_format="",
        )
        assert result == "DV"

    def test_no_dv_returns_none(self):
        result = _extract_dolby_vision_profile(
            hdr_format="",
            hdr_format_profile="",
            hdr_format_commercial="",
            hdr_format_compatibility="",
            other_hdr_format="",
        )
        assert result is None


# ============================================================================
# _safe_extract_track_attribute (with mock Track)
# ============================================================================


class TestSafeExtractTrackAttribute:
    def test_string_attribute(self):
        track = MagicMock()
        track.format = "HEVC"
        assert _safe_extract_track_attribute(track, "format") == "hevc"

    def test_int_attribute(self):
        track = MagicMock()
        track.height = 1080
        assert _safe_extract_track_attribute(track, "height") == "1080"

    def test_list_attribute(self):
        track = MagicMock()
        track.other = ["HDR", "SDR"]
        assert _safe_extract_track_attribute(track, "other") == "hdr,sdr"

    def test_missing_attribute_returns_default(self):
        track = MagicMock()
        del track.nonexistent  # ensure AttributeError
        # Use spec to properly raise AttributeError
        track = MagicMock(spec=[])
        assert _safe_extract_track_attribute(track, "format") == ""

    def test_custom_default(self):
        track = MagicMock(spec=[])
        assert _safe_extract_track_attribute(track, "format", default="N/A") == "N/A"

    def test_none_attribute_returns_default(self):
        track = MagicMock()
        track.format = None
        assert _safe_extract_track_attribute(track, "format") == ""


# ============================================================================
# extract_audio_codec / extract_channels (with simple duck-typed tracks)
# ============================================================================


def _audio_track(**kwargs: Any) -> Track:
    """Build a minimal duck-typed track; missing attributes raise AttributeError."""
    return cast(Track, SimpleNamespace(**kwargs))


class TestExtractAudioCodec:
    def test_plain_dts(self):
        track = _audio_track(
            format="DTS", commercial_name="DTS", codec_id="A_DTS", channel_s=2
        )
        assert extract_audio_codec(track) == "DTS.2.0"

    def test_dts_hd_master_audio(self):
        track = _audio_track(
            format="DTS",
            commercial_name="DTS-HD Master Audio",
            codec_id="A_DTS",
            channel_s=6,
        )
        assert extract_audio_codec(track) == "DTS-HD MA.5.1"

    def test_dts_hd_high_resolution(self):
        track = _audio_track(
            format="DTS",
            commercial_name="DTS-HD High Resolution Audio",
            codec_id="A_DTS",
            channel_s=6,
        )
        assert extract_audio_codec(track) == "DTS-HD.5.1"

    def test_dts_x(self):
        track = _audio_track(
            format="DTS", commercial_name="DTS:X", codec_id="A_DTS", channel_s=8
        )
        assert extract_audio_codec(track) == "DTS-X.7.1"

    def test_dts_express_is_not_dts_x(self):
        # Regression: a bare "x" check used to match "DTS Express".
        track = _audio_track(
            format="DTS",
            commercial_name="DTS Express",
            codec_id="A_DTS",
            channel_s=2,
        )
        assert extract_audio_codec(track) == "DTS.2.0"

    def test_pcm_from_codec_id(self):
        # Real MediaInfo data for a PCM track: format="PCM",
        # codec_id="A_PCM/INT/LIT".
        track = _audio_track(
            format="PCM",
            commercial_name="PCM",
            codec_id="A_PCM/INT/LIT",
            format_settings="Little / Signed",
            channel_s=2,
        )
        assert extract_audio_codec(track) == "PCM.2.0"

    def test_lpcm(self):
        track = _audio_track(format="LPCM", codec_id="A_PCM/INT/BIG", channel_s=6)
        assert extract_audio_codec(track) == "PCM.5.1"

    def test_truehd_atmos(self):
        track = _audio_track(
            format="MLP FBA",
            commercial_name="Dolby Atmos",
            codec_id="A_TRUEHD",
            channel_s=8,
        )
        assert extract_audio_codec(track) == "TrueHD.Atmos.7.1"

    def test_unknown_codec_raises(self):
        with pytest.raises(ValueError):
            extract_audio_codec(_audio_track(format="Vorbis"))


class TestExtractChannels:
    def test_mono(self):
        assert extract_channels(_audio_track(channel_s=1)) == "1.0"

    def test_stereo(self):
        assert extract_channels(_audio_track(channel_s=2)) == "2.0"

    def test_five_one(self):
        assert extract_channels(_audio_track(channel_s=6)) == "5.1"

    def test_seven_one(self):
        assert extract_channels(_audio_track(channel_s=8)) == "7.1"

    def test_from_channel_layout(self):
        track = _audio_track(channel_layout="C L R Ls Rs LFE")
        assert extract_channels(track) == "5.1"

    def test_unknown_channel_count_raises(self):
        with pytest.raises(ValueError):
            extract_channels(_audio_track(channel_s=4))
