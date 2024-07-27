def autodoc_process_bases(app, name, obj, option, bases: list) -> None:  # type: ignore
    """Here we fine tune how the base class's classes are displayed."""
    for idx, raw_base in enumerate(bases):
        # let's use a string representation of the object
        base = str(raw_base)
        print("#" * 8, base, raw_base)

        # Special case because base classes are in std lib:
        if "Enum" in base:
            __import__("ipdb").set_trace()
            bases[idx] = ":class:`enum.Enum`"
            continue

        elif "StringEnum" in base == "<enum 'StringEnum'>":
            bases[idx] = ":class:`enum.Enum`"
            bases.insert(0, ":class:`str`")
            continue

        elif "IntEnum" in base:
            bases[idx] = ":class:`enum.IntEnum`"
            continue
