import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
import webbrowser

from pynicotine.pluginsystem import BasePlugin

BASE_PATH = Path(__file__).parent


def tag(tagname, content, **data):
    attrs = ' '.join(map(lambda i: f'{i[0]}="{i[1]}"', data.items()))
    return f'<{tagname} {attrs}>{content}</{tagname}>'


def tagger(tagname):
    def wrapper(content, **data):
        return tag(tagname, content, **data)
    return wrapper


abbr = tagger('abbr')
a = tagger('a')


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


class Plugin(BasePlugin):

    __name__ = 'UploadStats'
    settings = {
        'stats_file': str(BASE_PATH / 'stats.json'),
        'dark_theme': True,
    }
    metasettings = {
        'stats_file': {
            'description': 'Statistics Savepath',
            'type': 'file',
            'chooser': 'file',
        },
        'dark_theme': {
            'description': 'Enable Dark Theme',
            'type': 'bool',
        }
    }

    def init(self):
        self.stats = {'file': {}, 'user': {}}
        self.ready = False

        self.load_stats()

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

    def save_stats(self):
        Path(self.settings['stats_file']).write_text(json.dumps(self.stats))

    def upload_finished_notification(self, user, virtual_path, real_path):
        info = self.stats['file'].get(real_path, {})
        try:
            stat = Path(real_path).stat()
        except: # noqa
            self.log(f'Could not get file info for "{real_path}"')
            stat = None

        self.stats['file'][real_path] = {
            'total': info.get('total', 0) + 1,
            'virtual_path': virtual_path,
            'last_user': user,
            'last_modified': stat.st_mtime if stat else '',
            'file_size': stat.st_size if stat else '',
            'total_bytes': info.get('total_bytes', 0) + stat.st_size if stat else '',
        }

        self.stats['user'][user] = {
            'total': self.stats['user'].get(user, {}).get('total', 0) + 1,
            'last_file': virtual_path,
            'last_real_file': real_path,
            'total_bytes': info.get('total_bytes', 0) + stat.st_size if stat else '',
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

    def user_stats(self):
        html = ''
        for user, data in sorted(self.stats['user'].items(), key=lambda i: i[1]['total'], reverse=True):
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

    def file_stats(self):
        html = ''
        for real_path, file in sorted(self.stats['file'].items(), key=lambda i: i[1]['total'], reverse=True):
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

    def build_html(self):
        template = (BASE_PATH / 'template.html').read_text()

        info = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'BASE': str(BASE_PATH).replace('\\', '/') + '/',
            'userstats': self.user_stats(),
            'filestats': self.file_stats(),
            'summary': self.summary(),
            'stats_link': self.stats_link(),
            'THEME': 'dark' if self.settings['dark_theme'] else '',
        }
        return template.format(**info)

    def open_stats(self, *_):
        with NamedTemporaryFile(suffix='.html', mode='w', delete=False, encoding='utf-8') as file:
            file.write(self.build_html())
            webbrowser.open(file.name)

    __privatecommands__ = __publiccommands__ = [('upstats', open_stats)]
