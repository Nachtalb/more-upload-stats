from base64 import urlsafe_b64encode
from datetime import datetime
from functools import partial
import json
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
import webbrowser

from pynicotine.pluginsystem import returncode

from .core.base import BasePlugin, PeriodicJob, __version__
from .core.utils import command, startfile
from .tag import a, id_string, li, readable_size_html, small, span, tag
from .utils import BUILD_PATH, HTML_PATH, create_m3u


class Plugin(BasePlugin):
    settings = {
        'stats_file': str(BUILD_PATH / 'stats.json'),
        'stats_html_file': str(BUILD_PATH / 'index.html'),
        'playlist_file': str(BUILD_PATH / 'playlist.m3u'),
        'dark_theme': True,
        'quiet': False,
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
        'quiet': {
            'description': '''Quieter
Don\'t print as much to the console''',
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
                                        update=self.update_stats,
                                        before_start=lambda: self.auto_update.first_round.wait())
        self.auto_builder.start()

    def pre_stop(self):
        self.auto_builder.stop(False)

    def load_stats(self):
        path = Path(self.settings['stats_file'])
        try:
            self.stats = self.default_stats.copy()
            self.stats.update(json.loads(path.read_text()))
        except FileNotFoundError:
            self.log(f'Statistics file does not exist yet. Creating "{path}"')
            self.save_stats()

    def log(self, *msg, msg_args=[], level=None, with_prefix=True, force=False):
        if self.settings['quiet'] and not force and not level:
            return
        super().log(*msg, msg_args=msg_args, level=level, with_prefix=with_prefix)

    def settings_changed(self, before, after, change):
        if not self.settings['quiet']:
            super().settings_changed(before, after, change)

    def save_stats(self, file=None):
        if not file:
            file = Path(self.settings['stats_file'])
        file.parent.mkdir(parents=True, exist_ok=True)
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

        user_bytes = tuple(filter(None, map(lambda i: i.get('total_bytes'), users))) or [0]
        user_files = tuple(map(lambda i: i['total'], users)) or [0]

        average_bytes_user = readable_size_html(mean(user_bytes))
        median_bytes_user = readable_size_html(median(user_bytes))
        average_files_user = format(mean(user_files), '.2f')
        median_files_user = median(user_files)

        total_uploads_per_file = tuple(map(lambda i: i['total'], files)) or [0]
        total_bytes_per_file = tuple(filter(None, map(lambda i: i.get('total_bytes'), files))) or [0]

        total_uploads = sum(total_uploads_per_file)
        total_bytes = readable_size_html(sum(total_bytes_per_file))

        file_size = tuple(filter(None, map(lambda i: i.get('file_size'), files))) or [0]

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
            if not self.stats['user']:
                return 0
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
            if not self.stats['file']:
                return 0
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
            html += li(a(small(f'{score} ') + span(span(title)), href=link_id or '#'))
        return html

    def user_ranking(self):
        return self.ranking(tuple(map(lambda i: (i[0], i[1]['total'], '#user-' + id_string(i[0])),
                                      self.stats['user'].items())))

    def file_ranking(self):
        return self.ranking(tuple(map(lambda i: (Path(i[0]).name, i[1]['total'], '#file-' + id_string(i[0])),
                                      self.stats['file'].items())))

    def icons(self):
        icons = ''
        for icon in (HTML_PATH / 'images').glob('*.svg'):
            icons += f'.icon-{icon.stem} {{ background-image: url("file:///{HTML_PATH}/images/{icon.name}"); }}'
        return tag('style', icons.replace('\\', '/'))

    def build_html(self, user_threshold=None, file_threshold=None):
        template = (HTML_PATH / 'template.html').read_text()

        info = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'BASE': str(HTML_PATH).replace('\\', '/') + '/',
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
                                 ), href=self.update_url, target='_blank')

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

    def create_m3u(self):
        songs = sorted(self.stats['file'], reverse=True, key=lambda i: self.stats['file'][i]['total'])
        file = self.settings['playlist_file']
        create_m3u('TOP #25', songs, file, max_files=25)
        self.log(f'Playlist generated and saved to "{file}"')

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
        self.log(f'Created a backup at "{backup}"', force=True)
        self.stats = self.default_stats.copy()
        self.save_stats()
        self.log('Statistics have been reset', force=True)
        return returncode['zap']

    __publiccommands__ = __privatecommands__ = [
        ('', update_and_open),
        ('playlist', partial(update_and_open, create_page=False, open_page=False, open_playlist=True)),
        ('page', partial(update_and_open, create_playlist=False)),
        ('build', update_stats),
        ('reset', reset_stats),
        ('open', open_stats),
        ('open-page', partial(open_stats, playlist=False)),
        ('open-playlist', partial(open_stats, page=False)),
        ('build-page', partial(update_stats, playlist=False)),
        ('build-playlist', partial(update_stats, page=False)),
    ]
