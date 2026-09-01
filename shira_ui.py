"""Launcher for Shira UI.

The implementation lives in the `shiraui` package. This shim keeps the
documented `python shira_ui.py` command (and any existing shortcut) working.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shiraui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
