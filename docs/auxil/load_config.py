import tomllib
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

with open(pyproject, "rb") as f:
    toml_data = tomllib.load(f)

# UV uses standard PEP 621 metadata located under the [project] key
project_metadata = toml_data.get("project", {})

for option in CONFIG:
    if option in project_metadata:
        value = project_metadata[option]

        # Handle 'authors' specifically because in PEP 621 it is a list of dicts:
        # authors = [{ name = "Nachtalb", email = "..." }]
        if option == "authors" and isinstance(value, list):
            # Extract names and join them
            value = ", ".join(
                author.get("name", "") for author in value if isinstance(author, dict) and "name" in author
            )

        CONFIG[option] = value
