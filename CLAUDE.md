# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fork of [KraXen72/shira](https://github.com/KraXen72/shira) (a YouTube/YouTube Music/SoundCloud music downloader with heavy metadata enrichment) that adds `shira_ui.py`, a PyQt6 GUI on top of it. The vendored `shiradl/` package is upstream code; `shira_ui.py` is the fork-specific addition.

## Commands

```bash
python shira_ui.py           # launch the GUI
python -m shiradl <URL>      # upstream CLI (also installed as `shiradl`)
python -m shiradl.mbtag PATH # MusicBrainz re-tagger for existing files (also `mbtag`)
```

There is no test suite, linter config, or build step configured. Packaging is flit (`pyproject.toml`); `.github/workflows/main.yml` publishes to PyPI on GitHub release.

## Architecture

### Download pipeline

`shiradl/cli.py` is the orchestrator — the whole per-track pipeline lives in its `cli()` loop, not in `Dl`. Reading that loop is the fastest way to understand the project. Per track it:

1. `Dl.get_download_queue(url)` — yt-dlp flat extract; expands playlists, detects SoundCloud, resolves `MPREb_` YTMusic album URLs.
2. Metadata, via one of two mutually exclusive paths:
   - **YTMusic path** — `Dl.get_ytmusic_watch_playlist()` returns a hit → `Dl.get_tags()` builds `Tags` from the ytmusicapi album/watch-playlist data.
   - **"Tigerv2" path** (`metadata.smart_metadata`) — no YTMusic album (or SoundCloud). Scrapes tags out of the raw yt-dlp info dict using per-domain extractors (`youtube_extractor` / `soundcloud_extractor`) plus `smart_tag()`, which picks the most frequently occurring candidate value across several info-dict keys.
3. `musicbrainz.musicbrainz_enrich_tags()` — queries the MusicBrainz WS/2 API and *overwrites* title/artist/album/date when a match is found, then adds `mb_*` MBID tags. Match confidence comes from `normalized_compare_regex` (strips leading zeros, `feat.`/`ft.` clauses, commas; normalizes exotic hyphens).
4. `Dl.get_final_location()` — formats `--template-folder`/`--template-file` against the tags. Singles get special-cased: the trailing `/{album}` segment and the `{track:02d} ` prefix are stripped unless `--single-folder`.
5. Download (`Dl.download` / `download_souncloud`) → `Dl.fixup` (ffmpeg remux, `-f mp4` when ffprobe reports opus) → `tagging.metadata_applier` → move into place.

Failures are per-track: exceptions are logged and counted, the loop continues, and `temp_path` is wiped in the `finally`.

### Key invariants

- **`Tags`** (`tagging.py`) is the single dict passed between every stage. It is a `TypedDict` whose keys are `mediafile` attribute names — `metadata_applier` does `setattr(MediaFile_handle, key, value)`, so adding a tag means adding a key mediafile understands. `mb_*` values are utf-8 **bytes** unless `skip_encode`.
- **`Dl.tags` is a single-track cache.** `cli.py` must reset `dl.tags = None` before each track or the previous track's tags leak through `get_tags()`.
- **`Dl.soundcloud` is sticky mutable state** set during `get_download_queue` and read everywhere afterwards to pick mp3 vs m4a, skip the YTMusic lookup, and switch the default output folder to `./SoundCloud`.
- Multi-value artists are joined with `MV_SEPARATOR` (`/`) in file tags but `MV_SEPARATOR_VISUAL` (` & `) in filenames. `fallback_mv=True` in `metadata_applier` exists because Auxio doesn't read real multi-value m4a tags yet.
- Cover art is fetched through a shared `requests_cache` session named `shira` (`.sqlite` in cwd, gitignored). `--cover-crop auto` runs `determine_image_crop`, which samples corner pixels of a smoothed 64-color version of the thumbnail and decides crop-vs-pad from the per-channel stddev.

### Config resolution

`--no-config-file` carries a Click **callback** (`no_config_callback`) that does the actual config loading as a side effect — it writes a default `~/.shiradl/config.json` from the option defaults on first run, then injects file values into `ctx.params` for any option whose `ParameterSource` isn't `COMMANDLINE`. Option ordering in the decorator stack therefore matters: `--config-location` must be parsed before the callback fires. Adding a non-persistable option means adding it to `EXCLUDED_PARAMS`.

### GUI

`shira_ui.py` does **not** shell out — it imports `shiradl.cli.cli` and calls it in a `QThread` with `standalone_mode=False`, building an argv list from the widgets. To surface progress it redirects stdout into `EmittingStream`, which splits on `\n`/`\r` and re-emits; lines prefixed `\r` (yt-dlp progress) overwrite the last block in the `QTextEdit` instead of appending. `DummyBuffer` exists only because yt-dlp reaches for `sys.stdout.buffer`.

Every widget value is passed as an explicit CLI flag, so GUI defaults silently win over `config.json` for those options. Adding a CLI option means wiring it into both the Advanced tab and `start_download()`.

## Known inconsistencies (don't "fix" without checking)

- `pyproject.toml` claims `requires-python = ">=3.8"`, but the code needs 3.11+ (`typing.NotRequired`, PEP 604 unions) and `mbtag.py:128` uses a PEP 701 nested-quote f-string requiring 3.12+.
- `PyQt6` is not declared in `pyproject.toml` dependencies — the packaged distribution is the upstream CLI only.
- Config/cookie paths disagree: the CLI defaults to `~/.shiradl/config.json`, the GUI's cookies checkbox hardcodes `~/.shira/cookies.txt`, and the README says `.shira/config.json`.
- `shiradl/` uses tabs; `shira_ui.py` uses 4 spaces. Match the file you're editing.
- `Dl.get_audio_codec` invokes bare `ffprobe` from PATH, ignoring `--ffmpeg-location`.
