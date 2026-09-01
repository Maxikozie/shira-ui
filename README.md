# Shira UI

A lightweight PyQt6 interface for [shira](https://github.com/KraXen72/shira) — smart music downloader.

### Features
- Supports YouTube, YouTube Music, and SoundCloud
- Light and dark themes, remembered between launches
- Queue several links at once, or drop a `links.txt` onto the window
- Live progress, a working Cancel button, and a colour-coded activity log
- Plain-language advanced options, collapsed by default
- Your settings are remembered and are always what actually runs

### Requirements
- Python 3.11+ (upstream `shiradl` now sets `requires-python = ">=3.11"`)
- PyQt6
- `shiradl` **installed as a package**, not just present in the folder

### Setup

`shiradl` must be installed, not merely checked out. Since v1.8.x it reads its own
version through `importlib.metadata`, which only works for an installed
distribution — running against a bare source tree raises `PackageNotFoundError`
on every track.

```bash
pip install -e .
```

```bash
pip install PyQt6
```

Icons are optional. Install `qtawesome` for them; without it the app falls
back to built-in icons and Unicode glyphs and looks correct either way.

```bash
pip install qtawesome
```

### Run
```bash
python shira_ui.py
```

The interface lives in the `shiraui/` package; `shira_ui.py` is a small
launcher. Run the interface's tests with:

```bash
python -m pytest tests_ui
```

### Troubleshooting

If you experience issues such as downloads failing or no formats being available, try the following:
- **Update `yt-dlp`**:  

  ```bash
  yt-dlp -U
  ```
  If installed via pip:  
  ```bash
  pip install -U yt-dlp
  ```
- **Update `ffmpeg`**:  

  Make sure `ffmpeg` is installed and the latest version is available in your system PATH. You can download the latest from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).
- **`PackageNotFoundError: No package metadata was found for shiradl`**:  

  You are running against an uninstalled source tree. Run `pip install -e .` from the repo root.
