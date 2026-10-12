"""The Settings window: rows that must (not) be there.

Runs a real hub under the isolation guard (app/conftest.py) with a hidden window.
"""

import os
import sys
from tkinter import ttk

import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pt_hub  # noqa: E402


@pytest.fixture
def hub(monkeypatch):
    import helpers_trainer as ht

    hub = ht.build_real_hub(monkeypatch)  # skips when Tk cannot start
    monkeypatch.setattr(pt_hub, "API_SERVER_AVAILABLE", False)
    yield hub
    ht.close_hub(hub)


def test_settings_has_no_robinhood_api_row(hub):
    from test_trainer_launch import open_settings, widgets

    win = open_settings(hub)
    texts = [
        str(w.cget("text"))
        for w in widgets(win)
        if isinstance(w, (ttk.Label, ttk.Button)) and "text" in w.keys()
    ]
    assert "Robinhood API:" not in texts
    assert "Setup Wizard" not in texts
    assert not any("no API key / private key saved" in t for t in texts)
    # the rows around it are still there
    assert "pt_trader.py path:" in texts and "Paper Account..." in texts
    win.destroy()
