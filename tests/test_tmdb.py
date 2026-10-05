"""Unit tests for tmdb.py functions (with HTTP mocking)."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from config import EPISODE_NAME_FILE
from models import FileDefinition, FileOrganization, ParsedFileInfo
from tmdb import (
    _find_episode_name,
    _parse_nfo_xml,
    _tmdb_get,
    build_episode_title,
    extract_id_from_folder_name,
    fetch_episode_names_for_show,
    fetch_title_and_ids_for_movie,
    search_show_by_name,
)

# This is a unit test file, private functions are imported and tested directly
# pyright: reportPrivateUsage=false


# ============================================================================
# _find_episode_name
# ============================================================================


class TestFindEpisodeName:
    def test_finds_matching_episode(self):
        episodes = [
            {"episode_number": 1, "name": "Pilot"},
            {"episode_number": 2, "name": "Episode 2"},
        ]
        assert _find_episode_name(episodes, 1) == "Pilot"

    def test_returns_none_when_not_found(self):
        episodes = [{"episode_number": 1, "name": "Pilot"}]
        assert _find_episode_name(episodes, 99) is None

    def test_empty_list_returns_none(self):
        assert _find_episode_name([], 1) is None

    def test_episode_number_as_string(self):
        episodes = [{"episode_number": "1", "name": "Pilot"}]
        assert _find_episode_name(episodes, 1) == "Pilot"

    def test_empty_name_returns_none(self):
        episodes = [{"episode_number": 1, "name": ""}]
        assert _find_episode_name(episodes, 1) is None


# ============================================================================
# build_episode_title (merged multi-episode files)
# ============================================================================


class TestBuildEpisodeTitle:
    EPISODES = [
        {"episode_number": 1, "name": "Feline Fervor"},
        {"episode_number": 2, "name": "King Me"},
        {"episode_number": 4, "name": "Action Reaction"},
    ]

    def test_single_episode(self):
        assert build_episode_title(self.EPISODES, ["02"]) == "King Me"

    def test_merged_episodes_are_joined(self):
        assert (
            build_episode_title(self.EPISODES, ["01", "04"])
            == "Feline Fervor & Action Reaction"
        )

    def test_unknown_episode_is_skipped(self):
        assert build_episode_title(self.EPISODES, ["01", "99"]) == "Feline Fervor"

    def test_no_match_returns_empty(self):
        assert build_episode_title(self.EPISODES, ["99"]) == ""

    def test_duplicate_names_are_collapsed(self):
        """A title already holding the joined name must round-trip unchanged."""
        episodes = [
            {"episode_number": 1, "name": "Feline Fervor & Action Reaction"},
            {"episode_number": 4, "name": "Feline Fervor & Action Reaction"},
        ]
        assert (
            build_episode_title(episodes, ["01", "04"])
            == "Feline Fervor & Action Reaction"
        )

    def test_invalid_number_returns_empty(self):
        assert build_episode_title(self.EPISODES, [""]) == ""


# ============================================================================
# fetch_episode_names_for_show (merged files + full season index)
# ============================================================================


def _merged_show_organization(folder: str) -> FileOrganization:
    """One merged file (S03E01E04) whose parsed info carries the TMDB id."""
    parsed = ParsedFileInfo(
        show_name="The Penguins of Madagascar",
        season="03",
        episode="01",
        episodes=["01", "04"],
        title="",
        extension="mkv",
        tmdb_id=7869,
    )
    file_def = FileDefinition(
        parsed=parsed,
        folder=folder,
        filename=f"{folder}/Show.S03E01E04.1080p.mkv",
        is_media=True,
    )
    return {
        "The Penguins of Madagascar": {
            "folder": folder,
            "seasons": {"03": {"01": {"mkv": file_def}}},
        }
    }


def _season_three_episodes() -> list[dict[str, object]]:
    return [
        {"episode_number": 1, "name": "Feline Fervor"},
        {"episode_number": 2, "name": "King Me"},
        {"episode_number": 3, "name": "The Otter Woman"},
        {"episode_number": 4, "name": "Action Reaction"},
    ]


class TestFetchEpisodeNamesForShow:
    def _file_def(self, organized: FileOrganization) -> FileDefinition:
        return organized["The Penguins of Madagascar"]["seasons"]["03"]["01"]["mkv"]

    def test_merged_file_title_and_full_season_index(self, tmp_path: Path):
        folder = str(tmp_path)
        organized = _merged_show_organization(folder)

        with (
            patch("tmdb._get_api_key", return_value="key"),
            patch(
                "tmdb._get_show_info_by_tmdb_id",
                return_value={"name": "Show", "first_air_date": "2008-11-28"},
            ),
            patch(
                "tmdb._get_season_episodes",
                return_value=_season_three_episodes(),
            ),
        ):
            result = fetch_episode_names_for_show(folder, organized)

        assert result is True
        parsed = self._file_def(organized).parsed
        assert parsed.title == "Feline Fervor & Action Reaction"
        assert parsed.tmdb_id == 7869
        assert parsed.year == "2008"

        # The index holds every episode of the fetched season, even though only
        # the merged file (episodes 1 and 4) exists locally.
        index_text = (tmp_path / EPISODE_NAME_FILE).read_text(encoding="utf-8")
        assert index_text.splitlines() == [
            "The Penguins of Madagascar",
            "03|01|Feline Fervor",
            "03|02|King Me",
            "03|03|The Otter Woman",
            "03|04|Action Reaction",
        ]

    def test_season_fetch_failure_writes_nothing(self, tmp_path: Path):
        folder = str(tmp_path)
        organized = _merged_show_organization(folder)

        with (
            patch("tmdb._get_api_key", return_value="key"),
            patch("tmdb._get_show_info_by_tmdb_id", return_value={"name": "Show"}),
            patch("tmdb._get_season_episodes", return_value=None),
        ):
            result = fetch_episode_names_for_show(folder, organized)

        assert result is False
        assert not (tmp_path / EPISODE_NAME_FILE).exists()
        assert self._file_def(organized).parsed.title == ""

    def test_empty_organization_returns_false(self, tmp_path: Path):
        assert fetch_episode_names_for_show(str(tmp_path), {}) is False


# ============================================================================
# _tmdb_get (with httpx mock)
# ============================================================================


class TestTmdbGet:
    @patch("tmdb.httpx.Client")
    def test_successful_request(self, mock_client_class: MagicMock):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 123, "name": "Test"}]}
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = _tmdb_get("/search/tv", {"api_key": "fake_key", "query": "Test"})
        assert result == {"results": [{"id": 123, "name": "Test"}]}

    @patch("tmdb.httpx.Client")
    def test_http_error_returns_none(self, mock_client_class: MagicMock):
        from httpx import HTTPError

        mock_client = MagicMock()
        mock_client.get.side_effect = HTTPError("Connection failed")
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = _tmdb_get("/search/tv", {"api_key": "fake_key"})
        assert result is None

    @patch("tmdb.httpx.Client")
    def test_general_exception_returns_none(self, mock_client_class: MagicMock):
        mock_client = MagicMock()
        mock_client.get.side_effect = RuntimeError("Unexpected")
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = _tmdb_get("/search/tv", {"api_key": "fake_key"})
        assert result is None


# ============================================================================
# search_show_by_name (with httpx mock)
# ============================================================================


class TestSearchShowByName:
    @patch("tmdb._tmdb_get")
    @patch("tmdb._get_api_key")
    def test_returns_show_info(self, mock_api_key: MagicMock, mock_tmdb_get: MagicMock):
        mock_api_key.return_value = "fake_key"
        mock_tmdb_get.return_value = {
            "results": [
                {
                    "id": 123,
                    "name": "Test Show",
                    "overview": "A test show",
                    "first_air_date": "2020-01-01",
                    "poster_path": "/poster.jpg",
                }
            ]
        }

        result = search_show_by_name("Test Show")
        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "Test Show"
        assert result["first_air_date"] == "2020-01-01"

    @patch("tmdb._tmdb_get")
    @patch("tmdb._get_api_key")
    def test_no_results_returns_none(
        self, mock_api_key: MagicMock, mock_tmdb_get: MagicMock
    ):
        mock_api_key.return_value = "fake_key"
        mock_tmdb_get.return_value = {"results": []}

        result = search_show_by_name("Nonexistent Show")
        assert result is None

    @patch("tmdb._tmdb_get")
    @patch("tmdb._get_api_key")
    def test_api_error_returns_none(
        self, mock_api_key: MagicMock, mock_tmdb_get: MagicMock
    ):
        mock_api_key.return_value = "fake_key"
        mock_tmdb_get.return_value = None

        result = search_show_by_name("Error Show")
        assert result is None


# ============================================================================
# extract_id_from_folder_name
# ============================================================================


class TestExtractIdFromFolderName:
    def test_extracts_imdb_id(self):
        result = extract_id_from_folder_name("/path/to/Show Name {imdb-tt1234567}")
        assert result == ("imdb", "tt1234567")

    def test_extracts_tmdb_id(self):
        result = extract_id_from_folder_name("/path/to/Show Name {tmdb-123456}")
        assert result == ("tmdb", "123456")

    def test_no_id_returns_none(self):
        result = extract_id_from_folder_name("/path/to/Show Name")
        assert result is None

    def test_empty_folder_returns_none(self):
        result = extract_id_from_folder_name("")
        assert result is None


# ============================================================================
# _parse_nfo_xml (with mock XML)
# ============================================================================


class TestParseNfoXml:
    def test_parses_tvshow_fields(self):
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<tvshow>\n"
            "  <imdb_id>tt1234567</imdb_id>\n"
            "  <tmdbid>123456</tmdbid>\n"
            "  <originaltitle>Test Show</originaltitle>\n"
            "  <year>2020</year>\n"
            "</tvshow>"
        )
        with patch("builtins.open", mock_open(read_data=xml_content)):
            result = _parse_nfo_xml(
                "/fake/tvshow.nfo",
                {
                    "imdb_id": "imdb_id",
                    "tmdbid": "tmdb_id",
                    "originaltitle": "original_title",
                    "year": "year",
                },
                "tvshow.nfo",
            )
        assert result == {
            "imdb_id": "tt1234567",
            "tmdb_id": "123456",
            "original_title": "Test Show",
            "year": "2020",
        }

    def test_parses_movie_fields(self):
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<movie>\n"
            "  <imdbid>tt9876543</imdbid>\n"
            "  <tmdbid>987654</tmdbid>\n"
            "</movie>"
        )
        with patch("builtins.open", mock_open(read_data=xml_content)):
            result = _parse_nfo_xml(
                "/fake/movie.nfo",
                {
                    "imdbid": "imdb_id",
                    "tmdbid": "tmdb_id",
                },
                "movie info",
            )
        assert result == {"imdb_id": "tt9876543", "tmdb_id": "987654"}

    def test_empty_xml_returns_none(self):
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<tvshow>\n</tvshow>'
        with patch("builtins.open", mock_open(read_data=xml_content)):
            result = _parse_nfo_xml(
                "/fake/tvshow.nfo",
                {"imdb_id": "imdb_id"},
                "tvshow.nfo",
            )
        assert result is None

    def test_parse_error_returns_none(self):
        with patch("builtins.open", mock_open(read_data="not valid xml")):
            result = _parse_nfo_xml(
                "/fake/bad.nfo",
                {"imdb_id": "imdb_id"},
                "bad.nfo",
            )
        assert result is None


# ============================================================================
# fetch_title_and_ids_for_movie
# ============================================================================


def _movie_organization(
    folder: str, filename: str = "aaa.2000.mkv", tmdb_id: int = 0
) -> dict:
    file_def = FileDefinition(
        parsed=ParsedFileInfo(
            show_name="aaa",
            season="",
            episode="",
            title="",
            year="2000",
            extension="mkv",
            tmdb_id=tmdb_id,
        ),
        folder=folder,
        filename=f"{folder}/{filename}",
        is_media=True,
    )
    return {"aaa": {"folder": folder, "seasons": {"": {"": {"mkv": file_def}}}}}


class TestFetchTitleAndIdsForMovie:
    def test_uses_movie_nfo_without_any_api_call(self, tmp_path):
        folder = str(tmp_path)
        (tmp_path / "movie.nfo").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<movie>\n"
            "  <imdbid>tt1234567</imdbid>\n"
            "  <tmdbid>987654</tmdbid>\n"
            "  <originaltitle>Aaa Original</originaltitle>\n"
            "  <year>2000</year>\n"
            "</movie>",
            encoding="utf-8",
        )
        organized = _movie_organization(folder)

        with patch("tmdb._get_api_key") as mock_key:
            result = fetch_title_and_ids_for_movie(folder, organized)

        mock_key.assert_not_called()
        assert result == ("Aaa Original", "2000")

        parsed = organized["aaa"]["seasons"][""][""]["mkv"].parsed
        assert parsed.show_name == "Aaa Original"
        assert parsed.year == "2000"
        assert parsed.imdb_id == "tt1234567"
        assert parsed.tmdb_id == 987654

    def test_uses_id_from_folder_name(self, tmp_path):
        folder = tmp_path / "aaa {tmdb-12345}"
        folder.mkdir()
        organized = _movie_organization(str(folder))

        movie_info = {
            "id": 12345,
            "title": "Aaa",
            "original_title": "Aaa Original",
            "release_date": "2000-05-01",
            "imdb_id": "tt0000001",
        }
        with (
            patch("tmdb._get_api_key", return_value="key"),
            patch(
                "tmdb._get_movie_info_by_tmdb_id", return_value=movie_info
            ) as mock_lookup,
        ):
            result = fetch_title_and_ids_for_movie(str(folder), organized)

        mock_lookup.assert_called_once_with("key", 12345)
        assert result == ("Aaa Original", "2000")

        parsed = organized["aaa"]["seasons"][""][""]["mkv"].parsed
        assert parsed.show_name == "Aaa Original"
        assert parsed.tmdb_id == 12345
        assert parsed.imdb_id == "tt0000001"

    def test_uses_id_from_file_name(self, tmp_path):
        folder = str(tmp_path)
        organized = _movie_organization(folder, "aaa.2000.{imdb-tt777}.mkv")
        file_def = organized["aaa"]["seasons"][""][""]["mkv"]
        file_def.parsed.imdb_id = "tt777"
        file_def.parsed.year = ""

        movie_info = {
            "id": 55,
            "original_title": "Aaa",
            "release_date": "2000-01-01",
        }
        with (
            patch("tmdb._get_api_key", return_value="key"),
            patch("tmdb._get_movie_info_by_imdb_id", return_value=movie_info),
        ):
            result = fetch_title_and_ids_for_movie(folder, organized)

        assert result == ("Aaa", "2000")
        assert file_def.parsed.tmdb_id == 55

    def test_returns_none_when_nothing_is_known(self, tmp_path):
        folder = str(tmp_path)
        organized = _movie_organization(folder)
        organized["aaa"]["seasons"][""][""]["mkv"].parsed.year = ""

        with patch("tmdb._get_api_key") as mock_key:
            result = fetch_title_and_ids_for_movie(folder, organized)

        mock_key.assert_not_called()
        assert result is None

    def test_empty_organization_returns_none(self, tmp_path):
        assert fetch_title_and_ids_for_movie(str(tmp_path), {}) is None
