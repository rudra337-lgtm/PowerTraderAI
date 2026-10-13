# FDS-SIG-003 — Candlestick-Pattern Signal Candidates

**Issue:** none yet. Link it to FDS-SIG-001's issue when that is raised.
**Target repo:** `sjackson0109/powertraderai`
**Branch:** this spec is on `docs/fds-sig-003-candlestick-candidates`, cut from `main` at `efe1eb9`. The two rules and their tests go on `feat/signal-audit-1`, with FDS-SIG-001's implementation.
**Recommended model:** Claude Sonnet 5.5, effort high: two rules over `cp.detect()` and their tests, built inside FDS-SIG-001's implementation.
**Run log:** none of its own. Results are logged in the run log of the round that registers these candidates.
**Status:** draft for owner review. Nothing is implemented yet, and this document changes no code, trainer, strategy, runner or trader.
**Depends on:** FDS-SIG-001, `docs/dev/specs/FDS-SIG-001-signal-candidate-audit.md`, and FDS-CHART-001, `docs/dev/specs/FDS-CHART-001-candlestick-patterns.md` (built as `app/candlestick_patterns.py` in PR #161). This spec defines no audit process and changes none. It defines two candidates, written as the rules FDS-SIG-001 §5 requires, for copying into a round's registration (FDS-SIG-001 §12, step 1).
**Related:** FDS-SIG-002 names round one's other candidates, SIG-A and SIG-B. Neither is registered yet.

---

## 1. Objective

Name two candlestick-pattern candidates as exact, eligible rules, and record why single named patterns are not
candidates yet.

Every candidate here must meet FDS-SIG-001's requirements:
- **§4:** only the OHLCV of coins the round fetches and hashes. These rules read open, high, low and close only;
- **§5:** an up/down/abstain rule with fixed parameters;
- **§6:** round one's target, the direction of the next bar.

**Why.** The chart labels candlestick patterns, and by design it shows no hit rate for any of them (FDS-CHART-001 §10).
No candlestick pattern has been scored for direction in this repo. Published hit rates (Bulkowski and others) come from
other instruments, other eras and other market structure, so they are not evidence about these coins on 1h and 4h bars.
FDS-SIG-001's audit is how this repo finds out, and this spec gives it the candidates.

FDS-CHART-001 §10.4 already sets the shape: not pattern by pattern, but "a few pooled rules, each registered as one
two-sided candidate". Its "pooled" means patterns grouped into one rule. Coins are never pooled (FDS-SIG-001 §8.2), so
this spec says "grouped".

## 2. What the repo already has

### 2.1 The pattern library

`app/candlestick_patterns.py` defines 46 patterns in `PATTERNS`. Each `PatternDef` has a `direction` (bullish, bearish or
none), a `kind` (reversal, continuation, indecision or none) and a `family` (classical or price_action).

| kind | bullish | bearish | no direction | total |
|---|---|---|---|---|
| reversal | 16 | 16 | 0 | 32 |
| continuation | 2 | 1 | 0 | 3 |
| indecision | 1 | 1 | 7 | 9 |
| none | 1 | 1 | 0 | 2 |
| **total** | **20** | **19** | **7** | **46** |

37 patterns have a direction and are not indecision patterns: 31 classical (16 bullish, 15 bearish) and 6 price action
(3 and 3).

**What the rules call.**
- `cp.detect(bars, step, now)` returns every detection on closed bars. It is the function the chart calls, and it knows
  nothing about chart settings, so the rules below use it unchanged.
- The rules do **not** use `merge_runs()`, which turns consecutive detections of one pattern into one and would drop
  calls. They also do not use `layout()`, the chart's visibility toggles or its label cap.
- `Detection.next_move` and `Detection.next_after` look at bars after the pattern, for the chart's detail window. The
  rules never read them (§9, item 3).
- The module is pure: no Tk, no plotting, no network. The bars come from the audit's own candle fetch (FDS-SIG-001 §12,
  step 3).

### 2.2 The existing trainer is not a starting point

`app/pt_pattern_trainer.py`'s `run_pass()` matches on one number per candle, its
body percentage, against stored memories, and moves its match threshold towards about 20 matches per step. Its weight
updates are never saved, so every saved weight stays 1.0 (`app/pt_pattern_trainer.py:28-29`). That is an upstream-parity
quirk kept on purpose (FDS-MDL owner decision). The trainer has no pattern vocabulary to extend, and this spec does not
touch it.

