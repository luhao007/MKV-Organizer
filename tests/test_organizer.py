"""Unit tests for organizer.py utility functions."""

from pathlib import Path

import pytest

from models import FileDefinition, ParsedFileInfo
from organizer import (build_new_filename, build_season_episode_key,
                       check_file_type, find_best_audio_codec,
                       get_all_episode_files, get_subtitle_files,
                       get_video_files, has_video_file, is_subtitle_file,
                       is_video_file, parse_season_episode_key)

# ============================================================================
# check_file_type
# ============================================================================


@pytest.mark.parametrize(
    "filename,extensions,expected",
    [
        ("video.mkv", ["mkv", "mp4", "avi"], True),
        ("video.MKV", ["mkv", "mp4", "avi"], True),
        ("video.mp4", ["mkv", "mp4", "avi"], True),
        ("video.avi", ["mkv", "mp4", "avi"], True),
        ("video.srt", ["mkv", "mp4", "avi"], False),
        ("video", ["mkv"], False),
        ("archive.tar.gz", ["gz"], True),
    ],
)
def test_check_file_type(filename: str, extensions: list[str], expected: bool):
    assert check_file_type(filename, extensions) == expected


# ============================================================================
# is_video_file / is_subtitle_file
# ============================================================================


def test_is_video_file():
    assert is_video_file("show.mkv") is True
    assert is_video_file("show.mp4") is True
    assert is_video_file("show.avi") is True
    assert is_video_file("show.srt") is False
    assert is_video_file("show.txt") is False


def test_is_subtitle_file():
    assert is_subtitle_file("show.srt") is True
    assert is_subtitle_file("show.ass") is True
    assert is_subtitle_file("show.ssa") is True
    assert is_subtitle_file("show.sub") is True
    assert is_subtitle_file("show.mkv") is False


# ============================================================================
# build_season_episode_key / parse_season_episode_key
# ============================================================================


def test_build_season_episode_key():
    assert build_season_episode_key("01", "10") == "01|10"
    assert build_season_episode_key("1", "2") == "1|2"
    assert build_season_episode_key("", "") == "|"


def test_parse_season_episode_key():
    assert parse_season_episode_key("01|10") == ("01", "10")
    assert parse_season_episode_key("1|2") == ("1", "2")


def test_parse_season_episode_key_invalid():
    with pytest.raises(ValueError, match="Invalid season/episode key"):
        parse_season_episode_key("01")
    with pytest.raises(ValueError, match="Invalid season/episode key"):
        parse_season_episode_key("01|02|03")


def test_key_roundtrip():
    """build → parse should give back the original values."""
    original = ("03", "07")
    key = build_season_episode_key(*original)
    assert parse_season_episode_key(key) == original


# ============================================================================
# has_video_file / get_video_files / get_subtitle_files / get_all_episode_files
# ============================================================================


def _make_file_def(
    is_subtitle: bool = False, show_name: str = "Test Show"
) -> FileDefinition:
    return FileDefinition(
        parsed=ParsedFileInfo(
            show_name=show_name,
            season="01",
            episode="01",
            title="",
        ),
        folder="/fake",
        filename="/fake/test.mkv",
        is_subtitle=is_subtitle,
        is_media=not is_subtitle,
    )


class TestEpisodeFileHelpers:
    """Tests for episode_files dict helper functions."""

    def test_has_video_file_true(self):
        files = {"mkv": _make_file_def(is_subtitle=False)}
        assert has_video_file(files) is True

    def test_has_video_file_false_subtitle_only(self):
        files = {"srt": _make_file_def(is_subtitle=True)}
        assert has_video_file(files) is False

    def test_has_video_file_empty(self):
        assert has_video_file({}) is False

    def test_get_all_episode_files(self):
        f1 = _make_file_def()
        f2 = _make_file_def()
        files = {"mkv": f1, "srt": f2}
        result = get_all_episode_files(files)
        assert len(result) == 2
        assert f1 in result and f2 in result

    def test_get_video_files(self):
        f_video = _make_file_def(is_subtitle=False)
        f_sub = _make_file_def(is_subtitle=True)
        files = {"mkv": f_video, "srt": f_sub}
        result = get_video_files(files)
        assert result == [f_video]

    def test_get_subtitle_files(self):
        f_video = _make_file_def(is_subtitle=False)
        f_sub = _make_file_def(is_subtitle=True)
        files = {"mkv": f_video, "srt": f_sub}
        result = get_subtitle_files(files)
        assert result == [f_sub]


