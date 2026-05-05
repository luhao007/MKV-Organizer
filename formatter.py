"""Format and capitalize video filenames according to naming conventions."""

from typing import Iterable

from config import (
    KNOWN_AUDIO_CODECS,
    KNOWN_CODECS,
    KNOWN_LANGUAGES,
    KNOWN_SOURCES,
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


def format_title(title: str) -> str:
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

    # Remove commas (they're noise in filenames)
    title = title.replace(",", "")

    # Split on separators while preserving the structure
    tokens = [t for t in WORD_SPLIT_PATTERN.split(title) if t]

    # Capitalize each token
    capitalized_tokens = [
        capitalize_word(token, is_first=(i == 0)) for i, token in enumerate(tokens)
    ]

    return ".".join(capitalized_tokens)


def format_resolution(resolution: str) -> str:
    """Format resolution string in lowercase. E.g., '1080p'"""
    return resolution.lower() if resolution else ""


def format_known(value: str, known_list: Iterable[str]) -> str:
    """Format a value by matching it against a known list (case-insensitive)."""
    if not value:
        return ""

    for known in known_list:
        if value.lower() == known.lower():
            return known

    return value


def format_show_name(show_name: str) -> str:
    """Format show/series name using title case."""
    return format_title(show_name)


def build_filename(
    show_name: str,
    season: str,
    episode: str,
    title: str,
    resolution: str = "",
    codec: str = "",
    audio_codec: str = "",
    lang: str = "",
    source: str = "",
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
    # Build parts list (skip empty parts)
    parts = [
        format_show_name(show_name),
        f"S{season}E{episode}",
        format_title(title),
        format_resolution(resolution),
        format_known(source, KNOWN_SOURCES),
        format_known(codec, KNOWN_CODECS),
        format_known(audio_codec, KNOWN_AUDIO_CODECS),
        format_known(lang, KNOWN_LANGUAGES),
        extra,
    ]
    parts = [p for p in parts if p]

    # Join with dots
    filename = ".".join(parts)

    # Add release group if present
    if release_group:
        filename = f"{filename}-{release_group}"

    return filename
