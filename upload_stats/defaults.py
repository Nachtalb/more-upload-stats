"""This module contains the default constants for this plugin."""

import os

from .npc import BASE_PATH

BUILD_PATH = BASE_PATH / "build"
"""Path to the build directory"""
HTML_PATH = BASE_PATH / "html"
"""Path to the HTML directory"""
REL_HTML_PATH = os.path.relpath(HTML_PATH, BUILD_PATH)
"""Relative path from the :data:`BUILD_PATH` to the :data:`HTML_PATH`"""
