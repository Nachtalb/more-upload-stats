import base64
from datetime import datetime
from functools import partial, reduce, wraps
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
from statistics import mean, median
import subprocess
from tempfile import NamedTemporaryFile
from threading import Event, Thread
from time import sleep, time
from urllib import request
import webbrowser
from mimetypes import guess_type

from pynicotine.pluginsystem import BasePlugin, returncode

BASE_PATH = Path(__file__).parent
__version__ = (BASE_PATH / 'PLUGININFO').read_text().split('\n')[0].split('=')[1].replace('"', '')  # noqa


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
    def wrapper(self, initiator=None, argstring=None, *args, **kwargs):
        argspec = inspect.signature(func)
        command_args = list(filter(None, map(str2num, map(str.strip, (argstring or '').split()))))
        extra_args = []

        if 'initiator' in argspec.parameters and 'initiator' not in kwargs and initiator is not None:  # noqa
            extra_args.append(initiator)
        if 'args' in argspec.parameters and 'args' not in kwargs and argstring is not None:
            extra_args.append(command_args)

        return func(self, *extra_args, *args, **kwargs)
    return wrapper


def str2num(string):
    if string.isdigit():
        return int(string)
    try:
        string = float(string)
    except ValueError:
        pass
    return string


class PeriodicJob(Thread):
    __stopped = False
    last_run = None

    name = ''
    delay = 1
    _min_delay = 1

    def __init__(self, delay=None, update=None, name=None, before_start=None):
        super().__init__(name=name or self.name)
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


class Plugin(BasePlugin):

    __name__ = 'Upload Statistics DEV'
    settings = {
        'stats_file': str(BASE_PATH / 'stats.json'),
        'stats_html_file': str(BASE_PATH / 'index.html'),
        'playlist_file': str(BASE_PATH / 'playlist.m3u'),
        'dark_theme': True,
        'check_update': True,
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
        'check_update': {
            'description': '''Check for Updates
Check for updates on start and periodically''',
            'type': 'bool',
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

    update_url = 'https://api.github.com/repos/Nachtalb/more-upload-stats/tags'
    release_url = 'https://github.com/Nachtalb/more-upload-stats/releases/tag/'
    update_version = None

    default_stats = {'file': {}, 'user': {}, 'day': [0, 0, 0, 0, 0, 0, 0]}

    def init(self):
        self.stats = self.default_stats.copy()
        self.ready = False

        self.load_stats()

        self.auto_update = PeriodicJob(name='AutoUpdate',
                                       delay=3600,
                                       update=self.check_update)
        self.auto_update.start()

        self.auto_builder = PeriodicJob(name='AutoBuilder',
                                        delay=lambda: self.settings['auto_regenerate'] * 60,
                                        update=self.update_index_html,
                                        before_start=lambda: self.auto_update.first_round.wait())
        self.auto_builder.start()
        self.log(f'Running version {__version__}')

    def check_update(self):
        try:
            if 'dev' in __version__ or not self.settings['check_update']:
                self.update_version = None
                return

            self.log('Checking for updates')

            with request.urlopen(self.update_url) as file:
                latest_info = next(iter(json.load(file)), {})
                latest_version = latest_info.get('name', '')
                if latest_version.replace('v', '') != __version__:
                    self.update_version = latest_version
                    msg = f'# A new version of "Upload Statistics" is available: {latest_version} {self.release_url}{latest_version}'  # noqa
                    self.log('\n{border}\n{msg}\n{border}'.format(msg=msg, border='#' * len(msg)))
        except Exception as e:
            self.log(f'ERROR: Could not fetch update {e}')

    def stop(self):
        self.auto_builder.stop(False)
        self.auto_update.stop(False)

    def disable(self):
        self.stop()

    def shutdown_notification(self):
        self.stop()

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

    def stats_link(self):
        filepath = self.settings['stats_file']
        name = Path(filepath).name
        return a(name,
                 href='file:///' + filepath,
                 data_tooltip=filepath,
                 target='_blank',
                 download=name)

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
            'stats_link': self.stats_link(),
            'userranking': self.user_ranking(),
            'fileranking': self.file_ranking(),
            'icons': self.icons()
        }

        if self.settings['auto_refresh'] and user_threshold is file_threshold is None:
            info['head'] = tag('meta', http_equiv='refresh', content=60)

        if self.update_version:
            info['update'] = tag('h4 a',
                                 'A new update is available. Current: {current} New: {new}'.format(
                                     current=tag('kbd', __version__),
                                     new=tag('kbd', self.update_version[1:])
                                 ), href=self.release_url + self.update_version, target='_blank')

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
    def update_stats(self, args=[], page=True, playlist=True):
        if playlist:
            self.create_m3u()

        if page:
            try:
                thresholds = tuple(map(int, args[:2]))
            except ValueError:
                thresholds = []

            if thresholds:
                with NamedTemporaryFile('w', encoding='utf-8', suffix='.html', delete=False) as file:
                    file.write(self.build_html(*thresholds))
            else:
                self.update_index_html()
        return returncode['zap']

    @command
    def open_stats(self, page=True, playlist=True):
        if page:
            webbrowser.open(self.settings['stats_html_file'])
        if playlist:
            startfile(self.settings['playlist_file'])

    @command
    def update_and_open(self,
                        args=None,
                        create_page=True,
                        create_playlist=True,
                        open_page=True,
                        open_playlist=False):
        self.update_stats(args=args, page=create_page, playlist=create_playlist)
        self.open_stats(page=open_page, playlist=open_playlist)
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
        ('dupstats', update_and_open),
        ('dup', update_and_open),
        ('dup-playlist', partial(update_and_open, create_page=False, open_page=False, open_playlist=True)),
        ('dup-page', partial(update_and_open, create_playlist=False)),
        ('dup-update', partial(update_and_open, open_page=False)),
        ('dup-reset', reset_stats),
        ('dup-open-page', partial(open_stats, playlist=False)),
        ('dup-open-playlist', partial(open_stats, page=False)),
        ('dup-update-page', partial(update_stats, playlist=False)),
        ('dup-update-playlist', partial(update_stats, page=False)),
    ]
