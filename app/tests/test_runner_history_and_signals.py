"""The neural runner gets real recent candles, cannot stall on one coin, writes its
signal counts where the trader and the hub read them, and says TRAINING while a
coin trains. The trader ignores signal files the runner has stopped updating.

Everything runs under the isolation guard (app/conftest.py); no network: candle
requests go to fakes.
"""

import json
import os
import sys
import time
import types
import urllib.error
from unittest import mock

import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pt_data_provider  # noqa: E402
import pt_hub  # noqa: E402
from market_data import runner_history  # noqa: E402
from market_data.candles import CandleFetchError  # noqa: E402
from pt_exchange_abstraction import MarketNotFound  # noqa: E402

HOUR = 3600
NOW = 1_760_000_000 + 1800  # half way through an hour bar


def kline(open_s, o, h, lo, c, quote_volume=10.0):
    """A Binance klines row: [open ms, o, h, l, c, volume, close ms, quote volume, ...]."""
    return [open_s * 1000, str(o), str(h), str(lo), str(c), "1.5", 0, str(quote_volume)]


class FakeKlines:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows or [], error, []

    def fetch(self, symbol, tf, start_ms, end_ms=None):
        self.calls.append((symbol, tf, start_ms))
        if self.error:
            raise self.error
        return list(self.rows)


def hour_rows():
    forming = NOW - NOW % HOUR
    return [
        kline(forming - 2 * HOUR, 100, 103, 99, 102),
        kline(forming - HOUR, 102, 106, 101, 105),
        kline(forming, 105, 107, 104, 106),  # still forming
    ]


def test_recent_candles_are_newest_first_in_the_runners_row_order():
    fake = FakeKlines(hour_rows())
    candles = runner_history.RecentCandles(fetcher=fake, clock=lambda: NOW)
    rows = json.loads(candles.kucoin_text("BTC-USDT", "1hour"))
    forming = NOW - NOW % HOUR
    # [time_s, open, close, high, low, volume, turnover]
    assert rows[0] == [forming, 105.0, 106.0, 107.0, 104.0, 1.5, 10.0]
    assert rows[1] == [forming - HOUR, 102.0, 105.0, 106.0, 101.0, 1.5, 10.0]
    assert rows[2][0] == forming - 2 * HOUR
    assert fake.calls == [("BTCUSDT", "1h", (forming - 3 * HOUR) * 1000)]


def test_recent_candles_are_reused_for_a_short_while():
    fake = FakeKlines(hour_rows())
    clock = [NOW]
    candles = runner_history.RecentCandles(fetcher=fake, ttl=30, clock=lambda: clock[0])
    first = candles.kucoin_text("BTC", "1hour")
    clock[0] += 10
    assert candles.kucoin_text("BTCUSDT", "1h") == first
    assert len(fake.calls) == 1
    clock[0] += 30
    candles.kucoin_text("BTC", "1hour")
    assert len(fake.calls) == 2


def test_a_bar_with_no_trade_yet_gets_a_flat_placeholder():
    fake = FakeKlines(hour_rows()[:2])  # Binance sent no forming bar
    candles = runner_history.RecentCandles(fetcher=fake, clock=lambda: NOW)
    rows = json.loads(candles.kucoin_text("BTC", "1hour"))
    assert rows[0] == [NOW - NOW % HOUR, 105.0, 105.0, 105.0, 105.0, 0.0, 0.0]
    assert rows[1][2] == 105.0