## 3. Why not single named patterns

**Fresh windows only.** FDS-SIG-001 §11 scores candidates only on a window registered before it starts, starting no
earlier than 2026-10-01, and §15.1 item 5 (owner, 2026-10-12) says the same. Past bars cannot be evidence, however much
history a pattern has.

**Most single patterns are too rare for a fresh window.** On the committed 1h fixtures (§4.4):

| Pattern | Detections in 63 days (BTC + ETH, 1h) | Days of 1h bars to 1,000 calls on one coin |
|---|---|---|
| Long upper wick / long lower wick | 393 / 376 | 321 / 335 |
| Belt hold (bearish) / bearish engulfing | 127 / 125 | 992 / 1,008 |
| Bullish engulfing | 88 | 1,432 |
| Hammer | 37 | 3,407 |
| Morning star | 13 | 9,696 |
| Three white soldiers | 1 | about 126,000 |
| Three black crows | 0 | none seen |

Only the two long-wick patterns reach the 1,000-call floor (FDS-SIG-001 §6) inside a year of 1h bars. If the per-bar
rates are the same at 4h, even the long wicks need about 3½ years there.

**Unassessable rows still cost the family.** A NOT ASSESSABLE (row, statistic) stays in F with p = 1 (FDS-SIG-001 §7.4,
§8.1). Testing the 37 patterns one by one gives F = 37 × 10 coins × 2 timeframes × 2 statistics = 1,480, and a first Holm
step of z ≥ 3.99, paid almost entirely by rows that cannot be assessed.

**Two other routes exist, and this spec takes neither.** Amending FDS-SIG-001 §11 to admit past bars, or §8.2 to pool
coins, would each reopen an owner decision of 2026-10-12. Grouping patterns into two candidates needs no change to
FDS-SIG-001.

## 4. The candidates

Both candidates are registered as written below, with no parameter left open. Both are **two-sided**: each can call up
and down (FDS-SIG-001 §5, item 4). Both run on 1h and 4h (FDS-SIG-001 §10.2) and call at the close of bar t from closed
bars only (FDS-SIG-001 §6).

**Shared definitions.**
- **A pattern completes on bar t** when `cp.detect()` returns a detection of it whose `last_index` is bar t.
- **Inputs:** the coin's own open, high, low and close on the same timeframe. No volume and no other coin.
- **Parameters:** the pattern rules and thresholds of `app/candlestick_patterns.py` as at commit `efe1eb9`, unchanged.
  The registration records that file's SHA-256, and `app/` is a frozen path (FDS-SIG-001 §12, step 2). A later change to
  the file changes the rule, so the changed rule is a new candidate for a later round.
- **Warm-up:** 19 bars (`cp.WARMUP_BARS`), taken from before the window. That is 19 hours at 1h and 76 hours at 4h, the
  same as SIG-A's. It is an upper bound on what any pattern's own bars, trend-context bars and averages need.
- **Missing bars:** `cp.detect()` finds a pattern only when its bars, its trend-context bars and the bars its averages
  need form one contiguous run. A gap therefore gives abstentions, never a call.
- **Coins:** all 10 audited coins.

### 4.1 SIG-C: classical pattern direction

- **Patterns:** the 31 with `family="classical"`, a `direction` and a `kind` of reversal or continuation. The
  registration lists their ids:
  - **bullish (16):** `hammer`, `inverted_hammer`, `belt_hold_bullish`, `bullish_engulfing`, `bullish_harami`,
    `tweezer_bottom`, `piercing_line_247`, `matching_low`, `morning_star_247`, `morning_doji_star_247`,
    `three_white_soldiers`, `three_outside_up`, `three_inside_up`, `rising_three_methods`, `mat_hold`,
    `three_line_strike_white`;
  - **bearish (15):** `hanging_man`, `shooting_star`, `belt_hold_bearish`, `bearish_engulfing`, `bearish_harami`,
    `tweezer_top`, `dark_cloud_cover_247`, `matching_high`, `evening_star_247`, `evening_doji_star_247`,
    `three_black_crows`, `three_outside_down`, `three_inside_down`, `falling_three_methods`, `three_line_strike_black`.
- **Rule at bar t:**
  - **up** if at least one bullish SIG-C pattern completes on bar t and no bearish one does;
  - **down** if at least one bearish SIG-C pattern completes on bar t and no bullish one does;
  - **abstain** otherwise: no SIG-C pattern completes on bar t, or patterns of both directions do.
