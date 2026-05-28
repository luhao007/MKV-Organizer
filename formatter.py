"""Format and capitalize video filenames according to naming conventions."""

import re
from typing import Iterable, Optional

from config import (
    AUDIO_CODECS,
    CODECS,
    HDR,
    HDR_RENAME_MAPPING,
    LANGUAGES,
    PACKAGE,
    SOURCE_RENAME_MAPPINGS,
    SOURCES,
    STOPWORDS,
    WORD_SPLIT_PATTERN,
    WRAP_PATTERN,
)


def capitalize_word(word: str, is_first: bool = False) -> str:
    """
    Capitalize a word according to title case rules.

    Rules:
    - First word: always capitalize
    - Stopwords (the, of, and, etc.): keep lowercase
    - Other words: capitalize first letter

    Args:
        word: Word to capitalize (may include wrapping brackets)
        is_first: Whether this is the first word

    Returns:
        Capitalized word
    """
    if not word:
        return ""

    # Extract core word from brackets/parentheses
    match = WRAP_PATTERN.match(word)
    if not match:
        core = word
        prefix = suffix = ""
    else:
        prefix, core, suffix = match.groups()

    if not core:
        return word

    core_lower = core.lower()

    # Apply stopword rules
    if not is_first and core_lower in STOPWORDS:
        return prefix + core_lower + suffix

    # Preserve acronyms and tokens containing digits (e.g. HDTV, DD5.1)
    if core.isupper() or any(char.isdigit() for char in core):
        return prefix + core + suffix

    # Capitalize first letter
    capitalized = (
        core_lower[0].upper() + core_lower[1:]
        if len(core_lower) > 1
        else core_lower.upper()
    )
    return prefix + capitalized + suffix


def format_title(title: str, style: int = 1) -> str:
    """
    Format a title using title case conventions.

    Handles:
    - Stopwords capitalization
    - Bracket/parentheses preservation
    - Multiple separators (dots, spaces, underscores, hyphens)

    Examples:
        "unlocking disaster" -> "Unlocking Disaster"
        "the call of duty" -> "The Call of Duty"
        "(united airlines)" -> "(United Airlines)"

    Args:
        title: Title text to format

    Returns:
        Formatted title with proper capitalization
    """
    if not title:
        return ""

    # Remove characters that are not be able to be used in filenames
    title = title.replace(",", "").replace("?", "").replace("!", "")

    # Split on separators while preserving the structure
    tokens = [t for t in WORD_SPLIT_PATTERN.split(title) if t]

    # Capitalize each token
    capitalized_tokens = [
        capitalize_word(token, is_first=(i == 0)) for i, token in enumerate(tokens)
    ]

    separator = "." if style == 1 else " "
    return separator.join(capitalized_tokens)


def format_resolution(resolution: str) -> str:
    """Format resolution string in lowercase. E.g., '1080p'"""
    return resolution.lower() if resolution else ""


def format_known(
    value: str,
    known_list: Iterable[str],
    rename_mapping: Optional[dict[str, str]] = None,
    style: int = 1,
) -> str:
    """Format a value by matching it against a known list (case-insensitive)."""
    if not value:
        return ""

    mapping = dict([(known, known) for known in known_list])

    if rename_mapping:
        mapping.update(rename_mapping)

    for alias, standard in mapping.items():
        if alias.lower() in value.lower():
            value = re.sub(alias, standard, value, flags=re.IGNORECASE)

    if style != 1:
        # Use space as separator
        value = value.replace(".", " ")
        # Handle audio channel
        channels = ["2.0", "5.1", "7.1"]
        for channel in channels:
            value = value.replace(channel.replace(".", " "), channel)
    return value


def build_filename(
    style: int,
    show_name: str,
    season: str,
    episode: str,
    title: str,
    year: str = "",
    resolution: str = "",
    codec: str = "",
    hdr: str = "",
    source: str = "",
    package: str = "",
    audio_codec: str = "",
    lang: str = "",
    extra: str = "",
    release_group: str = "",
) -> str:
    """
    Build a standardized filename from components.

    Format: "ShowName.S01E01.Title.1080p.x265-GROUP"

    Args:
        show_name: Show/series name
        season: Season number (should be 2 digits like "01")
        episode: Episode number (should be 2 digits like "10")
        title: Episode title
        year: Release year
        resolution: Video resolution (e.g., "1080p")
        codec: Video codec (e.g., "x265")
        audio_codec: Audio codec (e.g., "DD5.1")
        lang: Language code (e.g., "eng")
        source: Source type (e.g., "WEB-DL")
        extra: Extra information (e.g., "REPACK")
        release_group: Release group name (e.g., "RARBG")

    Returns:
        Formatted filename without extension
    """
    if style == 1:
        # Build parts list (skip empty parts)
        parts = [
            format_title(show_name, 1),
            year,
            f"S{season}E{episode}" if season and episode else "",
            format_title(title, 1),
            format_resolution(resolution),
            format_known(source, SOURCES, SOURCE_RENAME_MAPPINGS, style=1),
            format_known(package, PACKAGE, style=1),
            format_known(codec, CODECS, style=1),
            format_known(hdr, HDR, HDR_RENAME_MAPPING, style=1),
            format_known(audio_codec, AUDIO_CODECS, style=1),
            format_known(lang, LANGUAGES, style=1),
            extra,
        ]
        parts = [p for p in parts if p]

        # Join with dots
        filename = ".".join(parts)
    elif style == 2:
        filename = format_title(show_name, 2)
        if year:
            filename += f" ({year})"
        if season and episode:
            filename += f" S{season}E{episode}"
        if title:
            filename += f" - {format_title(title, 2)}"

        parts = [
            format_resolution(resolution),
            format_known(source, SOURCES, SOURCE_RENAME_MAPPINGS, style=2),
            format_known(package, PACKAGE, style=2),
            format_known(codec, CODECS, style=2),
            format_known(hdr, HDR, HDR_RENAME_MAPPING, style=2),
            format_known(audio_codec, AUDIO_CODECS, style=2),
            format_known(lang, LANGUAGES, style=2),
            extra,
        ]
        parts = [p for p in parts if p]
        if parts:
            filename += f" {''.join(f'[{part}]' for part in parts)}"
    else:
        raise ValueError("Unknown style")

    # Add release group if present
    if release_group:
        filename = f"{filename}-{release_group}"

    return filename
