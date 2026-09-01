# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fork of [KraXen72/shira](https://github.com/KraXen72/shira) (a YouTube/YouTube Music/SoundCloud music downloader with heavy metadata enrichment) that adds `shira_ui.py`, a PyQt6 GUI on top of it. `shiradl/` is upstream code kept pristine so it can be merged forward; `shira_ui.py` is the only fork-specific source file.

Syncing with upstream is a real git merge, not a file copy — the fork shares history with `KraXen72/shira`:

```bash
git remote add upstream https://github.com/KraXen72/shira.git
```

```bash
git fetch upstream && git merge upstream/master
```

Only `.gitignore` and `README.md` conflict (both are fork-owned; keep our side and re-apply upstream's new ignore entries). Currently synced to upstream **v1.8.5**.

## Commands

`shiradl` must be **installed**, not just checked out — see "The install requirement" below.

```bash
pip install -e .             # required before anything works
python shira_ui.py           # launch the GUI
python -m shiradl <URL>      # upstream CLI (also installed as `shiradl`)
python -m shiradl.mbtag PATH # MusicBrainz re-tagger for existing files (also `mbtag`)
```

Upstream manages deps with uv and defines tasks via taskipy in `pyproject.toml`:

```bash
pytest -v -x                       # or: task test
pytest tests/smoke.test.py -v -x   # or: task test:smoke
pytest tests/metadata.test.py -v -x
pytest tests/download.test.py -v -x
```

Tests are marked `download`, `metadata`, and `smoke` (all hit the network); select with `-m`. Note `python_files = ["*.test.py", "test_*.py"]` — the unusual `*.test.py` naming is deliberate, so a new test file named otherwise silently won't run. There is no linter configured.

## The install requirement

Since v1.8.x, `shiradl` resolves its own version through `importlib.metadata`:

- `musicbrainz.py:162` — `_pkg_version('shiradl')` inside `MBSong.__init__`
- `cli.py` — `@click.version_option(package_name="shiradl")`

Neither has a fallback, and `__init__.py` no longer defines `__version__`. Running against a bare source tree raises `PackageNotFoundError`. The `MBSong(...)` construction in `musicbrainz_enrich_tags` sits *outside* the surrounding try/except, so this surfaces as every single track failing, not as a clean startup error. `pip install -e .` fixes it.

## Architecture

### Download pipeline

`shiradl/cli.py` is the orchestrator — the whole per-track pipeline lives in its `cli()` loop, not in `Dl`. Reading that loop is the fastest way to understand the project. Per track it:

1. `Dl.get_download_queue(url)` — yt-dlp flat extract; expands playlists, detects SoundCloud, resolves `MPREb_` YTMusic album URLs.
2. Metadata, via one of two mutually exclusive paths:
   - **YTMusic path** — `Dl.get_ytmusic_watch_playlist()` returns a hit → `Dl.get_tags()` builds `Tags` from the ytmusicapi album/watch-playlist data.
   - **"Tigerv2" path** (`metadata.smart_metadata`) — no YTMusic album (or SoundCloud). Scrapes tags out of the raw yt-dlp info dict using per-domain extractors (`youtube_extractor` / `soundcloud_extractor`) plus `smart_tag()`, which picks the most frequently occurring candidate value across several info-dict keys.
3. `musicbrainz.musicbrainz_enrich_tags()` — queries the MusicBrainz WS/2 API and *overwrites* title/artist/album/date when a match is found, then adds `mb_*` MBID tags. Match confidence comes from `normalized_compare_regex` (strips leading zeros, `feat.`/`ft.` clauses, commas; normalizes exotic hyphens). A failed fetch now degrades gracefully and returns the tags unenriched.
4. `Dl.get_final_location()` — formats `--template-folder`/`--template-file` against the tags. Singles get special-cased: the trailing `/{album}` segment and the `{track:02d} ` prefix are stripped unless `--single-folder`.
5. Download (`Dl.download` / `download_souncloud`, or `Dl.stub_download` under `--no-download`) → `Dl.fixup` (ffmpeg remux, `-f mp4` when ffprobe reports opus) → `tagging.metadata_applier` → move into place.

Failures are per-track: exceptions are logged and counted, the loop continues, and `temp_path` is wiped in the `finally`.

### Key invariants

- **`Tags`** (`tagging.py`) is the single dict passed between every stage. It is a `TypedDict` whose keys are `mediafile` attribute names — `metadata_applier` does `setattr(MediaFile_handle, key, value)`, so adding a tag means adding a key mediafile understands. `mb_*` values are utf-8 **bytes** unless `skip_encode`.
- **`Dl.tags` is a single-track cache.** `cli.py` must reset `dl.tags = None` before each track or the previous track's tags leak through `get_tags()`.
- **`Dl.soundcloud` is sticky mutable state** set during `get_download_queue` and read everywhere afterwards to pick mp3 vs m4a, skip the YTMusic lookup, and switch the default output folder to `./SoundCloud`.
- Multi-value artists are joined with `MV_SEPARATOR` (`/`) in file tags but `MV_SEPARATOR_VISUAL` (` & `) in filenames. `fallback_mv=True` in `metadata_applier` exists because Auxio doesn't read real multi-value m4a tags yet.
- Cover art is fetched through a shared `requests_cache` session named `shira_requests_cache`, stored in the OS cache directory (`use_cache_dir=True`). Three modules construct their own session with that same name but different TTLs.
- `--cover-crop auto` runs `determine_image_crop`, which samples corner pixels of a smoothed 64-color version of the thumbnail and decides crop-vs-pad from the per-channel stddev.

### Config resolution

`--no-config-file` carries a Click **callback** (`no_config_callback`) that does the actual config loading as a side effect — it writes a default `~/.shiradl/config.json` from the option defaults on first run, then injects file values into `ctx.params` for any option whose `ParameterSource` isn't `COMMANDLINE`. Option ordering in the decorator stack therefore matters: `--config-location` must be parsed before the callback fires. Adding a non-persistable option means adding it to `EXCLUDED_PARAMS`.

### GUI

`shira_ui.py` does **not** shell out — it imports `shiradl.cli.cli` and calls it in a `QThread` with `standalone_mode=False`, building an argv list from the widgets. To surface progress it redirects stdout into `EmittingStream`, which splits on `\n`/`\r` and re-emits; lines prefixed `\r` (yt-dlp progress) overwrite the last block in the `QTextEdit` instead of appending. `DummyBuffer` exists only because yt-dlp reaches for `sys.stdout.buffer`.

Every widget value is passed as an explicit CLI flag, so GUI defaults silently win over `config.json` for those options. Adding a CLI option means wiring it into both the Advanced tab and `start_download()`. When merging upstream, diff `cli.py`'s `@click.option` list against the flags `start_download()` emits — that string-built argv is the fork's one real coupling point to upstream, and nothing enforces it.

## Fork-specific notes

- `PyQt6` is deliberately **not** in `pyproject.toml` — that file describes the upstream `shiradl` distribution, and keeping it untouched avoids a conflict on every future merge. Install PyQt6 separately.
- The GUI's cookies checkbox hardcodes `~/.shira/cookies.txt`, while the CLI config lives at `~/.shiradl/config.json`. Different directories, and the checkbox silently does nothing if the file is absent.
- `shiradl/` uses tabs; `shira_ui.py` uses 4 spaces. Match the file you're editing.
- `Dl.get_audio_codec` invokes bare `ffprobe` from PATH, ignoring `--ffmpeg-location`.
