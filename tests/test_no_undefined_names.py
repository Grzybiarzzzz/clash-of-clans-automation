"""Every global name a function refers to must exist in its module.

A misspelt or forgotten name only fails when that line runs, which for this
project means in the middle of a live attack. This check finds them up front.
"""

import builtins
import dis
import importlib
import pkgutil
import types

import pytest

import coc_bot

MODULES = sorted(m.name for m in pkgutil.walk_packages(coc_bot.__path__, "coc_bot."))


def code_objects(code):
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from code_objects(const)


@pytest.mark.parametrize("module_name", MODULES)
def test_global_names_resolve(module_name):
    module = importlib.import_module(module_name)
    with open(module.__file__, encoding="utf-8") as source:
        code = compile(source.read(), module.__file__, "exec")

    referenced, assigned = set(), set()
    for obj in code_objects(code):
        for instruction in dis.get_instructions(obj):
            if instruction.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
                referenced.add(instruction.argval)
            elif instruction.opname in ("STORE_GLOBAL", "STORE_NAME"):
                assigned.add(instruction.argval)

    missing = sorted(
        name for name in referenced - assigned if not hasattr(module, name) and not hasattr(builtins, name)
    )
    assert missing == []
