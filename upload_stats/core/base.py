import json
from pathlib import Path
import sys
from threading import Thread
from time import sleep

from pynicotine.pluginsystem import returncode
from pynicotine.pluginsystem import BasePlugin as NBasePlugin

from .utils import BASE_PATH, command, log, get
from .threading import PeriodicJob
from .version import Version
from . import CONFIG, __version__

__all__ = ['BasePlugin']


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

    plugin_config = dict([(key.lower(), value) for key, value in CONFIG.items()])

    @property
    def __name__(self):
        return self.plugin_config.get('name', self.__class__.__name__)

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
        default_commands = [
            ('reload', self.reload),
            ('update', self.check_update),
        ]

        self.auto_update = PeriodicJob(name='AutoUpdate',
                                       delay=3600 * 6,  # Every 6h
                                       update=self.check_update)
        self.auto_update.start()

        self.settings_watcher = PeriodicJob(name='SettingsWatcher', update=self.detect_settings_change)
        self.settings_watcher.start()

        if prefix := self.plugin_config.get('prefix'):
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

    @property
    def plugin_name(self):
        return BASE_PATH.name

    @command
    def reload(self):
        def _reload(name, plugin_name, handler):
            log('#' * 80)
            try:
                log(f'# {name}: Disabling plugin...')
                sleep(1)
                try:
                    handler.disable_plugin(plugin_name)
                except Exception as e:
                    log(f'# {name}: Failed to diable plugin: {e}')
                    return
                log(f'# {name}: Enabling plugin...')
                try:
                    handler.enable_plugin(plugin_name)
                except Exception as e:
                    log(f'# {name}: Failed to enable the plugin: {e}')
                    return
                log(f'# {name}: Reload complete')
            finally:
                log('#' * 80)

        Thread(target=_reload, daemon=True, args=(self.__name__, self.plugin_name, self.parent)).start()
        return returncode['zap']

    def log(self, *msg, msg_args=[], level=None, with_prefix=True):
        log(*msg, msg_args=msg_args, level=level, prefix=f'{self.__name__}: ' if with_prefix else None)

    def error_window(self, *msg, msg_args=[], with_prefix=True):
        self.log(*msg, msg_args=msg_args, level='important_error', with_prefix=with_prefix)

    def info_window(self, *msg, msg_args=[], with_prefix=True):
        self.log(*msg, msg_args=msg_args, level='important_info', with_prefix=with_prefix)

    @property
    def update_url(self):
        repo = self.plugin_config.get('repository')
        if not self.update_version or not repo:
            return
        return f'https://github.com/{repo}/releases/tag/{self.update_version}'

    @command
    def check_update(self, force=False):
        try:
            repo = self.plugin_config.get('repository')
            if not repo and force:
                self.log('This update endpoint defined for this plugin')
                return
            if not force and repo and 'dev' in __version__ or not self.settings['check_update']:
                self.update_version = None
                return

            current_version = Version.parse(__version__)

            with get(f'https://api.github.com/repos/{repo}/releases') as response:
                msg = ''
                for release in response.json:
                    if release['draft'] or release['prerelease'] or Version.parse(release['tag_name'][1:]) <= current_version:  # noqa
                        continue
                    if not msg:
                        msg += f'New version of {self.__name__} plugin available (current: {current_version}) at: {release["html_url"]}\n\n'  # noqa
                        self.update_version = release['tag_name']
                    msg += f'{release["name"]}\n{release["body"]}\n\n'
                if msg:
                    self.log('\n{border}\n{msg}\n{border}'.format(msg=msg.strip(), border='#' * 80))
                    self.info_window(msg)
                else:
                    self.log('No new version available')
        except Exception as e:
            self.log(f'ERROR: Could not fetch update: {e}')

    def stop(self):
        if hasattr(self, 'pre_stop'):
            self.pre_stop()
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
            self._settings_before = set([(k, tuple(v) if isinstance(v, list) else v)
                                         for k, v in self.settings.items()])
            return

        after = set([(k, tuple(v) if isinstance(v, list) else v)
                     for k, v in self.settings.items()])
        if changes := self._settings_before ^ after:
            change_dict = {
                'before': dict(filter(lambda i: i in self._settings_before, changes)),
                'after': dict(filter(lambda i: i in after, changes))
            }
            self.settings_changed(before=self._settings_before,
                                  after=self.settings,
                                  change=change_dict)
            self._settings_before = after

    def settings_changed(self, before, after, change):
        self.log(f'Settings change: {json.dumps(change)}')
