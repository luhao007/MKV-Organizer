"""Fetch episode names from The Movie Database (TMDB)."""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Final, Optional

import httpx

from config import EPISODE_NAME_FILE
from models import FileDefinition, FileOrganization
from utils import get_logger

logger = get_logger(__name__)

# TMDB API v3 endpoint
TMDB_API_BASE: Final[str] = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE: Final[str] = "https://image.tmdb.org/p/original/"


def _get_api_key() -> str:
    """Read TMDB API key from tmdb-api.txt."""
    api_key_path = Path(__file__).parent / "tmdb-api.txt"
    if not api_key_path.exists():
        raise FileNotFoundError("TMDB API key file not found: tmdb-api.txt")

    api_key = api_key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError("TMDB API key is empty in tmdb-api.txt")

    return api_key


def _search_show(api_key: str, show_name: str) -> Optional[dict[str, str | int]]:
    """Search for a TV show by name on TMDB."""
    url = f"{TMDB_API_BASE}/search/tv"
    params = {"api_key": api_key, "query": show_name}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("results"):
                # Return the first result with highest popularity
                results = data["results"]
                best = max(results, key=lambda x: x.get("popularity", 0))
                logger.info(f"Found TMDB show: {best['name']} (id: {best['id']})")
                return best

            logger.warning(f"No TMDB results for show name: '{show_name}'")
            return None

    except httpx.HTTPError as e:
        logger.error(f"HTTP error searching TMDB for '{show_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Error searching TMDB for '{show_name}': {e}")
        return None


def _get_season_episodes(
    api_key: str, tmdb_show_id: int, season_number: int
) -> Optional[list[dict[str, Any]]]:
    """Get all episodes for a specific season from TMDB."""
    url = f"{TMDB_API_BASE}/tv/{tmdb_show_id}/season/{season_number}"
    params = {"api_key": api_key}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            episodes = data.get("episodes", [])
            logger.info(f"Found {len(episodes)} episodes for season {season_number}")
            return episodes

    except httpx.HTTPError as e:
        logger.error(
            f"HTTP error fetching season {season_number} from TMDB (show id:"
            f" {tmdb_show_id}): {e}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Error fetching season {season_number} from TMDB (show id:"
            f" {tmdb_show_id}): {e}"
        )
        return None


def _fetch_seasons_for_episodes(
    api_key: str,
    tmdb_show_id: int,
    seasons_needed: set[int],
) -> dict[int, list[dict[str, Any]]]:
    """Fetch full season data for all requested seasons of a show.

    One API call per unique season number.  Returns episode dicts that can be
    looked up by ``episode_number`` later.

    Args:
        api_key: TMDB API key.
        tmdb_show_id: TMDB show ID.
        seasons_needed: Set of season numbers to fetch (as integers).

    Returns:
        Dict mapping ``season_number -> list[episode_dict]`` for successfully
        fetched seasons.
    """
    if not seasons_needed:
        return {}

    # Fetch each needed season's episodes (one API call per unique season)
    seasons_cache: dict[int, list[dict[str, Any]]] = {}
    for season_num in sorted(seasons_needed):
        episodes = _get_season_episodes(api_key, tmdb_show_id, season_num)
        if episodes:
            logger.info(
                f"Fetched season {season_num} ({len(episodes)} eps) "
                f"for TMDB show id {tmdb_show_id}"
            )
            seasons_cache[season_num] = episodes
        else:
            logger.warning(f"Failed to fetch season {season_num} from TMDB")

    return seasons_cache


def fetch_episode_name(
    show_name: str,
    season: str,
    episode: str,
) -> Optional[str]:
    """
    Fetch the official episode name from TMDB.

    Args:
        show_name: The name of the TV series.
        season: Season number (e.g., "1", "01").
        episode: Episode number (e.g., "1", "01").

    Returns:
        The episode name if found, otherwise None.
    """
    # Parse season and episode numbers
    try:
        season_num = int(season)
        episode_num = int(episode)
    except ValueError:
        logger.error(f"Invalid season/episode format: S{season}E{episode}")
        return None

    api_key = _get_api_key()

    # Search for the show
    show_data = _search_show(api_key, show_name)
    if not show_data:
        return None

    tmdb_show_id = int(show_data["id"])

    # Get episodes for this season
    episodes = _get_season_episodes(api_key, tmdb_show_id, season_num)
    if not episodes:
        return None

    # Find the matching episode by episode number
    for ep in episodes:
        ep_number = int(ep.get("episode_number", 0))
        if ep_number == episode_num:
            ep_name = ep.get("name", "")
            if ep_name:
                logger.info(
                    f"Found TMDB episode name: S{season_num:02d}E{episode_num:02d} -"
                    f" {ep_name}"
                )
                return ep_name

    logger.warning(
        f"No TMDB episode found for S{season_num:02d}E{episode_num:02d} "
        f"in show '{show_name}' (TMDB id: {tmdb_show_id})"
    )
    return None


