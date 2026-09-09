# MKV Organizer

Automatically organize and rename video files with a standardized naming
scheme. It supports three content types:

| Type        | Flag        | Meaning                                                                                                             |
| ----------- | ----------- | ------------------------------------------------------------------------------------------------------------------- |
| **Movie**   | _(default)_ | Each file is a standalone movie, renamed with its year.                                                             |
| **TV Show** | `--show`    | Episodes carry an `SxxExx` marker in their name.                                                                    |
| **Anime**   | `--anime`   | A **single-season** folder; every file is a consecutively numbered episode that usually has **no** `SxxExx` marker. |

---

## Quick start

```bash
# Preview what would be renamed (dry-run is the default)
py -m main "C:\path\to\folder" --show

# Actually rename files
py -m main "C:\path\to\folder" --show --commit

# Anime (single-season folder)
py -m main "C:\path\to\anime-folder" --anime --commit
```

Run `py -m main -h` for the full list of options.

---

## Content types

### Movies (default)

A movie folder needs no extra flag:

```
Avengers Infinity War (2018) [Hybrid]...mkv
  -> Avengers.Infinity.War.2018.1080p...mkv            (style 1)
```

### TV Shows (`--show`)

Show folders are detected from `SxxExx` markers:

```
Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4
  -> Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4 (style 1)
```

### Anime (`--anime`)

Anime releases usually have **one season** worth of episodes in a single
folder and number them _consecutively without an `SxxExx` marker_:

```
Detective Conan - 0123 [1080p][Multiple Subtitle][FDB1F25C].mkv
Detective Conan - 0124 [1080p][Multiple Subtitle][FDB1F25C].mkv
Detective Conan - 0125 [1080p][DDP 5.1][11223344].chs.srt
```

`--anime` tells the tool that the folder is **one season** and every file is a
numbered episode:

- The episode number is the **4-digit zero-padded number in the filename**
  (e.g. `0001`, `0123`). Short numbers are padded to 4 digits (`123` →
  `0123`).
- Because a bare number is ambiguous (it could be a channel count, a CRC, …),
  the tool first scans **all files in the same folder** and picks the number
  that forms the _consecutive / incrementing_ sequence — the other numbers
  (e.g. `5.1`) repeat from file to file and are ignored.
