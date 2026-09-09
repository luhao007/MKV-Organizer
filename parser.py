"""Parse and extract information from video filenames."""

import re
from collections import Counter
from pathlib import Path
from typing import Final, Iterable, Optional

from config import (
    AUDIO_CODECS,
    CODECS,
    EDITION_PATTERN,
    EDITIONS,
    EXTRA,
    HDR,
    IDENTIFIER_PATTERN,
    LANGUAGES,
    PACKAGE,
    RELEASE_GROUP_PATTERN,
    RESOLUTION_PATTERN,
    SEASON_EPISODE_PATTERN,
    SOURCES,
    SUBTITLE_FORMATS,
    TITLE_METADATA_SUFFIX_PATTERN,
)
from models import ParsedFileInfo
from utils import get_logger

logger = get_logger(__name__)

# ============================================================================
# Anime-specific constants
#
# Anime files usually have *no* season/episode marker (e.g. no "S01E05").  The
# folder is considered a single season and the episode number is just a plain
# (often zero-padded, e.g. "0123") number embedded in the filename:
#
#     "Detective Conan - 0123 [1080p][Multiple Subtitle][FDB1F25C].mkv"
#
# Because a bare number is ambiguous (it could be a resolution, a channel
# count, a CRC ...), we detect it using the "consecutive number pattern" of
# all files living in the same folder (see detect_anime_episode_numbers).
# ============================================================================

# Anime episode numbers are formatted as zero-padded 4-digit numbers (0001...).
ANIME_EPISODE_WIDTH: Final = 4

# A standalone run of digits that is NOT glued to letters (so "1080p", "H264"
# or "FDB1F25C" are ignored, while "0123" / "5" / "1" are kept as candidates).
_NUMERIC_TOKEN_RE: Final = re.compile(r"(?<![A-Za-z0-9])(?P<num>\d+)(?![A-Za-z0-9])")


# Known metadata tokens used to tell "release tags" apart from noise brackets.
# We compare bracket contents by collapsing every separator (. _ - space) to a
# single space so that "[TrueHD Atmos 7.1]" == "TrueHD.Atmos.7.1" etc.
def _norm_sep(text: str) -> str:
    return re.sub(r"[._\-\s]+", " ", text.strip()).strip().lower()


_KNOWN_META_TOKENS: Final = tuple(
    dict.fromkeys(
        token
        for group in (
            CODECS,
            SOURCES,
            PACKAGE,
            HDR,
            AUDIO_CODECS,
            LANGUAGES,
            EDITIONS,
            EXTRA,
        )
        for token in group
    )
)
_META_ALTS: Final = tuple(re.escape(_norm_sep(token)) for token in _KNOWN_META_TOKENS)
# A bracket group is "metadata" when it is a sequence of one or more known
# metadata tokens (e.g. "[DV HDR10]", "[DDP 5.1]") or a resolution ("[1080p]").
_KNOWN_META_SEQ_RE: Final = re.compile(
    rf"^(?:{'|'.join(_META_ALTS)})(?:\s+(?:{'|'.join(_META_ALTS)}))*$"
)
_RESOLUTION_TAG_RE: Final = re.compile(r"^\d{3,4}p$")


# ============================================================================
# Private Utility Functions
# ============================================================================


def _extract_through_pattern_base(
    pattern: re.Pattern[str], text: str
) -> tuple[str, str]:
    """Extract a value using the provided regex pattern."""
    match = pattern.search(text)
    if match:
        res = match.group(1)
        left = text[: match.start()].strip(" ._-")
        right = text[match.end() :].strip(" ._-")
        remaining = ".".join([left, right]) if left and right else left or right
        return res, remaining
    return "", text


def _extract_from_list_single(lists: Iterable[str], text: str) -> tuple[str, str]:
    """Extract single value from known lists."""
    pattern_str = "|".join(sorted(map(re.escape, lists), key=len, reverse=True))
    pattern = re.compile(rf"(?i)\b(?P<value>{pattern_str})\b")
    return _extract_through_pattern_base(pattern, text)