def test_weekly_bars_open_on_monday():
    fake = FakeKlines([])
    candles = runner_history.RecentCandles(fetcher=fake, clock=lambda: NOW)
    with pytest.raises(Exception):
        candles.kucoin_text("ETH", "1week")  # no closed bar in the fake
    symbol, tf, start_ms = fake.calls[0]
    assert (symbol, tf) == ("ETHUSDT", "1w")
    assert time.gmtime(start_ms // 1000).tm_wday == 0  # Monday 00:00 UTC
    assert start_ms // 1000 % 86400 == 0


def test_an_unknown_symbol_is_a_missing_market():
    http = urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
    error = CandleFetchError("klines HTTP 400 for HYPEUSDT 1h")
    error.__cause__ = http
    candles = runner_history.RecentCandles(
        fetcher=FakeKlines(error=error), clock=lambda: NOW
    )
    with pytest.raises(MarketNotFound, match="no spot market HYPEUSDT"):
        candles.kucoin_text("HYPE-USDT", "1hour")


def test_the_data_provider_serves_history_without_the_exchange_connection(
    monkeypatch,
):
    provider = pt_data_provider.DataProvider.__new__(pt_data_provider.DataProvider)
    provider.initialized = False  # e.g. Coinbase could not be reached
    provider.multi_exchange = None
    shared = runner_history.RecentCandles(
        fetcher=FakeKlines(hour_rows()), clock=lambda: NOW
    )
    monkeypatch.setattr(runner_history, "_shared", shared)
    rows = json.loads(provider.get_historical_data("BTC-USDT", "1hour"))
    assert len(rows) == 3 and rows[1][2] == 105.0


# --- the runner -------------------------------------------------------------------


class TextProvider:
    """A data provider answering with fixed history text (or raising)."""

    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, 0

    def is_available(self):
        return True

    def get_provider_info(self):
        return "fake"

    def get_historical_data(self, coin, tf, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.text


@pytest.fixture
def runner():
    cwd = os.getcwd()
    sys.modules.pop("pt_thinker", None)
    with mock.patch.object(
        pt_data_provider, "get_data_provider", return_value=TextProvider()
    ):
        import pt_thinker
    yield pt_thinker
    os.chdir(cwd)
    sys.modules.pop("pt_thinker", None)


def history_text():
    return runner_history.RecentCandles(
        fetcher=FakeKlines(hour_rows()), clock=lambda: NOW
    ).kucoin_text("BTC", "1hour")


def test_the_runner_reads_the_last_closed_bar(runner, monkeypatch):
    monkeypatch.setattr(runner, "data_provider", TextProvider(history_text()))
    t, o, c = runner._last_closed_bar("BTC-USDT", "1hour")
    assert (int(t), o, c) == (NOW - NOW % HOUR - HOUR, 102.0, 105.0)


def test_one_candle_is_not_enough_and_does_not_hang(runner, monkeypatch):
    provider = TextProvider("[[1760000000000, 5.0, 5.0, 5.0, 5.0, 1000]]")
    monkeypatch.setattr(runner, "data_provider", provider)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    with pytest.raises(runner.CoinDataError, match="only 1 candle"):
        runner._last_closed_bar("BTC-USDT", "1hour")
    assert provider.calls == runner._HISTORY_ATTEMPTS


def test_a_failing_source_is_retried_briefly_then_skipped(runner, monkeypatch):
    provider = TextProvider(error=RuntimeError("timeout"))
    monkeypatch.setattr(runner, "data_provider", provider)
    sleeps = []
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    with pytest.raises(runner.CoinDataError, match="timeout"):
        runner._history_rows("BTC-USDT", "4hour")
    assert provider.calls == runner._HISTORY_ATTEMPTS
    assert len(sleeps) == runner._HISTORY_ATTEMPTS - 1


def test_the_current_price_falls_back_to_the_candles(runner, monkeypatch):
    def no_market(symbol):
        raise RuntimeError("Coinbase has no market BNB-USD")

    monkeypatch.setattr(runner, "robinhood_current_ask", no_market)
    monkeypatch.setattr(runner, "data_provider", TextProvider(history_text()))
    assert runner._current_price("BNB") == 106.0  # the forming bar's latest close
    monkeypatch.setattr(runner, "data_provider", TextProvider(error=OSError("dns")))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    with pytest.raises(runner.CoinDataError, match="no current price for BNB"):
        runner._current_price("BNB")


def test_init_does_not_hang_when_the_source_is_down(runner, monkeypatch, capsys):
    monkeypatch.setattr(runner, "data_provider", TextProvider(error=OSError("down")))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    runner.init_coin("DOGE")
    assert runner.states["DOGE"]["tf_times"] == [0.0] * len(runner.tf_choices)
    assert "DOGE: no 1hour price history" in capsys.readouterr().out


class StopLoop(BaseException):
    """Ends the runner's endless main loop from a test."""


def test_one_coins_error_does_not_stop_the_runner(runner, monkeypatch, capsys):
    stepped = []

    def step(sym):
        stepped.append(sym)
        if sym == "ZEC":
            raise FileNotFoundError("memories_1hour.txt")

    monkeypatch.setattr(runner, "CURRENT_COINS", ["ZEC", "XRP"])
    monkeypatch.setattr(runner, "init_coin", lambda sym: None)
    monkeypatch.setattr(runner, "step_coin", step)
    monkeypatch.setattr(runner, "_sync_coins_from_settings", lambda: None)
    monkeypatch.setattr(runner.sys, "argv", ["pt_thinker.py"])
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopLoop()

    monkeypatch.setattr(runner.time, "sleep", sleep)
    with pytest.raises(StopLoop):
        runner.main()
    assert stepped == ["ZEC", "XRP", "ZEC", "XRP"]  # two full passes
    out = capsys.readouterr().out
    assert out.count("ZEC: skipped this pass - FileNotFoundError") == 1
    assert "Error in main loop" not in out
    assert runner.display_cache["ZEC"].startswith("ZEC  (ERROR - FileNotFoundError")


# --- the hub --------------------------------------------------------------------


def test_a_stopped_trainer_is_not_left_marked_training(tmp_path):
    folder = str(tmp_path)
    path = os.path.join(folder, "trainer_status.json")
    with open(path, "w") as f:
        json.dump({"state": "TRAINING"}, f)
    hub = types.SimpleNamespace(coin_folders={"BTC": folder})
    pt_hub.PowerTraderHub._mark_training_ended(hub, "BTC", 1)
    with open(path) as f:
        assert json.load(f)["state"] == "STOPPED"
    # a finished status is left alone
    with open(path, "w") as f:
        json.dump({"state": "FINISHED"}, f)
    pt_hub.PowerTraderHub._mark_training_ended(hub, "BTC", 1)
    with open(path) as f:
        assert json.load(f)["state"] == "FINISHED"


def test_recent_candles_are_fetched_again_once_the_bar_closes():
    forming = NOW - NOW % HOUR
    fake = FakeKlines(hour_rows())
    clock = [forming + HOUR - 10]
    candles = runner_history.RecentCandles(fetcher=fake, ttl=30, clock=lambda: clock[0])
    candles.kucoin_text("BTC", "1hour")
    clock[0] = forming + HOUR + 5  # inside the ttl, but the bar has closed
    candles.kucoin_text("BTC", "1hour")
    assert len(fake.calls) == 2


class StopStep(Exception):
    pass


def test_a_new_model_starts_from_placeholders(runner, monkeypatch):
    st = runner.states["BTC"] = runner.new_coin_state()
    st.update(
        model_id="old",
        low_bound_prices=[123.0] * 7,
        bounds_version=3,
        last_display_bounds_version=3,
        tf_choice_index=4,
        tf_times=["t"] * 7,
    )
    runner._ready_coins.add("BTC")
    monkeypatch.setattr(runner, "_coin_is_trained", lambda sym: True)
    monkeypatch.setattr(runner, "_model_verified", lambda sym: True)
    monkeypatch.setitem(runner._verified_models, "BTC", (None, {"model_id": "new"}))

    def stop(coin, tf):
        raise StopStep(tf)

    monkeypatch.setattr(runner, "_last_closed_bar", stop)
    with pytest.raises(StopStep, match="1hour"):  # the sweep starts again at 1hour
        runner.step_coin("BTC")
    st = runner.states["BTC"]
    assert st["model_id"] == "new"
    assert st["low_bound_prices"] == [0.01] * 7
    assert (st["bounds_version"], st["last_display_bounds_version"]) == (0, -1)
    assert st["tf_times"] == ["t"] * 7
    assert "BTC" not in runner._ready_coins


def test_a_held_coin_forgets_its_predictions(runner):
    os.makedirs(runner.coin_folder("SOL"), exist_ok=True)
    st = runner.states["SOL"] = runner.new_coin_state()
    st.update(low_bound_prices=[5.0] * 7, bounds_version=2, tf_times=["x"] * 7)
    runner.step_coin("SOL")  # no training stamp: held
    st = runner.states["SOL"]
    assert st["low_bound_prices"] == [0.01] * 7 and st["bounds_version"] == 0
    assert st["tf_times"] == ["x"] * 7
