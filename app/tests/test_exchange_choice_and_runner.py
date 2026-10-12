"""The exchange choice made in Settings reaches the neural runner, and the hub's
exchange status is a real price check.

Everything runs under the isolation guard (app/conftest.py); no network.
"""

import os
import sys
import types
from unittest import mock

import pytest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pt_data_provider  # noqa: E402
import pt_hub  # noqa: E402
from pt_multi_exchange import ExchangeConfigManager  # noqa: E402


def test_settings_save_writes_the_exchange_choice_where_the_runner_reads_it():
    hub = types.SimpleNamespace(
        settings={"region": "eu", "primary_exchange": "coinbase"}
    )
    pt_hub.PowerTraderHub._sync_exchange_choice(hub)
    config = ExchangeConfigManager().load_config()
    assert (config.user_region, config.primary_exchange) == ("EU", "coinbase")
    # a second save with other values updates it again
    hub.settings = {"region": "uk", "primary_exchange": "kraken"}
    pt_hub.PowerTraderHub._sync_exchange_choice(hub)
    config = ExchangeConfigManager().load_config()
    assert (config.user_region, config.primary_exchange) == ("UK", "kraken")


def test_the_data_provider_takes_its_region_from_the_shared_config(monkeypatch):
    monkeypatch.delenv("POWERTRADER_USER_REGION", raising=False)
    hub = types.SimpleNamespace(
        settings={"region": "eu", "primary_exchange": "coinbase"}
    )
    pt_hub.PowerTraderHub._sync_exchange_choice(hub)
    seen = []

    def fake_initialize(self, user_region=None):
        seen.append(user_region)
        return False  # connect nothing: no network

    monkeypatch.setattr(
        "pt_multi_exchange.MultiExchangeManager.initialize", fake_initialize
    )
    pt_data_provider.DataProvider()
    assert seen == ["EU"]
    monkeypatch.setenv("POWERTRADER_USER_REGION", "US")
    pt_data_provider.DataProvider()
    assert seen[-1] == "US"  # the environment variable still wins


class FakeConnector:
    def __init__(self, price=None, error=None, live=False):
        self.price, self.error, self.SUPPORTS_LIVE_ORDERS = price, error, live

    def get_current_price(self, symbol):
        assert symbol == "BTC-USD"
        if self.error:
            raise self.error
        return self.price


def status_for(connector, primary="coinbase"):
    hub = types.SimpleNamespace()
    with mock.patch(
        "pt_exchange_abstraction.ExchangeFactory.get_exchange", return_value=connector
    ):
        return pt_hub.PowerTraderHub._exchange_status_once(hub, primary)


def test_the_exchange_status_is_a_real_price_check():
    # the old check used a manager that was never connected: always "not available"
    status, details = status_for(FakeConnector(price=81000.0))
    assert status == "✅ COINBASE (prices only)"
    assert "BTC $81,000.00" in details
    assert "cannot read balances or place live orders on coinbase" in details

    status, details = status_for(FakeConnector(price=81000.0, live=True), "binance")
    assert status == "✅ BINANCE" and "live orders supported" in details

    status, details = status_for(FakeConnector(error=ConnectionError("dns")))
    assert status == "❌ COINBASE" and "No price from coinbase: dns" in details


def test_only_binance_claims_live_orders():
    import pt_exchanges  # noqa: F401
    from pt_exchange_abstraction import ExchangeFactory

    live = sorted(
        e.value
        for e in ExchangeFactory.get_available_exchanges()
        if getattr(ExchangeFactory.get_exchange_class(e), "SUPPORTS_LIVE_ORDERS", False)
    )
    assert live == ["binance"]
