"""
Paper trading mode helpers for the PowerTrader hub.

Provides:
- (The blue palette that paints the hub when paper mode is on, so the user can
  instantly see they are not trading real money, is ui_tokens.PAPER; the hub
  picks it with ui_tokens.palette(paper_mode) and ui_theme applies it.)
- "PAPER TRADING" banner label that gets injected into the trading section.
- A sample-trade runner that pulls a live BTC price from Binance's public
  ticker endpoint and routes a simulated BUY then SELL through
  PaperTradingAccount.
- Helpers that read the persisted `trading.mode` (the source of truth, owned by
  trading_mode.py) so the hub can paint itself correctly at start-up.

This module is deliberately small and self-contained so pt_hub.py changes
remain surgical. All side effects on the hub happen through the helper
functions exported here; pt_hub.py never reaches into Tk internals from a
paper-mode branch directly.
"""

from __future__ import annotations

import json
import os
import tkinter as tk
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

import ui_tokens
from pt_paper_trading import OrderSide, OrderType, PaperTradingAccount
from trading_mode import read_trading_settings

# Owner spec (PR #90 comment): "paper mode changes the CSS of the background.
# Say BLUE instead of BLACK." Tk has no CSS: ui_tokens.PAPER mirrors the dark
# palette's keys in blue, and the hub applies the one that matches the mode.

# --- Settings persistence -----------------------------------------------------
# The mode itself lives in `trading.mode` (see trading_mode.py) - the single
# source of truth shared with the trader's order gate. The old
# `paper_mode_enabled` flag in gui_settings.json is no longer read.
PAPER_MODE_BALANCE_KEY = "paper_mode_balance"


def is_paper_mode(settings: Any = None) -> bool:
    """True unless `trading.mode` is explicitly "live" (fail closed to paper).

    `settings` may be a nested dict, a SettingsManager, a settings-file path, or
    None to read the settings file.
    """
    return not read_trading_settings(settings).is_live


# --- Live BTC price (Binance public ticker, no auth) -------------------------
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"


def fetch_binance_btc_price(
    timeout: float = 5.0,
    url: str = BINANCE_TICKER_URL,
    opener: Optional[Callable[[str, float], Any]] = None,
) -> Optional[Decimal]:
    """
    Pull the current BTC/USDT price from Binance's public REST endpoint.

    Returns None on any failure - the sample runner falls back to the
    PaperTradingAccount's own MarketDataSimulator so the demo still works
    when offline. `opener` is overridable for tests.
    """
    try:
        if opener is None:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        else:
            payload = json.loads(opener(url, timeout))
        price = payload.get("price")
        if price is None:
            return None
        return Decimal(str(price))
    except (urllib.error.URLError, ValueError, KeyError, OSError):
        return None


# --- Sample-scenario runner ---------------------------------------------------
def run_sample_scenario(
    account: PaperTradingAccount,
    quantity: Decimal = Decimal("0.001"),
    symbol: str = "BTC",
    price_fetcher: Callable[[], Optional[Decimal]] = fetch_binance_btc_price,
) -> Dict[str, Any]:
    """
    Place a simulated BUY then SELL through the paper account, using a live
    BTC price when available. Mirrors the demo flow from the now-retired
    standalone demo_paper_trading.py but lives behind the hub's "Run sample"
    button.

    Returns a dict the GUI can render directly. Keys:
      starting_balance, final_balance, buy_price, sell_price, source
    """
    starting = account.cash_balance
    live_price = price_fetcher()
    source = "binance_public" if live_price is not None else "simulated"

    # Seed the simulator so BUY/SELL fills land near the live spot price
    # instead of the simulator's default $45k anchor.
    if live_price is not None:
        account.market_simulator.current_prices[symbol] = live_price

    buy_id = account.place_order(
        symbol=symbol,
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=quantity,
    )
    buy_order = account.orders[buy_id]

    sell_id = account.place_order(
        symbol=symbol,
        order_type=OrderType.MARKET,
        side=OrderSide.SELL,
        quantity=quantity,
    )
    sell_order = account.orders[sell_id]

    return {
        "source": source,
        "starting_balance": float(starting),
        "final_balance": float(account.cash_balance),
        "buy_price": float(buy_order.filled_price),
        "sell_price": float(sell_order.filled_price),
        "buy_status": buy_order.status.value,
        "sell_status": sell_order.status.value,
        "live_price": float(live_price) if live_price is not None else None,
    }


# --- Tk widgets ---------------------------------------------------------------
class PaperBanner(tk.Frame):
    """
    Top-of-window banner that screams PAPER TRADING. Visible only when
    paper mode is on. Single tk.Frame so we can pack/forget cheaply on
    toggle without rebuilding the layout. It is the whole header row: the hub
    packs the mode strip (price and signal notes) into it, right of the title
    (owner, 2026-10-23).
    """

    def __init__(
        self,
        parent: tk.Misc,
        palette: Dict[str, str],
        on_run_sample: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(
            parent,
            bg=palette["ACCENT"],
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._palette = palette

        label = tk.Label(
            self,
            text="PAPER TRADING",
            bg=palette["ACCENT"],
            fg=palette["BG"],
            font=ui_tokens.font("display", "bold"),
            padx=12,
            pady=4,
        )
        label.pack(side="left")

        run_btn = tk.Button(
            self,
            text="Run sample trade",
            command=on_run_sample,
            bg=palette["BG2"],
            fg=palette["ACCENT"],
            activebackground=palette["PANEL2"],
            activeforeground=palette["ACCENT2"],
            relief="flat",
            padx=10,
            pady=2,
        )
        run_btn.pack(side="right", padx=6, pady=2)

        self.result_var = tk.StringVar(value="")
        result_lbl = tk.Label(
            self,
            textvariable=self.result_var,
            bg=palette["ACCENT"],
            fg=palette["BG"],
            font=ui_tokens.font("small", "italic"),
            padx=8,
        )
        result_lbl.pack(side="right")

    def set_result(self, text: str) -> None:
        self.result_var.set(text)


def attach_trading_section_label(parent: tk.Misc, palette: Dict[str, str]) -> tk.Label:
    """
    Owner spec: "in the trading section, add the words 'PAPER TRADING'.
    In a contrasting font colour." Returns a tk.Label the caller packs above
    the trades table. Caller is responsible for destroying it on toggle off.
    """
    return tk.Label(
        parent,
        text="PAPER TRADING",
        bg=palette["BG"],
        fg=palette["ACCENT"],
        font=ui_tokens.font("title", "bold"),
        pady=2,
    )


# --- Read settings without instantiating the hub ----------------------------
def read_paper_mode_from_disk(settings_path: Optional[str] = None) -> bool:
    """
    Used by pt_hub before settings are loaded into self so the very first
    `_apply_forced_dark_mode` call can paint the window the right color
    immediately - no flash of dark theme before paper mode kicks in.

    Reads `trading.mode` from the settings file (default: pt_config.json in
    the user config folder, see pt_paths). A missing, unreadable or malformed
    file means paper.
    """
    return is_paper_mode(settings_path)


def settings_path_for(app_dir: str, filename: Optional[str] = None) -> str:
    import pt_paths

    return os.path.join(app_dir, filename or pt_paths.GUI_SETTINGS_FILE)