def _extract_from_list_repeated(
    lists: Iterable[str], text: str
) -> tuple[list[str], str]:
    """Extract multiple values from known lists."""
    pattern_str = "|".join(sorted(map(re.escape, lists), key=len, reverse=True))
    pattern = re.compile(rf"(?i)\b(?P<value>{pattern_str})\b")

    extracted_list: list[str] = []
    remaining = text
    extracted, remaining = _extract_through_pattern_base(pattern, remaining)
    while extracted:
        if extracted not in extracted_list:
            extracted_list.append(extracted)
        extracted, remaining = _extract_through_pattern_base(pattern, remaining)

    return extracted_list, remaining


# ============================================================================
# Public API
# ============================================================================


def normalize_separators(text: str) -> str:
    """
    Normalize common filename separators to spaces.

    Keeps other punctuation (parentheses, commas) intact.
    E.g., "Better.Call.Saul" -> "Better Call Saul"
    """
    # Replace dots and underscores with spaces
    text = text.replace(".", " ").replace("_", " ")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip("- (")


def strip_noise_prefix(stem: str) -> str:
    """Remove common noise prefixes like 'Rename:' from filenames."""
    return re.sub(
        r"^(?:rename|renamed|download|new)\s*:\s*", "", stem, flags=re.IGNORECASE
    ).strip()


def strip_trailing_metadata(text: str) -> str:
    """Remove trailing metadata tags from extracted titles."""
    if not text:
        return ""

    stripped = text.strip(" ._- ")
    match = TITLE_METADATA_SUFFIX_PATTERN.match(stripped)
    if match:
        return match.group("title").strip(" ._- ")

    return stripped


def extract_release_group(stem: str) -> Optional[str]:
    """
    Extract release group from filename.

    Release groups are typically at the end after a hyphen.
    E.g., "Better.Call.Saul.S01E10.1080p.x265-RARBG" -> "RARBG"
    """
    match = RELEASE_GROUP_PATTERN.search(stem)
    if match:
        return match.group(1)
    return None


def extract_season_episode(text: str) -> tuple[str, str, str, str]:
    """
    Extract season and episode numbers.

    Returns:
        Tuple of (season_str, episode_str, left_text, right_text)
        Season/episode are zero-padded to 2 digits if found.
    """
    match = SEASON_EPISODE_PATTERN.search(text)
    if not match:
        logger.error(f"No season/episode pattern found in filename: {text}")
        raise ValueError("No season/episode pattern found")

    season = match.group("season_s") or match.group("season_x")
    episode = match.group("episode_s") or match.group("episode_x")
    if not season or not episode:
        raise ValueError("No season/episode pattern found")

    left = text[: match.start()]
    right = text[match.end() :]

    return season.zfill(2), episode.zfill(2), left, right


def extract_movie_name(text: str) -> tuple[tuple[str, str], str]:
    """
    Extract movie name and year.

    E.g., "Inception.2010.1080p.x265" -> ("Inception", "2010")
    """
    # The assumption is that all the filename is starting with $MOVIE_NAME.$YEAR.$EXTRA
    # Search the year pattern
    match = re.search(
        r"(?i)(?<!\d)[\.\(]*(19\d{2}|20\d{2})[\.\)]*(?!\d)", text, flags=re.IGNORECASE
    )
    if match:
        year = match.group(1)
        left = text[: match.start()]
        right = text[match.end() :]
        return (left.strip(" ._-"), year), right
    return (text, ""), ""


def extract_resolution(text: str) -> Optional[str]:
    """Extract resolution (e.g., 1080p, 720p)."""
    match = RESOLUTION_PATTERN.search(text)
    if match:
        return match.group("res").lower()
    return None


# ============================================================================
# Anime parsing helpers
# ============================================================================


def _flatten_filename(filename: str) -> str:
    """Flatten a filename into the parser's internal dot-separated form."""
    fn = filename.replace(" ", ".")
    fn = fn.replace("[", "").replace("]-", "-").replace("]", ".")
    fn = fn.replace("..", ".")
    return fn


def _is_known_metadata_bracket(content: str) -> bool:
    """Return True if a bracket group looks like release metadata (not noise).

    Used only in anime mode, where trailing square brackets after the episode
    number usually carry either real metadata ("[1080p]", "[HEVC]") or pure
    noise ("[Multiple Subtitle]", "[FDB1F25C]").  We keep the metadata and drop
    the noise so it never leaks into the episode title.
    """
    norm = _norm_sep(content)
    if not norm:
        return False
    if _RESOLUTION_TAG_RE.match(norm):
        return True
    return bool(_KNOWN_META_SEQ_RE.fullmatch(norm))


