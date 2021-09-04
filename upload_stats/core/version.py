import re

__all__ = ['Version']


class Version:
    def __init__(self, major, minor, patch, dev=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.dev = dev

    @property
    def astuple(self):
        return self.major, self.minor, self.patch, self.dev

    @staticmethod
    def parse(*version):
        if len(version) == 1 and isinstance(version[0], str):
            match = re.match(r'v?(\d+)\.?(\d+)?\.?(\d+)?\.?(\w+)?', version[0])
            if not match:
                raise ValueError(f'Version {version} cannot be parsed')
            version = filter(None, match.groups())
        version = list(version)
        version += [0] * (3 - len(version))  # type: ignore
        if len(version) == 3:
            version += [None]
        return Version(*map(int, version[:3]), version[3])  # type: ignore

    def __str__(self):
        return '.'.join(map(str, self.astuple[:3])) + (self.dev if self.dev is not None else '')

    def __repr__(self):
        return f'Version({self})'

    def __eq__(self, version: 'Version'):
        return self.astuple == version.astuple

    def __lt__(self, version: 'Version'):
        return self.astuple[:3] < version.astuple[:3] or (
            self.astuple[:3] == version.astuple[:3] and (
                (self.dev is None and version.dev is not None) or
                (self.dev is not None and version.dev is not None and self.dev < version.dev)
            ))

    def __le__(self, v):
        return self < v or self == v

    def __gt__(self, v):
        return not self < v

    def __ge__(self, v):
        return not self < v or self == v

    def __ne__(self, v):
        return not self == v
