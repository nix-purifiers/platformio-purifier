"""Keep hooks inside native operations, including SCons subprocess imports."""

import ast
from pathlib import Path


def insert_guard(filename, function, statement):
    path = Path(filename)
    text = path.read_text()
    matches = [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef) and node.name == function
    ]
    assert len(matches) == 1, (filename, function)
    body = matches[0].body
    first = (
        body[1]
        if isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
        else body[0]
    )
    lines = text.splitlines(True)
    lines.insert(
        first.lineno - 1,
        " " * first.col_offset
        + "if os.environ.get('PLATFORMIO_PURIFIER_CONTEXT'):\n"
        + " " * (first.col_offset + 4)
        + "from platformio import platformio_purifier_native as purifier\n"
        + " " * (first.col_offset + 4)
        + statement
        + "\n",
    )
    path.write_text("".join(lines))


base = Path("platformio/package/manager")
insert_guard(
    base / "_install.py", "_install", "purifier.check_install(self, spec, force)"
)
insert_guard(base / "_download.py", "download", "purifier.deny_if_frozen()")
insert_guard(base / "_update.py", "update", "purifier.deny_if_frozen()")
insert_guard(base / "_uninstall.py", "uninstall", "purifier.deny_if_frozen()")
path = base / "_install.py"
text = path.read_text()
before = "            return self._install_tmp_pkg(pkg_item)"
after = """            installed = self._install_tmp_pkg(pkg_item)
            if os.environ.get('PLATFORMIO_PURIFIER_CONTEXT'):
                from platformio import platformio_purifier_native as purifier
                purifier.record_install(self, uri, spec, checksum, installed)
            return installed"""
assert text.count(before) == 1
path.write_text(text.replace(before, after))
path = Path("platformio/__main__.py")
text = path.read_text()
before = "        cli()  # pylint: disable=no-value-for-parameter"
assert text.count(before) == 1
path.write_text(
    text.replace(
        before,
        """        if os.environ.get('PLATFORMIO_PURIFIER_CONTEXT'):
            from platformio import platformio_purifier_native as purifier
            purifier.guard_project()
"""
        + before,
    )
)
