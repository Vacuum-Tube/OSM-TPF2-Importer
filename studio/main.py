"""OSM-TPF2 Studio — desktop UI over the converter and in-game Lua mod."""
from __future__ import annotations

import sys
from pathlib import Path

def _paths():
    if getattr(sys, "frozen", False):
        here = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        root = Path(sys.executable).resolve().parent
        for candidate in (root, root.parent, root.parent.parent):
            if (candidate / "python" / "main.py").is_file():
                root = candidate
                break
        return here, root
    here = Path(__file__).resolve().parent
    return here, here.parent


HERE, ROOT = _paths()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import webview

from backend.api import StudioApi


def main() -> None:
    api = StudioApi(ROOT, ui_root=HERE / "ui")

    ui = (HERE / "ui" / "start.html").resolve().as_uri()
    window = webview.create_window(
        "OSM-TPF2 Studio",
        ui,
        js_api=api,
        width=1480,
        height=940,
        min_size=(1080, 720),
        background_color="#14110c",
    )
    api._window = window
    try:
        webview.start(gui="edgechromium")
    except Exception:
        webview.start()


if __name__ == "__main__":
    main()
