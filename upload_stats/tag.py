import hashlib
from base64 import urlsafe_b64encode
from functools import reduce
from typing import Any

__all__ = ["tag", "readable_size", "id_string", "readable_size_html", "abbr", "a", "li", "mark", "small", "span"]


def tag(tagname: str, c: str = "", **data: Any) -> str:
    tags = tagname.split()
    if (tooltip := data.get("data_tooltip")) and "title" not in data:
        data["title"] = tooltip
    if len(tags) > 1:
        tags[-1] = tag(tags[-1], c, **data)
        return reduce(lambda c, o: tag(o, c), tags[::-1])

    attrs = " ".join(map(lambda i: f'{i[0].replace("_", "-")}="{i[1]}"', data.items()))
    return f"<{tagname} {attrs}>{c}</{tagname}>"


def tagger(tagname: str):  # type: ignore[no-untyped-def] # Callable[[str, **Any], str]
    def wrapper(c: str = "", **data: Any) -> str:
        return tag(tagname, c, **data)

    return wrapper


abbr = tagger("abbr")
a = tagger("a")
small = tagger("small")
span = tagger("span")
li = tagger("li")
mark = tagger("mark")


def readable_size(num: float, suffix: str = "B") -> str:
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Y", suffix)


def id_string(string: str) -> str:
    hasher = hashlib.sha1(string.encode("utf-8"))
    return urlsafe_b64encode(hasher.digest()[:10]).decode("ascii")


def readable_size_html(num: float) -> str:
    return abbr(readable_size(num), data_tooltip=format(num, ".2f") if isinstance(num, float) else num)  # type: ignore[no-any-return]
