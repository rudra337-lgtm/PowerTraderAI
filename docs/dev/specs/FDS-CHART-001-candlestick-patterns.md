# FDS-CHART-001 — Candlestick Patterns on the Hub Chart (display only)

**Issue:** none yet. Raise "Show candlestick patterns on the chart" and link it here.
**Target repo:** `sjackson0109/powertraderai`
**Branch:** this spec is on `docs/fds-chart-001-candlestick-patterns`, cut from `main` at `8f8c1d0`. Phase 1 is built on `feat/chart-patterns-1`, cut from `main` after this spec is merged.
**Recommended model:** Claude Opus 5.5, effort high, for the detection module and its tests. Sonnet 5.5, effort high, for the chart and settings wiring.
**Run log:** `docs/dev/RUN-LOG-chart-patterns-1.md`.
**Status:** draft for owner review. This version is the owner's UI-CHANGE draft revised after a review on 2026-10-12, with the owner's decisions of 2026-10-12 and 2026-10-13 (§12). Phase 1 is implemented on `feat/chart-patterns-1` (§6.8 records the exact rules as built). It changes no trainer, strategy or trading code.
**Related:** FDS-SIG-001 (`docs/dev/specs/FDS-SIG-001-signal-candidate-audit.md`) and FDS-SIG-002 (`docs/dev/specs/FDS-SIG-002-round-one-candidates.md`). This spec registers nothing with them (§10).

---

## 1. Objective

Detect classical candlestick patterns on the coin chart and show them as small labels. A user can see which candles a
pattern used, what its textbook meaning is, and that its reliability on this market has not been measured.

The point is to make pattern claims inspectable and questionable, not to act on them. Nothing here feeds
`strategy.engine`, the trainer, the runner or the trader.

## 2. Background: the chart today

The live chart is `CandleChart` in `app/pt_hub.py`: one matplotlib Axes on a Tk canvas. It is created for each coin tab.
`app/pt_hub_chart_components.py` has another `CandleChart`, but nothing imports it.

