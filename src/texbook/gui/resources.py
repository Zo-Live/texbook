"""Resource path helpers for source and PyInstaller runtime modes."""

from __future__ import annotations

import sys
from pathlib import Path


APP_DISPLAY_NAME = "TexBook"
APP_ORGANIZATION_NAME = "TexBook"
APP_WINDOW_TITLE = "TexBook PDF 转 LaTeX"
ICON_RELATIVE_PATH = Path("docs") / "icon.ico"


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    pyinstaller_root = getattr(sys, "_MEIPASS", None)
    if pyinstaller_root:
        roots.append(Path(pyinstaller_root))

    package_file = Path(__file__).resolve()
    roots.extend(
        [
            package_file.parents[3],
            package_file.parents[2],
            Path.cwd(),
        ]
    )
    return roots


def resolve_app_icon_path() -> Path | None:
    """Return the application icon path when the resource is available."""
    for root in _candidate_roots():
        icon_path = root / ICON_RELATIVE_PATH
        if icon_path.is_file():
            return icon_path
    return None
