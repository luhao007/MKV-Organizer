# MKV Organizer - Refactored Code Structure

## 📁 New Project Structure

```
MKV-Organizer/
├── main.py                 # Entry point (clean CLI interface)
├── config.py              # All constants and regex patterns
├── models.py              # Data models (ParsedFileInfo, FileDefinition, etc.)
├── parser.py              # Filename parsing logic
├── media_info.py          # MediaInfo extraction
├── formatter.py           # Filename formatting & capitalization
├── organizer.py           # File organization and renaming
├── subtitle_shift.py      # Subtitle timing adjustment (separate utility)
├── requirements.txt
├── utils/
│   ├── src/
│   │   ├── logger.py
│   │   └── timer.py
│   └── tests/
└── README.md (this file)
```

## 🎯 Key Improvements

### 1. **Separation of Concerns** ✨

- **`parser.py`**: Handles filename parsing
  - Extracts show name, season, episode, title
  - Finds resolution and codec from filename
  - Detects release groups
- **`media_info.py`**: Extracts metadata from actual video files
  - Gets resolution from video height
  - Detects codec (x264, x265, AV1, etc.)
  - Intelligent fallback for non-standard values
- **`formatter.py`**: Formats output filenames
  - Title case capitalization with stopword handling
  - Preserves brackets and parentheses
  - Builds standardized filenames
- **`organizer.py`**: Orchestrates the renaming
  - Scans and organizes files
  - Fills missing metadata
  - Performs the actual renaming

### 2. **Strong Type System** 🔒

```python
# Before: dict[str, str]
# After: using dataclasses for clarity
@dataclass
class ParsedFileInfo:
    show_name: str
    season: str
    episode: str
    title: str
    resolution: str = ""
    codec: str = ""
    release_group: str = ""
```

### 3. **Centralized Configuration** ⚙️

All constants in `config.py`:

```python
VIDEO_FORMATS = ["mkv", "mp4", "avi"]
SEASON_EPISODE_PATTERN = re.compile(...)
CODEC_PATTERN = re.compile(...)
STOPWORDS = {"in", "as", "of", "the", ...}
```

### 4. **Better Documentation** 📖

- Clear docstrings for all functions
- Type hints throughout
- Comments explain complex logic
- Examples in docstrings

### 5. **Improved CLI** 🖥️

```bash
# Usage examples:
python main.py /path/to/videos          # Dry run (default)
python main.py /path/to/videos --commit # Actually rename
python main.py -v /path/to/videos       # Verbose logging
python main.py --no-language /path      # Skip language codes
```

## 📝 Filename Patterns Supported

### Pattern 1: Release Group Format

```
Better.Call.Saul.S01E10.Marco.1080p.X265.x265-RARBG.mp4
                 ↓
Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4
```

### Pattern 2: Parentheses-Based Title

```
Air.Crash.Investigations.S01E01 Unlocking Disaster (United Airlines, Flight 811).avi
                                 ↓
Air.Crash.Investigations.S01E01.Unlocking.Disaster.(United.Airlines.Flight.811).avi
```

## 🔄 Data Flow

```
Filename
   ↓
[Parser] → ParsedFileInfo
   ↓
[Organizer] → Organize by season/episode
   ↓
[MediaInfo] → Extract resolution/codec (fills gaps)
   ↓
[Formatter] → Build standard filename
   ↓
Rename file
```

## 🚀 Usage

### Basic Usage

```python
from organizer import organize_files, rename_files

# Scan and organize files
organized = organize_files("/path/to/videos")

# Rename with dry run (default)
rename_files(organized, dry_run=True)

# Actually rename files
rename_files(organized, dry_run=False)
```

### Advanced Usage

```python
from parser import parse_filename
from media_info import extract_media_info
from formatter import build_filename

# Parse a single file
info = parse_filename("Show.S01E10.Title.1080p.x265-GROUP.mkv")
print(info.show_name)  # "Show"
print(info.season)     # "01"

# Extract media info
media = extract_media_info("/path/to/video.mkv")
print(media.resolution)  # "1080p"

# Build new filename
new_name = build_filename(
    show_name="Better Call Saul",
    season="01",
    episode="10",
    title="Marco",
    resolution="1080p",
    codec="x265",
    release_group="RARBG"
)
# "Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG"
```

## 📊 Naming Convention

Output format:

```
ShowName.S{season}E{episode}.Title.{resolution}.{codec}-{group}.{ext}
```

### Components

- **ShowName**: Title case, words separated by dots
  - Removes common separators (underscores, spaces)
  - Handles stopwords (of, the, and, etc.)
- **S{season}E{episode}**: Zero-padded (e.g., S01E10)

- **Title**: Episode title in title case
  - Preserves parentheses and brackets
  - Example: `Unlocking.Disaster.(United.Airlines.Flight.811)`

- **Resolution**: Lowercase (1080p, 720p, 2160p)
  - Extracted from video file if not in filename

- **Codec**: Lowercase (x265, x264, AV1)
  - Extracted from video file if not in filename

- **Group**: Release group (RARBG, DEFLATE, etc.)
  - Optional, detected from trailing text

- **Extension**: Original file extension (mkv, mp4, avi)

### Subtitle Files

Subtitles get language code appended:

```
Show.S01E10.Title.1080p.x265.chs.srt    (Chinese)
Show.S01E10.Title.1080p.x265.eng.srt    (English)
Show.S01E10.Title.1080p.x265.cht&eng.srt (Traditional Chinese + English)
```

## 🧪 Testing

The code includes proper test structure:

```
utils/tests/
├── test_logger.py
└── test_timer.py
```

You can add more tests:

```python
# tests/test_parser.py
from parser import parse_filename

def test_parse_better_call_saul():
    info = parse_filename("Better.Call.Saul.S01E10.Marco.1080p.x265-RARBG.mp4")
    assert info.show_name == "Better Call Saul"
    assert info.season == "01"
    assert info.episode == "10"
```

## ✅ What Was Improved

| Aspect            | Before                   | After                        |
| ----------------- | ------------------------ | ---------------------------- |
| File Organization | Monolithic (400+ lines)  | Modular (5 focused modules)  |
| Type Safety       | `dict[str, str]`         | `dataclass` with type hints  |
| Maintainability   | Scattered logic          | Clear separation of concerns |
| Documentation     | Minimal, Chinese/English | Comprehensive docstrings     |
| Testing           | Hard to test             | Easily testable functions    |
| Configuration     | Constants everywhere     | Centralized `config.py`      |
| Reusability       | Tightly coupled          | Independent modules          |
| Naming            | Inconsistent             | Clear and consistent         |

## 🔧 Future Improvements

Potential enhancements:

1. Add more tests (unit + integration)
2. Support for anime naming conventions (AnimeTitle - 01)
3. Undo/rollback functionality
4. Configuration file support (JSON/YAML)
5. Watch mode (monitor folder for new files)
6. Multi-language support for logs
7. Web UI for preview and manual confirmation

## 📜 License

Same as parent project.
