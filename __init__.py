import ast
import base64
from base64 import urlsafe_b64encode
from datetime import datetime
from functools import partial, reduce, wraps
import hashlib
import inspect
import json
from mimetypes import guess_type
import os
from pathlib import Path
import platform
import re
from statistics import mean, median
import subprocess
from tempfile import NamedTemporaryFile
from threading import Event, Thread
from time import sleep, time
from urllib import request
import webbrowser

from pynicotine.logfacility import log
from pynicotine.pluginsystem import returncode
from pynicotine.pluginsystem import BasePlugin as NBasePlugin

BASE_PATH = Path(__file__).parent
config_file = BASE_PATH / 'PLUGININFO'
CONFIG = dict([(key, ast.literal_eval(value) if value.startswith('[') else value[1:-1].replace('\\n', '\n'))
               for key, value in map(lambda i: i.split('=', 1), filter(None, config_file.read_text().split('\n')))])

__version__ = CONFIG.get('Version', '0.0.1')


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


class PeriodicJob(Thread):
    __stopped = False
    last_run = None

    name = ''
    delay = 1
    _min_delay = 1

    def __init__(self, delay=None, update=None, name=None, before_start=None):
        super().__init__(name=name or self.name, daemon=True)
        self.delay = delay or self.delay
        self.before_start = before_start
        self.first_round = Event()

        self.__pause = Event()
        self.__pause.set()

        if update:
            self.update = update

    def time_to_work(self):
        delay = self.delay() if callable(self.delay) else self.delay
        return self.__pause.wait() and delay and (not self.last_run or time() - self.last_run > delay)

    def run(self):
        if self.before_start:
            self.before_start()
        while not self.__stopped:
            if self.time_to_work():
                self.update()
                self.last_run = time()
            if not self.first_round.is_set():
                self.first_round.set()
            sleep(self._min_delay)

    def stop(self, wait=True):
        self.__stopped = True
        if wait and self.is_alive():
            self.join()

    def pause(self):
        self.__pause.clear()

    def resume(self):
        self.__pause.set()


class BasePlugin(NBasePlugin):
    settings = metasettings = {}
    default_settings = {
        'check_update': True,
    }
    default_metasettings = {
        'check_update': {
            'description': '''Check for Updates
Check for updates on start and periodically''',
            'type': 'bool',
        },
    }

    @property
    def __name__(self):
        return CONFIG.get('Name', self.__class__.__name__)

    update_version = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = self.default_settings
        settings.update(self.settings)
        self.settings = settings
        metasettings = self.default_metasettings
        metasettings.update(self.metasettings)
        self.metasettings = metasettings

    def init(self):
        self.auto_update = PeriodicJob(name='AutoUpdate',
                                       delay=3600,
                                       update=self.check_update)
        self.auto_update.start()

        self.settings_watcher = PeriodicJob(name='SettingsWatcher', update=self.detect_settings_change)
        self.settings_watcher.start()

        if prefix := CONFIG.get('Prefix'):
            public_commands = self.__publiccommands__
            self.__publiccommands__ = []
            private_commands = self.__privatecommands__
            self.__privatecommands__ = []
            for name, callback in public_commands:
                if name:
                    name = '-' + name
                self.__publiccommands__.append((prefix + name, callback))
            for name, callback in private_commands:
                if name:
                    name = '-' + name
                self.__privatecommands__.append((prefix + name, callback))

        self.log(f'Running version {__version__}')

    def log(self, *msg, msg_args=[], level=None):
        if len(msg) == 1:
            msg = msg[0]
        else:
            msg = ', '.join(map(str, msg))

        log.add(f'{self.__name__}: {msg}', msg_args, level)

    @property
    def update_url(self):
        repo = CONFIG.get('Repository')
        if not self.update_version or not repo:
            return
        return f'https://github.com/{repo}/releases/tag/{self.update_version}'

    def check_update(self):
        try:
            repo = CONFIG.get('Repository')
            if 'dev' in __version__ or not repo or not self.settings['check_update']:
                self.update_version = None
                return

            current_version = Version.parse(__version__)

            with request.urlopen(f'https://api.github.com/repos/{repo}/releases') as response:
                releases = json.load(response)
                msg = ''
                for release in releases:
                    if release['draft'] or release['prerelease'] or Version.parse(release['tag_name'][1:]) <= current_version:  # noqa
                        continue
                    if not msg:
                        msg += f'New version available (current: {current_version}) at: {release["html_url"]}\n\n'
                        self.update_version = release['tag_name']
                    msg += f'{release["name"]}\n{release["body"]}\n\n'
                if msg:
                    self.log('\n{border}\n{msg}\n{border}'.format(msg=msg.strip(), border='#' * 80))
                else:
                    self.log('No new version available')
        except Exception as e:
            self.log(f'ERROR: Could not fetch update: {e}')

    def stop(self):
        self.auto_update.stop(False)
        self.settings_watcher.stop(False)

    def shutdown_notification(self):
        self.stop()

    def disable(self):
        self.stop()

    def detect_settings_change(self):
        if not hasattr(self, '_settings_before'):
            self._settings_before = set(self.settings.items())
            return

        after = set(self.settings.items())
        if changes := self._settings_before ^ after:
            change_dict = {
                'before': dict(filter(lambda i: i in self._settings_before, changes)),
                'after': dict(filter(lambda i: i in after, changes))
            }
            self.settings_changed(before=self._settings_before,
                                  after=self.settings,
                                  change=change_dict)
            self._settings_before = set(self.settings.items())

    def settings_changed(self, before, after, change):
        self.log(f'Settings change: {json.dumps(change)}')


