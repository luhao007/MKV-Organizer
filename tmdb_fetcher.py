"""Fetch episode names from The Movie Database (TMDB)."""

from pathlib import Path
from typing import Any, Final, Optional

import httpx

from config import EPISODE_NAME_FILE
from models import FileOrganization
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


def fetch_episode_names_batch(parsed_episodes: list[dict[str, str]]) -> dict[str, str]:
    if not parsed_episodes:
        return {}

    results: dict[str, str] = {}
    api_key = _get_api_key()

    # ── Step 1: group episodes by show name ────────────────────────────
    shows_map: dict[str, int] = {}  # show_name -> tmdb_show_id
    for ep_info in parsed_episodes:
        show_name = ep_info["show_name"]
        if show_name not in shows_map:
            show_data = _search_show(api_key, show_name)
            if show_data:
                shows_map[show_name] = int(show_data["id"])
            else:
                logger.warning(f"Could not find TMDB show for '{show_name}', skipping.")

    # ── Step 2: for each show, fetch needed seasons once ───────────────
    # season_cache[tmdb_show_id][season_number] -> list[episode_dicts]
    season_cache: dict[int, dict[int, list[dict[str, Any]]]] = {}

    for show_name, tmdb_show_id in shows_map.items():
        # Collect unique season numbers needed for this show
        needed_seasons: set[int] = set()
        for ep_info in parsed_episodes:
            if ep_info["show_name"] == show_name:
                try:
                    needed_seasons.add(int(ep_info["season"]))
                except ValueError:
                    continue

        # Fetch each season once (cached per show)
        seasons_for_show = _fetch_seasons_for_episodes(
            api_key, tmdb_show_id, needed_seasons
        )
        season_cache[tmdb_show_id] = seasons_for_show

    # ── Step 3: look up each requested episode from cached data ────────
    for ep_info in parsed_episodes:
        show_name = ep_info["show_name"]
        tmdb_show_id = shows_map.get(show_name)
        if not tmdb_show_id:
            continue

        try:
            season_num = int(ep_info["season"])
            episode_num = int(ep_info["episode"])
        except ValueError:
            logger.warning(
                "Invalid season/episode in batch request:"
                f" S{ep_info['season']}E{ep_info['episode']}"
            )
            continue

        seasons_for_show = season_cache.get(tmdb_show_id, {})
        episodes_for_season = seasons_for_show.get(season_num)
        if not episodes_for_season:
            logger.warning(f"No cached data for S{ep_info['season']} of '{show_name}'")
            continue

        # Find the matching episode within this season's cache
        for ep in episodes_for_season:
            if int(ep.get("episode_number", 0)) == episode_num:
                ep_name = ep.get("name", "")
                if ep_name:
                    key = f"{ep_info['season']}|{ep_info['episode']}"
                    results[key] = ep_name
                    logger.info(
                        "Found TMDB episode name:"
                        f" S{season_num:02d}E{episode_num:02d} - {ep_name}"
                    )
                break

    return results


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
) -> bool:
    """
    Fetch episode names from TMDB and save to EPISODE_NAME_FILE.

    Args:
        organized: The FileOrganization structure (nested dict of season/episode/files).
        folder: Path to the target folder where the index file will be saved.
        show_name: Explicit show name. If None, auto-detects from organized data.

    Returns:
        True if at least one episode name was fetched and saved, False otherwise.
    """
    # Auto-detect show name if not provided
    if not show_name:
        show_names: set[str] = set()
        for season_files in organized.values():
            for episode_files in season_files.values():
                for file_def in episode_files.values():
                    if not file_def.is_subtitle and file_def.parsed.show_name:
                        show_names.add(file_def.parsed.show_name)

        if len(show_names) == 1:
            show_name = next(iter(show_names))
            logger.info(f"Auto-detected TMDB show name: {show_name}")
        elif len(show_names) > 1:
            logger.warning(
                f"Multiple show names detected: {show_names}. "
                "Using first one. Specify with --fetch-tmdb <SHOW_NAME>"
            )
            show_name = sorted(show_names)[0]
        else:
            logger.error("Cannot detect show name from filenames.")
            return False

    # Collect unique season/episode combinations from organized data
    episodes_to_fetch: dict[str, dict[str, str]] = {}
    for season, episodes in organized.items():
        for episode in episodes:
            key = f"{season}|{episode}"
            if key not in episodes_to_fetch:
                episodes_to_fetch[key] = {
                    "show_name": show_name,
                    "season": season.zfill(2),
                    "episode": episode.zfill(2),
                }

    # Fetch names from TMDB
    logger.info(f"Fetching {len(episodes_to_fetch)} episode names from TMDB...")
    fetched_names = fetch_episode_names_batch(list(episodes_to_fetch.values()))

    if not fetched_names:
        logger.error("No episode names found on TMDB. Check show name.")
        return False

    # Save to EPISODE_NAME_FILE
    index_path = Path(folder) / EPISODE_NAME_FILE
    with index_path.open("w", encoding="utf-8") as file:
        file.write(show_name)
        file.write("\n")
        for key in sorted(fetched_names.keys()):
            season, episode = key.split("|")
            title = fetched_names[key]
            file.write(f"{season}|{episode}|{title}\n")

            for file_def in organized[season][episode].values():
                file_def.parsed.title = title

    logger.info(f"Fetched {len(fetched_names)} episode names to: {index_path}")
    return True
