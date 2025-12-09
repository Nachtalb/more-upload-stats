import os
import sys
from pathlib import Path

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
from sphinx.application import Sphinx  # noqa: F401

sys.path.insert(0, str(Path("../..").resolve().absolute()))

from docs.auxil.load_config import CONFIG  # noqa: E402

# -- General configuration ------------------------------------------------
# General information about the project.
project = CONFIG["name"]
copyright = CONFIG["copyright"]
author = CONFIG["authors"]

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.

# Import needs to be below the sys.path.insert above
# import npc  # noqa: E402


version = CONFIG["version"]
# The full version, including alpha/beta/rc tags.
release = CONFIG["version"]

# If your documentation needs a minimal Sphinx version, state it here.
needs_sphinx = "6.1.3"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "enum_tools.autoenum",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    #  "sphinx.ext.linkcode",
    "sphinx.ext.extlinks",
    "sphinx_paramlinks",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.mermaid",
]

# Use intersphinx to reference the python builtin library docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "npc": ("https://nicotine-plugin-core-npc.readthedocs.io/stable", None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# Global substitutions
rst_prolog = ""
for file in Path.cwd().glob("../substitutions/*.rst"):
    rst_prolog += "\n" + file.read_text(encoding="utf-8")

# -- Extension settings ------------------------------------------------
napoleon_use_admonition_for_examples = True

# Don't show type hints in the signature - that just makes it hardly readable
# and we document the types anyway
#  autodoc_typehints = "none"

autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"


# Mock imports for pynicotine
autodoc_mock_imports = ["pynicotine"]

# Show docstring for special members
autodoc_default_options = {
    "special-members": True,
    # For some reason, __weakref__ can not be ignored by using "inherited-members" in all cases
    # so we list it here.
    "exclude-members": "__init__, __weakref__",
    "member-order": "bysource",
}


# Fail on warnings & unresolved references etc
nitpicky = True

# Paramlink style
paramlinks_hyperlink_param = "name"

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# Decides the language used for syntax highlighting of code blocks.
highlight_language = "python3"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "furo"

# Theme options are theme-specific and customize the look and feel of a theme
# further. For a list of options available for each theme, see the documentation.
html_theme_options = {
    "navigation_with_keys": True,
    "dark_css_variables": {
        "admonition-title-font-size": "0.95rem",
        "admonition-font-size": "0.92rem",
    },
    "light_css_variables": {
        "admonition-title-font-size": "0.95rem",
        "admonition-font-size": "0.92rem",
    },
    "footer_icons": [
        {
            "name": "Nachtalb",
            "url": "https://t.me/nachtalb/",
            # Following svg is from https://react-icons.github.io/react-icons/search?q=telegram
            "html": (
                '<svg stroke="currentColor" fill="currentColor" stroke-width="0" '
                'viewBox="0 0 16 16" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg">'
                '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM8.287 5.906c-.778.324-2.334.994'
                "-4.666 2.01-.378.15-.577.298-.595.442-.03.243.275.339.69.47l.175.055c.408.133."
                "958.288 1.243.294.26.006.549-.1.868-.32 2.179-1.471 3.304-2.214 3.374-2.23.0"
                "5-.012.12-.026.166.016.047.041.042.12.037.141-.03.129-1.227 1.241-1.846 1.81"
                "7-.193.18-.33.307-.358.336a8.154 8.154 0 0 1-.188.186c-.38.366-.664.64.015 1.08"
                "8.327.216.589.393.85.571.284.194.568.387.936.629.093.06.183.125.27.187.331.23"
                "6.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.426 "
                "1.426 0 0 0-.013-.315.337.337 0 0 0-.114-.217.526.526 0 0 0-.31-.093c-.3.005-.7"
                '63.166-2.984 1.09z"></path></svg>'
            ),
            "class": "",
        },
        {  # Github logo
            "name": "GitHub",
            "url": "https://github.com/Nachtalb/more-upload-stats",
            "html": (
                '<svg stroke="currentColor" fill="currentColor" stroke-width="0" '
                'viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 '
                "2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.4"
                "9-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23"
                ".82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 "
                "0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.2"
                "7 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.5"
                "1.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 "
                '1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z">'
                "</path></svg>"
            ),
            "class": "",
        },
    ],
}

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = f"{project}<br> v{version}"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_permalinks_icon = "¶"  # Furo's default permalink icon is `#` which doesn't look great imo.

# Output file base name for HTML help builder.
htmlhelp_basename = "npc-doc"

# The base URL which points to the root of the HTML documentation. It is used to indicate the
# location of document using The Canonical Link Relation. Default: ''.
# Set canonical URL from the Read the Docs Domain
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

# Tell Jinja2 templates the build is running on Read the Docs
html_context = {}
if os.environ.get("READTHEDOCS", "") == "True":
    html_context["READTHEDOCS"] = True

# -- Scripts ------------------------------------------------------------

from docs.auxil.no_docstring import NoDocstringDocumenter  # noqa: E402
from docs.auxil.sphinx_hooks import autodoc_process_bases  # noqa: E402


def setup(app):
    app.connect("autodoc-process-bases", autodoc_process_bases)
    app.add_autodocumenter(NoDocstringDocumenter, override=True)
