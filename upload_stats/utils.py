import os
from mimetypes import guess_type
from pathlib import Path
from typing import List, Union

from .core.utils import BASE_PATH

BUILD_PATH = BASE_PATH / "build"
HTML_PATH = BASE_PATH / "html"
REL_HTML_PATH = os.path.relpath(HTML_PATH, BUILD_PATH)


def create_m3u(title: str, files: List[str], out_file: Union[str, Path], max_files: int = -1) -> None:
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
