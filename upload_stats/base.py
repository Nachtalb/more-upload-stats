import ast
import json
from pathlib import Path
import re
import sys
import tarfile
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import sleep, time
from urllib import request

from pynicotine.logfacility import log
from pynicotine.pluginsystem import returncode
from pynicotine.pluginsystem import BasePlugin as NBasePlugin

from .utils import BASE_PATH, command


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

    config = CONFIG

    @property
    def __name__(self):
        return CONFIG.get('Name', self.__class__.__name__)

    @property
    def plugin_name(self):
        return BASE_PATH.name

    update_version = None
    protected = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = self.default_settings
        settings.update(self.settings)
        self.settings = settings
        metasettings = self.default_metasettings
        metasettings.update(self.metasettings)
        self.metasettings = metasettings

        self.protected.extend(['.git/', 'backup.tar.gz', '.vim'])

    def init(self):
        default_commands = [
            ('reload', self.reload),
            ('update', self.check_update),
            ('upgrade', self.update_plugin),
        ]

        self.auto_update = PeriodicJob(name='AutoUpdate',
                                       delay=3600,
                                       update=self.check_update)
        self.auto_update.start()

        self.settings_watcher = PeriodicJob(name='SettingsWatcher', update=self.detect_settings_change)
        self.settings_watcher.start()

        if prefix := CONFIG.get('Prefix'):
            public_commands = self.__publiccommands__ + default_commands
            self.__publiccommands__ = []
            private_commands = self.__privatecommands__ + default_commands
            self.__privatecommands__ = []
            for name, callback in public_commands:
                if name:
                    name = '-' + name
                self.__publiccommands__.append((prefix + name, callback))
            for name, callback in private_commands:
                if name:
                    name = '-' + name
                self.__privatecommands__.append((prefix + name, callback))
        else:
            for name, callback in default_commands:
                name = f'{self.plugin_name}-{name}'
                self.__publiccommands__.append((name, callback))
                self.__privatecommands__.append((name, callback))

        self.log(f'Running version {__version__}')

    @command
    def reload(self):
        def _reload(name, plugin_name, handler):
            log.add('#' * 80)
            try:
                log.add(f'# {name}: Disabling plugin...')
                sleep(1)
                try:
                    handler.disable_plugin(plugin_name)
                except Exception as e:
                    log.add(f'# {name}: Failed to diable plugin: {e}')
                    return
                log.add(f'# {name}: Enabling plugin...')
                try:
                    handler.enable_plugin(plugin_name)
                except Exception as e:
                    log.add(f'# {name}: Failed to enable the plugin: {e}')
                    return
                log.add(f'# {name}: Reload complete')
            finally:
                log.add('#' * 80)

        Thread(target=_reload, daemon=True, args=(self.__name__, self.plugin_name, self.parent)).start()
        return returncode['zap']

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

    @command
    def update_plugin(self):
        if not self.update_version:
            self.check_update(quiet=True, force=True)
        if not self.update_version:
            self.log('No updates available')
            return returncode['zap']
        url = f'https://github.com/{CONFIG["Repository"]}/archive/refs/tags/{self.update_version}.tar.gz'
        Thread(target=BasePlugin._update, args=(self.__name__, self.plugin_name,
                                                self.parent, BASE_PATH, self.protected,
                                                url)).start()
        return returncode['zap']

    @staticmethod
    def _update(name, plugin_name, handler, path, protected, tarball_url):
        prefix = f'# {name}: '
        log.add('#' * 80)
        sleep(1)

        class UpdateError(Exception):
            pass

        backup_file = BASE_PATH / 'backup.tar.gz'
        if backup_file.is_file():
            backup_file.unlink()
        rollback_needed = False

        protected_files = set(filter(lambda i: not i.endswith('/'), protected))  # type: ignore
        protected_folders = set(map(lambda i: i[:-1], set(protected) - protected_files))

        def is_protected(file, root):
            relative = str(file.relative_to(root))
            return (
                (file.is_file() and relative in protected_files) or
                (file.is_dir() and relative.startswith(tuple(protected_folders)))
            )

        def clean_folder(folder=BASE_PATH):
            for file in folder.glob('*'):
                if is_protected(file, BASE_PATH):
                    continue
                elif file.is_dir():
                    clean_folder(file)
                file.unlink()

        def move_folder(dic):
            root = next(Path(dic.name).glob('*'))
            for file in root.glob('**/*'):
                if is_protected(file, root):
                    continue
                file.rename(BASE_PATH / file.relative_to(root))

        try:
            try:
                log.add(prefix + 'Disabling plugin...')
                handler.disable_plugin(plugin_name)
                sleep(1)
            except Exception as e:
                raise UpdateError(f'Could not diable plugin "{e}"')
            log.add(prefix + '[OK]')

            try:
                log.add(prefix + 'Creating a backup...')
                with tarfile.open(backup_file, 'w:gz') as tar_handle:
                    tar_handle.add(BASE_PATH, '')
            except Exception as e:
                raise UpdateError(f'Could not create backup "{e}"')
            log.add(prefix + '[OK]')

            dic = TemporaryDirectory()
            try:
                log.add(prefix + 'Download udpate')
                with request.urlopen(tarball_url) as response:
                    with tarfile.open(fileobj=response, mode='r:gz') as tar_handle:
                        tar_handle.extractall(dic.name)
            except Exception as e:
                raise UpdateError(f'Could not download update {e}')
            log.add(prefix + '[OK]')

            try:
                rollback_needed = True
                log.add('Removing old data...')
                clean_folder()
            except Exception as e:
                raise UpdateError(f'Could not remove old data {e}')
            log.add(prefix + '[OK]')

            try:
                log.add('Installing new data...')
                move_folder(dic.name)
            except Exception as e:
                raise UpdateError(f'Could not install new data {e}')
            log.add(prefix + '[OK]')

            try:
                log.add('Enabling plugin...')
                handler.enable_plugin(plugin_name)
            except Exception as e:
                raise UpdateError(f'Could not enable plugin {e}')
            log.add(prefix + '[OK]')
        except Exception as e:
            rollback = ''
            rollback_success = False
            if rollback_needed:
                try:
                    clean_folder()
                    with TemporaryDirectory() as backup_dic:
                        with tarfile.open(backup_file, mode='r:gz') as tar_handle:
                            tar_handle.extractall(backup_dic)
                        move_folder(backup_dic)
                    rollback = 'Rolled back'
                    rollback_success = True
                except Exception as e2:
                    rollback = f'Rollback failed: {e2}'

            reenabled = ''
            if rollback_needed and rollback_success or not rollback_needed:
                try:
                    handler.enable_plugin(plugin_name)
                    reenabled = 'Plugin enabled again'
                except Exception as e2:
                    reenabled = f'Plugin could not be enable again {e2}'

            if isinstance(e, UpdateError):
                msg = prefix + str(e)
            else:
                msg = prefix + f'An error occured: {e}.'

            msg += f'\n\n{rollback}\n\n{reenabled}'
            log.add(msg)
            log.add_important_error(msg.strip())
        else:
            log.add_important_info(prefix + 'Update successful!')
        finally:
            log.add('#' * 80)

    @command
    def check_update(self, quiet=True, force=False):
        try:
            repo = CONFIG.get('Repository')
            if not repo:
                return

            if not force and ('dev' in __version__ or not self.settings['check_update']):
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
                        msg += f'New version of {self.__name__} plugin available (current: {current_version}) at: {release["html_url"]}\n\n'  # noqa
                        self.update_version = release['tag_name']
                    msg += f'{release["name"]}\n{release["body"]}\n\n'
                if not quiet:
                    if msg:
                        self.log('\n{border}\n{msg}\n{border}'.format(msg=msg.strip(), border='#' * 80))
                        log.add_important_info(msg)
                    else:
                        self.log('No new version available')
        except Exception as e:
            self.log(f'ERROR: Could not fetch update: {e}')
        return returncode['zap']

    def stop(self):
        if hasattr(self, 'pre_stop'):
            self.pre_stop()  # type: ignore
        self.auto_update.stop(False)
        self.settings_watcher.stop(False)

        # Module injection cleanup
        module_path = str(BASE_PATH.absolute())
        if module_path in sys.path:
            sys.path.remove(module_path)

        for name in list(sys.modules.keys())[:]:
            if name.startswith(Path(__file__).parent.name):
                sys.modules.pop(name)

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
