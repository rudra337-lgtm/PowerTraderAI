"""Settings > Paper Account: see and set every value of the paper trader's book.

The paper trader keeps its account in ``<hub>/paper/paper_account.json`` (starting
balance, cash, and each held coin's quantity and average price). It loads that
file once, when it starts, and saves over it after every paper order. So this
window only saves while the trader is stopped, and the new values apply the next
time the trader starts.

Saving also sets each position's cost basis in the paper P&L ledger
(``pnl_ledger.json``): the trader takes the cost basis for take-profit and DCA
from the ledger, not from the book. Reset backs up the ledger and the paper
history first (renamed, never deleted), so profit and loss start from zero.

The file format and the checks live in ``trading_mode`` (shared with the
trader); this module is only the window.
"""

from __future__ import annotations

import json
import tkinter as tk
from decimal import Decimal
from tkinter import messagebox as _messagebox
from tkinter import ttk
from typing import Callable, Dict, Iterable, Optional, Tuple

import trading_mode as tm
import ui_tokens

TITLE = "Paper Account"
STOP_THE_TRADER = "Stop the trader first"


def _plain(number: Decimal) -> str:
    """``Decimal('1E+4')`` -> ``'10000'``, ``Decimal('0.50')`` -> ``'0.5'``."""
    text = format(number.normalize(), "f")
    return text