| Aspect | Today |
|---|---|
| **Candle source** | **KuCoin** `{COIN}-USDT`, through `CandleFetcher.get_klines(symbol, timeframe, limit=120)`. The trainer, the runner and the FDS-SIG-001 audit use **Binance** spot `{COIN}USDT` (`app/market_data/candles.py`). |
| **Window** | Always the newest 120 bars, ending now. The fetch asks for about 200 and keeps the newest 120. |
| **Forming bar** | Included: the last candle is still forming. |
| **Refresh** | Every 10 s (`chart_refresh_seconds`), and on a timeframe change, the chart is cleared and redrawn (`ax.cla()`). Candles are plotted by list index, so every candle shifts one place when a new bar arrives. |
| **Fetch thread** | Synchronous, on the Tk thread, with a 10 s timeout. |
| **Missing bars** | KuCoin publishes no bar for an interval with no trades. The chart does not check that timestamps are consecutive. |
| **Candle colours** | Matplotlib `"green"` (#008000) up and `"red"` (#FF0000) down, bodies at alpha 0.9, on `DARK_PANEL` #0E1626 (figure `DARK_BG` #070B10). Both are fully saturated, and red is the brighter. The two differ by only 1.28:1 in luminance, which is the weakness. |
| **Overlays** | The neural long and short price levels are full-width lines in `"blue"` and `"orange"` with no label. "Neural: long=N short=N" is a toolbar text label, not a line. ASK, BID, AVG, DCA and SELL lines are labelled at the right edge. `"green"` and `"red"` are also used for the SELL trail line, the DCA line and the trade dots. |
| **Timeframes** | 1min, 5min, 15min, 30min, 1hour, 2hour, 4hour, 8hour, 12hour, 1day and 1week (`DEFAULT_SETTINGS["timeframes"]`). `app/market_data/timeframes.py` supports the same set on Binance (1m to 1d, plus 1w as candle-only). |
| **Settings** | There is no chart-settings area, and the chosen timeframe is not saved. |

Candlestick notation for raw OHLC is long established. The named patterns drawn on it have **no demonstrated predictive
value on this data** (§10).

## 3. Scope, non-goals and phases

- **Phase 1 (this spec):**
  - detection on Binance closed bars;
  - labels, hover and click detail;
  - a **Chart settings** pop-out with a planned on/off toggle for every chart overlay: each existing line, the markers,
    the Neural readout, and each candlestick pattern and pattern group (§8);
  - an alternate palette and hollow-up candles.
- **Phase 2 (a separate spec):** timeframe drill-down (§11). It needs new fetch work and is not part of phase 1.
- **Non-goals:**
  - No detection result reaches `strategy.engine`, the trainer, the runner, the trader or paper trading.
  - The existing overlays are drawn exactly as today, with the same colours, values and positions. The only change is
    that each one can be hidden from Chart settings (§8), and every one is shown by default. Their contrast problems
    are noted in §9, for a separate change.
  - Hiding an overlay never changes what the runner, trader or trainer compute or do.
  - **No percentage from published sources appears anywhere in the UI** (§10).
  - The candle source of the chart itself does not change.

## 4. Data: detect on Binance closed bars

**Hard requirement.** Patterns are detected on **Binance spot closed bars**, read through
`market_data.candles.get_candles(..., closed_only=True)`, not on the KuCoin bars the chart draws. That way a detection
is exactly the event a future FDS-SIG-001 audit would score, on the same venue and bars (§10).

1. **What is fetched:** for the displayed coin and timeframe, the bars matching the chart's visible window, plus each
   rule's warm-up bars (§5.3). Warm-up bars are never drawn.
2. **Off the Tk thread:** the fetch and the detection run in a background thread. Results are applied with `after()`.
   While detection runs, the chart shows no labels and a small "detecting…" note.
3. **Placement:** a detection is drawn on the chart candle whose **open time** equals the Binance bar's open time. If
   no chart candle has that open time, the detection is listed in the detail panel only and not drawn. This happens with
   a missing KuCoin bar, a venue mismatch, or weekly bars aligned differently.
4. **No Binance market:**
   - If the coin has no Binance spot market, or `market_status.json` records it as not trading (`market_data/listing.py`),
     the chart shows "Candlestick patterns: no Binance market" and detects nothing.
   - The listing check uses the shared cached check, so it adds at most one request per coin per hour.
5. **Refresh:** detection re-runs only when a new Binance bar has closed for the displayed timeframe, not every 10 s.

## 5. Detection rules (all patterns)

### 5.1 Closed and contiguous bars

- **Closed bars only.** A pattern is detected only when every bar in its window, including its trend-context bars, has
  closed. The forming bar is never part of a detection, so no label appears and then vanishes.
- **Time-contiguous.** The bars in a window, including warm-up and trend context, must have consecutive open times
  exactly one timeframe apart. Otherwise there is no match.

### 5.2 Reference definitions and tolerances

Each rule follows the **TA-Lib** candlestick function named in §6, with TA-Lib's default candle settings, unless this
section or §6 says otherwise. TA-Lib's code is the codeable reference. Phase 1 reimplements the rules in pure Python and
adds no dependency.

The shared definitions (TA-Lib defaults) are:

| Term | Definition |
|---|---|
| Range | high − low |
| Body | \|close − open\| |
| Upper shadow | high − max(open, close) |
| Lower shadow | min(open, close) − low |
| Average range R(n) | mean range of the previous n closed bars |
| Average body B(n) | mean body of the previous n closed bars |
| **Doji** | body ≤ 0.10 × R(10) |
| Long body | body > B(10) |
| Short body | body < B(10) |
| Long shadow | shadow > body |
| Very long shadow | shadow > 2 × body |
| Very short shadow | shadow < 0.10 × R(10) |
| **Equal** | within 0.05 × R(5) |
| **Near** | within 0.20 × R(5) |
| Far | at least 0.60 × R(5) |

These choices follow from the draft and the review:

- **The doji is measured against the average range of the previous 10 bars,** not the bar's own range. The draft's
  "body / own range < 10%" divides by zero on a flat bar (high = low), which happens on thin 1-minute bars. A flat bar has
  body 0, so it is a doji here; it is shown as a "Four-price doji".
- **Comparisons against another body's edge are inclusive** (≤ and ≥), and "matching" tests use "equal".
  - On 24/7 markets a bar opens at the previous close on about half of all bars. On the repo's recorded Binance 1h BTC
    data, the open equals the previous close on 774 of 1,512 bars, and every open is within 0.6 basis points of it.
  - So strict versus inclusive decides whether many rules fire at all. On BTC 1h, Bullish Engulfing fires 32 times
    strict and 129 inclusive.

### 5.3 Trend context and warm-up

Patterns marked "needs trend" in §6 use one fixed rule, computed on closed bars before the pattern's first bar s:

- **Downtrend:** close[s−1] < SMA₁₀(close)[s−1], and SMA₁₀[s−1] < SMA₁₀[s−4].
- **Uptrend:** the mirror.
- **Otherwise:** no trend, and a pattern that needs one is not detected.

N = 10 and k = 3 are fixed here and change only by an amendment to this spec. Each rule's warm-up is its window, plus
the bars its averages need (13 for the trend rule, 10 for R(10) and B(10)).

### 5.4 One label per candle

- **Merging:** consecutive detections of the same pattern merge into one label, and its bracket covers the whole run.
- **Precedence on one candle:**
  1. the pattern with the most bars wins;
  2. then a classical pattern beats a price-action pattern (§6.6);
  3. then the order in the §6 tables.

  The rest are shown as a "+n" badge, expanded on hover.
- **Staggering:** labels on the same side within 10 candles of each other are raised one level each (up to four
  levels, 16 pt apart), so they do not sit on top of each other.
- **Cap:** at most 12 labels per chart by default ("Max labels per chart", §8.3), in this priority:
  1. the pinned Three White Soldiers and Three Black Crows (§6.3);
  2. then by bar count;
  3. then by recency.

  A note says how many detections were hidden.

## 6. Pattern library

**Tags are textbook meaning, not measured behaviour.** The UI shows "textbook meaning" next to every tag. Bulkowski's
tests found several patterns behave opposite to their textbook meaning (§10.3).

Each pattern has a direction (`bullish`, `bearish` or `none`) and a type (`reversal`, `continuation` or `indecision`).
Rows marked **24/7** replace a textbook gap with a body-position test. They are different rules from the textbook
patterns, and no published figure applies to them.

### 6.1 One bar

| Pattern | Direction | Type | Needs trend | Reference |
|---|---|---|---|---|
| Doji | none | indecision | no | CDLDOJI |
| Four-price doji (flat bar) | none | indecision | no | §5.2 |
| Long-legged doji | none | indecision | no | CDLLONGLEGGEDDOJI |
| Dragonfly doji | bullish | indecision | no | CDLDRAGONFLYDOJI |
| Gravestone doji | bearish | indecision | no | CDLGRAVESTONEDOJI |
| Spinning top (white body) | none | indecision | no | CDLSPINNINGTOP |
| Spinning top (black body) | none | indecision | no | CDLSPINNINGTOP |
| High wave | none | indecision | no | CDLHIGHWAVE |
| Hammer | bullish | reversal | downtrend | CDLHAMMER |
| Hanging man | bearish | reversal | uptrend | CDLHANGINGMAN |
| Inverted hammer | bullish | reversal | downtrend | CDLINVERTEDHAMMER |
| Shooting star | bearish | reversal | uptrend | CDLSHOOTINGSTAR |
| Belt hold, bullish | bullish | reversal | downtrend | CDLBELTHOLD |
| Belt hold, bearish | bearish | reversal | uptrend | CDLBELTHOLD |

The draft's "Bullish/Bearish Spinning Top" referred to body colour, not direction, so both are indecision here.

### 6.2 Two bars

| Pattern | Direction | Type | Needs trend | Reference |
|---|---|---|---|---|
| Bullish engulfing | bullish | reversal | downtrend | CDLENGULFING |
| Bearish engulfing | bearish | reversal | uptrend | CDLENGULFING |
| Bullish harami | bullish | reversal | downtrend | CDLHARAMI |
| Bearish harami | bearish | reversal | uptrend | CDLHARAMI |
| Tweezer bottom (equal lows) | bullish | reversal | downtrend | Bulkowski "Tweezers bottom" |
| Tweezer top (equal highs) | bearish | reversal | uptrend | Bulkowski "Tweezers top" |
| Piercing line (24/7) | bullish | reversal | downtrend | §6.5 |
| Dark cloud cover (24/7) | bearish | reversal | uptrend | §6.5 |
| Matching low | bullish | reversal | downtrend | CDLMATCHINGLOW |
| Matching high (non-canonical mirror) | bearish | reversal | uptrend | mirror of CDLMATCHINGLOW |

**Matching low** is two black candles with **equal closes** ("equal", §5.2), not equal lows. Equal lows or highs is the
Tweezer rule. **Matching high** is the mirror, with two white candles and equal closes. It appears in secondary sources
only, and the UI marks it "non-canonical". Both are drawn as a short labelled segment between the two closes, never as a
full-width line.

### 6.3 Three bars

| Pattern | Direction | Type | Needs trend | Reference |
|---|---|---|---|---|
| Morning star (24/7) | bullish | reversal | downtrend | §6.5 |
| Morning doji star (24/7) | bullish | reversal | downtrend | §6.5 |
| Evening star (24/7) | bearish | reversal | uptrend | §6.5 |
| Evening doji star (24/7) | bearish | reversal | uptrend | §6.5 |
| **Three white soldiers** (pinned) | bullish | reversal | downtrend | below |
| **Three black crows** (pinned) | bearish | reversal | uptrend | below |
| Three outside up | bullish | reversal | downtrend | CDL3OUTSIDE |
| Three outside down | bearish | reversal | uptrend | CDL3OUTSIDE |
| Three inside up | bullish | reversal | downtrend | CDL3INSIDE |
| Three inside down | bearish | reversal | uptrend | CDL3INSIDE |

**Three white soldiers and three black crows are always visible** (owner, §12). Their thresholds are fixed here,
because no toggle can hide them. Three white soldiers needs a downtrend before bar 1, and three bars that are each:
- white, with a long body (> B(10));
- closing higher than the previous bar;
- opening within or at the edge of the previous bar's body, inclusive (bars 2 and 3);
- with an upper shadow of at most 0.25 × body.

Three black crows is the mirror, with a lower shadow of at most 0.25 × body.

On the recorded 1h fixtures, the rule as pinned fired once in about 3,000 bars: 0 times in 1,513 BTC bars and once in
1,512 ETH bars. A looser rule without the body, shadow and trend limits fired 14–17 times per 120 bars, as overlapping
runs. That is why the thresholds are pinned: an always-visible label must be rare.

The draft also tagged both "continuation". In theory both are reversal patterns, so that tag is dropped.

### 6.4 Four, five and variable bars

| Pattern | Bars | Direction | Type | Needs trend | Reference |
|---|---|---|---|---|---|
| Rising three methods | 5 | bullish | continuation | uptrend | CDLRISEFALL3METHODS |
| Falling three methods | 5 | bearish | continuation | downtrend | CDLRISEFALL3METHODS |
| Mat hold | 5 | bullish | continuation | uptrend | Bulkowski "Mat hold" (no gap) |
| Three line strike, white strike | 4 | see note | see note | downtrend | CDL3LINESTRIKE |
| Three line strike, black strike | 4 | see note | see note | uptrend | CDL3LINESTRIKE |
| Hikkake, bullish / bearish | 3 + up to 3 | bullish / bearish | reversal | no | CDLHIKKAKE |

**Mat hold** and "Bullish mat hold" are the same pattern, and it has no bearish form. It is distinct from Rising three
methods: its reaction candles only need to stay above the first candle's low, not inside its range. Bulkowski's rule is
used, which has no gap; TA-Lib's version requires one. When both match the same bars, only Mat hold is shown.

**Three line strike** is named differently by different sources:
- Bulkowski's "bullish" form is three white candles plus a black candle (a continuation in theory).
- The common Farley/Investopedia "bullish" form is three black candles plus a white candle (a reversal).

So the rows are named by the strike candle's colour. The detail panel states both readings, and the direction tag
follows the strike candle's move.

**Hikkake** is confirmed up to three bars after its inside bar, so its label appears only once it is confirmed, on the
bars it used.

### 6.5 The 24/7 variants

These keep the body sequence that gives each pattern its meaning, and drop the gap that 24/7 bars never have.

| Variant | Rule |
|---|---|
| **Piercing line (24/7)** | Bar 1 black with a long body. Bar 2 white, opening at or below bar 1's close ("near") and closing above bar 1's body midpoint but below bar 1's open. |
| **Dark cloud cover (24/7)** | The mirror. |
| **Morning star (24/7)** | Bar 1 black with a long body. Bar 2 has a short body lying wholly below bar 1's body midpoint. Bar 3 is white and closes above bar 1's body midpoint. |
| **Morning doji star (24/7)** | As morning star, with bar 2 a doji. |
| **Evening star (24/7), evening doji star (24/7)** | The mirrors. |

The textbook forms need an opening gap, and on the repo's recorded Binance 1h BTC and ETH data they fired zero times.

### 6.6 Price-action patterns (Western, not classical)

| Pattern | Direction | Type | Reference |
|---|---|---|---|
| Pin bar, bullish (long lower tail) | bullish | reversal | price action: body in the top third, lower shadow ≥ 2 × body, upper shadow very short |
| Pin bar, bearish (long upper tail) | bearish | reversal | the mirror |
| Inside bar | none | indecision | high ≤ previous high and low ≥ previous low |
| Long lower wick | bullish | none | lower shadow ≥ 2 × body and ≥ 0.5 × range |
| Long upper wick | bearish | none | the mirror |

These have their own group in Settings, and they are shown only when no classical pattern matched the same candle
(§5.4). Hikkake is a price-action pattern too, but it is listed in §6.4 by length.

### 6.7 Dropped, and why

| Pattern | Why |
|---|---|
| Window (rising / falling), Upside / downside Tasuki gap | **Its meaning is the gap**, and gaps do not occur on 24/7 bars (owner, §12). "Tsuki" in the draft is spelt "Tasuki". |
| Kicker (bullish / bearish) | Its meaning is the gap (owner). |
| Abandoned baby (bullish / bearish) | Its meaning is the gap (owner). |
| Tri-star | Its meaning is the gap (owner). |
| Separating lines (bullish / bearish) | Its meaning is a shared open after a move, which 24/7 bars have on almost every bar (owner). |
| Counterattack lines = Meeting lines | One pattern under two names (§9.1 of the draft resolved). It opens with a gap in the trend direction, so it is dropped (owner). The draft also had its open direction backwards. |
| On-neck, Thrusting | They need an open below the prior low (owner). |
| In-neck | Dropped by the owner in the draft. |
| "Upside thrust" | Not a candlestick pattern. The nearest term, Wyckoff's "upthrust", is a bearish false breakout, a different idea. |
| Doji star (2-bar, standalone) | Its textbook form needs a gap. Its meaning survives in Morning and Evening doji star (24/7). |
| Ladder bottom, Concealing baby swallow | Their signal candles depend on gaps (same rule as above). Both are very rare. |
| Tower bottom | Not in Bulkowski or TA-Lib, and undefined in the draft. Can be added later with a definition. |

### 6.8 Rules as built

`app/candlestick_patterns.py` is the exact codification of every rule. Each rule is pinned by a matching fixture and
a near-miss fixture in `app/tests/test_candlestick_patterns.py`. Where the built rule goes beyond the TA-Lib reference
or this spec, it is listed here:

| Rule | As built | Why |
|---|---|---|
| Long-legged doji | A doji with **both** shadows ≥ 0.5 × R(10) | TA-Lib's "either shadow longer than the body" makes almost every doji long-legged. |
| Hammer, hanging man, inverted hammer, shooting star | Short body; the long shadow > 2 × body; the opposite shadow very short. The §5.3 trend decides the name. | Twice the body is Nison's rule; TA-Lib uses "longer than the body". TA-Lib's prior-candle position tests and the textbook gaps are not used. |
| Spinning tops, high wave | Exclude bars that are dojis | The doji is the more specific name. |
| Bullish / bearish engulfing | TA-Lib's rule: one body edge inclusive | As referenced. |
| Harami (and three inside up / down) | Inclusive containment; the direction comes from the first bar's colour | §5.2 inclusive edges. |
| Tweezer bottom / top | Black then white with equal lows / white then black with equal highs | Bulkowski's colour order. |
| Rising / falling three methods | Three short bodies inside the first bar's range; the fifth bar opens "near" the fourth close | A strict open beyond the fourth close rarely happens on 24/7 bars. |
| Three line strike | Bars 2 and 3 open within the previous body (with "near"); the strike opens near the third close | §5.2 tolerances. |
| Hikkake | TA-Lib's strict inside bar; confirmed by a close beyond the inside bar within three bars of the false break; first confirmation only | As referenced. |
| Pin bar | Body in the top (bottom) third, tail ≥ 2 × body, opposite shadow very short | Written out from §6.6. |
| Inside bar | Inclusive containment, with a smaller range than the previous bar | Two identical bars are not "inside". |
| Long lower / upper wick | Shadow ≥ 2 × body and ≥ half the range | As §6.6. |

## 7. Display and interaction (phase 1)

**Labels.**
- **Style:** a small text label above (bullish), below (bearish) or beside (none) its candle. The text is in `DARK_FG`,
  at least 4.5:1 against `DARK_PANEL`, and direction is shown by a glyph, not by hue: ▲ bullish, ▼ bearish, ◆ none.
  For example "▲ Hammer".
- **Hit target:** each label has a box of at least 24 × 24 px, which is the hover and click target. Candles themselves
  are about 6 px wide at the hub's normal size.

**Hover.**
- **Bracket:** hovering a label brackets the pattern's exact window and its trend-context bars, in a dashed `DARK_FG`
  outline (at least 3:1).
- **Text:** a one-line plain explanation.
- **Arrows:** a trend arrow into the pattern (from the §5.3 rule) and, once enough later bars have closed, an arrow
  showing what price did after the pattern. That arrow is labelled "what happened next", not a forecast.

**Click.** A detail window (a Tk `Toplevel`) shows:
- the name, the bars it used, and the bar times;
- the direction and type tags, marked "textbook meaning, not measured";
- the rule used, including "24/7 variant" or "non-canonical" where it applies, and the venue: "Binance spot, closed bars";
- a reference link to the primary source, with its market and metric in words, and **no number** (§10);
- the reliability line (§10.2).

**Keyboard.** With the chart focused, ← and → step between labels, Enter opens the detail, and Esc closes it.

**Rendering constraints.**
- **Identity:** every label, bracket and open detail is keyed by the candle's open timestamp, not its index, and is
  re-applied after every redraw.
- **Hover:** uses `motion_notify_event`, and redraws (`draw_idle`) only when the hovered label changes.
- **Click:** uses `button_press_event`.
- **Scope:** detection covers only the displayed coin and timeframe.

**Code.**
- **Detection module:** a new pure module `app/candlestick_patterns.py`, with no Tk and no matplotlib. Its input is
  OHLC with open timestamps, and it returns `(pattern_id, direction, type, first_open, last_open, context_first_open)`.
- **Chart wiring:** lives in `pt_hub.CandleChart`, not in `pt_hub_chart_components.py`.
- **Naming:** UI text always says "candlestick pattern", so it is never confused with the trained "pattern model",
  whose output is the blue and orange level lines.
- **Placement:** the module stays out of `app/strategies/`, so it carries no strategy meaning.

## 8. Chart settings (pop-out)

Users want different things on the chart. One user may not care about doji stars; another may want only bullish
patterns, or no position lines at all. So every overlay the chart can draw gets its own planned toggle.

### 8.1 Where it lives and how it behaves

- **Opening it:** a **Chart settings…** button in the Settings window opens a non-modal pop-out (a Tk `Toplevel`). The
  same pop-out also opens from a small ⚙ button on each chart's toolbar. Only one is open at a time.
- **Applying changes:** a change applies at once to every open chart, with an immediate redraw and no restart. It is
  saved to `gui_settings`.
- **Scope:** settings are global, the same for every coin and timeframe.
- **Buttons:** each tab has **All on** and **All off**. The window also has **Reset to defaults**, which restores
  §8.5.
- **Defaults:** every existing overlay is on, so the chart looks exactly as it does today until the user changes
  something.

The pop-out has three tabs: Overlays, Candlestick patterns and Appearance.

### 8.2 Overlays tab: the existing chart overlays

| Toggle | What it shows or hides | Default |
|---|---|---|
| Neural long levels | the blue full-width lines (one per long level) | on |
| Neural short levels | the orange full-width lines (one per short level) | on |
| Neural readout | the toolbar text "Neural: long=… short=… \| levels L=… S=…" | on |
| Ask price | the purple ASK line and its right-edge label | on |
| Bid price | the teal BID line and its right-edge label | on |
| Average cost | the yellow AVG line and its right-edge label | on |
| Next DCA level | the red DCA line and its right-edge label | on |
| Trailing sell line | the green SELL line and its right-edge label | on |
| Trade markers | the BUY, DCA and SELL dots and their labels | on |

Each line and its right-edge label are toggled together, so a label never floats without its line. Hiding an overlay
only skips drawing it. Nothing upstream changes (§3).

### 8.3 Candlestick patterns tab

- **Master toggle:** "Show candlestick patterns".
- **Filters,** one checkbox each:

  | Filter group | Checkboxes |
  |---|---|
  | Direction | Bullish, Bearish, No direction |
  | Type | Reversal, Continuation, Indecision |
  | Family | Classical, Price action (§6.6) |

- **Patterns:** one checkbox per §6 row, grouped as in §6 (1 bar, 2 bars, 3 bars, 4 or more bars, price action). Each
  row shows its glyph (▲ ▼ ◆) and its tags, so the user can see which filters apply to it.
- **Display options:**
  - "Max labels per chart" (1–30), with the §5.4 cap as its default;
  - "Show what happened next" (the after-pattern arrow, §7).

**Visibility rule.** A pattern is shown when **all** of these hold:
1. the master toggle is on;
2. its own checkbox is on;
3. **every** filter it belongs to is on.

So unticking one filter hides every pattern in it, whatever their own checkboxes say. Two examples:
- **Only bullish patterns:** untick Bearish and No direction.
- **No doji stars:** untick Morning doji star (24/7) and Evening doji star (24/7). To drop every doji-type pattern,
  untick Indecision.

**The two pinned patterns.** Three white soldiers and three black crows are shown ticked and greyed out, with the note
"always visible (owner decision)". They ignore the master toggle, the filters and their own checkbox (§6.3). §12.3 item 10 asks
whether to keep that exemption now that users can tailor everything else.

### 8.4 Appearance tab

| Setting | Values (stored as) |
|---|---|
| Palette | Default (`"default"`), or Blue / vermilion (`"blue_vermilion"`) (§9) |
| Candle style | Filled (`"filled"`, today), or Hollow up (`"hollow_up"`: up bodies hollow, down filled) |

### 8.5 Storage

All of these go in one `gui_settings` key, `chart`. Its defaults are:

```json
"chart": {
  "overlays": {
    "neural_long": true, "neural_short": true, "neural_readout": true,
    "ask": true, "bid": true, "avg": true, "dca": true, "trail": true, "trades": true
  },
  "patterns": {
    "enabled": true,
    "filters": {
      "bullish": true, "bearish": true, "none": true,
      "reversal": true, "continuation": true, "indecision": true,
      "classical": true, "price_action": false
    },
    "items": {"hammer": true, "...": true},
    "max_labels": 12,
    "next_arrows": true
  },
  "palette": "default",
  "candle_style": "filled"
}
```

- **Missing keys** take their defaults, so an older settings file still works.
- **Unknown keys** are kept but ignored.
- **A pattern added later** defaults to on.
- **Pattern ids** are stable snake_case names from §6, for example `morning_doji_star_247`.

`CandleChart` must read the whole `chart` key, and a test checks every toggle. The repo already has one saved setting
that nothing reads (`dark_theme`), and this must not become another.

## 9. Colour and accessibility

**Criteria.** These are checked by a test that composites each colour at its drawn alpha (0.9) on `DARK_PANEL`:
1. each candle colour is at least 3:1 against `DARK_PANEL` (WCAG 1.4.11), also under simulated protanopia and
   deuteranopia (Machado 2009);
2. up and down differ by ΔE2000 ≥ 20 under both simulations, or `hollow_up` is on.

**The palettes.**
- **`default`** keeps today's colours, by the owner's choice, so it is held to criterion 1 for **typical vision only**.
  - Typical vision: up 3.07:1, down 3.79:1.
  - Under simulation it misses: protanopia gives a down candle of 2.41:1 and ΔE2000 7.4; deuteranopia gives an up
    candle of 2.94:1.
  - That is why `hollow_up` exists and works with any palette. It is also the white/black convention behind the names
    "three white soldiers" and "three black crows".
- **`blue_vermilion`** meets both criteria in full: at least 3.16:1 against the panel and ΔE2000 about 50, under all
  three views.
- **`blue_vermilion`**: up #56B4E9 (sky blue), down #D55E00 (vermilion).
  - Both lie along the blue–yellow axis that dichromats keep.
  - Both stay clear of the overlay colours: ΔE2000 about 43 from the blue level line, and about 18 from the orange one.
  - The draft's "blue/orange" suggestion would have clashed with the orange short-level line (ΔE2000 4–6).
  - Okabe-Ito blue #0072B2 is too dark for this panel.
- **Not an accessible option:** the hub's `STATUS_GREEN` #4CAF50 and `STATUS_RED` #FF6B6B are equally bright (1.00:1).
  Under deuteranopia they are harder to tell apart than today's colours (ΔE2000 from about 14 down to 4.5).

**Labels and overlays.** Labels, brackets and arrows use `DARK_FG` (§7), so they never reuse a candle or overlay
colour.

**Out of scope here, noted for a separate change:** the blue long-level line (1.64:1) and the purple ASK line (1.80:1)
are below 3:1.

## 10. Reliability: no published numbers, and the audit

### 10.1 No published percentages on screen

No percentage from a book, website or blog appears on a label, a hover or the detail window, with or without a caveat.
A bare percentage beside a pattern reads as a probability whatever the caveat says, and has no comparator and no n.
Published figures can also point the wrong way (§10.3).

### 10.2 The reliability line in the detail window

It shows one of two things:
- **A verdict line from a registered FDS-SIG-001 round,** in that spec's §13 form: the score against its comparator,
  n, the family F, the round and window, the venue and timeframe, and PASS (provisional), CONFIRMED, FAIL (with its bound
  and smallest detectable effect) or NOT ASSESSABLE.
- **Otherwise:** "Not measured on this data."

It is never a hit rate computed on the bars the chart has shown. FDS-SIG-001 §11 treats such a re-run as examined data
with no verdict.

**Expect "Not measured" almost everywhere.**
- **The 1,000-call minimum:** a single pattern needs years of 1h data to reach it. A relaxed Piercing line needs about
  6 years; three white soldiers about 57–86 years.
- **The audit's coverage:** only 1h and 4h, and only the 10 largest Binance coins. The chart offers 11 timeframes and
  the user's own coins.
- **Indecision patterns** have no direction to test.

This is the expected state, not a gap to fill with published figures.

### 10.3 What the published figures actually measured (record only, never displayed)

The draft listed figures gathered from discussion. Checked against their most-cited primary source, Thomas Bulkowski
(thepatternsite.com):

| Pattern | Draft said | Bulkowski measured |
|---|---|---|
| Hanging man | 55–60% "accuracy" | bearish reversal **41%** of the time (bullish continuation 59%) |
| Inverted hammer | 53–65% "accuracy" | bullish reversal **35%** of the time (bearish continuation 65%) |
| Piercing line | 64–80% | 64%. The 80% appears only in an unattributed line in an ATAS blog post. There is no "ATAS Aggregates Research Group". |
| Dark cloud cover | 60–64% | about 60% |
| Separating lines | 78% | bullish 72%, bearish 63%. Dropped here anyway (§6.7). |
| Tri-star | 83% confirmation, 34% at 2:1 | no primary source found for either figure. Bulkowski: bullish 60%, bearish 52%. Dropped here anyway. |

What these numbers are:
- **The metric:** the direction of the first breakout close beyond the pattern, with no fixed horizon. Not "accuracy".
- **The data:** hundreds of US stocks, daily bars, from the 1980s.
- **Comparator:** Bulkowski's own comparator is 50% (random).
- **The 24/7 variants:** none of these figures applies to them.
- **Costs:** at 2:1 reward-to-risk, 34% is +0.02R per trade before costs. After this repo's 30 bps round trip it loses
  money unless the stop is about 15% or wider. Breakeven is 43% at a 1% stop and 38% at 2%.

### 10.4 Forward note: patterns as a future audit candidate

Candlestick patterns use OHLC only, so they meet FDS-SIG-001 §4's data rule, but registering them pattern by pattern
does not work:
- **No coverage:** individual patterns never reach the 1,000-call minimum (§10.2).
- **Too many tests:** about 60 rules × 10 coins × 2 timeframes × 2 statistics gives F ≈ 2,400, so Holm's first step is
  z ≈ 4.1, and the smallest detectable edge at the minimum rises to about 11 points.

If they are ever audited, it should be as **a few pooled rules**, each registered as one two-sided candidate in its own
round, so SIG-A and SIG-B keep z ≥ 3.21. For example: "any bullish-tagged pattern → up, any bearish-tagged → down,
otherwise abstain". The target would be next-bar direction (SIG-001 §6), which differs from what the published figures
measured. That decision is not made here.

## 11. Phase 2: timeframe drill-down (separate spec)

Stepping down from a candle to lower timeframes (1w → 1d → … → 1m) **needs new fetch work**. It is not covered by "what
is already fetched", because the chart fetches only the newest 120 bars of the displayed timeframe.

Phase 2 needs:
- **A windowed fetch:** a fetch for an explicit `[start, end)` window, through `market_data.candles.get_candles`, which
  already pages through Binance's results and covers 1m–1w.
- **A row cap:** a cap on child bars, for example at most 1,500, or one step down at a time. One weekly candle holds
  10,080 one-minute bars.
- **Off the Tk thread:** the fetch runs in the background, with a loading state.
- **Click only:** drill-down starts on click, never on hover.
- **Cache growth:** `get_candles` writes cache files, so drilling to 1m grows them.

## 12. Owner decisions

### 12.1 From the draft and the review (2026-10-12)

1. **Detection runs on Binance closed bars** (§4). This is a hard requirement.
2. **The work is split into phases.** Phase 1 is closed-bar, gap-free detection with labels, hover and detail.
   Drill-down is phase 2 (§3, §11).
3. **Gap patterns are split by meaning** (§6.5, §6.7).
   - **Dropped, because their meaning is the gap:** Window, Tasuki gap, Kicker, Abandoned baby, Tri-star, Separating
     lines, Counterattack/Meeting lines, On-neck and Thrusting.
   - **Kept as named 24/7 variants:** Morning and Evening star, Piercing line and Dark cloud cover.
4. **No published percentages on screen** (§10.1).
5. **The forward audit note is kept,** reframed (§10.4).
6. **Three white soldiers and three black crows are always visible** (§6.3).
7. **In-neck is dropped.**

### 12.2 Added on 2026-10-13

8. **Every chart overlay gets a planned on/off toggle,** in a Chart settings pop-out reached from the Settings window
   (§8). That covers each existing line and the markers, the Neural readout, every candlestick pattern, and the pattern
   groups. The reason: whatever a user wants (no doji stars, only bullish patterns, no position lines), the chart must
   support it.

### 12.3 Defaults this spec sets, to confirm before phase 1

1. **The same "meaning of the gap" rule applied to patterns the decision did not name:**
   - Doji star (2-bar) is dropped, because its meaning survives in the doji-star variants;
   - Ladder bottom and Concealing baby swallow are dropped;
   - Mat hold uses Bulkowski's no-gap rule.
2. **Tower bottom** is dropped until it has a definition.
3. **Doji against R(10) rather than the bar's own range,** and TA-Lib's default thresholds throughout (§5.2).
4. **The trend rule:** SMA₁₀ with a 3-bar slope (§5.3).
5. **One label per candle,** a default cap of 12 that the user can change from 1 to 30, and the precedence order
   (§5.4, §8.3).
6. **Pinned thresholds** for three white soldiers and three black crows (§6.3).
7. **Price-action patterns in their own group,** shown only where no classical pattern matched, with that group **off
   by default** (§6.6, §8.5).
8. **The Chart settings design (§8):**
   - three tabs, and global scope;
   - the "all filters must be on" visibility rule;
   - every existing overlay on by default;
   - one `chart` key in `gui_settings`.
9. **The `blue_vermilion` palette and the `hollow_up` option** (§9).
10. **The pinned exemption.** Should three white soldiers and three black crows stay always visible, ignoring every
    toggle (§12.1 item 6)? Or, now that users can tailor everything else (§12.2), should they become default-on
    patterns the user can hide?

## 13. Acceptance criteria (phase 1)

1. **The detection module.** `app/candlestick_patterns.py` is pure (no Tk or matplotlib import). Each §6 rule has a
   hand-built fixture that matches, and a near-miss fixture that does not. The tests cover:
   - the inclusive edges and the "equal" tolerance;
   - the flat-bar doji;
   - the trend rule and warm-up;
   - non-contiguous timestamps, which give no match;
   - the forming bar never being used.
2. **The recorded fixtures (test).** On `app/tests/fixtures/BTCUSDT_1h.csv` and `ETHUSDT_1h.csv`:
   - each rule's count is reported in the test output, for the run log;
   - the pinned three white soldiers and three black crows reproduce the §6.3 counts (BTC 0, ETH 1);
   - no §6.7 pattern has a rule.
3. **Data source (test).** Detection reads Binance closed bars through `market_data` (mocked; no network). A detection
   with no matching chart candle is listed but not drawn. A coin with no Binance market, or one recorded not trading,
   gets the "no Binance market" note.
4. **Off the Tk thread.** Fetching and detection never run on the Tk thread (test with a fake that asserts the thread).
5. **Labels (tests):**
   - placement by open timestamp, surviving a redraw and a one-bar shift;
   - merging, precedence, the "+n" badge, and the cap of 12 with the hidden-count note;
   - glyphs and `DARK_FG` text.
6. **Chart settings (tests):**
   - The pop-out opens from the Settings window and from the chart toolbar, and only one is open at a time.
   - **Overlays:** each §8.2 toggle hides exactly its own element (its line and label, the markers or the readout) and
     nothing else, checked against the drawn artists of a rendered test chart.
   - **Defaults** reproduce today's chart: the same artists as before this change.
   - **Patterns:** the §8.3 visibility rule holds, including the two worked examples ("only bullish" and "no doji
     stars"). The master toggle and every filter work, and the pinned patterns cannot be hidden. "Max labels" and
     "Show what happened next" take effect.
   - **Appearance:** the palette and candle style take effect.
   - **Applying:** a change applies to every open chart at once, without a restart.
   - **Storage:** the `chart` key round-trips through `gui_settings`. Missing keys take defaults, unknown keys are kept,
     and a newly added pattern defaults to on.
   - **Reset to defaults** restores §8.5.
7. **Colour (test).** Computed in the test:
   - `blue_vermilion` meets both §9 criteria under all three views;
   - `default` is unchanged and meets 3:1 for typical vision;
   - `hollow_up` draws up bodies with no fill.
8. **No published numbers (test).** No pattern description, label or detail text contains a percentage or a published
   hit rate.
9. **Nothing else changes.**
   - No import of `candlestick_patterns` from `strategies`, `signal_engine`, `pt_trader`, `pt_thinker` or the trainer
     (test).
   - The overlays are drawn as before when shown, and hiding one changes nothing outside the chart (test).
10. **Suite and network.** No test touches the network. The full suite (`app/tests` and `app/test_*.py`) is no worse
    than `main`.

## 14. Run protocol

Same as `00-RUN-ORDER.md`:
- **Paper only.** No API keys are read or created.
- **Network:** public Binance market data only, and never in tests.
- **Commits:** one commit per step, with the full suite no worse than before.
- **Blocked steps:** log BLOCKED with the reason. Never weaken a test or a criterion to make it pass.
