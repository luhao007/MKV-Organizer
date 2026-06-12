"""Format and capitalize video filenames according to naming conventions."""

import re
from typing import Iterable, Optional

from config import (
    AUDIO_CODECS,
    CODECS,
    EXTRA,
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
    illegal_chars = ",?!\\/:"
    for char in illegal_chars:
        title = title.replace(char, "")

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
    """
    Normalize a metadata value against a known list (case-insensitive).

    If a match is found, the value is replaced with the canonical form.
    Dot/space separators are adjusted based on ``style`` (1=dots, 2=spaces).

    Args:
        value: The raw metadata string to normalize.
        known_list: Iterable of canonical value names.
        rename_mapping: Optional dict mapping aliases → canonical names.
        style: 1 for dot-separated output, 2 for space-separated.

    Returns:
        Normalized value string, or ``""`` if input is empty.
    """
    if not value:
        return ""

    mapping = dict([(known, known) for known in known_list])

    if rename_mapping:
        mapping.update(rename_mapping)

    for alias, standard in mapping.items():
        if alias.lower() in value.lower():
            value = re.sub(alias, standard, value, flags=re.IGNORECASE)

    if style == 1:
        value = value.replace(" ", ".")
    elif style == 2:
        # Use space as separator
        value = value.replace(".", " ")
        # Handle audio channel
        channels = ["2.0", "5.1", "7.1"]
        dv_profils = ["7.6", "8.1", "8.4"]
        for channel in channels + dv_profils:
            value = value.replace(channel.replace(".", " "), channel)
    return value


def normalize_illegal_chars(text: str) -> str:
    """
    Remove or replace characters that are illegal in filenames.

    Removes: ``,`` ``?`` ``!`` ``\\`` ``/`` ``:``
    Replaces ``*`` with ``-``.

    Args:
        text: Raw string that may contain illegal filename characters.

    Returns:
        Cleaned string safe for use as a file or folder name.
    """
    illegal_chars = ",?!\\/:"
    for char in illegal_chars:
        text = text.replace(char, "")
    text = text.replace("*", "-")
    return text


def build_filename(
    style: int,
    show_name: str,
    season: str,
    episode: str,
    title: str,
    year: str = "",
    identifier: str = "",
    edition: str = "",
    resolution: str = "",
    codec: str = "",
    hdr: str = "",
    source: str = "",
    package: str = "",
    audio_codec: str = "",
    lang: str = "",
    extras: list[str] | None = None,
    release_group: str = "",
) -> str:
    """
    Build a standardized filename from components.

    **Style 1** (dot-separated):
        ``Show.Name.S01E01.{id}.Title.1080p.HEVC.DV.WEB-DL.TrueHD.Atmos.7.1-GROUP``

    **Style 2** (space-separated, metadata in brackets):
        ``Show Name S01E01 {id} - Title [1080p][HEVC][DV][WEB-DL][TrueHD Atmos 7.1]-GROUP``

    Empty/optional fields are silently omitted.

    Args:
        style: 1 for dot-separated, 2 for space-separated with brackets.
        show_name: Show or movie name.
        season: Season number (zero-padded, e.g., ``"01"``).
        episode: Episode number (zero-padded, e.g., ``"10"``).
        title: Episode or movie title.
        year: Release year (movies only).
        identifier: IMDb/TMDB identifier in braces (e.g., ``"{imdb-tt1234567}"``).
        edition: Edition label (e.g., ``"Director's Cut"``).
        resolution: Video resolution (e.g., ``"1080p"``).
        codec: Video codec (e.g., ``"HEVC"``).
        hdr: HDR format (e.g., ``"DV"``, ``"HDR"``).
        source: Source type (e.g., ``"WEB-DL"``).
        package: Release package (e.g., ``"REPACK"``).
        audio_codec: Audio codec with channels (e.g., ``"TrueHD.Atmos.7.1"``).
        lang: Language code (e.g., ``"eng"``).
        extras: Additional tags (e.g., ``["IMAX.Enhanced"]``).
        release_group: Release group name (e.g., ``"RARBG"``).

    Returns:
        Formatted filename string (without extension).

    Raises:
        ValueError: If ``style`` is not 1 or 2.
    """
    metas = [
        format_resolution(resolution),
        format_known(source, SOURCES, SOURCE_RENAME_MAPPINGS, style=style),
        format_known(package, PACKAGE, style=style),
        format_known(codec, CODECS, style=style),
        format_known(hdr, HDR, HDR_RENAME_MAPPING, style=style),
        format_known(audio_codec, AUDIO_CODECS, style=style),
        format_known(lang, LANGUAGES, style=style),
    ]
    if extras:
        for extra in extras:
            metas.append(format_known(extra, EXTRA, style=style))
    metas = [p for p in metas if p]

    if style == 1:
        parts = [format_title(show_name, style)]
        if season and episode:
            # show
            parts.append(f"S{season}E{episode}")
            if identifier:
                parts.append(identifier)
            if title:
                parts.append(format_title(title, style))
        else:
            # movie
            parts.append(year)
            # Build parts list (skip empty parts)

        # Join with dots
        filename = ".".join(parts + metas)
    elif style == 2:
        filename = format_title(show_name, 2)
        if season and episode:
            # show
            filename += f" S{season}E{episode}"
            if identifier:
                filename += f" {identifier}"
            filename += " - "
            if title:
                filename += f"{format_title(title, 2)}"
        else:
            # movie
            if year:
                filename += f" ({year})"
            if identifier:
                filename += f" {identifier}"
            filename += " - "
            if edition:
                filename += f"{edition.replace('.', ' ')} "

        if metas:
            filename += f"{''.join(f'[{part}]' for part in metas)}"
    else:
        raise ValueError("Unknown style")

    # Add release group if present
    if release_group:
        filename = f"{filename}-{release_group}"

    return normalize_illegal_chars(filename)
