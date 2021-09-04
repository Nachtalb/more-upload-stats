from mimetypes import guess_type
from pathlib import Path

from .core.utils import BASE_PATH

BUILD_PATH = BASE_PATH / 'build'
HTML_PATH = BASE_PATH / 'html'


def create_m3u(title, files, out_file, max_files=None):
    m3u = f'#EXTM3U\n#EXTENC: UTF-8\n#PLAYLIST: {title}\n'
    total = 0
    for file in files:
        type = guess_type(file)[0]
        if type and type.startswith('audio'):
            m3u += file + '\n'
            total += 1
        if total == max_files:
            break

    Path(out_file).write_text(m3u, encoding='utf-8')
