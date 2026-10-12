"""The compact Controls pane: Account grid with the trader row, the coin table
(training status and the runner's long/short counts) and the Controls/Live
Output split.

Runs under the isolation guard (app/conftest.py); the real-hub test uses a hidden
window and processes no events.
"""

import os
import queue
import sys
import types
from tkinter import ttk
from unittest import mock

import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pt_hub  # noqa: E402

Hub = pt_hub.PowerTraderHub


@pytest.mark.parametrize(
    "requested, total, target",
    [
        (300, 900, 302),  # Controls gets what it asks for
        (100, 900, 160),  # never less than 160
        (800, 900, 450),  # at most half, or 450 when that is more
        (800, 1400, 700),  # half of a tall window
        (800, 500, 380),  # Live Output keeps at least 120
    ],
)
def test_the_controls_split_fits_its_content_within_limits(requested, total, target):
    assert pt_hub._left_split_target(requested, total) == target


class FakeLabel:
    def __init__(self):
        self.calls = []

    def configure(self, **kw):
        self.calls.append(kw)


def test_training_cells_are_updated_in_place_and_only_when_changed():
    cells = {c: tuple(FakeLabel() for _ in range(5)) for c in ("ZEC", "BTC")}
    hub = types.SimpleNamespace(
        coins=["ZEC", "BTC"],
        _training_table_coins=("ZEC", "BTC"),
        _training_cells=cells,
        _training_cell_state={},
        _build_training_table=mock.Mock(),
        _get_training_hours=lambda coin: "1.5h",
    )
    hub._get_status_border_color = (
        lambda status, coin=None: Hub._get_status_border_color(hub, status, coin)
    )
    Hub._update_training_table(hub, {"ZEC": "●", "BTC": "✅"})
    _, zec_dot, _, zec_age, _ = cells["ZEC"]
    _, btc_dot, _, btc_age, _ = cells["BTC"]
    assert zec_dot.calls == [{"text": "●", "fg": pt_hub.STATUS_AMBER}]
    assert zec_age.calls == [{"text": "training"}]
    assert btc_dot.calls == [{"text": "●", "fg": pt_hub.STATUS_GREEN}]
    assert btc_age.calls == [{"text": "1.5h"}]
    Hub._update_training_table(hub, {"ZEC": "●", "BTC": "✅"})
    assert len(zec_dot.calls) == 1 and len(btc_age.calls) == 1  # nothing changed
    Hub._update_training_table(hub, {"ZEC": "○", "BTC": "✅"})  # the training blink
    assert zec_dot.calls[-1] == {"text": "○", "fg": pt_hub.STATUS_AMBER}
    hub._build_training_table.assert_not_called()


def test_a_changed_coin_list_rebuilds_the_training_table():
    hub = types.SimpleNamespace(
        coins=["ZEC", "BTC", "ETH"],
        _training_table_coins=("ZEC", "BTC"),
        _training_cells={},
        _training_cell_state={},
    )
    hub._build_training_table = mock.Mock()
    Hub._update_training_table(hub, {})
    hub._build_training_table.assert_called_once()


@pytest.fixture
def hub(monkeypatch):
    import helpers_trainer as ht

    hub = ht.build_real_hub(monkeypatch)  # skips when Tk cannot start
    yield hub
    ht.close_hub(hub)


def all_widgets(parent):
    out = []
    for child in parent.winfo_children():
        out.append(child)
        out.extend(all_widgets(child))
    return out


def test_the_controls_pane_is_compact(hub):
    frames = [w for w in all_widgets(hub) if isinstance(w, ttk.LabelFrame)]
    titles = [str(w.cget("text")) for w in frames]
    assert "Trading (Exchanges)" not in titles  # folded into the Account box
    assert "Thinking (Signals)" not in titles  # its counts are in the coin table
    assert {"Account", "Coins"} <= set(titles)
    (account,) = [w for w in frames if str(w.cget("text")) == "Account"]
    inside = all_widgets(account)
    for name in (
        "lbl_trader",
        "lbl_exchange",
        "btn_start_trader",
        "btn_stop_trader",
        "lbl_acct_total_value",
        "lbl_acct_buying_power",
        "lbl_acct_holdings_value",
        "lbl_acct_percent_in_trade",
        "lbl_acct_dca_single",
        "lbl_acct_dca_spread",
        "lbl_pnl",
    ):
        assert getattr(hub, name) in inside, name
    keys = [str(w.cget("text")) for w in inside if isinstance(w, ttk.Label)]
    assert {"Value", "Buying Power", "Holdings", "% in Trade", "DCA Single"} <= set(
        keys
    )
    assert list(hub._training_cells) == list(hub.coins)  # one cell per coin
    (coins,) = [w for w in frames if str(w.cget("text")) == "Coins"]
    for name in ("lbl_neural", "btn_start_neural", "btn_stop_neural"):
        assert getattr(hub, name) in all_widgets(coins), name
    hub._tick()  # the refresh loop runs with the new widgets
    assert str(hub.lbl_trader.cget("text")) == "stopped"


class SigLabel:
    def __init__(self):
        self.text, self.fg, self.calls = None, None, 0

    def configure(self, text, fg):
        self.text, self.fg, self.calls = text, fg, self.calls + 1


