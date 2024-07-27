"""This module contins utility functions."""

from mimetypes import guess_type
from pathlib import Path
from typing import List, Union

__all__ = ["create_m3u"]


def create_m3u(title: str, files: List[str], out_file: Union[str, Path], max_files: int = -1) -> None:
    """Create an M3U playlist file with the given files.

    Args:
        title (:obj:`str`): Title for the playlist.
        files (:obj:`List` of :obj:`str`): List of files to add to the playlist.
        out_file (:obj:`str` | :obj:`Path`): Output file path.
        max_files (:obj:`int`, optional): Maximum number of files to add to the playlist. Default is -1 (all files).
    """
    m3u = f"#EXTM3U\n#EXTENC: UTF-8\n#PLAYLIST: {title}\n"
    total = 0
    for file in files:
        type = guess_type(file)[0]
        if type and type.startswith("audio"):
            m3u += file + "\n"
            total += 1
        if total == max_files:
            break

    Path(out_file).write_text(m3u, encoding="utf-8")