def fetch_episode_names_batch(
    organized: FileOrganization, override_show_name: Optional[str] = None
) -> bool:
    """Fetch episode names from TMDB and update FileOrganization in-place.

    Processes files grouped by show_name:
    1. For each unique show, searches TMDB once to get show ID and year
    2. Stores tmdb_id and year in all parsed info for that show
    3. Fetches all unique seasons for that show
    4. Updates episode title (and other fields) for each file

    This reduces API calls from O(N) (one per episode) to roughly
    O(unique_shows + sum_of_unique_seasons_per_show).

    Args:
        organized: FileOrganization dict (season -> episode -> ext -> FileDefinition).
                   Gets updated in-place with tmdb_id, year, and title.

    Returns:
        True if at least one episode name was fetched and updated, False otherwise.
    """
    if not organized:
        return False

    api_key = _get_api_key()
    updated_any = False

    # Group files by show_name
    # show_name -> (tmdb_show_id, year)
    shows_map: dict[str, tuple[int, str]] = {}
    #   show_name -> [FileDefinition, ...]
    show_files: dict[str, list[FileDefinition]] = {}

    for show_name, show_data in organized.items():
        seasons = show_data["seasons"]
        for season_files in seasons.values():
            for episode_files in season_files.values():
                for file_def in episode_files.values():
                    if file_def.is_subtitle:
                        continue

                    if override_show_name:
                        show_name = override_show_name
                    if show_name not in show_files:
                        show_files[show_name] = []
                    show_files[show_name].append(file_def)

    if not show_files:
        logger.warning("No video files found in organized data")
        return False

    # ── Step 1: Search TMDB for each unique show ───────────────────────
    for show_name in show_files:
        if show_name not in shows_map:
            show_data = _search_show(api_key, show_name)
            if show_data:
                tmdb_show_id = int(show_data["id"])
                # Extract year from first_air_date (format: YYYY-MM-DD)
                first_air_date = str(show_data.get("first_air_date", ""))
                year = first_air_date[:4] if first_air_date else ""
                shows_map[show_name] = (tmdb_show_id, year)
                logger.info(
                    f"Found TMDB show: {show_data['name']} "
                    f"(id: {tmdb_show_id}, year: {year})"
                )
            else:
                logger.warning(f"Could not find TMDB show for '{show_name}', skipping.")

    # ── Step 2: For each show, fetch needed seasons and update files ────
    for show_name, file_list in show_files.items():
        if show_name not in shows_map:
            continue

        tmdb_show_id, year = shows_map[show_name]

        # Collect unique season numbers needed for this show
        needed_seasons: set[int] = set()
        for file_def in file_list:
            try:
                needed_seasons.add(int(file_def.parsed.season))
            except ValueError:
                continue

        # Fetch all seasons at once
        seasons_cache = _fetch_seasons_for_episodes(
            api_key, tmdb_show_id, needed_seasons
        )

        # ── Step 3: Update each file's parsed info with TMDB data ────────
        for file_def in file_list:
            # Store TMDB ID and year in parsed info
            file_def.parsed.tmdb_id = tmdb_show_id
            if year:
                file_def.parsed.year = year

            try:
                season_num = int(file_def.parsed.season)
                episode_num = int(file_def.parsed.episode)
            except ValueError:
                logger.warning(
                    f"Invalid season/episode for {file_def.filename}: "
                    f"S{file_def.parsed.season}E{file_def.parsed.episode}"
                )
                continue

            episodes_for_season = seasons_cache.get(season_num)
            if not episodes_for_season:
                logger.debug(
                    f"No cached season data for S{file_def.parsed.season} "
                    f"of '{show_name}'"
                )
                continue

            # Find the matching episode and update title
            for ep in episodes_for_season:
                if int(ep.get("episode_number", 0)) == episode_num:
                    ep_name = ep.get("name", "")
                    if ep_name:
                        file_def.parsed.title = ep_name
                        logger.debug(
                            f"Updated S{season_num:02d}E{episode_num:02d} title:"
                            f" {ep_name}"
                        )
                        updated_any = True
                    break

    return updated_any


