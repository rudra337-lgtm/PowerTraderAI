"""
Is a Binance spot pair still trading?

The trainer and the runner take their candles from Binance spot (candles.py,
runner_history.py), so a pair Binance no longer trades has no new bars. Its signals
would be stale and its model would describe a market that is gone. This module asks
Binance's public exchange-information endpoint for the pair's status:

- ``TRADING``: the market is open;
- any other status Binance reports (``BREAK``, ``HALT``, ...): it is not trading;
- ``NOT_LISTED``: Binance does not know the pair (HTTP 400 "Invalid symbol").

A failed request gives an unknown status (``None``). Callers treat unknown as "no
verdict", never as "not trading", and fall back on their own checks (a pair with no
recent bars still gets no signals).

The verdict for each coin is also kept in ``market_status.json`` in the coin's folder.
The trainer and the runner write it, and the trader reads it, so a coin that is not
trading gets no buys even while no runner is running.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
TRADING = "TRADING"
NOT_LISTED = "NOT_LISTED"
MARKET_STATUS_FILE = "market_status.json"


@dataclass(frozen=True)
class PairStatus:
    pair: str
    status: Optional[str]  # Binance's status, NOT_LISTED, or None when unknown
    detail: str = ""

    @property
    def trading(self) -> Optional[bool]:
        """True or False when Binance answered; None when the status is unknown."""
        return None if self.status is None else self.status == TRADING

    def describe(self) -> str:
        if self.status is None:
            return f"status of Binance spot {self.pair} unknown ({self.detail})"
        if self.status == NOT_LISTED:
            return f"Binance has no spot market {self.pair}"
        if self.status == TRADING:
            return f"Binance spot {self.pair} is trading"
        return f"Binance spot {self.pair} is {self.status}, not trading"


class ListingChecker:
    """Cached status lookups: a known status is kept for ``ttl`` seconds, an unknown
    one for ``retry_ttl`` seconds."""

    def __init__(
        self,
        opener: Optional[Callable] = None,
        clock: Callable[[], float] = time.time,
        ttl: float = 3600.0,
        retry_ttl: float = 300.0,
        timeout: float = 5.0,
    ) -> None:
        self._opener = opener  # None: urllib.request.urlopen, looked up per request
        self._clock = clock
        self._ttl = ttl
        self._retry_ttl = retry_ttl
        self._timeout = timeout
        self._cache: Dict[str, Tuple[float, PairStatus]] = {}
        self._lock = threading.Lock()

    def status(self, pair: str) -> PairStatus:
        pair = str(pair).upper().replace("-", "")
        now = self._clock()
        with self._lock:
            hit = self._cache.get(pair)
        if hit is not None and now < hit[0]:
            return hit[1]
        result = self._fetch(pair)
        ttl = self._retry_ttl if result.status is None else self._ttl
        with self._lock:
            self._cache[pair] = (now + ttl, result)
        return result

    def _fetch(self, pair: str) -> PairStatus:
        url = f"{EXCHANGE_INFO_URL}?{urllib.parse.urlencode({'symbol': pair})}"
        try:
            opener = self._opener or urllib.request.urlopen
            with opener(url, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 400:  # {"code": -1121, "msg": "Invalid symbol."}
                return PairStatus(pair, NOT_LISTED, "Invalid symbol")
            return PairStatus(pair, None, f"HTTP {exc.code}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return PairStatus(pair, None, str(exc) or type(exc).__name__)
        for entry in (data or {}).get("symbols", []) if isinstance(data, dict) else []:
            if str(entry.get("symbol", "")).upper() == pair:
                status = str(entry.get("status") or "").upper()
                return PairStatus(pair, status or None, "" if status else "no status")
        return PairStatus(pair, NOT_LISTED, "not in exchange information")


_shared: Optional[ListingChecker] = None
_shared_lock = threading.Lock()


def pair_status(pair: str) -> PairStatus:
    """The shared, cached status of a Binance spot pair (e.g. ``HYPEUSDT``)."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = ListingChecker()
        checker = _shared
    return checker.status(pair)


# --- the per-coin verdict file -----------------------------------------------------


def write_market_status(folder: str, pair: str, trading: bool, reason: str) -> bool:
    """Record whether the coin's market is trading, in ``folder``. Returns whether the
    record was written; never raises. On Windows the replace fails while another
    process has the file open (the trader reads it every pass), so it is retried
    briefly, as the runner's signal files are."""
    record = {
        "pair": str(pair).upper(),
        "trading": bool(trading),
        "reason": str(reason),
        "checked_at": int(time.time()),
    }
    path = os.path.join(folder, MARKET_STATUS_FILE)
    tmp = f"{path}.writing"
    try:
        os.makedirs(folder, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f)
    except Exception:
        return False
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.1)
        except Exception:
            break
    try:
        os.remove(tmp)
    except OSError:
        pass
    return False


def read_market_status(folder: str) -> Optional[dict]:
    """The recorded verdict, or None if there is none (or it is unreadable)."""
    try:
        with open(os.path.join(folder, MARKET_STATUS_FILE), encoding="utf-8") as f:
            record = json.load(f)
        return record if isinstance(record, dict) and "trading" in record else None
    except Exception:
        return None


def not_trading_reason(folder: str) -> Optional[str]:
    """Why the coin in ``folder`` must not be traded, or None if nothing says so."""
    record = read_market_status(folder)
    if record is None or record.get("trading") is not False:
        return None
    return str(record.get("reason") or "its market is not trading")
