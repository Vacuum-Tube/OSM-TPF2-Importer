"""Temp-file then replace, so a crash cannot leave a truncated destination."""
from __future__ import annotations

import shutil
from pathlib import Path


def write_bytes(path: Path | str, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def write_text(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    write_bytes(path, text.encode(encoding))


def copy_file(src: Path | str, dest: Path | str, progress=None, start_pct: float = 0, end_pct: float = 100) -> None:
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    size = src.stat().st_size
    copied = 0
    with src.open("rb") as inf, tmp.open("wb") as out:
        while True:
            buf = inf.read(8 * 1024 * 1024)
            if not buf:
                break
            out.write(buf)
            copied += len(buf)
            if progress and size >= 8 * 1024 * 1024:
                pct = start_pct + (end_pct - start_pct) * copied / max(1, size)
                progress(
                    f"Copying {src.name} {copied / 1e6:.0f}/{size / 1e6:.0f} MB",
                    pct,
                )
    try:
        shutil.copystat(src, tmp)
    except OSError:
        pass
    tmp.replace(dest)
