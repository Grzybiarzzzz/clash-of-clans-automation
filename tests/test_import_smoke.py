"""Every module of the package must import cleanly (no circular imports)."""

import importlib
import pkgutil

import pytest

import coc_bot

# coc_bot.app is the entry point: importing it is safe, but it is covered separately.
MODULES = sorted(m.name for m in pkgutil.walk_packages(coc_bot.__path__, "coc_bot.") if m.name != "coc_bot.app")


def test_package_has_modules():
    assert "coc_bot.geometry" in MODULES


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    importlib.import_module(module_name)


def test_importing_the_entry_point_does_not_start_the_application():
    from coc_bot import runtime

    entry = importlib.import_module("main")
    app = importlib.import_module("coc_bot.app")

    assert entry.main is app.main
    assert runtime.gui is None and runtime.root is None