- **Kind:** two-sided.
- **Expected coverage:** 26–28% at 1h and about 26% at 4h (§4.4).
- **Both directions on one bar:** none in the fixtures, and rare by construction. Every classical pattern has a trend
  rule, and the 28 reversals need opposite trends by direction. Only a continuation pattern can complete in the same
  trend as an opposite reversal.
- **What drives it:** of its 809 calls in the fixtures, bearish belt hold appears on 127, bearish engulfing on 125,
  bullish belt hold on 91 and bullish engulfing on 88.

### 4.2 SIG-D: price-action pattern direction

- **Patterns:** the 6 with `family="price_action"` and a `direction`. The registration lists their ids:
  - **bullish (3):** `hikkake_bullish`, `pin_bar_bullish`, `long_lower_wick`;
  - **bearish (3):** `hikkake_bearish`, `pin_bar_bearish`, `long_upper_wick`.
- **Rule at bar t:** as SIG-C's, over these 6 patterns. When patterns of both directions complete on bar t, the rule
  abstains. That happened on 3 of 3,025 bars in the fixtures.
- **Kind:** two-sided.
- **Expected coverage:** 27–30% at 1h and 27–28% at 4h (§4.4).
- **What drives it:** of its 876 calls in the fixtures, 766 (87%) include a long wick and 599 (68%) are a long wick
  alone. A pass for SIG-D would mostly be a statement about long wicks.

### 4.3 Indecision patterns

The 9 indecision patterns are in neither candidate. Two of them do carry a direction: `dragonfly_doji` is bullish and
`gravestone_doji` is bearish. They are excluded as a kind, not for lacking a direction. An indecision pattern describes
a candle whose close came back near its open, which is a different claim from a reversal or a continuation.

### 4.4 Where the figures come from

- **Data:** the committed fixtures `app/tests/fixtures/BTCUSDT_1h.csv` and `ETHUSDT_1h.csv`, 1,513 and 1,512 bars, from
  2026-06-10 to 2026-08-12 UTC.
- **4h figures:** from complete 4h groups of those bars, 378 per coin, so about 100 calls per candidate per coin.
- **Method:** `cp.detect()` at `efe1eb9`. The scripts are not committed.
- **Limits:** two coins and 63 days. Rare patterns have single-digit counts, and other coins may differ.
- **Planning only:** these bars predate 2026-10-01. They plan the window, and they are never evidence (FDS-SIG-001 §11).

## 5. The tests that apply

Both candidates are two-sided, so FDS-SIG-001 applies to them as it does to SIG-A and SIG-B:
- **Hit rate:** the exact paired test against the best constant on the called pairs (FDS-SIG-001 §7.1), with the
  m ≥ 200 discordant-pair floor (§7.4);
- **Magnitude:** the mean over called pairs of c × (r − r̄), where a pass also needs the raw mean of c × r above zero
  (§7.3);
- **WORSE:** judged against chance at the candidate's mix (§7.5);
- **Dependence, Holm, no pooling and confirmation:** §7.4 and §8.1–8.3, unchanged.

FDS-SIG-001 §7.2's test against abstained pairs, and its floor of 200 abstained pairs, are for one-sided candidates and
do not apply here.

**Which floor binds.** In the fixtures:
- **Discordant pairs:** up calls were 43–54% of each candidate's calls, so m is roughly 43–57% of n. At n = 1,000 that
  is about 430–570, above the m floor.
- **Blocks:** the call indicators' autocorrelation times were 1.0–2.0 bars, so the block length is one day (24 bars at
  1h, 6 at 4h). Thirty blocks need 30 days.
- **Result:** the floor that binds is n ≥ 1,000 calls.

## 6. Family size, power and window length

**Family size.** F = 2 candidates × 10 coins × 2 timeframes × 2 statistics = **80**.
- **The bar:** the first Holm step is z ≥ 3.23 (α₁ = 6.25 × 10⁻⁴).
- **Resamples:** the bootstrap needs B ≥ 160,000 (FDS-SIG-001 §7.4, §8.1).
- **One statistic only** (FDS-SIG-001 §15.3 item 1): F = 40 and the first step is z ≥ 3.02.

**Power.** This uses the method of FDS-SIG-001 §9's planning table: 80% power against Holm's first step, with spread
√(0.5/n). The figures are lower bounds, for the reasons §9 gives.