def search_show_by_name(show_name: str) -> Optional[dict[str, Any]]:
    """
    Search for a TV show and return basic info.

    Returns dict with 'id', 'name', 'overview', 'first_air_date' or None.
    """
    api_key = _get_api_key()
    show_data = _search_show(api_key, show_name)
    if not show_data:
        return None

    return {
        "id": int(show_data["id"]),
        "name": show_data["name"],
        "overview": show_data.get("overview", ""),
        "first_air_date": show_data.get("first_air_date", ""),
        "poster_path": (
            f"{TMDB_IMAGE_BASE}{show_data.get('poster_path', '')}"
            if show_data.get("poster_path")
            else ""
        ),
    }


def fetch_and_save_episode_names(
    organized: FileOrganization,
    folder: str,
    show_name: Optional[str] = None,
):
    """Fetch episode names from TMDB and update FileOrganization in-place.

    Also saves results to EPISODE_NAME_FILE for backward compatibility.

    Args:
        organized: The FileOrganization structure (season -> episode -> ext -> FileDefinition).
                   Gets updated in-place with parsed.title, parsed.tmdb_id, parsed.year.
        folder: Path to the target folder where EPISODE_NAME_FILE will be saved.
        show_name: Explicit show name filter. If provided, only fetches for that show.
                   If None, fetches for all shows in organized data.

    Returns:
        True if at least one episode name was fetched and saved, False otherwise.
    """
    logger.info("Fetching episode names from TMDB and updating parsed info...")

    # Call the batch function to fetch and update in-place
    success = fetch_episode_names_batch(organized, show_name)
    if not success:
        logger.error("No episode names found or updated from TMDB")
        return

    # Build EPISODE_NAME_FILE data from updated parsed info
    # Group by show_name and collect updated titles
    show_data: dict[str, dict[str, str]] = {}  # show_name -> {S#|E#: title}

    for show, data in organized.items():
        seasons = data["seasons"]
        for season, episodes in seasons.items():
            for episode, files in episodes.items():
                for file_def in files.values():
                    if file_def.is_subtitle:
                        continue

                    if show_name:
                        show = show_name
                    if show not in show_data:
                        show_data[show] = {}

                    key = f"{file_def.parsed.season.zfill(2)}|{file_def.parsed.episode.zfill(2)}"
                    if file_def.parsed.title and key not in show_data[show]:
                        show_data[show][key] = file_def.parsed.title

    if not show_data:
        logger.warning("No parsed episode data found to save")
        return

    # Save to EPISODE_NAME_FILE (one file per show if multiple shows exist)
    if len(show_data) == 1:
        # Single show: save to folder root
        show_name = next(iter(show_data))
        index_path = Path(folder) / EPISODE_NAME_FILE
        with index_path.open("w", encoding="utf-8") as f:
            f.write(show_name + "\n")
            for key in sorted(show_data[show_name].keys()):
                season, episode = key.split("|")
                title = show_data[show_name][key]
                f.write(f"{season}|{episode}|{title}\n")
        logger.info(f"Saved episode names to: {index_path}")
    else:
        # Multiple shows: save one file per show in subfolder
        for show, episodes in show_data.items():
            index_path = Path(folder) / f"episode_names_{show.replace('/', '_')}.txt"
            with index_path.open("w", encoding="utf-8") as f:
                f.write(show + "\n")
                for key in sorted(episodes.keys()):
                    season, episode = key.split("|")
                    title = episodes[key]
                    f.write(f"{season}|{episode}|{title}\n")
            logger.info(f"Saved episode names for '{show}' to: {index_path}")

    return


# ── Show Folder Episode Names Handling ────────────────────────────────────
def extract_id_from_folder_name(folder_path: str) -> Optional[tuple[str, str]]:
    """
    Extract IMDB or TMDB ID from folder name.

    Looks for patterns like:
    - "Series Name {imdb-tt1234567}"
    - "Series Name {tmdb-123456}"

    Returns:
        Tuple of (id_type, id_value) where id_type is "imdb" or "tmdb",
        or None if no ID found.
    """
    folder_name = Path(folder_path).name

    # Look for {imdb-xxxxx} or {tmdb-xxxxx}
    imdb_match = re.search(r"\{imdb-([^\}]+)\}", folder_name)
    if imdb_match:
        return ("imdb", imdb_match.group(1))

    tmdb_match = re.search(r"\{tmdb-([^\}]+)\}", folder_name)
    if tmdb_match:
        return ("tmdb", tmdb_match.group(1))

    return None


