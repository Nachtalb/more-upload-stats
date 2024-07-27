#!/usr/bin/env python
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Union

from generate_changelog import arg_main as generate_changelog
from generate_changelog import main as generate_changelog_main

BASE_PATH = Path(__file__).resolve().parent
CWD = Path().resolve()


def _cwd_or_base_path(file: Union[str, Path]) -> Path:
    final_file = CWD / file
    if final_file.exists():
        return final_file
    return BASE_PATH / file


def build_docs() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    generate_changelog()

    docs_dir = _cwd_or_base_path("docs")
    os.chdir(docs_dir)
    subprocess.run(["make", "html"])


def open_docs() -> None:
    index_path = _cwd_or_base_path("docs/build/html/index.html")
    webbrowser.open(f"file://{index_path}")


def check() -> None:
    subprocess.run(["pre-commit", "run", "--all-files"])


def build_changelog() -> None:
    generate_changelog_main()


def change_version() -> None:
    args = sys.argv[1:]
    file = str(BASE_PATH / "change-version-doc.sh")
    subprocess.run([file, *args])


def release() -> None:
    args = sys.argv[1:]
    file = str(BASE_PATH / "release.sh")
    subprocess.run([file, *args])
