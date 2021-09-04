from functools import wraps
from http.client import HTTPResponse
import inspect
import json
import os
from pathlib import Path
import platform
from random import choice
import subprocess
from threading import Thread
from typing import Union
from urllib.request import Request, urlopen

from pynicotine.logfacility import log as nlog

__all__ = ['BASE_PATH', 'USER_AGENTS', 'startfile', 'command', 'Response', 'get', 'log',
           'str2num']

BASE_PATH = Path(__file__).parent.parent.parent.absolute()

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',  # noqa
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393',  # noqa
]


def startfile(file):
    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', file))
    elif platform.system() == 'Windows':    # Windows
        os.startfile(file)  # type: ignore
    else:                                   # linux variants
        subprocess.call(('xdg-open', file))


def _parse_according_to_spec(spec, value):
    if isinstance(spec.annotation, bool) or isinstance(spec.default, bool):
        return False if value.lower() == 'false' else True
    for t in [int, float, str]:
        if isinstance(spec.annotation, t) or isinstance(spec.default, t):
            try:
                return t(value)
            except Exception:
                log(f'Expected type {t} for argument {spec.name}')
                return


def command(func):
    @wraps(func)
    def wrapper(self, initiator=None, argstring=None, *_args, **_kwargs):
        if self == initiator:
            initiator = argstring
            argstring, _args = _args[0], _args[1:]
        parameters = inspect.signature(func).parameters
        command_args = list(map(str2num, filter(None, map(str.strip, (argstring or '').split()))))
        extra_args = []

        if 'initiator' in parameters and 'initiator' not in _kwargs and initiator is not None:  # noqa
            extra_args.append(initiator)
        if 'args' in parameters and 'args' not in _kwargs and command_args:
            extra_args.append(command_args)
        elif command_args:
            for arg in command_args:
                if not isinstance(arg, str):
                    continue

                orig_arg = arg = arg.lstrip('-')
                arg = arg.lower()

                if '=' in arg:
                    key = arg.split('=')[0]
                    value = orig_arg.split('=')

                    if key and value and key in parameters:
                        value = _parse_according_to_spec(parameters[key], value)
                        if value is None:
                            continue
                        _kwargs[key] = value
                elif arg in parameters and (value := _parse_according_to_spec(parameters[arg], orig_arg)) is not None:
                    _kwargs[arg] = value

        curframe = inspect.currentframe()
        callframe = inspect.getouterframes(curframe, 2)
        if callframe[1][3] == '_trigger_command':
            Thread(target=func, args=(self, *extra_args, *_args), kwargs=_kwargs, daemon=True).start()
        else:
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


def log(*msg, msg_args=[], level=None, prefix=None):
    if len(msg) == 1:
        msg = msg[0]
    else:
        msg = ', '.join(map(str, msg))

    msg = (prefix if prefix else '') + f'{msg}'
    nlog.add(msg, msg_args, level)


class Response:
    _raw = _content = _json = None
    mime_type = None
    encoding = None

    def __init__(self, obj: HTTPResponse):
        self._wrapped_obj = obj
        self.mime_type = self.headers.get_content_type()
        self.encoding = self.headers.get_content_charset()
        self.content

    def __enter__(self):
        self._wrapped_obj.__enter__()
        return self

    def __exit__(self, *args, **kwargs):
        return self._wrapped_obj.__exit__(*args, **kwargs)

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return getattr(self, attr)
        return getattr(self._wrapped_obj, attr)

    def __repr__(self):
        return f'{self.__class__}(url="{self.geturl()}", status={self.status})'

    @property
    def raw(self) -> bytes:
        if not self._raw:
            self._raw = self.read()
        return self._raw

    @property
    def content(self) -> Union[bytes, str]:
        if not self._content:
            try:
                self._content = self.raw.decode(self.encoding or 'utf-8')
            except Exception:
                self._content = self.raw
        return self._content

    @property
    def json(self) -> dict:
        if not self._json:
            self._json = json.loads(self.content)
        return self._json


def get(url, data=None, headers={}, timeout=30):
    if 'User-Agent' not in headers:
        headers['User-Agent'] = choice(USER_AGENTS)

    response = urlopen(Request(url=url, data=data, headers=headers), timeout=timeout)
    return Response(response)
