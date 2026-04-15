# JCAMP_DataCollector v0.3 — MTF Feature Patch

Adds 5 new features derived from v4.6.0's multi-timeframe alignment logic,
ported to M5/M15/M30/H1 (the timeframes DataCollector already loads).

## What's New

| Feature | Range | Meaning |
|---|---|---|
| `mtf_alignment_score` | -4 to +4 | (# TFs price > SMA) - (# TFs price < SMA) |
| `mtf_stacking_score` | -3 to +3 | Count of pairwise SMA orderings in trend direction |
| `bars_since_tf_fast_flip` | 0 to 200 | Bars since M15 price-vs-SMA alignment last flipped |
| `tf_fast_flip_direction` | -1, 0, +1 | Direction of most recent M15 flip (within 200 bars) |
| `mtf_alignment_duration` | -200 to +200 | Signed count of consecutive bars current alignment held |

All continuous / integer. No binary flags. ML gets the raw ingredients.

## Why M15 for the "fast flip" instead of M3?

v4.6.0 uses M3 as TF0 (entry trigger). Since DataCollector decides on M5 bar
closes, the fastest meaningful timeframe below the decision horizon is... well,
there isn't one — M5 IS the decision bar. The next step up is M15, which is
what we use as the "fast flip" proxy. This is the same concept (the
faster-timeframe crossover trigger) shifted to what's actionable on an M5
decision cycle.

---

## CHANGE 1 — Add to CHANGELOG block (top of file)

Insert after the v0.2 entry in the CHANGELOG comment:

```csharp
//   v0.3 (2026-04-14)
//     - FEATURE: Added 5 MTF alignment features derived from v4.6.0 logic.
//       mtf_alignment_score, mtf_stacking_score, bars_since_tf_fast_flip,
//       tf_fast_flip_direction, mtf_alignment_duration. Uses M5/M15/M30/H1
//       with SMA 275 on M5 and SMA 200 on HTFs (existing indicators).
//     - STATE: Added _prevM15Alignment, _lastFlipBarIdx, _lastFlipDirection
//       for cross-bar tracking. Reset on OnStart.
```

---

## CHANGE 2 — Add private fields (near line 79, below `_headerWritten`)

```csharp
        // ----- MTF state tracking (v0.3) --------------------------------------
        // Track M15 alignment across bars to detect flips (v4.6.0-style trigger)
        private string _prevM15Alignment = "";
        private int    _lastFlipBarIdx   = -1;     // M5 bar index where M15 last flipped
        private int    _lastFlipDirection = 0;     // +1 = flipped to BUY, -1 = flipped to SELL

        // Track MTF alignment state persistence across bars
        private int _prevAlignmentScore  = 0;      // last bar's alignment score
        private int _alignmentRunLength  = 0;      // signed: + if bull-aligned run, - if bear-aligned run
```

---

## CHANGE 3 — Reset state in OnStart (add after line 116, just before the final brace of OnStart)

```csharp
            // ---- Reset MTF tracking state ------------------------------------
            _prevM15Alignment    = "";
            _lastFlipBarIdx      = -1;
            _lastFlipDirection   = 0;
            _prevAlignmentScore  = 0;
            _alignmentRunLength  = 0;
```

---

## CHANGE 4 — Add new MTF section inside ComputeFeatures

Insert this block AFTER the "Cost context" section (after line 224,
`f["spread_pips"] = Symbol.Spread / Symbol.PipSize;`) and BEFORE `return f;`:

```csharp
            // --- MTF alignment (v4.6.0-derived, v0.3) -----------------------
            // Concept: multi-timeframe SMA alignment + faster-TF flip trigger.
            // Ported from JCAMP_FxScalper v4.6.0 (which used M1/M3/M5/M10 +
            // SMA 275). We use M5/M15/M30/H1 because (a) they're already loaded
            // here, (b) M5 IS our decision bar so anything faster than M15 is
            // noise at the decision horizon.
            //
            // IMPORTANT: we use the existing SMA200 on HTFs and SMA275 on M5.
            // Period mismatch is small and the ML will handle it. To be strict,
            // add _smaM15_275, _smaM30_275, _smaH1_275 in OnStart.

            // Per-TF alignment: +1 if price > SMA on that TF, -1 if below.
            // M5 uses SMA275 (same period as v4.6.0). HTFs use existing SMA200.
            int m5Align  = (px > _smaM5_275.Result[closedBarIdx]) ? 1 : -1;
            int m15Align = (px > _smaM15_200.Result.Last(1))      ? 1 : -1;
            int m30Align = (px > _smaM30_200.Result.Last(1))      ? 1 : -1;
            int h1Align  = (px > _smaH1_200.Result.Last(1))       ? 1 : -1;

            // Feature 1: mtf_alignment_score (-4 to +4)
            int alignScore = m5Align + m15Align + m30Align + h1Align;
            f["mtf_alignment_score"] = alignScore;

            // Feature 2: mtf_stacking_score (-3 to +3)
            // v4.6.0's CheckSMAStacking: in an uptrend, faster SMAs sit above
            // slower SMAs. We count pairwise orderings in the bullish direction
            // and subtract those in bearish direction. Range -3 to +3.
            double sma_m5  = _smaM5_275.Result[closedBarIdx];
            double sma_m15 = _smaM15_200.Result.Last(1);
            double sma_m30 = _smaM30_200.Result.Last(1);
            double sma_h1  = _smaH1_200.Result.Last(1);
            int stackScore = 0;
            stackScore += (sma_m5  > sma_m15) ? 1 : -1;
            stackScore += (sma_m15 > sma_m30) ? 1 : -1;
            stackScore += (sma_m30 > sma_h1)  ? 1 : -1;
            f["mtf_stacking_score"] = stackScore;

            // Feature 3 + 4: M15 flip detection (v4.6.0's TF0 crossover concept)
            // Detect when M15 price-vs-SMA alignment changes between bars.
            // NOTE: we use Last(1) for M15 to match how the rest of the HTF
            // features read — the last CLOSED M15 bar at this M5 bar close.
            string currM15AlignStr = m15Align > 0 ? "BUY" : "SELL";
            if (_prevM15Alignment != "" && _prevM15Alignment != currM15AlignStr)
            {
                _lastFlipBarIdx    = closedBarIdx;
                _lastFlipDirection = (currM15AlignStr == "BUY") ? 1 : -1;
            }
            _prevM15Alignment = currM15AlignStr;

            // bars_since: cap at 200 to keep scale bounded. If no flip yet in
            // this run, emit 200 (treated as "stale / unknown").
            int barsSinceFlip = (_lastFlipBarIdx < 0)
                ? 200
                : Math.Min(200, closedBarIdx - _lastFlipBarIdx);
            f["bars_since_tf_fast_flip"] = barsSinceFlip;

            // Direction: 0 if the flip is stale (>200 bars) or never happened.
            // Otherwise +1 (flipped to BUY) or -1 (flipped to SELL).
            int flipDir = (barsSinceFlip >= 200) ? 0 : _lastFlipDirection;
            f["tf_fast_flip_direction"] = flipDir;

            // Feature 5: mtf_alignment_duration (signed run length)
            // How long has the current alignment regime persisted?
            // Positive = bull-aligned run (score >= +3 sustained)
            // Negative = bear-aligned run (score <= -3 sustained)
            // Zero = no strong alignment on this bar.
            if (alignScore >= 3)
            {
                // Bull-aligned this bar. Extend or start a bull run.
                _alignmentRunLength = (_prevAlignmentScore >= 3)
                    ? _alignmentRunLength + 1
                    : 1;
            }
            else if (alignScore <= -3)
            {
                // Bear-aligned this bar.
                _alignmentRunLength = (_prevAlignmentScore <= -3)
                    ? _alignmentRunLength - 1
                    : -1;
            }
            else
            {
                // Mixed — no sustained alignment.
                _alignmentRunLength = 0;
            }
            _prevAlignmentScore = alignScore;

            // Cap at ±200 to keep distribution bounded for the ML.
            int boundedDuration = Math.Max(-200, Math.Min(200, _alignmentRunLength));
            f["mtf_alignment_duration"] = boundedDuration;
```

---

## CHANGE 5 — Smoke test BEFORE re-running full history

After pasting, build the cBot and run ONE month (Jan 2023 or any single month)
first. Open the CSV and verify:

1. **5 new columns exist** in the header row.
2. **`mtf_alignment_score` ranges -4 to +4** and actually hits both extremes.
   If it's stuck at only +4 and -4, something's wrong with the `Last(1)` reads.
   If it's stuck at 0, HTF SMAs aren't initialized.
3. **`mtf_stacking_score` ranges -3 to +3.** Should correlate loosely with
   alignment score but not be identical.
4. **`bars_since_tf_fast_flip`** — most values should be in the 1-50 range
   with occasional 200s at the start. If everything is 200, M15 flip detection
   is broken.
5. **`tf_fast_flip_direction`** — should be mostly ±1, rarely 0.
6. **`mtf_alignment_duration`** — should have a mix of 0, small positive,
   small negative, with occasional runs of 10-30. If it's always 0, the
   alignment threshold (|score| >= 3) is never being hit.
7. **No NaN or Inf anywhere in the new columns.**

If any of those checks fail, STOP and debug the single month before re-running
2+ years of data. The PRD's "smoke test first" rule exists for exactly this
reason.

---

## What this patch deliberately does NOT do

- **No ADX-based features.** You already have adx_m5, di_plus_m5, di_minus_m5.
  v4.6.0's ADX filter is fully captured by those.
- **No binary "v4.6.0 would trade here" flag.** Features 1+3+4 together let
  the ML reconstruct v4.6.0's exact entry condition. A separate flag would be
  redundant and would let the model cheat by copying v4.6.0 verbatim instead
  of learning the nuances.
- **No session-specific alignment.** Your existing sess_london / sess_ny / etc.
  flags let the ML learn interactions automatically (e.g., "alignment score +4
  works in London but not Asia").

---

## After this patch lands

You'll have ~40 features total (was ~35). Re-run DataCollector on the full
Jan 2023 → present range. Expect the CSV size to grow by roughly 15%. Then
proceed to Phase 2 training as specified in the PRD — the new features will
flow through with no changes needed to the Python pipeline.

When you train the baseline in `02_train_baseline.ipynb`, watch the feature
importance plot. The interesting verdict lives there:

- `mtf_alignment_score` importance > 5%  → v4.6.0's core idea has real merit
- all 5 features importance < 2%         → v4.6.0's logic adds nothing the
                                            raw SMA distance features don't
                                            already provide (honest abandon
                                            signal for the multi-TF approach)
- `bars_since_tf_fast_flip` high AND
  feature importance peaks at low values → v4.6.0 was right that fresh flips
                                            matter; the 5:1 RR was the real
                                            problem, not the entry signal