def _strip_noise_brackets(text: str) -> str:
    """Remove square-bracket groups that are not recognized metadata tags."""

    def _repl(match: re.Match[str]) -> str:
        content = match.group(0)[1:-1]
        return match.group(0) if _is_known_metadata_bracket(content) else ""

    return re.sub(r"\[[^\]]*\]", _repl, text)


def _strip_metadata_parentheses(text: str) -> str:
    """Handle parentheses groups the same way as bracket noise in anime mode.

    Some anime releases wrap the resolution hint in parentheses
    (``"[Group] Show - 0123 (1080p) [hash].mkv"``).  Parentheses that only wrap
    metadata are *unwrapped* (kept, so the resolution/codec is still parsed);
    all other parenthesized tags (``(Special)``, ``(OVA)`` ...) are treated as
    release noise and dropped, consistent with the "unknown bracket tags are
    noise" rule.
    """

    def _repl(match: re.Match[str]) -> str:
        content = match.group(0)[1:-1]
        if not content.strip():
            return ""
        return content if _is_known_metadata_bracket(content) else ""

    return re.sub(r"\([^()]*\)", _repl, text)


def _anime_candidate_tokens(stem: str) -> list[tuple[int, str]]:
    """Return (value, raw) candidate episode numbers found in an anime stem.

    Square-bracket groups (release tags/hashes) are ignored entirely and only
    standalone runs of digits count (e.g. "1080p" / "H264" do not match).
    Leading zeros of the first occurrence are preserved in the raw string.
    """
    cleaned = re.sub(r"\[[^\]]*\]", "", stem)
    seen: dict[int, str] = {}
    for match in _NUMERIC_TOKEN_RE.finditer(cleaned):
        raw = match.group("num")
        value = int(raw)
        if value not in seen:
            seen[value] = raw
    return list(seen.items())


def detect_anime_episode_numbers(filenames: Iterable[str]) -> dict[str, str]:
    """
    Detect the episode number for every anime file in one folder.

    Anime releases are "one season, consecutive numbers": each file contains
    its own absolute episode number (often zero-padded, e.g. ``0001``), and the
    numbers *increase* across the folder.  A plain number is ambiguous by
    itself (it could also be a channel count "5.1", a year, ...) but the real
    episode numbers are the only ones that are (almost) unique per file and
    span the folder as an incrementing range, while the other numbers stay
    constant and keep reappearing in file after file.

    Files that already contain an explicit ``SxxExx`` marker are skipped here.

    Args:
        filenames: All (video + subtitle) file names inside one folder.

    Returns:
        Mapping ``filename -> raw episode token`` for the files that could be
        detected.  Files that are ambiguous or have no number are omitted.
    """
    files = [f for f in filenames if f]

    # Skip files that already carry an explicit season/episode marker.
    candidates: dict[str, list[tuple[int, str]]] = {}
    for name in files:
        if SEASON_EPISODE_PATTERN.search(_flatten_filename(name)):
            continue
        stem = Path(name).stem if "." in name else name
        tokens = _anime_candidate_tokens(stem)
        if tokens:
            candidates[name] = tokens

    # How many distinct files contain each candidate value.
    frequency: Counter[int] = Counter()
    for tokens in candidates.values():
        for value, _ in tokens:
            frequency[value] += 1

    result: dict[str, str] = {}
    for name, tokens in candidates.items():
        # Real episode numbers are (almost) unique per file, so we pick the
        # candidate seen in the fewest files.  Ties are broken by preferring a
        # zero-padded token ("0123" over "5") then the longest one.
        def _sort_key(item: tuple[int, str]) -> tuple[int, int, int]:
            value, raw = item
            padded = 0 if (len(raw) > 1 and raw[0] == "0") else 1
            return (frequency[value], padded, -len(raw))

        best = min(tokens, key=_sort_key)
        result[name] = best[1]

    return result