def parse_tvshow_nfo(nfo_path: str) -> Optional[dict[str, str]]:
    """
    Parse tvshow.nfo XML file to extract IDs.

    Returns:
        Dict with 'imdb_id' and/or 'tmdb_id' keys, or None if parsing fails.
    """
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        result: dict[str, str] = {}

        # Try to find imdb_id
        imdb_elem = root.find("imdb_id")
        if imdb_elem is not None and imdb_elem.text:
            result["imdb_id"] = imdb_elem.text

        # Try to find tmdbid
        tmdb_elem = root.find("tmdbid")
        if tmdb_elem is not None and tmdb_elem.text:
            result["tmdb_id"] = tmdb_elem.text

        title_elem = root.find("originaltitle")
        if title_elem is not None and title_elem.text:
            result["original_title"] = title_elem.text

        year_elem = root.find("year")
        if year_elem is not None and year_elem.text:
            result["year"] = year_elem.text

        if result:
            logger.info(f"Parsed tvshow.nfo: {result}")
            return result

        return None
    except Exception as e:
        logger.error(f"Error parsing tvshow.nfo: {e}")
        return None


def parse_movie_info(nfo_path: str) -> Optional[dict[str, str]]:
    """
    Parse movie info XML file to extract IDs.

    Returns:
        Dict with 'imdb_id' and/or 'tmdb_id' keys, or None if parsing fails.
    """
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        result: dict[str, str] = {}

        # Try to find imdb_id
        imdb_elem = root.find("imdbid")
        if imdb_elem is not None and imdb_elem.text:
            result["imdb_id"] = imdb_elem.text

        # Try to find tmdbid
        tmdb_elem = root.find("tmdbid")
        if tmdb_elem is not None and tmdb_elem.text:
            result["tmdb_id"] = tmdb_elem.text

        title_elem = root.find("originaltitle")
        if title_elem is not None and title_elem.text:
            result["original_title"] = title_elem.text

        year_elem = root.find("year")
        if year_elem is not None and year_elem.text:
            result["year"] = year_elem.text

        if result:
            logger.info(f"Parsed movie info: {result}")
            return result

        return None
    except Exception as e:
        logger.error(f"Error parsing movie info: {e}")
        return None


def _get_show_info_by_tmdb_id(
    api_key: str, tmdb_show_id: int
) -> Optional[dict[str, Any]]:
    """Get show info from TMDB using direct TMDB ID."""
    url = f"{TMDB_API_BASE}/tv/{tmdb_show_id}"
    params = {"api_key": api_key}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(
                f"Found TMDB show: {data.get('name', 'Unknown')} (id: {tmdb_show_id})"
            )
            return data
    except Exception as e:
        logger.error(f"Error fetching show info for TMDB ID {tmdb_show_id}: {e}")
        return None


def _get_show_info_by_imdb_id(api_key: str, imdb_id: str) -> Optional[dict[str, Any]]:
    """Get show info from TMDB using IMDB ID."""
    url = f"{TMDB_API_BASE}/find/{imdb_id}"
    params = {"api_key": api_key, "external_source": "imdb_id"}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Find the TV show result
            tv_results = data.get("tv_results", [])
            if tv_results:
                show = tv_results[0]
                logger.info(
                    f"Found TMDB show via IMDB: {show.get('name', 'Unknown')} (id:"
                    f" {show['id']})"
                )
                return show

            logger.warning(f"No TMDB show found for IMDB ID: {imdb_id}")
            return None
    except Exception as e:
        logger.error(f"Error fetching show info for IMDB ID {imdb_id}: {e}")
        return None


def fetch_title_by_tmdb_id(api_key: str, tmdb_show_id: int) -> Optional[str]:
    """Fetch show title from TMDB using TMDB ID."""
    show_info = _get_show_info_by_tmdb_id(api_key, tmdb_show_id)
    if show_info:
        return show_info.get("name")
    return None