- Files that do carry an explicit `SxxExx` marker are parsed normally (and, in
  an anime folder, the marker's season/episode is used for grouping/listing).
- Release-tag/hash brackets after the episode number (`[Multiple Subtitle]`,
  `[FDB1F25C]`, `[hash]`) are treated as noise and dropped; recognized
  metadata (`[1080p]`, `[HEVC]`, `[DDP 5.1]`) is kept. Episode titles, when
  present, are preserved (`Show - 0002 - The Episode Title` → title
  `The Episode Title`).

Internally the files are still grouped as a single season (`S01`) so that
listing, `episode_names.txt` and TMDB flows work like a normal show. By
default the **written filename keeps only the episode number** — no `SxxExx`
marker. Add `--anime-season` to also write the marker (e.g. `S01E0123`).

Example results:

```
Detective.Conan.0123.1080p.mkv                    (style 1, default)
Detective.Conan.S01E0123.1080p.mkv                (style 1, with --anime-season)
Detective Conan 0123 [1080p][HEVC].mkv            (style 2, default)
Detective.Conan.0125.1080p.DDP.5.1.chs.srt        (style 1, subtitle)
```

> If a folder contains **multiple seasons**, use `--show` instead of `--anime`
> so each file's `SxxExx` marker drives the season/episode.

Anime mode behaves like `--show` for everything else: it can list episodes,
fetch episode titles from TMDB / `episode_names.txt`, check for missing
episodes, etc.

---

## Options

| Option                                  | Description                                                                                      |
| --------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `folder`                                | Folder containing the video files.                                                               |
| `-l, --list`                            | List all files in the folder (table).                                                            |
| `--list-csv`                            | Write the listing to `videos.csv`.                                                               |
| `-d, --dry-run`                         | Preview only (default is `True`).                                                                |
| `-c, --commit`                          | Actually rename files (overrides dry-run).                                                       |
| `--show / --no-show`                    | Treat the folder as TV shows.                                                                    |
| `--anime`                               | Treat the folder as a single-season anime folder.                                                |
| `--anime-season`                        | Write the `SxxExx` marker (e.g. `S01E0123`) in anime names (default: off - episode number only). |
| `--id-in-filename, --no-id-in-filename` | Embed known IMDb/TMDB id in names (default on).                                                  |
| `-s, --style 1\|2`                      | Naming style (see below).                                                                        |
| `-r, --recursive`                       | Recurse into subdirectories.                                                                     |
| `--no-language`                         | Don't append language codes to subtitle names.                                                   |
| `-v, --verbose`                         | Verbose (debug) logging.                                                                         |
| `-f, --force-use-media-info`            | Re-read media info even when fields are parsed.                                                  |
| `--normalize-folders`                   | Rename show folders to `Show Name {identifier}`.                                                 |
| `--fetch-tmdb-for-normalize`            | Fetch TMDB info while normalizing folders.                                                       |
| `--[no-]export-episode-names`           | Write/parse `episode_names.txt` (default on).                                                    |
| `--[no-]use-episode-names`              | Use `episode_names.txt` to fill titles (default on).                                             |
| `--[no-]fetch-if-missing`               | Fetch from TMDB when no index exists (default on).                                               |
| `--force-fetch`                         | Ignore `episode_names.txt` and always fetch from TMDB.                                           |
| `--check-missing`                       | Report episodes in the index missing from the folder.                                            |
| `--check-low-resolution N`              | Report episodes below `N` (e.g. `1080`) resolution.                                              |

---

## Naming styles

**Style 1** — dot-separated:

```
Movie : Movie.Name.Year.1080p.HEVC.DV.WEB-DL.TrueHD.Atmos.7.1-GROUP.mkv
TV    : Show.Name.S01E01.Title.1080p.HEVC.DV.WEB-DL.-GROUP.mkv
Anime : Show.Name.0123.1080p.mkv          (with --anime-season: Show.Name.S01E0123.1080p.mkv)
```

**Style 2** — space-separated with bracket metadata:

```
Movie : Movie Name (Year) [1080p][HEVC][DV][WEB-DL][TrueHD Atmos 7.1]-GROUP.mkv
TV    : Show Name S01E01 - Title [1080p][HEVC][DV][WEB-DL]-GROUP.mkv
Anime : Show Name 0123 [1080p][HEVC]-GROUP.mkv
```

Language is always appended as a dotted suffix before the extension, e.g.
`Show.Name.S01E01.chs.srt`.

---

## Episode titles (`episode_names.txt`)

For shows/anime the tool can store episode titles in a per-folder
`episode_names.txt`:

```
Show Name
01|0001|Episode One Title
01|0002|Episode Two Title
```

Titles are applied to parsed files and/or fetched from TMDB. Long-running
anime is often split into many TMDB seasons, so episode numbers past the first
season may simply not resolve to a title — the file will still be renamed
without one.

### Identifiers (`{imdb-…}` / `{tmdb-…}`)

When an id is known (from a fetch or an existing name) it can be embedded in
the filename — by default it is (`--id-in-filename`), or you can keep names
clean with `--no-id-in-filename`:

```
Style 1 (keep id): Detective.Conan.0001.{tmdb-30983}.1080p.mkv
Style 1 (no id)  : Detective.Conan.0001.1080p.mkv
Style 2 (keep id): Detective Conan {tmdb-30983} 0001 [1080p].mkv
```

On re-runs the parser detects the id whether it sits _next to the show name_
(`Show Name {tmdb-30983} S01E01 …`) or _after the marker_
(`Show.S01E01.{tmdb-30983}…`), strips it from the show name and stores it as
`tmdb_id` / `imdb_id`. A later `--force-fetch` therefore reuses that id for the
TMDB lookup instead of searching by (possibly wrong or mangled) show name.
