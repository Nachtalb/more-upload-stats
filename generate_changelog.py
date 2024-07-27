#!/usr/bin/env python
import argparse
import ast
import logging
import os
import sys
from typing import Any, List, Literal, NamedTuple, Optional, Set

LOG = logging.getLogger(__name__)
# Find first dir with __init__.py file
DEFAULT_DIR = next((d for d in os.listdir() if os.path.exists(os.path.join(d, "__init__.py"))), "")

# Find an NPC module if it exists
DEFAULT_EXCLUDE = []
if DEFAULT_DIR and (npc := os.path.join(DEFAULT_DIR, "npc")) and os.path.exists(npc):
    DEFAULT_EXCLUDE = [npc]

DEFAULT_FILE = "CHANGELOG.rst"


Entry = NamedTuple(
    "Entry",
    [
        ("version", str),
        ("change_type", str),
        ("description", str),
        ("item_name", str),
        ("fully_qualified_name", str),
        ("type", Literal["func", "class", "variable", "meth", "mod"]),
    ],
)


def get_init_exports(directory: str) -> Set[str]:
    init_path = os.path.join(directory, "__init__.py")
    if not os.path.exists(init_path):
        return set()

    with open(init_path, "r") as f:
        tree = ast.parse(f.read())

    exports = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                exports.add(alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    exports.add(target.id)

    return exports


def get_fully_qualified_name(
    node: ast.AST,
    module_name: str,
    class_name: Optional[str] = None,
    init_exports: Set[str] = set(),
) -> str:
    if isinstance(node, ast.FunctionDef):
        name = f"{class_name}.{node.name}" if class_name else node.name
        return f"{name}" if name in init_exports or class_name in init_exports else f"{module_name}.{name}"
    elif isinstance(node, ast.ClassDef):
        return node.name if node.name in init_exports else f"{module_name}.{node.name}"
    elif isinstance(node, ast.Assign) and len(node.targets) == 1:
        if isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            return name if name in init_exports else f"{module_name}.{name}"
    return module_name


def get_item_type(node: ast.AST, in_class: bool) -> Literal["func", "class", "variable", "meth"]:
    if isinstance(node, ast.FunctionDef):
        return "meth" if in_class else "func"
    elif isinstance(node, ast.ClassDef):
        return "class"
    elif isinstance(node, ast.Assign):
        return "variable"
    return "func"  # Default to function if unknown


def parse_version_info(node: ast.AST, module_name: str, init_exports: Set[str]) -> List[Entry]:
    version_info = []

    def process_docstring(node: Any, item_name: str, in_class: bool, class_name: Optional[str] = None) -> None:
        docstring = ast.get_docstring(node)
        if docstring:
            fully_qualified_name = get_fully_qualified_name(node, module_name, class_name, init_exports)
            item_type = get_item_type(node, in_class)
            version_info.extend(parse_docstring(docstring, item_name, fully_qualified_name, item_type))

    # Process module-level docstring
    module_docstring = ast.get_docstring(node)
    if module_docstring:
        version_info.extend(parse_docstring(module_docstring, module_name, module_name, "mod"))

    def visit_node(node: ast.AST, in_class: bool = False, class_name: Optional[str] = None) -> None:
        if isinstance(node, ast.ClassDef):
            process_docstring(node, node.name, in_class)
            for child in ast.iter_child_nodes(node):
                visit_node(child, True, node.name)
        elif isinstance(node, ast.FunctionDef):
            process_docstring(node, node.name, in_class, class_name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper():
                if isinstance(node.value, ast.Str):
                    docstring = node.value.s
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    docstring = node.value.value
                else:
                    return
                fully_qualified_name = get_fully_qualified_name(node, module_name, class_name, init_exports)
                item_type = get_item_type(node, in_class)
                version_info.extend(parse_docstring(docstring, node.targets[0].id, fully_qualified_name, item_type))
        else:
            for child in ast.iter_child_nodes(node):
                visit_node(child, in_class, class_name)

    visit_node(node)
    return version_info


def parse_docstring(
    docstring: str,
    item_name: str,
    fully_qualified_name: str,
    item_type: Literal["func", "class", "variable", "meth"],
) -> List[Entry]:
    version_info = []
    lines = docstring.split("\n")
    current_version: Optional[str] = None
    current_type: Optional[str] = None
    current_description: List[str] = []
    in_version_block = False

    for line in lines:
        line = line.strip()
        if line.startswith(".. version"):
            if current_version:
                description = (
                    " ".join(current_description).strip() if current_description else "(no description provided)"
                )
                version_info.append(
                    Entry(current_version, current_type or "", description, item_name, fully_qualified_name, item_type)
                )
                current_description = []

            parts = line.split("::")
            if len(parts) == 2:
                current_type = parts[0].split()[-1].lower()
                version_parts = parts[1].strip().split(None, 1)
                current_version = version_parts[0]
                if len(version_parts) > 1:
                    current_description = [version_parts[1]]
                else:
                    current_description = []
            in_version_block = True
        elif in_version_block and line and not line.startswith(".."):
            current_description.append(line)
        elif in_version_block and not line:
            in_version_block = False
        elif not in_version_block:
            continue

    if current_version:
        description = " ".join(current_description).strip() if current_description else "(no description provided)"
        version_info.append(
            Entry(current_version, current_type or "", description, item_name, fully_qualified_name, item_type)
        )

    return version_info


def generate_changelog(directory: str, exclude_dirs: List[str]) -> List[Entry]:
    changelog = []
    init_exports = get_init_exports(directory)
    for root, _, files in os.walk(directory):
        if any(exclude in root for exclude in exclude_dirs):
            continue

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory)
                module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, ".")
                LOG.info(f"{file_path} Processing file")
                with open(file_path, "r") as f:
                    try:
                        tree = ast.parse(f.read())
                        file_changelog = parse_version_info(tree, module_name, init_exports)
                        changelog.extend(file_changelog)
                        LOG.info(f"{file_path} Found {len(file_changelog)} entries")
                    except SyntaxError as e:
                        LOG.exception(f"{file_path} Error parsing: {e}")
    return changelog