| Calls n | Smallest detectable edge (F = 80) | 1h bars needed at 26–30% coverage |
|---|---|---|
| 1,000 (the floor) | at least 9.1 points | 137–162 days |
| 2,190 | at least 6.1 | 300–355 days |
| 4,383 | at least 4.3 | 601–711 days |
| 8,766 | at least 3.1 | 1,202–1,421 days |

**Window length.** Days to 1,000 calls on one coin, before any margin for ties and gaps:

| | 1h | 4h |
|---|---|---|
| SIG-C | 150–162 days | 629–654 days |
| SIG-D | 137–152 days | 597–620 days |

- **Under about 4½ months:** every row of both candidates is NOT ASSESSABLE.
- **Under about 22 months:** their 40 4h rows are NOT ASSESSABLE, and those rows still count in F.

This is input to the window-end decision (FDS-SIG-001 §15.2 item 1), which stays open.

## 7. Not in this spec

- **Single named patterns** (hammer, morning star and so on), for the reasons in §3.
  - If SIG-C or SIG-D is CONFIRMED, a later round could register the patterns inside it one by one.
  - Those single patterns would meet the same floors. Only the long wicks reach 1,000 calls inside a year of 1h bars.
- **Pooling** across coins or timeframes. Each row stands alone (FDS-SIG-001 §8.2).
- **Any trading use.** Nothing here feeds `app/pt_thinker.py`, the runner, the trader or a strategy. Acting on a result is
  a separate, later decision (FDS-SIG-001 §14).
- **Changes to the chart:** its display, `app/pt_chart_patterns.py`'s gating, or FDS-CHART-001's rule against showing
  published figures.
- **Changes to `app/candlestick_patterns.py`.** This spec reads its output and changes nothing in it.

## 8. Owner decisions

### 8.1 To settle before registration

1. **Which round.**
   - **Combined with SIG-A and SIG-B:** F = 76 + 80 = 156, so the first Holm step is z ≥ 3.41 for all four candidates
     (B ≥ 312,000). The one window must then run long enough for SIG-C and SIG-D (§6).
   - **A round of their own:** F = 80, z ≥ 3.23. SIG-A and SIG-B keep FDS-SIG-002's F = 76 and z ≥ 3.21. This is what
     FDS-CHART-001 §10.4 suggested.
2. **The window end** (FDS-SIG-001 §15.2 item 1), using §6's figures.
3. **Single patterns later** (§7): not a round-one question, but it helps planning to know whether you want it.

### 8.2 Defaults this spec sets, to confirm or change

1. **Two candidates, split by family.** The alternative is one candidate over all 37 patterns:
   - 42–44% coverage at 1h, so 1,000 calls in 95–99 days;
   - both directions completed on the same bar on 3–4% of bars, and the rule would abstain there;
   - F = 40, z ≥ 3.02;
   - a pass could not say whether the classical or the price-action patterns did the work.
2. **Abstain when both directions complete on one bar** (§4.1, §4.2).
3. **Indecision patterns excluded,** dragonfly and gravestone doji included (§4.3).
4. **Detection as at `efe1eb9`,** pinned by the file's SHA-256 (§4).

## 9. Acceptance

**Procedural.** This spec is accepted when a round's registration (FDS-SIG-001 §12, step 1) copies §4's two rules
verbatim, with the pattern ids, inputs, the SHA-256 of `app/candlestick_patterns.py`, the kind, warm-up and coins. F is
computed from the registered candidates and coin list as in §6.

**Implementation.** FDS-SIG-001 §16 governs the implementation, plus:

1. **Rule tests.** On built bars:
   - one bullish pattern of the set completing gives up, and one bearish pattern gives down;
   - no pattern gives abstain;
   - a SIG-D bar with both directions gives abstain;
   - a gap inside a pattern's window gives abstain.
2. **Same detections as the chart.** On both committed fixtures, every call matches the directions of the `cp.detect()`
   detections ending on that bar. No `merge_runs()`, no `layout()`, no chart settings.
3. **No look-ahead,** as FDS-SIG-001 §16 item 3 requires. Poisoning the bars after t leaves every call at t unchanged. This
   also shows that `next_move` and `next_after` are not read.
4. **History independence.** The call at t is the same whether `cp.detect()` sees only the 19 warm-up bars before t or
   the whole series.
5. **Pinned detection.** The run refuses if `app/candlestick_patterns.py`'s SHA-256 differs from the registered one.
