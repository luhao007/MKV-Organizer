"""Unit tests for tmdb.py functions (with HTTP mocking)."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from tmdb import (
    _find_episode_name,
    _parse_nfo_xml,
    _tmdb_get,
    extract_id_from_folder_name,
    search_show_by_name,
)


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
# _tmdb_get (with httpx mock)
# ============================================================================


class TestTmdbGet:
    @patch("tmdb.httpx.Client")
    def test_successful_request(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 123, "name": "Test"}]}
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = _tmdb_get("/search/tv", {"api_key": "fake_key", "query": "Test"})
        assert result == {"results": [{"id": 123, "name": "Test"}]}

    @patch("tmdb.httpx.Client")
    def test_http_error_returns_none(self, mock_client_class):
        from httpx import HTTPError

        mock_client = MagicMock()
        mock_client.get.side_effect = HTTPError("Connection failed")
        mock_client_class.return_value.__enter__.return_value = mock_client

        result = _tmdb_get("/search/tv", {"api_key": "fake_key"})
        assert result is None

    @patch("tmdb.httpx.Client")
    def test_general_exception_returns_none(self, mock_client_class):
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
    def test_returns_show_info(self, mock_api_key, mock_tmdb_get):
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
    def test_no_results_returns_none(self, mock_api_key, mock_tmdb_get):
        mock_api_key.return_value = "fake_key"
        mock_tmdb_get.return_value = {"results": []}

        result = search_show_by_name("Nonexistent Show")
        assert result is None

    @patch("tmdb._tmdb_get")
    @patch("tmdb._get_api_key")
    def test_api_error_returns_none(self, mock_api_key, mock_tmdb_get):
        mock_api_key.return_value = "fake_key"
        mock_tmdb_get.return_value = None

        result = search_show_by_name("Error Show")
        assert result is None


# ============================================================================
# extract_id_from_folder_name
# ============================================================================


class TestExtractIdFromFolderName:
    def test_extracts_imdb_id(self):
        result = extract_id_from_folder_name(
            "/path/to/Show Name {imdb-tt1234567}"
        )
        assert result == ("imdb", "tt1234567")

    def test_extracts_tmdb_id(self):
        result = extract_id_from_folder_name(
            "/path/to/Show Name {tmdb-123456}"
        )
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
