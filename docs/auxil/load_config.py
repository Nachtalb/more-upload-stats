import configparser
from ast import literal_eval
from datetime import date
from pathlib import Path

current_year = date.today().year

CONFIG = {
    "name": "nicotine-plugin-core",
    "description": "A powerful core for building feature-rich Nicotine+ plugins with ease.",
    "authors": "Nachtalb",
    "version": "0.1.0",
    "copyright": f"2021-{current_year}, Nachtalb",
}

pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
config = configparser.ConfigParser()
config.read(str(pyproject))

for option in CONFIG:
    if config.has_option("tool.poetry", option):
        value = literal_eval(config.get("tool.poetry", option))

        if isinstance(value, list):
            value = ", ".join(value)

        CONFIG[option] = value