def _pad_anime_episode(raw: str) -> str:
    """Normalize a raw anime episode number to the canonical 4-digit form."""
    return f"{int(raw):0{ANIME_EPISODE_WIDTH}d}"


def _build_anime_flattened(filename: str, ep_raw: str) -> Optional[str]:
    """
    Rewrite an anime filename into the normal flattened show form.

    The bare episode number is replaced by an ``S01E####`` marker (anime = one
    season) and non-metadata bracket noise is dropped, so the resulting string
    can be fed through the standard show-parsing pipeline:

        "Detective Conan - 0123 [1080p][FDB1F25C].mkv"
            -> "Detective.Conan.-.S01E0123.1080p.mkv"

    Returns None when the episode token can not be located (shouldn't happen
    when ``ep_raw`` came from detect_anime_episode_numbers).
    """
    path = Path(filename)
    ext = path.suffix
    base = path.name[: -len(ext)] if ext else path.name

    # Drop release-tag / hash brackets but keep real metadata brackets.  Also
    # drop parentheses that only wrap metadata (e.g. "(1080p)") so their empty
    # leftovers never leak into the episode title.
    base = _strip_noise_brackets(base)
    base = _strip_metadata_parentheses(base)
    flat = _flatten_filename(base)
    flat = flat.replace("()", "")

    # Locate the numeric token matching the requested episode number.
    target = int(ep_raw)
    chosen: Optional[re.Match[str]] = None
    for match in _NUMERIC_TOKEN_RE.finditer(flat):
        if int(match.group("num")) != target:
            continue
        chosen = match
        if match.group("num") == ep_raw:
            break  # exact (leading-zero preserved) match found
    if chosen is None:
        return None

    marker = f"S01E{_pad_anime_episode(ep_raw)}"
    new_flat = flat[: chosen.start()] + marker + flat[chosen.end() :]
    return new_flat + ext


def _parse_flattened(fn: str, original_filename: str, is_show: bool) -> ParsedFileInfo:
    """Parse an already-flattened filename (see parse_filename)."""
    path = Path(fn)
    stem = path.stem
    extension = path.suffix.lstrip(".").lower()

    # Special handling for thumbnail images (e.g., "Show.Name.S01E10-thumb.jpg")
    if extension == "jpg" and stem.lower().endswith("-thumb"):
        extension = "thumb.jpg"
        stem = stem[:-6]  # Remove '-thumb' from the stem for parsing

    # Remove common noise prefixes that are not part of the title
    stem = strip_noise_prefix(stem)

    if extension in SUBTITLE_FORMATS:
        # Extract language tags first (at the end)
        lang, stem = _extract_from_list_repeated(LANGUAGES, stem)
        lang = ".".join(lang)
    else:
        lang = ""

    # Then extract release group (usually at the end after a hyphen)
    release_group, stem = _extract_through_pattern_base(RELEASE_GROUP_PATTERN, stem)

    if is_show:
        # Extract season and episode
        season, episode, show_name, unparsed = extract_season_episode(stem)
        logger.debug(f"Found season: {season}, episode: {episode}")
        year = ""
    else:
        # Grab the year of a movie
        season, episode = "", ""
        (show_name, year), unparsed = extract_movie_name(stem)

    # Extract show name (everything before SxxEyy)
    show_name = normalize_separators(show_name)

    # The identifier may be written *after* the season/episode marker (style 1:
    # "Show.S01E01.{tmdb-123}.1080p.mkv") or right next to the show name
    # (style 2: "Show Name {tmdb-123} S01E01 ...").  Extract it from the
    # remainder first, then fall back to the show-name portion so a stale id
    # is never mistaken for part of the show name on a later re-parse / TMDB
    # lookup.
    identifier, unparsed = _extract_through_pattern_base(IDENTIFIER_PATTERN, unparsed)
    if not identifier:
        identifier, show_name = _extract_through_pattern_base(
            IDENTIFIER_PATTERN, show_name
        )
        show_name = normalize_separators(show_name)

    imdb_id = ""
    tmdb_id = ""
    if identifier.startswith("{imdb-"):
        imdb_id = identifier[6:-1]  # Extract IMDb ID from {imdb-tt1234567}
        tmdb_id = ""
    elif identifier.startswith("{tmdb-"):
        # Tolerate "{tmdb-30983}" (raw numeric) and "{tmdb-tv12345}" (prefixed).
        digits = re.search(r"\d+", identifier[6:-1])
        tmdb_id = digits.group() if digits else ""
        imdb_id = ""

    edition, unparsed = _extract_through_pattern_base(EDITION_PATTERN, unparsed)
    resolution, unparsed = _extract_through_pattern_base(RESOLUTION_PATTERN, unparsed)
    codec, unparsed = _extract_from_list_single(CODECS, unparsed)
    source, unparsed = _extract_from_list_single(SOURCES, unparsed)
    package, unparsed = _extract_from_list_repeated(PACKAGE, unparsed)
    package = ".".join(package)
    hdr, unparsed = _extract_from_list_repeated(HDR, unparsed)
    hdr = ".".join(hdr)
    audio_codecs, unparsed = _extract_from_list_repeated(AUDIO_CODECS, unparsed)
    extras, unparsed = _extract_from_list_repeated(EXTRA, unparsed)

    if extension not in SUBTITLE_FORMATS:
        lang, unparsed = _extract_from_list_repeated(LANGUAGES, unparsed)
        lang = ".".join(lang)

    # Extract title directly
    title = strip_trailing_metadata(unparsed)
    unparsed = unparsed.replace(title, "").strip(" ._-")
    title = normalize_separators(title)

    logger.debug(
        f"Extracted: show={show_name}, title={title}, resolution={resolution},"
        f" codec={codec}, source={source}, package={package}, hdr={hdr},"
        f" audio_codecs={audio_codecs}, lang={lang}, extras={extras},"
        f" extension={extension}, release_group={release_group}, edition={edition}"
    )

    return ParsedFileInfo(
        show_name=show_name,
        season=season,
        episode=episode,
        title=title,
        resolution=resolution,
        codec=codec,
        source=source,
        package=package,
        hdr=hdr,
        audio_codecs=audio_codecs,
        lang=lang,
        extras=extras,
        release_group=release_group or "",
        extension=extension,
        original_filename=original_filename,
        year=year,
        edition=edition,
        imdb_id=imdb_id,
        tmdb_id=int(tmdb_id) if tmdb_id else 0,
    )


