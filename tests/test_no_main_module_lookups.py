"""Shared objects must be reached through coc_bot.runtime.

The original script kept its state in module globals of ``main.py`` and some
code looked them up by name (``globals()``, ``sys.modules['__main__']``).
Those lookups silently stop working once the code lives in a package, so
they are not allowed to come back.
"""
import ast
import pathlib

import coc_bot

PACKAGE = pathlib.Path(coc_bot.__file__).parent


def offenders():
    found = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "globals":
                found.append(f"{path.relative_to(PACKAGE)}:{node.lineno} globals()")
            if isinstance(node, ast.Constant) and node.value == "__main__":
                parent_is_guard = False
                for guard in ast.walk(tree):
                    if isinstance(guard, ast.Compare) and node in guard.comparators \
                            and isinstance(guard.left, ast.Name) and guard.left.id == "__name__":
                        parent_is_guard = True
                if not parent_is_guard:
                    found.append(f"{path.relative_to(PACKAGE)}:{node.lineno} '__main__' lookup")
    return found


def test_no_lookups_of_main_module_state():
    assert offenders() == []


def test_gui_queue_controls_use_the_shared_queue_manager(monkeypatch):
    """Stopping the bot from the GUI must reset the queue held in coc_bot.runtime."""
    from coc_bot import runtime
    from coc_bot.gui.bot_control import BotControlMixin

    class FakeQueue:
        reset_calls = 0

        def reset_queue(self):
            self.reset_calls += 1

    class FakeGUI(BotControlMixin):
        manual_mode_schedule = []

        def __getattr__(self, name):  # any widget or helper: accept and ignore
            return lambda *args, **kwargs: None

    queue = FakeQueue()
    monkeypatch.setattr(runtime, "queue_manager", queue)
    try:
        FakeGUI().stop_bot()
    except Exception:
        pass  # widget updates after the queue reset are irrelevant here
    assert queue.reset_calls == 1
