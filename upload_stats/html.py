"""This module provides functions for generating HTML tags

The functions in this module is used for generating everything HTML related.
From simple tags to more complex tags with attributes and content and even
human-readable sizes with tooltips.

Example:

    .. code-block:: python

        from upload_stats.html import a, abbr, readable_size_html

        file = Path("/path/to/somefile.txt")
        stats = file.stat()

        print(abbr(a(file.name, href=file), readable_size_html(stats.st_size))
        # Output: <abbr title="123.5KB"><a href="/path/to/somefile.txt">somefile.txt</a></abbr>
"""

import hashlib
from base64 import urlsafe_b64encode
from functools import reduce
from typing import Any, Callable, List

__all__ = ["tag", "readable_size", "id_string", "readable_size_html", "abbr", "a", "li", "mark", "small", "span"]


def tag(name: str, content: str = "", **attributes: Any) -> str:
    """Create an HTML tag with the given content and attributes

    Example:

        .. code-block:: python

            print(tag("a", "Link", href="https://example.com"))
            # Output: <a href="https://example.com">Link</a>

    Args:
        name (:obj:`str`): Tag name
        content (:obj:`str`, optional): Content of the tag. Default is an empty string.
        **attributes: Attributes for the tag

    Returns:
        :obj:`str`: HTML tag
    """
    tags = name.split()
    if (tooltip := attributes.get("data_tooltip")) and "title" not in attributes:
        attributes["title"] = tooltip
    if len(tags) > 1:
        tags[-1] = tag(tags[-1], content, **attributes)
        return reduce(lambda c, o: tag(o, c), tags[::-1])

    attrs = " ".join(map(lambda i: f'{i[0].replace("_", "-")}="{i[1]}"', attributes.items()))
    return f"<{name} {attrs}>{content}</{name}>"


def tagger(name: str, required_attributes: List[str] = []) -> Callable[..., str]:
    """Create an alias for a tag

    Example:

        .. code-block:: python

            a = tagger("a")  # Alias for tag("a", ...)
            print(a("Link", href="https://example.com"))
            # Output: <a href="https://example.com">Link</a>

    Args:
        name (:obj:`str`): Tag name
        required_attributes (:obj:`List` of :obj:`str`, optional): Required attributes
            for the tag. Default is an empty list.

    Returns:
        :obj:`typing.Callable`: Tag function
    """

    required_attributes_doc = "\n    ".join([f":obj:`str`: {attr}" for attr in required_attributes])

    def wrapper(content: str = "", **attributes: Any) -> str:
        f"""Create a {name} tag <{name}...>...</{name}>

        Args:
            content (:obj:`str`, optional): Content of the tag. Default is an empty string.
            {required_attributes_doc}
            **attributes: Attributes for the tag

        Returns:
            :obj:`str`: {name} tag

        Raises:
            :obj:`ValueError`: If any required attributes are missing
        """
        if not all(attr in attributes for attr in required_attributes):
            raise ValueError(f"Missing required attributes: {', '.join(required_attributes)}")
        return tag(name, content, **attributes)

    return wrapper


abbr = tagger("abbr")
a = tagger("a", ["href"])
small = tagger("small")
span = tagger("span")
li = tagger("li")
mark = tagger("mark")


def readable_size(num: float, suffix: str = "B") -> str:
    """Convert a number of bytes to a human-readable size

    Args:
        num (:obj:`float`): Number of bytes
        suffix (:obj:`str`, optional): Suffix for the size. Default is "B".

    Returns:
        :obj:`str`: Human-readable size
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Y", suffix)


def id_string(string: str) -> str:
    """Generate a unique ID from a string

    Args:
        string (:obj:`str`): Input string

    Returns:
        :obj:`str`: Unique ID
    """
    hasher = hashlib.sha1(string.encode("utf-8"))
    return urlsafe_b64encode(hasher.digest()[:10]).decode("ascii")


def readable_size_html(num: float) -> str:
    """Convet a number of bytes to a human-readable size with HTML tooltip

    Args:
        num (:obj:`float`): Number of bytes

    Returns:
        :obj:`str`: Human-readable size with HTML tooltip
    """
    return abbr(readable_size(num), data_tooltip=format(num, ".2f") if isinstance(num, float) else num)