def tag(tagname, c='', **data):
    tags = tagname.split()
    if (tooltip := data.get('data_tooltip')) and 'title' not in data:
        data['title'] = tooltip
    if len(tags) > 1:
        tags[-1] = tag(tags[-1], c, **data)
        return reduce(lambda c, o: tag(o, c), tags[::-1])

    attrs = ' '.join(map(lambda i: f'{i[0].replace("_", "-")}="{i[1]}"', data.items()))
    return f'<{tagname} {attrs}>{c}</{tagname}>'


def tagger(tagname):
    def wrapper(c='', **data):
        return tag(tagname, c, **data)
    return wrapper


abbr = tagger('abbr')
a = tagger('a')
li = tagger('li')
mark = tagger('mark')
small = tagger('small')
span = tagger('span')


def readable_size(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)


def id_string(string):
    hasher = hashlib.sha1(string.encode('utf-8'))
    return base64.urlsafe_b64encode(hasher.digest()[:10]).decode('ascii')


def readable_size_html(num):
    return abbr(readable_size(num), data_tooltip=format(num, '.2f') if isinstance(num, float) else num)


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


class Plugin(BasePlugin):
    settings = {
        'stats_file': str(BASE_PATH / 'stats.json'),
        'stats_html_file': str(BASE_PATH / 'index.html'),
        'playlist_file': str(BASE_PATH / 'playlist.m3u'),
        'dark_theme': True,
        'auto_regenerate': 30,
        'auto_refresh': False,
        'threshold_auto': True,
        'threshold_file': 2,
        'threshold_user': 5,
    }
    metasettings = {
        'stats_file': {
            'description': '''Raw statistics file
JSON file where containing the raw data''',
            'type': 'file',
            'chooser': 'file',
        },
        'stats_html_file': {
            'description': '''Statistic page file
HTML file presenting the data in a human readable way''',
            'type': 'file',
            'chooser': 'file',
        },
        'playlist_file': {
            'description': '''Playlist file
.m3u playlist file of the top 25 most uploaded songs''',
            'type': 'file',
            'chooser': 'file',
        },
        'dark_theme': {
            'description': '''Dark Theme
Enable / Disable dark theme''',
            'type': 'bool',
        },
        'auto_refresh': {
            'description': '''Auto refresh
Automatically refresh the statistics page every minute''',
            'type': 'bool',
        },
        'auto_regenerate': {
            'description': '''Auto regenerate
Automatically regenerate statistics page every X minutes''',
            'type': 'int',
        },
        'threshold_auto': {
            'description': '''Auto threshold
Automatically set a threshold respective to the gathered data.
Data under the threshold will be hidden from the statistics page.
Overrides both user and file threshold when enabled.''',
            'type': 'bool',
        },
        'threshold_file': {
            'description': '''User threshold
Fix threshold for users.
Only users who downloaded more files than this will be shown on the statistics page.''',
            'type': 'int',
        },
        'threshold_user': {
            'description': '''File threshold
Fix threshold for files.
Only files that have been uploaded more than this will be shown on the statistics page.''',
            'type': 'int',
        },
    }

    default_stats = {'file': {}, 'user': {}, 'day': [0, 0, 0, 0, 0, 0, 0]}

    def init(self):
        super().init()
        self.stats = self.default_stats.copy()

        self.load_stats()

        self.auto_builder = PeriodicJob(name='AutoBuilder',
                                        delay=lambda: self.settings['auto_regenerate'] * 60,
                                        update=self.update_index_html,
                                        before_start=lambda: self.auto_update.first_round.wait())
        self.auto_builder.start()

    def stop(self):
        super().stop()
        self.auto_builder.stop(False)

    def load_stats(self):
        path = Path(self.settings['stats_file'])
        try:
            self.stats = self.default_stats.copy()
            self.stats.update(json.loads(path.read_text()))
        except FileNotFoundError:
            self.log(f'Statistics file does not exist yet. Creating "{path}"')
            self.save_stats()

    def save_stats(self, file=None):
        if not file:
            file = Path(self.settings['stats_file'])
        file.write_text(json.dumps(self.stats))

    def upload_finished_notification(self, user, virtual_path, real_path):
        info = self.stats['file'].get(real_path, {})
        user_info = self.stats['user'].get(user, {})
        try:
            stat = Path(real_path).stat()
        except: # noqa
            self.log(f'Could not get file info for "{real_path}"')
            stat = None

        weekday = datetime.now().weekday()
        self.stats['day'][weekday] = self.stats['day'][weekday] + 1

        self.stats['file'][real_path] = {
            'total': info.get('total', 0) + 1,
            'virtual_path': virtual_path,
            'last_user': user,
            'last_modified': stat.st_mtime if stat else 0,
            'file_size': stat.st_size if stat else 0,
            'total_bytes': info.get('total_bytes', 0) + stat.st_size if stat else 0,
        }

        self.stats['user'][user] = {
            'total': user_info.get('total', 0) + 1,
            'last_file': virtual_path,
            'last_real_file': real_path,
            'total_bytes': user_info.get('total_bytes', 0) + stat.st_size if stat else 0,
        }
        self.save_stats()

    def summary(self):
        users, files = self.stats['user'].values(), self.stats['file'].values()
        total_users = len(users)
        total_files = len(files)

        user_bytes = tuple(filter(None, map(lambda i: i.get('total_bytes'), users)))
        user_files = tuple(map(lambda i: i['total'], users))

        average_bytes_user = readable_size_html(mean(user_bytes))
        median_bytes_user = readable_size_html(median(user_bytes))
        average_files_user = format(mean(user_files), '.2f')
        median_files_user = median(user_files)

        total_uploads_per_file = tuple(map(lambda i: i['total'], files))
        total_bytes_per_file = tuple(filter(None, map(lambda i: i.get('total_bytes'), files)))

        total_uploads = sum(total_uploads_per_file)
        total_bytes = readable_size_html(sum(total_bytes_per_file))

        file_size = tuple(filter(None, map(lambda i: i.get('file_size'), files)))

        average_filesize = readable_size_html(mean(file_size))
        median_filesize = readable_size_html(median(file_size))
        average_bytes = readable_size_html(mean(total_bytes_per_file))
        median_bytes = readable_size_html(median(total_bytes_per_file))
        average_uploads_file = format(mean(total_uploads_per_file), '.2f')
        median_uploads_files = median(total_uploads_per_file)

        return f'''
        <dl>
          <dt>Total unique Users:</dt>
          <dd>{total_users}</dd>
          <dt>Total unique Files:</dt>
          <dd>{total_files}</dd>
          <dt>Total Uploads:</dt>
          <dd>{total_uploads}</dd>
          <dt>Total Bytes:</dt>
          <dd>{total_bytes}</dd>
          <dt>Average per User:</dt>
          <dd>Average Bytes: {average_bytes_user}</dd>
          <dd>Median Bytes: {median_bytes_user}</dd>
          <dd>Average Files: {average_files_user}</dd>
          <dd>Median Files: {median_files_user}</dd>
          <dt>Average per File:</dt>
          <dd>Average Filesize: {average_filesize}</dd>
          <dd>Median Filesize: {median_filesize}</dd>
          <dd>Average Bytes Total: {average_bytes}</dd>
          <dd>Median Bytes Total: {median_bytes}</dd>
          <dd>Average Uploads: {average_uploads_file}</dd>
          <dd>Median Uploads: {median_uploads_files}</dd>
        </dl>
        '''

    def user_threshold(self):
        if self.settings['threshold_auto']:
            uniq_totals = set(map(lambda i: i['total'], self.stats['user'].values()))
            return sorted(uniq_totals)[int(len(uniq_totals) * .25)]
        else:
            return self.settings['threshold_user']

    def user_stats(self, threshold=0):
        html = ''
        for user, data in sorted(self.stats['user'].items(), key=lambda i: i[1]['total'], reverse=True):
            if data['total'] <= threshold:
                continue
            filename = a(Path(data['last_file']).name,
                         href='#file-' + id_string(data['last_real_file']),
                         data_tooltip=f'RP: {data["last_real_file"]}\nVP: {data["last_file"]}',
                         data_tooltip_align='left')

            total_bytes_raw = total_bytes = '-'
            if total_bytes_raw := data.get('total_bytes'):
                total_bytes = readable_size_html(total_bytes_raw)

            html += f'''
            <tr id="user-{id_string(user)}">
                <td>{user}</td>
                <td>{data["total"]}</td>
                <td sorttable_customkey="{total_bytes_raw}">{total_bytes}</td>
                <td>{filename}</td>
            </tr>'''
        return html

    def file_threshold(self):
        if self.settings['threshold_auto']:
            uniq_totals = set(map(lambda i: i['total'], self.stats['file'].values()))
            return sorted(uniq_totals)[int(len(uniq_totals) * .25)]
        else:
            return self.settings['threshold_file']

    def file_stats(self, threshold=0):
        html = ''

        for real_path, file in sorted(self.stats['file'].items(), key=lambda i: i[1]['total'], reverse=True):
            if file['total'] <= threshold:
                continue
            name = a(Path(real_path).name,
                     data_tooltip=f'RP: {real_path}\nVP: {file["virtual_path"]}',
                     href='file:///' + real_path,
                     target='_blank',
                     data_tooltip_align='left')

            total_bytes_raw = total_bytes = '-'
            if total_bytes_raw := file.get('total_bytes'):
                total_bytes = readable_size_html(total_bytes_raw)

            file_size_raw = file_size = '-'
            if file_size_raw := file.get('file_size'):
                file_size = readable_size_html(file_size_raw)

            last_user = a(file['last_user'], href='#user-' + id_string(file['last_user']))

            html += f'''
            <tr id="file-{id_string(real_path)}">
                <td>{name}</td>
                <td>{file["total"]}</td>
                <td sorttable_customkey="{total_bytes_raw}">{total_bytes}</td>
                <td sorttable_customkey="{file_size_raw}">{file_size}</td>
                <td>{last_user}</td>
            </tr>'''
        return html

    def file_link(self, file, base64=False):
        file = Path(file)
        href = f'file:///{file}'
        if base64:
            b64 = urlsafe_b64encode(file.read_bytes()).decode('utf-8')
            href = f'data:application/octet-stream;base64,{b64}'

        return a(file.name,
                 href=href,
                 data_tooltip=file,
                 target='_blank',
                 download=file.name)

    def ranking(self, data, size=5):
        html = ''
        data = sorted(data, key=lambda i: i[1], reverse=True)
        for index in range(size):
            title = score = '-'
            link_id = None
            if len(data) >= index + 1:
                title, score, link_id = data[index]
            if link_id:
                html += li(a(small(f'{score} ') + span(span(title)), href=link_id))
            else:
                html += li(small(f'{score} ') + span(span(title)))
        return html

    def user_ranking(self):
        return self.ranking(tuple(map(lambda i: (i[0], i[1]['total'], '#user-' + id_string(i[0])),
                                      self.stats['user'].items())))

    def file_ranking(self):
        return self.ranking(tuple(map(lambda i: (Path(i[0]).name, i[1]['total'], '#file-' + id_string(i[0])),
                                      self.stats['file'].items())))

    def icons(self):
        icons = ''
        for icon in (BASE_PATH / 'images').glob('*.svg'):
            icons += f'.icon-{icon.stem} {{ background-image: url("file:///{BASE_PATH}/images/{icon.name}"); }}'
        return tag('style', icons.replace('\\', '/'))

    def build_html(self, user_threshold=None, file_threshold=None):
        template = (BASE_PATH / 'template.html').read_text()

        info = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'BASE': str(BASE_PATH).replace('\\', '/') + '/',
            'DARK_THEME': 'checked' if self.settings['dark_theme'] else '',
            'head': '',
            'update': '',
            'summary': self.summary(),
            'stats_link': self.file_link(self.settings['stats_file']),
            'playlist_file': self.file_link(self.settings['playlist_file'], base64=True),
            'userranking': self.user_ranking(),
            'fileranking': self.file_ranking(),
            'icons': self.icons()
        }

        if self.settings['auto_refresh'] and user_threshold is file_threshold is None:
            info['head'] = tag('meta', http_equiv='refresh', content=60)

        if self.update_url and self.update_version:
            info['update'] = tag('h4 a',
                                 'A new update is available. Current: {current} New: {new}'.format(
                                     current=tag('kbd', __version__),
                                     new=tag('kbd', self.update_version[1:])
                                 ), href=self.update_url + self.update_version, target='_blank')

        max_day = max(self.stats['day']) or 1
        for index, day in enumerate(self.stats['day']):
            info[f'day_{index}'] = day
            info[f'day_{index}_p'] = 3 + (97 / max_day * day)

        user_threshold = self.user_threshold() if user_threshold is None else user_threshold
        file_threshold = self.file_threshold() if file_threshold is None else file_threshold
        info.update({
            'user_threshold': user_threshold,
            'file_threshold': file_threshold,
            'userstats': self.user_stats(user_threshold),
            'filestats': self.file_stats(file_threshold),
        })

        return template.format(**info)

    def update_index_html(self):
        file = Path(self.settings['stats_html_file'])
        file.write_text(self.build_html(), encoding='utf-8')
        self.log(f'Statistics generated and saved to "{file}"')
        return file

    def create_m3u(self, songs=[], top_x=25):
        m3u = '#EXTM3U\n#EXTENC: UTF-8\n'
        if not songs:
            all_songs = sorted(self.stats['file'],
                               key=lambda i: self.stats['file'][i]['total'],
                               reverse=True)
            for song in all_songs:
                type = guess_type(song)[0]
                if type and type.startswith('audio'):
                    songs.append(song)
                    if len(songs) == top_x:
                        break

            m3u += f'#PLAYLIST:Top {len(songs)}\n'
        for song in songs:
            m3u += song + '\n'

        file = Path(self.settings['playlist_file'])
        file.write_text(m3u, encoding='utf-8')
        self.log(f'Playlist generated and saved to "{file}"')
        return file

    @command
    def update_stats(self, initiator=None, args=None, page=True, playlist=True):
        if playlist:
            self.create_m3u()

        if page:
            args = args or []
            try:
                thresholds = tuple(map(int, args[:2]))
            except ValueError:
                thresholds = []

            if thresholds:
                with NamedTemporaryFile('w', encoding='utf-8', suffix='.html', delete=False) as file:
                    file.write(self.build_html(*thresholds))
                    filename = file.name
            else:
                filename = self.update_index_html()

            if not initiator:
                return filename
        return returncode['zap']

    @command
    def open_stats(self, page=True, playlist=True):
        if page:
            filename = page if isinstance(page, str) else self.settings['stats_html_file']
            webbrowser.open(filename)
        if playlist:
            startfile(self.settings['playlist_file'])

    @command
    def update_and_open(self,
                        args=None,
                        create_page=True,
                        create_playlist=True,
                        open_page=True,
                        open_playlist=False):
        filename = self.update_stats(args=args, page=create_page, playlist=create_playlist)
        self.open_stats(page=filename if filename and open_page else open_page, playlist=open_playlist)
        return returncode['zap']

    @command
    def reset_stats(self):
        backup = Path(self.settings['stats_file']).with_suffix('.bak.json')
        self.save_stats(backup)
        self.log(f'Created a backup at "{backup}"')
        self.stats = self.default_stats.copy()
        self.save_stats()
        self.log('Statistics have been reset')
        return returncode['zap']

    __publiccommands__ = __privatecommands__ = [
        ('', update_and_open),
        ('playlist', partial(update_and_open, create_page=False, open_page=False, open_playlist=True)),
        ('page', partial(update_and_open, create_playlist=False)),
        ('update', partial(update_and_open, open_page=False)),
        ('reset', reset_stats),
        ('open-page', partial(open_stats, playlist=False)),
        ('open-playlist', partial(open_stats, page=False)),
        ('update-page', partial(update_stats, playlist=False)),
        ('update-playlist', partial(update_stats, page=False)),
    ]
