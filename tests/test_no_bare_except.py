"""A bare ``except:`` also swallows KeyboardInterrupt and SystemExit."""

import ast
import pathlib

import coc_bot

PACKAGE = pathlib.Path(coc_bot.__file__).parent


def test_no_bare_except_in_package():
    bare = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert bare == []