def fetch_title_and_ids_for_show(
    show_folder: str, organized: FileOrganization
) -> Optional[tuple[str, str, str]]:
    """
    Fetch show title and IMDB ID and TMDB ID for a show folder.

    Returns:
        Tuple of (show_title, imdb_id, tmdb_id) if found, otherwise None.
    """
    if not organized:
        return None

    api_key = _get_api_key()

    # Get show name from organized dict
    show_names = list(organized.keys())
    if not show_names:
        logger.warning("No shows found in organized data")
        return None

    for show_name, show_data in organized.items():
        logger.info(f"Fetching show info for: {show_name}")

        imdb_id = None
        tmdb_id = None
        title = None
        year = None

        tvshow_nfo_path = Path(show_folder) / "tvshow.nfo"
        movie_nfo_path = Path(show_folder) / "movie.nfo"

        nfo_data = None
        if os.path.exists(tvshow_nfo_path):
            nfo_data = parse_tvshow_nfo(str(tvshow_nfo_path))
        elif os.path.exists(movie_nfo_path):
            nfo_data = parse_movie_info(str(movie_nfo_path))

        if nfo_data:
            title = nfo_data["original_title"]
            tmdb_id = nfo_data["tmdb_id"]
            imdb_id = nfo_data["imdb_id"]
            year = nfo_data["year"]

        else:
            id_info = extract_id_from_folder_name(show_folder)
            if id_info:
                id_type, id_value = id_info
                logger.info(f"Found {id_type} ID in folder name: {id_value}")

                show_info = None
                if id_type == "tmdb":
                    show_info = _get_show_info_by_tmdb_id(api_key, int(id_value))
                    tmdb_id = id_value

                elif id_type == "imdb":
                    show_info = _get_show_info_by_imdb_id(api_key, id_value)

                if show_info:
                    tmdb_id = show_info["id"]
                    show_name = show_info.get("name", show_name)
                    imdb_id = show_info.get("imdb_id", None)
                    year = show_info.get("year", None)

        if (imdb_id or tmdb_id) and title:
            for seasons in show_data["seasons"].values():
                for episodes in seasons.values():
                    for file_def in episodes.values():
                        if imdb_id:
                            file_def.parsed.imdb_id = imdb_id
                        if tmdb_id:
                            file_def.parsed.tmdb_id = int(tmdb_id)
                        file_def.parsed.show_name = show_name
                        if os.path.exists(movie_nfo_path):
                            file_def.parsed.show_name = title
                        else:
                            file_def.parsed.title = title
                        if year:
                            file_def.parsed.year = year