# ============================================================================
# find_best_audio_codec
# ============================================================================


class TestFindBestAudioCodec:
    def test_empty_returns_empty(self):
        assert find_best_audio_codec(None) == ""
        assert find_best_audio_codec([]) == ""

    def test_single_codec(self):
        assert find_best_audio_codec(["AAC"]) == "AAC"

    def test_picks_highest_priority(self):
        # TrueHD has the highest priority in the list
        assert find_best_audio_codec(["AAC", "TrueHD.Atmos.7.1"]) == "TrueHD.Atmos.7.1"

    def test_dts_over_aac(self):
        assert find_best_audio_codec(["AAC", "DTS"]) == "DTS"

    def test_flac_over_dd(self):
        assert find_best_audio_codec(["DD", "FLAC"]) == "FLAC"

    def test_substring_match(self):
        # "Atmos" substring should match "TrueHD.Atmos"
        assert "TrueHD.Atmos" in find_best_audio_codec(["TrueHD.Atmos.7.1", "AAC"])


# ============================================================================
# organize_files (anime mode)
# ============================================================================


class TestOrganizeFilesAnime:
    def test_groups_video_and_subtitle_by_detected_episode(
        self, tmp_path: Path
    ) -> None:
        """Anime files without a SxxExx marker are grouped into season 01 with
        their episode number taken from the consecutive numbering."""
        from organizer import organize_files

        file_names = [
            "Detective Conan - 0001 [1080p][Multiple Subtitle][FDB1F25C].mkv",
            "Detective Conan - 0001 [1080p][Multiple Subtitle][FDB1F25C].chs.srt",
            "Detective Conan - 0002 [1080p][Multiple Subtitle][AABBCCDD].mkv",
        ]
        for name in file_names:
            (tmp_path / name).write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), is_show=True, is_anime=True)

        assert list(organized.keys()) == ["Detective Conan"]
        seasons = organized["Detective Conan"]["seasons"]
        assert list(seasons.keys()) == ["01"]
        episodes = seasons["01"]
        assert set(episodes.keys()) == {"0001", "0002"}

        # Subtitle groups with the video of the same episode number.
        assert set(episodes["0001"].keys()) == {"mkv", "srt"}
        assert episodes["0001"]["srt"].is_subtitle is True
        assert list(episodes["0002"].keys()) == ["mkv"]

    def test_explicit_sxxe_marker_kept_in_anime_folder(self, tmp_path: Path) -> None:
        from organizer import organize_files

        file_names = [
            "Show Name - S01E0005 [1080p][HEVC].mkv",
            "Show Name - 0006 [1080p][HEVC].mkv",
        ]
        for name in file_names:
            (tmp_path / name).write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), is_show=True, is_anime=True)
        episodes = organized["Show Name"]["seasons"]["01"]
        assert set(episodes.keys()) == {"0005", "0006"}


# ============================================================================
# build_new_filename: identifier in filename toggle
# ============================================================================


class TestBuildNewFilenameIdentifier:
    def _file_def(
        self, tmdb_id: int = 0, imdb_id: str = ""
    ) -> FileDefinition:
        parsed = ParsedFileInfo(
            show_name="Detective Conan",
            season="01",
            episode="0001",
            title="",
            resolution="1080p",
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            extension="mkv",
        )
        return FileDefinition(
            parsed=parsed,
            folder="/fake",
            filename="/fake/x.mkv",
            is_media=True,
        )

    def test_identifier_included_by_default(self):
        fd = self._file_def(tmdb_id=30983)
        assert "{tmdb-30983}" in build_new_filename(fd, style=1)
        assert "{tmdb-30983}" in build_new_filename(fd, style=2)

    def test_identifier_omitted_when_disabled(self):
        fd = self._file_def(tmdb_id=30983)
        for style in (1, 2):
            name = build_new_filename(fd, style=style, include_identifier=False)
            assert "{tmdb-30983}" not in name
            assert "Detective" in name

    def test_imdb_identifier(self):
        fd = self._file_def(imdb_id="tt0903747")
        assert "{imdb-tt0903747}" in build_new_filename(fd, style=1)

    def test_no_identifier_when_none_known(self):
        fd = self._file_def()
        for style in (1, 2):
            assert "{" not in build_new_filename(fd, style=style)
