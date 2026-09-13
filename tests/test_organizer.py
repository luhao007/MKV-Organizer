"""Unit tests for organizer.py utility functions."""

import os
from pathlib import Path

import pytest

from models import FileDefinition, ParsedFileInfo
from organizer import (
    build_new_filename,
    build_normalized_folder_name,
    build_season_episode_key,
    check_file_type,
    find_best_audio_codec,
    get_all_episode_files,
    get_subtitle_files,
    get_video_files,
    has_video_file,
    is_meaningless_folder_name,
    is_subtitle_file,
    is_video_file,
    normalize_folders,
    organize_files,
    parse_season_episode_key,
)

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
    def _file_def(self, tmdb_id: int = 0, imdb_id: str = "") -> FileDefinition:
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


# ============================================================================
# is_meaningless_folder_name / build_normalized_folder_name
# ============================================================================


@pytest.mark.parametrize(
    "folder_name,expected",
    [
        ("1", True),
        ("2", True),
        ("007", True),
        ("CD1", True),
        ("part 2", True),
        ("New folder", True),
        ("Movies", True),
        ("Downloads", True),
        ("", True),
        ("   ", True),
        ("aaa", False),
        ("My Rips", False),
        ("aaa (2000)", False),
        ("Avengers Infinity War", False),
    ],
)
def test_is_meaningless_folder_name(folder_name: str, expected: bool):
    assert is_meaningless_folder_name(folder_name) is expected


class TestBuildNormalizedFolderName:
    def test_name_year_and_identifier(self):
        assert (
            build_normalized_folder_name("Aaa", "2000", "{tmdb-1}")
            == "Aaa (2000) {tmdb-1}"
        )

    def test_year_only(self):
        assert build_normalized_folder_name("Aaa", "2000", "") == "Aaa (2000)"

    def test_identifier_only(self):
        assert build_normalized_folder_name("Aaa", "", "{tmdb-1}") == "Aaa {tmdb-1}"

    def test_unknown_year_does_not_add_empty_parentheses(self):
        assert build_normalized_folder_name("Aaa", "", "") == "Aaa"


# ============================================================================
# organize_files (movies)
# ============================================================================


class TestOrganizeFilesMovies:
    def test_multiple_movies_in_one_folder_are_kept_separate(
        self, tmp_path: Path
    ) -> None:
        for name in ("aaa.2000.mkv", "bbb.2001.mkv"):
            (tmp_path / name).write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), is_show=False)

        assert set(organized.keys()) == {"aaa", "bbb"}
        assert organized["aaa"]["seasons"][""][""]["mkv"].parsed.year == "2000"
        assert organized["bbb"]["seasons"][""][""]["mkv"].parsed.year == "2001"

    def test_subtitle_is_grouped_with_its_movie(self, tmp_path: Path) -> None:
        for name in ("aaa.2000.mkv", "aaa.2000.chs.srt", "bbb.2001.mkv"):
            (tmp_path / name).write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), is_show=False)

        assert set(organized.keys()) == {"aaa", "bbb"}
        files = organized["aaa"]["seasons"][""][""]
        assert set(files.keys()) == {"mkv", "srt"}
        assert files["srt"].is_subtitle is True

    def test_same_movie_name_in_two_folders_keeps_both(self, tmp_path: Path) -> None:
        for sub in ("1", "2"):
            (tmp_path / sub).mkdir()
            (tmp_path / sub / "aaa.2000.mkv").write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)

        assert len(organized) == 2
        folders = sorted(
            os.path.basename(data["folder"]) for data in organized.values()
        )
        assert folders == ["1", "2"]


# ============================================================================
# normalize_folders (movies)
# ============================================================================