@pytest.mark.parametrize(
    "longs, shorts, age, level, text, colour",
    [
        (None, None, None, 3, "–", pt_hub.DARK_MUTED),  # no signal file
        (4, 0, 10, 3, "L4 S0", pt_hub.STATUS_GREEN),
        (3, 0, 10, 3, "L3 S0", pt_hub.STATUS_GREEN),  # the trader starts at 3
        (2, 0, 10, 3, "L2 S0", pt_hub.DARK_FG),  # below the start level: no trade
        (1, 0, 10, 1, "L1 S0", pt_hub.STATUS_GREEN),
        (4, 2, 10, 3, "L4 S2", pt_hub.LOG_SHORT),
        (0, 0, 10, 3, "L0 S0", pt_hub.DARK_FG),
        (4, 0, 16 * 60, 3, "L4 S0", pt_hub.DARK_MUTED),  # the trader ignores it now
    ],
)
def test_a_cell_shows_the_signal_counts(longs, shorts, age, level, text, colour):
    import time

    hub = types.SimpleNamespace(_training_signal_state={})
    label = SigLabel()
    mtime = None if age is None else time.time() - age
    Hub._show_signal_counts(hub, "BTC", label, longs, shorts, mtime, level)
    assert (label.text, label.fg) == (text, colour)
    Hub._show_signal_counts(hub, "BTC", label, longs, shorts, mtime, level)
    assert label.calls == 1  # unchanged: not touched again


def test_the_counts_are_read_from_each_coins_signal_files(tmp_path):
    btc, eth = tmp_path / "btc", tmp_path / "eth"
    btc.mkdir()
    eth.mkdir()
    (btc / "long_dca_signal.txt").write_text("5")
    (btc / "short_dca_signal.txt").write_text("0")
    labels = {c: SigLabel() for c in ("BTC", "ETH", "ZEC")}
    hub = types.SimpleNamespace(
        settings={"main_neural_dir": ""},
        coins=["BTC", "ETH", "ZEC"],
        _coin_folders_sig=("", ("BTC", "ETH", "ZEC")),  # keep these folders
        coin_folders={"BTC": str(btc), "ETH": str(eth), "ZEC": str(tmp_path / "none")},
        _training_cells={c: (None, None, None, None, labels[c]) for c in labels},
        _training_signal_state={},
        _neural_overview_cache={},
    )
    hub._show_signal_counts = lambda *a: Hub._show_signal_counts(hub, *a)
    Hub._refresh_neural_overview(hub)
    assert labels["BTC"].text == "L5 S0"
    assert labels["ETH"].text == "–"  # folder but no signal files yet
    assert labels["ZEC"].text == "–"  # no folder


def tooltip_hub(
    status="✅", signal=(3, 0, None, 3), engine="catalogue", trained_at=None
):
    import time

    return types.SimpleNamespace(
        _training_status={"ZEC": status},
        last_training_times={"ZEC": trained_at or time.time() - 2 * 3600},
        settings={"training_auto_enabled": True, "training_auto_interval_hours": 6},
        _training_signal_info={"ZEC": signal},
        _signals_engine=engine,
    )


def test_the_status_dot_explains_each_colour():
    tip = Hub._coin_tooltip(tooltip_hub("✅"), "ZEC", "status")
    assert "trained (green dot)" in tip and "less than 14 days" in tip
    tip = Hub._coin_tooltip(tooltip_hub("●"), "ZEC", "status")
    assert "training now (amber dot)" in tip and "skips ZEC" in tip
    tip = Hub._coin_tooltip(tooltip_hub("❌"), "ZEC", "status")
    assert "not trained (grey dot)" in tip and "no signals" in tip


def test_the_trained_for_time_says_when_and_how_long_it_lasts():
    tip = Hub._coin_tooltip(tooltip_hub("✅"), "ZEC", "age")
    assert "2.0 h ago, at " in tip
    assert "trained for 14 days" in tip
    assert "Auto-retrain: about every 6 h" in tip
    tip = Hub._coin_tooltip(tooltip_hub("❌"), "ZEC", "age")
    assert "never been trained" in tip


def test_the_signal_counts_explain_l_s_the_start_level_and_who_uses_them():
    import time

    tip = Hub._coin_tooltip(
        tooltip_hub(signal=(2, 0, time.time() - 30, 3)), "ZEC", "signal"
    )
    assert "L2 S0" in tip
    assert "price below their predicted low (long)" in tip
    assert "above their predicted high (short)" in tip
    assert "trade start level (3, Settings)" in tip
    assert "Updated 30 s ago." in tip
    assert "engine is catalogue, which does not use these counts" in tip
    tip = Hub._coin_tooltip(
        tooltip_hub(signal=(4, 0, time.time() - 20 * 60, 3), engine="legacy_neural"),
        "ZEC",
        "signal",
    )
    assert "Updated 20 min ago. Older than 15 minutes: the trader ignores it" in tip
    assert "these counts decide its new trades" in tip
    tip = Hub._coin_tooltip(tooltip_hub(signal=(None, None, None, 3)), "ZEC", "signal")
    assert "none yet" in tip and "two full sweeps" in tip


def test_each_coin_field_has_its_own_tooltip(hub):
    cell, dot, sym, age, sig = hub._training_cells[hub.coins[0]]
    for widget in (dot, sym, age, sig):
        assert widget.bind("<Enter>"), "no tooltip on a coin field"
    assert not cell.bind("<Enter>")  # not a second tooltip on the frame itself
