import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
from threading import Thread
from time import sleep, time
import webbrowser

from pynicotine.pluginsystem import BasePlugin, returncode

BASE_PATH = Path(__file__).parent


def tag(tagname, c='', **data):
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
    return abbr(readable_size(num), title=format(num, '.2f') if isinstance(num, float) else num)


class PeriodicJob(Thread):
    __stopped = False
    __pause = False
    last_run = None

    name = ''
    delay = 1
    _min_delay = 1

    def __init__(self, delay=None, update=None, name=None):
        super().__init__(name=name or self.name)
        self.delay = delay or self.delay
        if update:
            self.update = update

    def time_to_work(self):
        delay = self.delay() if callable(self.delay) else self.delay
        return not self.__pause and (not self.last_run or time() - self.last_run > delay)

    def run(self):
        while not self.__stopped:
            if self.time_to_work():
                self.update()
                self.last_run = time()
            sleep(self._min_delay)

    def stop(self, wait=True):
        self.__stopped = True
        if wait and self.is_alive():
            self.join()

    def pause(self):
        self.__pause = True

    def resume(self):
        self.__pause = False


class Plugin(BasePlugin):

    __name__ = 'Upload Statistics DEV'
    settings = {
        'stats_file': str(BASE_PATH / 'stats.json'),
        'stats_html_file': str(BASE_PATH / 'index.html'),
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

    def init(self):
        self.stats = {'file': {}, 'user': {}}
        self.ready = False

        self.load_stats()

        self.auto_builder = PeriodicJob(name='AutoBuilder',
                                        delay=lambda: self.settings['auto_regenerate'] * 60,
                                        update=self.update_index_html)
        self.auto_builder.start()

    def stop(self):
        self.auto_builder.stop(False)

    def disable(self):
        self.stop()

    def shutdown_notification(self):
        self.stop()

    def load_stats(self):
        path = Path(self.settings['stats_file'])
        try:
            self.stats = json.loads(path.read_text())
            if 'file' not in self.stats:
                self.stats['file'] = {}
            if 'user' not in self.stats:
                self.stats['user'] = {}
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
                         title=f'RP: {data["last_real_file"]}\nVP: {data["last_file"]}')

            if 'total_bytes' in data:
                total_bytes = readable_size_html(data['total_bytes'])
            else:
                total_bytes = '-'

            html += f'''
            <tr id="user-{id_string(user)}">
                <td>{user}</td>
                <td>{data["total"]}</td>
                <td>{total_bytes}</td>
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
                     title=f'RP: {real_path}\nVP: {file["virtual_path"]}',
                     href='file:///' + real_path,
                     target='_blank')

            if 'file_size' in file and 'total_bytes' in file:
                total_bytes = abbr(readable_size(file['total_bytes']),
                                   title='Filesize: {filesize} ({raw_filesize})\nTotal Bytes: {total_bytes}'.format(
                                       raw_filesize=file['file_size'],
                                       filesize=readable_size(file['file_size']),
                                       total_bytes=file['total_bytes']))
            else:
                total_bytes = '-'

            last_user = a(file['last_user'], href='#user-' + id_string(file['last_user']))

            html += f'''
            <tr id="file-{id_string(real_path)}">
                <td>{name}</td>
                <td>{file["total"]}</td>
                <td>{total_bytes}</td>
                <td>{last_user}</td>
            </tr>'''
        return html

    def stats_link(self):
        filepath = self.settings['stats_file']
        name = Path(filepath).name
        return a(name,
                 href='file:///' + filepath,
                 title=filepath,
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
                html += li(a(mark(span(title)) + small(score), href=link_id))
            else:
                html += li(mark(span(title)) + small(score))
        return html

    def user_ranking(self):
        return self.ranking(tuple(map(lambda i: (i[0], i[1]['total'], '#user-' + id_string(i[0])),
                                      self.stats['user'].items())))

    def file_ranking(self):
        return self.ranking(tuple(map(lambda i: (Path(i[0]).name, i[1]['total'], '#file-' + id_string(i[0])),
                                      self.stats['file'].items())))

    def build_html(self, user_threshold=None, file_threshold=None):
        template = (BASE_PATH / 'template.html').read_text()

        info = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'BASE': str(BASE_PATH).replace('\\', '/') + '/',
            'DARK_THEME': 'checked' if self.settings['dark_theme'] else '',
            'head': '',
            'summary': self.summary(),
            'stats_link': self.stats_link(),
            'userranking': self.user_ranking(),
            'fileranking': self.file_ranking(),
        }

        if self.settings['auto_refresh'] and user_threshold is file_threshold is None:
            info['head'] = tag('meta', http_equiv='refresh', content=60)

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

    def open_stats(self, _, args):
        args = tuple(filter(None, map(str.strip, args.split())))
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

        webbrowser.open(str(filename))
        return returncode['zap']

    def reset_stats(self, *_):
        backup = Path(self.settings['stats_file']).with_suffix('.bak.json')
        self.save_stats(backup)
        self.log(f'Created a backup at "{backup}"')
        self.stats = {}
        self.save_stats()
        self.load_stats()
        self.log('Statistics have been reset')
        return returncode['zap']

    __privatecommands__ = __publiccommands__ = [
        ('dupstats', open_stats),
        ('dupstats-reset', reset_stats)
    ]
