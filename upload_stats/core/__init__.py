import ast

from .utils import BASE_PATH, log

config_file = BASE_PATH / 'PLUGININFO'
CONFIG = dict([(key, ast.literal_eval(value) if value.startswith('[') else value[1:-1].replace('\\n', '\n'))
               for key, value in map(lambda i: i.split('=', 1), filter(None, config_file.read_text().split('\n')))])

__version__ = CONFIG.get('Version', '0.0.1')

if 'dev' in __version__:
    if 'Prefix' in CONFIG:
        log('#' * 40 + f'\nAttention: You are running this in dev mode. Prefix will be /d{CONFIG["Prefix"]}')
        CONFIG['Prefix'] = 'd' + CONFIG['Prefix']
    CONFIG['Name'] += ' DEV'
