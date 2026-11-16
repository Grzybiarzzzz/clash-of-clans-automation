"""The connection monitor aborts the bot thread instead of racing it for the mouse."""

import threading
from unittest.mock import MagicMock

import pytest

from coc_bot import connection, humanized_input, interrupts, loop, runtime
from coc_bot.vision import capture


@pytest.fixture(autouse=True)
def watched():
    """The test thread plays the bot thread."""
    interrupts.watch_current_thread()
    yield
    interrupts.clear()


def in_another_thread(function):
    outcome = {}

    def target():
        try:
            outcome["result"] = function()
        except BaseException as e:  # noqa: BLE001 - the test wants to see anything that escapes
            outcome["raised"] = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    return outcome


def test_a_checkpoint_passes_while_nothing_happened():
    interrupts.checkpoint()


def test_after_an_interrupt_the_bot_thread_stops_at_its_next_checkpoint():
    interrupts.interrupt()

    with pytest.raises(interrupts.ConnectionLost):
        interrupts.checkpoint()


def test_other_threads_are_never_interrupted():
    interrupts.interrupt()

    assert in_another_thread(interrupts.checkpoint) == {"result": None}


def test_error_handlers_inside_detectors_cannot_swallow_the_interrupt():
    interrupts.interrupt()

    with pytest.raises(interrupts.ConnectionLost):
        try:
            interrupts.checkpoint()
        except Exception:
            pass


def test_the_interrupt_stays_pending_until_the_bot_thread_clears_it():
    interrupts.interrupt()
    with pytest.raises(interrupts.ConnectionLost):
        interrupts.checkpoint()
    with pytest.raises(interrupts.ConnectionLost):
        interrupts.checkpoint()

    interrupts.clear()
    interrupts.checkpoint()


def test_capturing_the_screen_is_a_checkpoint(screen):
    interrupts.interrupt()

    with pytest.raises(interrupts.ConnectionLost):
        capture.grab((0, 0, 10, 10))
    assert screen.grabs == []


@pytest.mark.parametrize("click", [humanized_input.fast_click, humanized_input.human_like_move_click])
def test_clicking_is_a_checkpoint_and_the_mouse_does_not_move(click, monkeypatch):
    mouse = MagicMock(name="pyautogui")
    monkeypatch.setattr(humanized_input, "pyautogui", mouse)
    interrupts.interrupt()

    with pytest.raises(interrupts.ConnectionLost):
        click(500, 500)
    assert mouse.mock_calls == []


def test_the_monitor_interrupts_the_bot_thread_before_it_clicks_try_again(bot, monkeypatch):
    popup = iter([(1280, 800), None])
    events = []
    monkeypatch.setattr(connection, "detect_connection_lost", lambda: next(popup))
    monkeypatch.setattr(connection, "detect_in_base_state", lambda: True)
    monkeypatch.setattr(connection.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(connection, "fast_click", lambda x, y: events.append(("click", interrupts.pending())))

    outcome = in_another_thread(connection.handle_connection_lost)

    assert outcome == {"result": True}
    assert events == [("click", True)]
    assert interrupts.pending()
    assert not connection.reconnect_in_progress()


@pytest.fixture
def derank_loop(bot, monkeypatch):
    """The main loop in derank mode with every screen interaction stubbed out.

    The first attack is interrupted by the monitor; the second one ends the session.
    """
    bot.bot_running = True
    bot.bot_paused = False
    bot.get_settings.return_value = {"derank_mode": True, "current_profile": "Derank"}
    monkeypatch.setattr(runtime, "break_time", None)
    monkeypatch.setattr(runtime, "queue_manager", None)
    for name in ("check_discord_commands", "overlay_clear", "_start_search"):
        monkeypatch.setattr(loop, name, lambda *a, **k: None)
    for name in ("fast_click", "click_in_square", "humanized_sleep"):
        monkeypatch.setattr(loop, name, lambda *a, **k: None)
    monkeypatch.setattr(loop.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(loop, "detect_return_home_button", lambda quiet=False: None)

    class Session:
        attacks = []
        base_waits = []
        released = []

    session = Session()
    monkeypatch.setattr(loop, "wait_for_base_screen", lambda timeout=15: session.base_waits.append(timeout) or True)
    monkeypatch.setattr(loop, "release_held_inputs", lambda: session.released.append(True))

    def derank():
        session.attacks.append(len(session.attacks))
        if len(session.attacks) == 1:
            interrupts.interrupt()  # the monitor saw the popup mid-attack
            interrupts.checkpoint()
        runtime.running = False  # second attack: end the test
        return True

    monkeypatch.setattr(loop, "handle_derank_mode", derank)
    return session


def test_the_main_loop_abandons_the_attack_and_starts_over_after_a_reconnect(derank_loop):
    loop.main_loop()

    assert derank_loop.attacks == [0, 1]
    assert runtime.attacked_bases == 1  # only the attack that was not interrupted counts
    assert derank_loop.released == [True]
    assert len(derank_loop.base_waits) == 1
    assert runtime.paused is False  # a reconnect is not an error
    assert not interrupts.pending()


def test_a_second_disconnect_while_waiting_for_the_base_does_not_end_the_bot_thread(derank_loop, monkeypatch):
    def wait_for_base(timeout=15):
        derank_loop.base_waits.append(timeout)
        if len(derank_loop.base_waits) == 1:
            interrupts.interrupt()  # the popup came back while the game was reloading
            interrupts.checkpoint()
        return True

    monkeypatch.setattr(loop, "wait_for_base_screen", wait_for_base)

    loop.main_loop()

    assert derank_loop.attacks == [0, 1]
    assert len(derank_loop.base_waits) == 2