def write_changelog(changelog: List[Entry], output_file: str, default_module: str) -> None:
    sorted_changelog = sorted(changelog, key=lambda x: x.version, reverse=True)

    with open(output_file, "w") as f:
        f.write("Changelog\n=========\n\n")
        current_version = None
        for entry in sorted_changelog:
            if entry.version != current_version:
                if current_version is not None:
                    f.write("\n")  # Add extra newline between versions
                f.write(f"{entry.version}\n{'-' * len(entry.version)}\n\n")
                current_version = entry.version

            fully_qualified_name = entry.fully_qualified_name
            if f"{default_module}." not in entry.fully_qualified_name:
                fully_qualified_name = f"{default_module}.{entry.fully_qualified_name}"

            rst_reference = f":{entry.type}:`{fully_qualified_name}`"

            action = entry.change_type.replace("version", "").capitalize()
            f.write(f"* {action}: [{rst_reference}] {entry.description}\n")


def arg_main(
    directory: str = DEFAULT_DIR, output_file: str = DEFAULT_FILE, excluded_dirs: List[str] = DEFAULT_EXCLUDE
) -> bool:
    LOG.info(f"Generating changelog for {directory}")
    changelog = generate_changelog(directory, excluded_dirs)

    if not changelog:
        LOG.warning("No changelog entries found.")

    default_module = os.path.basename(directory)
    write_changelog(changelog=changelog, output_file=output_file, default_module=default_module)
    LOG.info(f"Changelog generated successfully. {len(changelog)} entries written to {output_file}")
    return bool(changelog)


def main():
    parser = argparse.ArgumentParser(description="Generate a changelog from docstrings in Python files.")
    parser.add_argument("-o", "--output_file", help="The file to write the changelog to.", default=DEFAULT_FILE)
    parser.add_argument("-d", "--directory", help="The directory to search for Python files.", default=DEFAULT_DIR)
    parser.add_argument(
        "-e", "--exclude", help="Directories to exclude from search.", nargs="*", default=DEFAULT_EXCLUDE
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Increase output verbosity.",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO,
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if DEFAULT_DIR:
        LOG.debug(f"Found default directory: {DEFAULT_DIR}")

        if DEFAULT_EXCLUDE:
            LOG.debug(f"Found default exclude directories: {DEFAULT_EXCLUDE}")
    else:
        LOG.warning("No default directory found. Please specify a directory to search for Python files.")
        sys.exit(1)

    if not arg_main(args.directory, args.output_file, args.exclude):
        sys.exit(1)


if __name__ == "__main__":
    main()