def parse_filename(
    filename: str,
    is_show: bool = True,
    is_anime: bool = False,
    anime_episode: str = "",
) -> ParsedFileInfo:
    """
    Parse a video filename and extract structured information.

    Handles three main patterns:
    1. "Better.Call.Saul.S01E10.Marco.1080p.X265.1080p.x265-RARBG.mp4"
    2. "Air.Crash.Investigations.S01E01 Unlocking Disaster (United Airlines, Flight 811).avi"
    3. Anime (single season, no marker):
       "Detective Conan - 0123 [1080p][Multiple Subtitle][FDB1F25C].mkv"

    Args:
        filename: The video filename.
        is_show: Whether the file belongs to a TV show (season/episode present).
        is_anime: Treat the filename as anime. When the file has no explicit
            ``SxxExx`` marker it is parsed as a single-season episode whose
            number is the (usually zero-padded) number in the filename.
        anime_episode: The raw episode number detected by
            ``detect_anime_episode_numbers`` (folder-level consecutive-number
            detection).  Optional - when omitted a unique numeric token is
            used as a fallback.

    Returns:
        ParsedFileInfo with extracted show name, season, episode, title, etc.

    Raises:
        ValueError: If filename doesn't contain season/episode pattern (and is
            neither a movie, nor a parseable anime file).
    """
    logger.debug(f"Parsing filename: {filename}")
    fn = _flatten_filename(filename)

    if is_anime:
        ep = (anime_episode or "").strip()
        if not ep and not SEASON_EPISODE_PATTERN.search(fn):
            # Fallback: if only a single distinct numeric token exists, use it.
            stem = Path(filename).stem if "." in filename else filename
            tokens = _anime_candidate_tokens(stem)
            unique = {value for value, _ in tokens}
            if len(unique) == 1:
                ep = tokens[0][1]
        if ep:
            anime_fn = _build_anime_flattened(filename, ep)
            if anime_fn is not None:
                return _parse_flattened(anime_fn, filename, is_show=True)

    return _parse_flattened(fn, filename, is_show)