class PaperAccountDialog(tk.Toplevel):
    """A window over ``parent`` for the paper book in ``hub_dir``.

    ``trader_running()`` returns why saving must wait (the trader is running or
    about to start), or None. It is asked when the window opens (to warn) and
    again at the moment of saving. The window is not modal, so the trader can be
    stopped while it stays open. ``known_coins`` are the hub's coins, used to warn
    about a position the trader may have no price for. ``live`` says the hub is in
    live mode (the paper book is then used only after switching back to paper).
    ``on_saved()`` is called after a successful save (the hub refreshes its
    Account panel)."""

    def __init__(
        self,
        parent: tk.Misc,
        hub_dir: str,
        trader_running: Callable[[], Optional[str]],
        known_coins: Iterable[str] = (),
        messagebox=None,
        palette: Optional[dict] = None,
        live: bool = False,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.title(TITLE)
        self.hub_dir = hub_dir
        self.book_path = tm.paper_book_path(hub_dir)
        self.ledger_path = tm.paper_ledger_path(hub_dir)
        self._trader_running = trader_running
        self._known = {str(c).strip().upper() for c in known_coins if str(c).strip()}
        self._box = messagebox or _messagebox
        self._live = live
        self._on_saved = on_saved
        self._reset_pending = False
        self.positions: Dict[str, Tuple[str, str]] = {}  # SYM -> (quantity, price)
        self._loaded_positions: Dict[str, Tuple[str, str]] = {}
        if palette and palette.get("BG"):
            self.configure(bg=palette["BG"])

        self.initial_var = tk.StringVar(master=self)
        self.cash_var = tk.StringVar(master=self)
        self.symbol_var = tk.StringVar(master=self)
        self.qty_var = tk.StringVar(master=self)
        self.price_var = tk.StringVar(master=self)
        self.status_var = tk.StringVar(master=self)

        try:
            self._build()
            self._load()
        except Exception:
            self.destroy()  # never leave a half-built window behind
            raise
        self._loaded_positions = dict(self.positions)
        notes = []
        if live:
            notes.append(
                "Trading Mode is live: this paper account is used when you switch "
                "back to paper."
            )
        reason = trader_running()
        if reason:
            notes.append(reason)
        if notes:
            self.status_var.set(" ".join([self.status_var.get()] + notes))
        self.transient(parent)

    # -- layout --
    def _build(self) -> None:
        body = ttk.Frame(self, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        ttk.Label(
            body, text="Paper trading account", font=ui_tokens.font("body", "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(body, textvariable=self.status_var, wraplength=560).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 10)
        )

        ttk.Label(body, text="Starting balance (USD):").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=4
        )
        self.initial_entry = ttk.Entry(body, textvariable=self.initial_var, width=18)
        self.initial_entry.grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(
            body, text="what the account started with; returns are measured from it"
        ).grid(row=2, column=2, sticky="w", padx=(10, 0))
        ttk.Label(body, text="Cash balance (USD):").grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=4
        )
        self.cash_entry = ttk.Entry(body, textvariable=self.cash_var, width=18)
        self.cash_entry.grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(body, text="what the trader can spend").grid(
            row=3, column=2, sticky="w", padx=(10, 0)
        )

        ttk.Label(body, text="Positions", font=ui_tokens.font("body", "bold")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(12, 4)
        )
        columns = ("symbol", "quantity", "price", "cost")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", height=6)
        for col, heading, width in (
            ("symbol", "Coin", 80),
            ("quantity", "Quantity", 140),
            ("price", "Average price (USD)", 160),
            ("cost", "Cost (USD)", 140),
        ):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor="e" if col != "symbol" else "w")
        self.tree.grid(row=5, column=0, columnspan=3, sticky="nsew")
        body.rowconfigure(5, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        edit = ttk.Frame(body)
        edit.grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))
        for i, (label, var, width) in enumerate(
            (
                ("Coin:", self.symbol_var, 8),
                ("Quantity:", self.qty_var, 14),
                ("Average price:", self.price_var, 14),
            )
        ):
            ttk.Label(edit, text=label).grid(row=0, column=2 * i, padx=(0, 4))
            ttk.Entry(edit, textvariable=var, width=width).grid(
                row=0, column=2 * i + 1, padx=(0, 10)
            )
        ttk.Button(edit, text="Add / Update", command=self.add_position).grid(
            row=0, column=6, padx=(0, 6)
        )
        ttk.Button(edit, text="Remove", command=self.remove_position).grid(
            row=0, column=7
        )

        ttk.Label(
            body,
            wraplength=560,
            text=(
                "A position counts as a coin the trader already holds: it opens no "
                "new entry in that coin while it is held, and strategy exits sell "
                "at most this quantity. Saving also sets each position's cost basis "
                "(quantity x average price) in the paper profit-and-loss ledger, so "
                "take-profit and DCA can act on it."
            ),
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(body, text=f"Saved in {self.book_path}", wraplength=560).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        buttons = ttk.Frame(body)
        buttons.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Reset...", command=self.reset).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        self.save_button = ttk.Button(buttons, text="Save", command=self.save)
        self.save_button.pack(side="right", padx=(0, 6))

    # -- data --
    def _load(self) -> None:
        book = None
        try:
            book = tm.read_paper_book(self.book_path)
        except tm.PaperBookUnreadable as exc:
            self.status_var.set(
                f"{exc} The trader cannot use it either: when it starts it keeps the "
                "file as paper_account.json.bad-<date-time> and begins a fresh "
                "$10,000 account. Set the values below and save to replace it."
            )
        except tm.PaperBookInvalid as exc:
            self.status_var.set(
                f"The saved paper account has a problem: {exc} The trader still "
                "loads these values as written. Correct them and save."
            )
            if self._load_raw():  # show what the file says, so it can be fixed
                return
        else:
            self.status_var.set(
                "No saved paper account yet. The trader starts with $10,000 and "
                "saves it when it starts. You can set the values now; they apply "
                "when the trader starts."
                if book is None
                else "This is the saved paper account. Changes apply the next time "
                "the trader starts."
            )
        if book is None:
            default = tm.DEFAULT_PAPER_BALANCE
            book = tm.PaperBook(default, default, {})
        self.initial_var.set(_plain(book.initial_balance))
        self.cash_var.set(_plain(book.cash_balance))
        self.positions = {
            sym: (_plain(qty), _plain(price))
            for sym, (qty, price) in book.positions.items()
        }
        self._refresh_tree()

    def _load_raw(self) -> bool:
        """Fill the form with a saved book's values as written, when it parses as
        JSON but fails a check (e.g. a starting balance of 0). False otherwise."""
        try:
            with open(self.book_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            initial = str(state.get("initial_balance", tm.DEFAULT_PAPER_BALANCE))
            cash = str(state["cash_balance"])
            positions = {}
            for sym, p in (state.get("positions") or {}).items():
                key = str(sym).strip().upper()
                if not key or key in positions:
                    return False  # an empty or repeated coin: show the defaults
                positions[key] = (str(p["quantity"]), str(p["average_price"]))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return False
        self.initial_var.set(initial)
        self.cash_var.set(cash)
        self.positions = positions
        self._refresh_tree()
        return True

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for sym in sorted(self.positions):
            qty, price = self.positions[sym]
            try:
                cost = f"{Decimal(qty) * Decimal(price):,.2f}"
            except ArithmeticError:
                cost = ""
            self.tree.insert("", "end", iid=sym, values=(sym, qty, price, cost))

    def _on_select(self, _event=None) -> None:
        selected = self.tree.selection()
        if selected and selected[0] in self.positions:
            qty, price = self.positions[selected[0]]
            self.symbol_var.set(selected[0])
            self.qty_var.set(qty)
            self.price_var.set(price)

    def add_position(self) -> bool:
        """Add the coin in the edit row, or update it if it is already listed."""
        symbol = self.symbol_var.get().strip().upper()
        try:
            checked = tm.validate_paper_book(
                1, 0, {symbol: (self.qty_var.get(), self.price_var.get())}
            )
        except tm.PaperBookError as exc:
            self._box.showerror(TITLE, str(exc), parent=self)
            return False
        ((sym, (qty, price)),) = checked.positions.items()
        self.positions[sym] = (_plain(qty), _plain(price))
        self._refresh_tree()
        for var in (self.symbol_var, self.qty_var, self.price_var):
            var.set("")
        return True

    def remove_position(self) -> None:
        """Remove the coin typed in the edit row, or else the selected coins."""
        typed = self.symbol_var.get().strip().upper()
        targets = [typed] if typed else list(self.tree.selection())
        for sym in targets:
            self.positions.pop(sym, None)
        for var in (self.symbol_var, self.qty_var, self.price_var):
            var.set("")
        self._refresh_tree()

    def _edit_row_pending(self) -> bool:
        """True when the edit row holds a position not yet added (or changed)."""
        typed = tuple(
            v.get().strip() for v in (self.symbol_var, self.qty_var, self.price_var)
        )
        if not any(typed):
            return False
        sym = typed[0].upper()
        return self.positions.get(sym) != (typed[1], typed[2])

    def reset(self) -> bool:
        """Cash back to the starting balance and no positions; on Save the ledger
        and paper history are backed up so P&L starts from zero."""
        try:
            book = tm.validate_paper_book(
                self.initial_var.get(), self.initial_var.get(), {}
            )
        except tm.PaperBookError as exc:
            self._box.showerror(TITLE, str(exc), parent=self)
            return False
        if not self._box.askyesno(
            "Reset paper account?",
            "Set the cash to the starting balance "
            f"(${book.initial_balance:,.2f}) and remove all positions?\n\n"
            "When you save, the paper ledger, trade history, account-value history, "
            "strategy state and trader status are backed up (renamed to "
            "<name>.bak-<date-time>, nothing is deleted), so profit and loss start "
            "from zero.",
            parent=self,
        ):
            return False
        self.cash_var.set(_plain(book.initial_balance))
        self.positions = {}
        self._refresh_tree()
        self._reset_pending = True
        self.status_var.set("Reset: press Save to apply it.")
        return True

    def save(self) -> bool:
        """Write the book (and the ledger's cost basis), unless the trader runs."""
        reason = self._trader_running()
        if reason:
            self._box.showerror(STOP_THE_TRADER, reason, parent=self)
            return False
        if self._edit_row_pending() and not self.add_position():
            return False  # the typed position is not valid: nothing saved
        try:
            book = tm.validate_paper_book(
                self.initial_var.get(), self.cash_var.get(), self.positions
            )
        except tm.PaperBookError as exc:
            self._box.showerror(TITLE, str(exc), parent=self)
            return False
        unknown = sorted(
            s for s in book.positions if self._known and s not in self._known
        )
        if unknown and not self._box.askyesno(
            "Coins not in your list",
            f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not in "
            "your coin list, so the trader may not price or trade "
            f"{'it' if len(unknown) == 1 else 'them'}. Save anyway?",
            parent=self,
        ):
            return False
        backed_up = []
        try:
            if self._reset_pending:
                backed_up = tm.backup_paper_history(self.hub_dir)
            tm.write_paper_book(self.book_path, book)
            untouched = [
                sym
                for sym, entry in self.positions.items()
                if not self._reset_pending and self._loaded_positions.get(sym) == entry
            ]
            tm.write_paper_ledger_positions(
                self.ledger_path,
                book,
                reset_realized=self._reset_pending,
                keep_cost=untouched,
            )
        except OSError as exc:
            self._box.showerror(
                TITLE, f"Could not save the paper account: {exc}", parent=self
            )
            return False
        held = ", ".join(
            f"{sym} {_plain(qty)} @ ${_plain(price)}"
            for sym, (qty, price) in sorted(book.positions.items())
        )
        message = (
            f"Saved: cash ${book.cash_balance:,.2f}; positions: {held or 'none'}.\n\n"
            + (
                "Switch Trading Mode back to paper to use it."
                if self._live
                else "The Account panel shows these values now. Start the trader "
                "(the \u25ba button in the Trading section) to trade with them."
            )
        )
        if backed_up:
            message += (
                f"\n\nBacked up {len(backed_up)} history file(s) in the paper folder."
            )
        self._box.showinfo(TITLE, message, parent=self)
        self.destroy()
        if self._on_saved is not None:
            try:
                self._on_saved()
            except Exception:
                pass  # the book is saved; a refresh problem must not hide that
        return True