def fetch_episode_names_for_show(
    show_folder: str,
    organized: FileOrganization,
) -> bool:
    """
    Fetch and apply episode names for a single show folder.

    Handles multiple shows under the same parent folder by looking for IDs:
    1. First checks folder name for {imdb-xxxxx} or {tmdb-xxxx}
    2. Then checks tvshow.nfo file
    3. Finally uses show name from organized dict

    Args:
        show_folder: Path to the show folder
        organized: FileOrganization dict for this show folder

    Returns:
        True if episode names were fetched and updated, False otherwise.
    """
    if not organized:
        return False

    try:
        api_key = _get_api_key()
    except Exception as e:
        logger.error(f"Cannot fetch episode names: {e}")
        return False

    # Get show name from organized dict
    show_names = list(organized.keys())
    if not show_names:
        logger.warning("No shows found in organized data")
        return False

    show_name = show_names[0]
    logger.info(f"Fetching episodes for show: {show_name}")

    # ── Step 1: Try to get TMDB ID from folder name or tvshow.nfo ────
    tmdb_show_id = None
    year = ""

    # Check folder name first
    id_info = extract_id_from_folder_name(show_folder)
    if id_info:
        id_type, id_value = id_info
        logger.info(f"Found {id_type} ID in folder name: {id_value}")

        if id_type == "tmdb":
            try:
                tmdb_show_id = int(id_value)
            except ValueError:
                logger.warning(f"Invalid TMDB ID format: {id_value}")
        elif id_type == "imdb":
            # Convert IMDB ID to TMDB ID
            show_info = _get_show_info_by_imdb_id(api_key, id_value)
            if show_info:
                tmdb_show_id = int(show_info["id"])
                year = str(show_info.get("first_air_date", ""))[:4]
                fetched_show_name = show_info.get("name", show_name)
                if fetched_show_name != show_name:
                    logger.info(f"Need to update show name to {fetched_show_name}")
                    organized[fetched_show_name] = organized.pop(show_name)
                    show_name = fetched_show_name

    # Check tvshow.nfo if no ID found yet
    if not tmdb_show_id:
        nfo_path = Path(show_folder) / "tvshow.nfo"
        if nfo_path.exists():
            nfo_data = parse_tvshow_nfo(str(nfo_path))
            if nfo_data:
                if "tmdb_id" in nfo_data:
                    try:
                        tmdb_show_id = int(nfo_data["tmdb_id"])
                    except ValueError:
                        logger.warning(f"Invalid TMDB ID in nfo: {nfo_data['tmdb_id']}")
                elif "imdb_id" in nfo_data:
                    # Convert IMDB ID to TMDB ID
                    show_info = _get_show_info_by_imdb_id(api_key, nfo_data["imdb_id"])
                    if show_info:
                        tmdb_show_id = int(show_info["id"])
                        year = str(show_info.get("first_air_date", ""))[:4]

    # ── Step 2: If still no ID, search by show name ────────────────────
    if not tmdb_show_id:
        logger.info(
            f"No ID found in folder or nfo, searching by show name: {show_name}"
        )
        show_info = _search_show(api_key, show_name)
        if show_info:
            tmdb_show_id = int(show_info["id"])
            year = str(show_info.get("first_air_date", ""))[:4]
        else:
            logger.error(f"Could not find TMDB show for: {show_name}")
            return False

    # ── Step 3: Get show info if not already obtained ────────────────
    if not year:
        show_info = _get_show_info_by_tmdb_id(api_key, tmdb_show_id)
        if show_info:
            year = str(show_info.get("first_air_date", ""))[:4]

    # ── Step 4: Fetch all needed seasons and update organized dict ────
    # Collect unique season numbers needed
    needed_seasons: set[int] = set()
    for season_files in organized[show_name]["seasons"].values():
        for episode_files in season_files.values():
            for file_def in episode_files.values():
                if not file_def.is_subtitle:
                    try:
                        needed_seasons.add(int(file_def.parsed.season))
                    except ValueError:
                        pass

    # Fetch all seasons
    seasons_cache = _fetch_seasons_for_episodes(api_key, tmdb_show_id, needed_seasons)

    # Update organized dict with fetched episode names
    updated_any = False
    for season_files in organized[show_name]["seasons"].values():
        for episode_files in season_files.values():
            for file_def in episode_files.values():
                if file_def.is_subtitle:
                    continue

                try:
                    season_num = int(file_def.parsed.season)
                    episode_num = int(file_def.parsed.episode)
                except ValueError:
                    continue

                episodes_for_season = seasons_cache.get(season_num)
                if not episodes_for_season:
                    continue

                # Find matching episode
                for ep in episodes_for_season:
                    if int(ep.get("episode_number", 0)) == episode_num:
                        ep_name = ep.get("name", "")
                        if ep_name:
                            file_def.parsed.title = ep_name
                            file_def.parsed.tmdb_id = tmdb_show_id
                            if year:
                                file_def.parsed.year = year
                            logger.debug(
                                f"Updated S{season_num:02d}E{episode_num:02d} title:"
                                f" {ep_name}"
                            )
                            updated_any = True
                        break

                if file_def.parsed.show_name != show_name:
                    file_def.parsed.show_name = show_name

    # ── Step 5: Save episode_names.txt ────────────────────────────────
    if updated_any:
        index_path = Path(show_folder) / EPISODE_NAME_FILE
        try:
            with index_path.open("w", encoding="utf-8") as f:
                f.write(show_name + "\n")

                # Collect all episode titles
                episodes_map: dict[str, str] = {}
                for season_files in organized[show_name]["seasons"].values():
                    for episode_files in season_files.values():
                        for file_def in episode_files.values():
                            if not file_def.is_subtitle and file_def.parsed.title:
                                key = f"{file_def.parsed.season.zfill(2)}|{file_def.parsed.episode.zfill(2)}"
                                if key not in episodes_map:
                                    episodes_map[key] = file_def.parsed.title

                # Write sorted episode list
                for key in sorted(episodes_map.keys()):
                    season, episode = key.split("|")
                    f.write(f"{season}|{episode}|{episodes_map[key]}\n")

            logger.info(f"Saved episode names to: {index_path}")
        except Exception as e:
            logger.error(f"Error saving episode_names.txt: {e}")

    return updated_any