class TestNormalizeFoldersMovies:
    def _nested_movie(self, tmp_path: Path, sub: str, filename: str) -> Path:
        folder = tmp_path / sub
        folder.mkdir()
        (folder / filename).write_text("", encoding="utf-8")
        return folder

    def test_nested_movie_folders_are_normalized(self, tmp_path: Path) -> None:
        self._nested_movie(tmp_path, "1", "aaa.2000.mkv")
        self._nested_movie(tmp_path, "2", "bbb.2001.1080p.mkv")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        count = normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        assert count == 2
        assert sorted(os.listdir(tmp_path)) == ["aaa (2000)", "bbb (2001)"]
        # Folder path AND full file path of the FileDefinitions are updated so
        # the following rename step can find the files.
        for data in organized.values():
            for episodes in data["seasons"].values():
                for files in episodes.values():
                    for file_def in files.values():
                        assert Path(file_def.folder).name in {
                            "aaa (2000)",
                            "bbb (2001)",
                        }
                        assert Path(file_def.filename).parent == Path(file_def.folder)
                        assert Path(file_def.filename).exists()

    def test_files_in_season_subfolder_keep_their_relative_path(
        self, tmp_path: Path
    ) -> None:
        folder = tmp_path / "Show.A"
        season = folder / "Season 1"
        season.mkdir(parents=True)
        (season / "Show.A.S01E01.{tmdb-123}.1080p.mkv").write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), recursive=True, is_show=True)
        count = normalize_folders(organized, is_show=True, base_folder=str(tmp_path))

        assert count == 1
        file_def = organized["Show A"]["seasons"]["01"]["01"]["mkv"]
        assert Path(file_def.folder) == tmp_path / "Show A {tmdb-123}" / "Season 1"
        assert Path(file_def.filename).exists()

    def test_identifier_is_kept_in_folder_name(self, tmp_path: Path) -> None:
        self._nested_movie(tmp_path, "1", "aaa.2000.{tmdb-9}.mkv")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        assert os.listdir(tmp_path) == ["aaa (2000) {tmdb-9}"]

    def test_folder_without_year_is_renamed_when_generic(self, tmp_path: Path) -> None:
        self._nested_movie(tmp_path, "1", "aaa.mkv")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        count = normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        assert count == 1
        assert os.listdir(tmp_path) == ["aaa"]

    def test_folder_without_year_and_meaningful_name_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        self._nested_movie(tmp_path, "My Rips", "aaa.mkv")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        count = normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        assert count == 0
        assert os.listdir(tmp_path) == ["My Rips"]

    def test_scanned_folder_is_never_renamed(self, tmp_path: Path) -> None:
        for name in ("aaa.2000.mkv", "bbb.2001.mkv"):
            (tmp_path / name).write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        count = normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        assert count == 0
        assert tmp_path.is_dir()
        assert sorted(os.listdir(tmp_path)) == [
            "aaa.2000.mkv",
            "bbb.2001.mkv",
        ]

    def test_folder_with_multiple_movies_is_skipped(self, tmp_path: Path) -> None:
        self._nested_movie(tmp_path, "1", "aaa.2000.mkv")
        (tmp_path / "1" / "bbb.2001.mkv").write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        count = normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        assert count == 0
        assert os.listdir(tmp_path) == ["1"]

    def test_already_normalized_folder_is_untouched(self, tmp_path: Path) -> None:
        self._nested_movie(tmp_path, "aaa (2000) {tmdb-9}", "aaa.2000.mkv")

        organized = organize_files(str(tmp_path), recursive=True, is_show=False)
        count = normalize_folders(organized, is_show=False, base_folder=str(tmp_path))

        # The {tmdb-9} already present in the folder name is preserved
        assert count == 0
        assert os.listdir(tmp_path) == ["aaa (2000) {tmdb-9}"]

    def test_show_normalization_still_works(self, tmp_path: Path) -> None:
        folder = tmp_path / "Show.A"
        folder.mkdir()
        (folder / "Show.A.S01E01.{tmdb-123}.1080p.mkv").write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), recursive=True, is_show=True)
        count = normalize_folders(organized, is_show=True, base_folder=str(tmp_path))

        assert count == 1
        assert os.listdir(tmp_path) == ["Show A {tmdb-123}"]

    def test_show_without_identifier_is_not_renamed(self, tmp_path: Path) -> None:
        folder = tmp_path / "Show.A"
        folder.mkdir()
        (folder / "Show.A.S01E01.1080p.mkv").write_text("", encoding="utf-8")

        organized = organize_files(str(tmp_path), recursive=True, is_show=True)
        count = normalize_folders(organized, is_show=True, base_folder=str(tmp_path))

        assert count == 0
        assert os.listdir(tmp_path) == ["Show.A"]
