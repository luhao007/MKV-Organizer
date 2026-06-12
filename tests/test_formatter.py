"""Unit tests for formatter.py functions."""

from formatter import (
    build_filename,
    capitalize_word,
    format_known,
    format_resolution,
    format_title,
    normalize_illegal_chars,
)

import pytest

# ============================================================================
# capitalize_word
# ============================================================================


class TestCapitalizeWord:
    def test_first_word_always_capitalized(self):
        assert capitalize_word("the", is_first=True) == "The"

    def test_stopword_not_first(self):
        assert capitalize_word("the", is_first=False) == "the"
        assert capitalize_word("of", is_first=False) == "of"
        assert capitalize_word("and", is_first=False) == "and"

    def test_normal_word(self):
        assert capitalize_word("hello", is_first=False) == "Hello"

    def test_acronym_preserved(self):
        assert capitalize_word("HDTV", is_first=False) == "HDTV"

    def test_digit_containing_preserved(self):
        assert capitalize_word("DD5.1", is_first=False) == "DD5.1"

    def test_wrapped_word(self):
        # Parentheses are preserved
        result = capitalize_word("(united)", is_first=False)
        assert "united" not in result.lower() or "United" in result

    def test_empty_word(self):
        assert capitalize_word("") == ""


# ============================================================================
# format_title
# ============================================================================


class TestFormatTitle:
    def test_simple_title(self):
        assert format_title("unlocking disaster") == "Unlocking.Disaster"

    def test_with_stopwords(self):
        result = format_title("the call of duty")
        assert result == "The.Call.of.Duty"

    def test_with_parentheses(self):
        result = format_title("helicopter down (united airlines)")
        assert "United" in result
        assert "Airlines" in result

    def test_empty_title(self):
        assert format_title("") == ""

    def test_style_2_spaces(self):
        result = format_title("unlocking disaster", style=2)
        assert result == "Unlocking Disaster"


# ============================================================================
# format_resolution
# ============================================================================


def test_format_resolution():
    assert format_resolution("1080p") == "1080p"
    assert format_resolution("720P") == "720p"
    assert format_resolution("") == ""


# ============================================================================
# format_known
# ============================================================================


class TestFormatKnown:
    def test_exact_match(self):
        assert format_known("HEVC", ["HEVC", "H264", "AV1"]) == "HEVC"

    def test_case_insensitive(self):
        assert format_known("hevc", ["HEVC", "H264", "AV1"]) == "HEVC"

    def test_rename_mapping(self):
        result = format_known("WEB.DL", ["WEB-DL"], {"WEB.DL": "WEB-DL"})
        assert result == "WEB-DL"

    def test_empty_value(self):
        assert format_known("", ["HEVC"]) == ""

    def test_style_2_spaces(self):
        assert format_known("HEVC", ["HEVC"], style=2) == "HEVC"


# ============================================================================
# normalize_illegal_chars
# ============================================================================


class TestNormalizeIllegalChars:
    def test_removes_commas(self):
        assert normalize_illegal_chars("Hello, World") == "Hello World"

    def test_removes_question_mark(self):
        assert normalize_illegal_chars("What?") == "What"

    def test_removes_colon(self):
        assert normalize_illegal_chars("Title: Subtitle") == "Title Subtitle"

    def test_replaces_asterisk(self):
        assert normalize_illegal_chars("bad*name") == "bad-name"

    def test_no_changes_needed(self):
        assert normalize_illegal_chars("Clean.Name") == "Clean.Name"


# ============================================================================
# build_filename
# ============================================================================


class TestBuildFilename:
    def test_style_1_show_basic(self):
        result = build_filename(
            style=1,
            show_name="Better Call Saul",
            season="01",
            episode="10",
            title="Marco",
            resolution="1080p",
            codec="HEVC",
            source="WEB-DL",
            release_group="RARBG",
        )
        # Should contain key components
        assert result.startswith("Better.Call.Saul.S01E10")
        assert "1080p" in result
        assert "HEVC" in result
        assert result.endswith("-RARBG")

    def test_style_1_show_with_title(self):
        result = build_filename(
            style=1,
            show_name="Show",
            season="01",
            episode="01",
            title="Pilot",
            resolution="1080p",
            codec="HEVC",
            source="WEB-DL",
        )
        assert "Pilot" in result
        assert "S01E01" in result

    def test_style_1_movie(self):
        result = build_filename(
            style=1,
            show_name="Inception",
            season="",
            episode="",
            title="",
            year="2010",
            resolution="1080p",
            codec="HEVC",
            source="BluRay",
        )
        assert result.startswith("Inception.2010")
        assert "1080p" in result

    def test_style_2_show(self):
        result = build_filename(
            style=2,
            show_name="Better Call Saul",
            season="01",
            episode="10",
            title="Marco",
            resolution="1080p",
            codec="HEVC",
            source="WEB-DL",
        )
        assert "Better Call Saul S01E10" in result
        assert "[1080p]" in result
        assert "[HEVC]" in result

    def test_style_with_identifier(self):
        result = build_filename(
            style=1,
            show_name="Show",
            season="01",
            episode="01",
            title="Pilot",
            identifier="{imdb-tt1234567}",
            resolution="1080p",
            codec="HEVC",
            source="WEB-DL",
        )
        assert "{imdb-tt1234567}" in result

    def test_style_with_hdr(self):
        result = build_filename(
            style=1,
            show_name="Show",
            season="01",
            episode="01",
            title="Ep",
            hdr="DV",
            resolution="2160p",
            codec="HEVC",
            source="WEB-DL",
        )
        assert "DV" in result

    def test_style_with_audio_codec(self):
        result = build_filename(
            style=1,
            show_name="Show",
            season="01",
            episode="01",
            title="Ep",
            audio_codec="TrueHD.Atmos.7.1",
            resolution="1080p",
            codec="HEVC",
            source="WEB-DL",
        )
        assert "TrueHD.Atmos.7.1" in result

    def test_style_with_extras(self):
        result = build_filename(
            style=1,
            show_name="Show",
            season="01",
            episode="01",
            title="Ep",
            extras=["IMAX.Enhanced"],
            resolution="1080p",
            codec="HEVC",
            source="WEB-DL",
        )
        assert "IMAX.Enhanced" in result or "IMAX" in result

    def test_style_invalid_raises(self):
        with pytest.raises(ValueError, match="Unknown style"):
            build_filename(
                style=99,
                show_name="Show",
                season="01",
                episode="01",
                title="Ep",
                resolution="1080p",
                codec="HEVC",
                source="WEB-DL",
            )

    def test_empty_optional_fields_omitted(self):
        result = build_filename(
            style=1,
            show_name="Show",
            season="01",
            episode="01",
            title="",
            resolution="",
            codec="",
            source="",
        )
        # Should not have trailing dots
        assert not result.endswith(".")
        assert "S01E01" in result
