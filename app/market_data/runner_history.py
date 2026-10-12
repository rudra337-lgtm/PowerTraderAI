"""
Recent candles for the legacy neural runner (pt_thinker), from the source the
pattern trainer learns from: Binance spot ``<COIN>USDT`` klines (public endpoint,
no keys).

pt_thinker parses KuCoin-style kline text, so ``kucoin_text`` returns rows
newest first: row 0 is the bar still forming, row 1 the last closed bar, and
each row is ``[open_time_s, open, close, high, low, volume, quote_volume]``.

Nothing is written to disk (the trainer owns the candle cache files); results
are kept in memory for up to ``ttl`` seconds, and never past the forming bar's
close, because the runner asks for the same coin and timeframe several times
per pass.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Callable, Dict, Optional, Tuple

from market_data.candles import BinanceKlines, CandleDataError, CandleFetchError
from market_data.timeframes import bar_open_floor, candle_timeframe_seconds

# The runner's timeframe names (pt_thinker.tf_choices) -> Binance intervals.
RUNNER_TIMEFRAMES = {
    "1hour": "1h",
    "2hour": "2h",
    "4hour": "4h",
    "8hour": "8h",
    "12hour": "12h",
    "1day": "1d",
    "1week": "1w",
}


def binance_pair(coin: str) -> str:
    """'BTC', 'BTC-USDT', 'BTCUSDT' or 'btc-usd' -> 'BTCUSDT'."""
    base = coin.upper().strip().replace("-", "").replace("/", "")
    for quote in ("USDT", "USDC", "USD"):
        if base.endswith(quote) and len(base) > len(quote):
            base = base[: -len(quote)]
            break
    return f"{base}USDT"


def binance_interval(timeframe: str) -> str:
    """'1hour' -> '1h'; Binance names ('4h', '1w') pass through."""
    tf = timeframe.strip()
    tf = RUNNER_TIMEFRAMES.get(tf, tf)
    candle_timeframe_seconds(tf)  # raises ValueError for an unknown timeframe
    return tf


class RecentCandles:
    """The last few candles per (pair, interval), fetched at most once per ``ttl``."""

    def __init__(
        self,
        fetcher: Optional[BinanceKlines] = None,
        ttl: float = 30.0,
        closed_bars: int = 3,
        clock: Callable[[], float] = time.time,
    ) -> None:
        # One request per call: the runner retries on its own and must not stall.
        self._fetcher = fetcher or BinanceKlines(max_retries=0, timeout=10.0)
        self._ttl = ttl
        self._closed_bars = closed_bars
        self._clock = clock
        self._cache: Dict[Tuple[str, str], Tuple[float, str]] = {}
        self._lock = threading.Lock()

    def kucoin_text(self, coin: str, timeframe: str) -> str:
        from pt_exchange_abstraction import MarketNotFound

        pair, tf = binance_pair(coin), binance_interval(timeframe)
        now = self._clock()
        with self._lock:
            hit = self._cache.get((pair, tf))
        if hit is not None and now < hit[0]:  # (expiry, text)
            return hit[1]

        step = candle_timeframe_seconds(tf)
        forming_open = bar_open_floor(int(now), tf)
        start = forming_open - self._closed_bars * step
        try:
            raw = self._fetcher.fetch(pair, tf, start * 1000)
        except CandleFetchError as exc:
            if getattr(exc.__cause__, "code", None) == 400:  # unknown symbol
                raise MarketNotFound(f"Binance has no spot market {pair}") from None
            raise

        closed, forming = [], None
        for r in raw:
            open_s = int(r[0]) // 1000
            row = [
                open_s,
                float(r[1]),  # open
                float(r[4]),  # close
                float(r[2]),  # high
                float(r[3]),  # low
                float(r[5]),  # volume
                float(r[7]) if len(r) > 7 else 0.0,  # quote volume
            ]
            if open_s + step <= now:
                closed.append(row)
            elif open_s == forming_open:
                forming = row
        if not closed:
            raise CandleDataError(f"no closed {tf} candle for {pair}")
        closed.sort(key=lambda row: row[0], reverse=True)
        if forming is None:  # no trade yet in this bar: a flat one at the last close
            last_close = closed[0][2]
            forming = [forming_open, last_close, last_close, last_close, last_close]
            forming += [0.0, 0.0]
        text = json.dumps([forming] + closed)
        # never served past the forming bar's close: row 1 must be the last closed bar
        expiry = min(now + self._ttl, forming_open + step)
        with self._lock:
            self._cache[(pair, tf)] = (expiry, text)
        return text


_shared: Optional[RecentCandles] = None


def kucoin_text(coin: str, timeframe: str) -> str:
    """``RecentCandles.kucoin_text`` on one shared instance per process."""
    global _shared
    if _shared is None:
        _shared = RecentCandles()
    return _shared.kucoin_text(coin, timeframe)
