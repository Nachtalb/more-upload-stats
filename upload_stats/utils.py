from functools import wraps
import inspect
import os
import platform
import subprocess
from pathlib import Path
from mimetypes import guess_type

BASE_PATH = Path(__file__).parent.parent.absolute()
BUILD_PATH = BASE_PATH / 'build'
HTML_PATH = BASE_PATH / 'html'


def startfile(file):
    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', file))
    elif platform.system() == 'Windows':    # Windows
        os.startfile(file)  # type: ignore
    else:                                   # linux variants
        subprocess.call(('xdg-open', file))


def command(func):
    @wraps(func)
    def wrapper(self, initiator=None, argstring=None, *_args, **_kwargs):
        if self == initiator:
            initiator = argstring
            argstring, _args = _args[0], _args[1:]
        argspec = inspect.signature(func)
        command_args = list(map(str2num, filter(None, map(str.strip, (argstring or '').split()))))
        extra_args = []

        if 'initiator' in argspec.parameters and 'initiator' not in _kwargs and initiator is not None:  # noqa
            extra_args.append(initiator)
        if 'args' in argspec.parameters and 'args' not in _kwargs and command_args:
            extra_args.append(command_args)

        return func(self, *extra_args, *_args, **_kwargs)
    return wrapper


def str2num(string):
    if string.isdigit():
        return int(string)
    try:
        string = float(string)
    except ValueError:
        pass
    return string


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
