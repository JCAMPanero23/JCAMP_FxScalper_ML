// =============================================================================
// JCAMP_Features.cs — Shared Feature Computation Module
// -----------------------------------------------------------------------------
// CRITICAL: This file must be IDENTICAL in DataCollector and FxScalper_ML.
//           Any change here requires updating BOTH copies and re-running
//           the skew test (JCAMP_FeatureSkewTest).
//
// DO NOT duplicate feature logic. If you need a new feature, add it HERE
// and copy the file to both cBot folders.
//
// Version: v0.6.1 (49 features)
// Last updated: 2026-04-25
// v0.6.1: replaced 3 local-structure features (bars_since_swing_high/low,
//         pullback_depth_pct) that hurt CV with 3 H4 regime features
//         (slope_sma_h4_200, mtf_with_h4_score, h4_alignment_duration).
// =============================================================================

using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    public class FeatureComputer
    {
        // Feature names in exact order (must match Python config.py)
        public static readonly string[] FEATURE_NAMES = new string[]
        {
            "dist_sma_m5_50", "dist_sma_m5_100", "dist_sma_m5_200",
            "dist_sma_m5_275", "dist_sma_m15_200", "dist_sma_m30_200",
            "dist_sma_h1_200", "dist_sma_h4_200",
            "slope_sma_m5_200", "slope_sma_h1_200", "slope_sma_h4_200",
            "rsi_m5", "rsi_m15", "rsi_m30",
            "adx_m5", "di_plus_m5", "di_minus_m5",
            "atr_m5", "atr_m15", "atr_h1", "atr_ratio_m5_h1", "bb_width",
            "bar0_body", "bar0_range", "bar1_body", "bar1_range",
            "bar2_body", "bar2_range", "bar3_body", "bar3_range",
            "bar4_body", "bar4_range",
            "dist_swing_high", "dist_swing_low",
            "hour_utc", "dow", "sess_asia", "sess_london", "sess_ny",
            "spread_pips",
            "mtf_alignment_score", "mtf_stacking_score",
            "bars_since_tf_fast_flip", "tf_fast_flip_direction",
            "mtf_alignment_duration",
            "atr_percentile_2000bar", "h1_alignment_agreement",
            "mtf_with_h4_score", "h4_alignment_duration",
        };

        // Stateful fields (persist across bars)
        private string _prevM15Alignment = "";
        private int _lastFlipBarIdx = -1;
        private int _lastFlipDirection = 0;
        private int _prevAlignmentScore = 0;
        private int _alignmentRunLength = 0;
        private int _prevH4Align = 0;
        private int _h4RunLength = 0;

        private const int ATR_HISTORY_SIZE = 2000;
        private readonly Queue<double> _atrHistory = new Queue<double>();

        /// <summary>
        /// Compute all 49 features for the just-closed M5 bar.
        /// This method MUST produce identical output across DataCollector and FxScalper_ML.
        /// </summary>
        /// <param name="bars">M5 chart bars</param>
        /// <param name="closedBarIdx">Index of the just-closed bar (Count-2)</param>
        /// <param name="symbol">Symbol for spread reading</param>
        /// <param name="smaM5_50">SMA(50) on M5</param>
        /// <param name="smaM5_100">SMA(100) on M5</param>
        /// <param name="smaM5_200">SMA(200) on M5</param>
        /// <param name="smaM5_275">SMA(275) on M5</param>
        /// <param name="smaM15_200">SMA(200) on M15</param>
        /// <param name="smaM30_200">SMA(200) on M30</param>
        /// <param name="smaH1_200">SMA(200) on H1</param>
        /// <param name="smaH4_200">SMA(200) on H4</param>
        /// <param name="rsiM5">RSI(14) on M5</param>
        /// <param name="rsiM15">RSI(14) on M15</param>
        /// <param name="rsiM30">RSI(14) on M30</param>
        /// <param name="adxM5">DMS on M5</param>
        /// <param name="atrM5">ATR(14) on M5</param>
        /// <param name="atrM15">ATR(14) on M15</param>
        /// <param name="atrH1">ATR(14) on H1</param>
        /// <param name="bbM5">Bollinger Bands on M5</param>
        /// <returns>Dictionary of 49 features, or null if warmup incomplete</returns>
        public Dictionary<string, double> Compute(
            Bars bars, int closedBarIdx, Symbol symbol,
            SimpleMovingAverage smaM5_50, SimpleMovingAverage smaM5_100,
            SimpleMovingAverage smaM5_200, SimpleMovingAverage smaM5_275,
            SimpleMovingAverage smaM15_200, SimpleMovingAverage smaM30_200,
            SimpleMovingAverage smaH1_200, SimpleMovingAverage smaH4_200,
            RelativeStrengthIndex rsiM5,
            RelativeStrengthIndex rsiM15, RelativeStrengthIndex rsiM30,
            DirectionalMovementSystem adxM5,
            AverageTrueRange atrM5, AverageTrueRange atrM15,
            AverageTrueRange atrH1,
            BollingerBands bbM5)
        {
            var f   = new Dictionary<string, double>();
            var px  = bars.ClosePrices[closedBarIdx];
            var atr = atrM5.Result[closedBarIdx];
            if (atr <= 0) return null;

            // --- Price vs SMAs (ATR-normalized distances) -------------------
            f["dist_sma_m5_50"]   = (px - smaM5_50.Result[closedBarIdx])  / atr;
            f["dist_sma_m5_100"]  = (px - smaM5_100.Result[closedBarIdx]) / atr;
            f["dist_sma_m5_200"]  = (px - smaM5_200.Result[closedBarIdx]) / atr;
            f["dist_sma_m5_275"]  = (px - smaM5_275.Result[closedBarIdx]) / atr;
            // HTF: use Last(1) = most recently CLOSED HTF bar
            f["dist_sma_m15_200"] = (px - smaM15_200.Result.Last(1)) / atr;
            f["dist_sma_m30_200"] = (px - smaM30_200.Result.Last(1)) / atr;
            f["dist_sma_h1_200"]  = (px - smaH1_200.Result.Last(1))  / atr;
            f["dist_sma_h4_200"]  = (px - smaH4_200.Result.Last(1))  / atr;

            // --- SMA slopes (5-bar % change, computed at closed bar) --------
            f["slope_sma_m5_200"] = SmaSlopeAt(smaM5_200.Result, closedBarIdx, 5);
            f["slope_sma_h1_200"] = SmaSlopeHtf(smaH1_200.Result, 5);
            f["slope_sma_h4_200"] = SmaSlopeHtf(smaH4_200.Result, 5);

            // --- Momentum ----------------------------------------------------
            f["rsi_m5"]      = rsiM5.Result[closedBarIdx];
            f["rsi_m15"]     = rsiM15.Result.Last(1);
            f["rsi_m30"]     = rsiM30.Result.Last(1);
            f["adx_m5"]      = adxM5.ADX[closedBarIdx];
            f["di_plus_m5"]  = adxM5.DIPlus[closedBarIdx];
            f["di_minus_m5"] = adxM5.DIMinus[closedBarIdx];

            // --- Volatility regime ------------------------------------------
            f["atr_m5"]          = atr;
            f["atr_m15"]         = atrM15.Result.Last(1);
            f["atr_h1"]          = atrH1.Result.Last(1);
            f["atr_ratio_m5_h1"] = atr / Math.Max(atrH1.Result.Last(1), 1e-9);
            f["bb_width"]        = (bbM5.Top[closedBarIdx] - bbM5.Bottom[closedBarIdx]) / atr;

            // --- Recent bar shape (last 5 closed bars, ATR-normalized) ------
            // bar0 = the just-closed bar, bar1 = one before, etc.
            for (int i = 0; i < 5; i++)
            {
                var idx = closedBarIdx - i;
                if (idx < 0) return null;
                var body  = (bars.ClosePrices[idx] - bars.OpenPrices[idx]) / atr;
                var range = (bars.HighPrices[idx]  - bars.LowPrices[idx])  / atr;
                f[$"bar{i}_body"]  = body;
                f[$"bar{i}_range"] = range;
            }

            // --- Swing structure (50-bar lookback before closed bar) --------
            double hi = double.MinValue, lo = double.MaxValue;
            int lookback = Math.Min(50, closedBarIdx);
            for (int i = 1; i <= lookback; i++)
            {
                var idx = closedBarIdx - i;
                if (bars.HighPrices[idx] > hi) hi = bars.HighPrices[idx];
                if (bars.LowPrices[idx]  < lo) lo = bars.LowPrices[idx];
            }
            f["dist_swing_high"] = (hi - px) / atr;
            f["dist_swing_low"]  = (px - lo) / atr;

            // --- Time / session context (use closed bar's open time) --------
            var t = bars.OpenTimes[closedBarIdx];
            f["hour_utc"]    = t.Hour;
            f["dow"]         = (int)t.DayOfWeek;
            f["sess_asia"]   = (t.Hour >= 0  && t.Hour < 8)  ? 1 : 0;
            f["sess_london"] = (t.Hour >= 8  && t.Hour < 16) ? 1 : 0;
            f["sess_ny"]     = (t.Hour >= 13 && t.Hour < 21) ? 1 : 0;

            // --- Cost context ------------------------------------------------
            f["spread_pips"] = symbol.Spread / symbol.PipSize;

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
            int m5Align  = (px > smaM5_275.Result[closedBarIdx]) ? 1 : -1;
            int m15Align = (px > smaM15_200.Result.Last(1))      ? 1 : -1;
            int m30Align = (px > smaM30_200.Result.Last(1))      ? 1 : -1;
            int h1Align  = (px > smaH1_200.Result.Last(1))       ? 1 : -1;

            // Feature 1: mtf_alignment_score (-4 to +4)
            int alignScore = m5Align + m15Align + m30Align + h1Align;
            f["mtf_alignment_score"] = alignScore;

            // Feature 2: mtf_stacking_score (-3 to +3)
            // v4.6.0's CheckSMAStacking: in an uptrend, faster SMAs sit above
            // slower SMAs. We count pairwise orderings in the bullish direction
            // and subtract those in bearish direction. Range -3 to +3.
            double sma_m5  = smaM5_275.Result[closedBarIdx];
            double sma_m15 = smaM15_200.Result.Last(1);
            double sma_m30 = smaM30_200.Result.Last(1);
            double sma_h1  = smaH1_200.Result.Last(1);
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

            // --- Regime quality (v0.4) ------------------------------------------
            // These features address the fold-diagnosis finding: model needs to
            // know (a) whether current volatility is high/low RELATIVE to recent
            // history, and (b) whether MTF direction agrees with H1 macro slope.

            // Feature 1: atr_percentile_2000bar
            // Rolling percentile: what fraction of the last 2000 ATR values are
            // <= the current ATR? Range 0.0 (unusually calm) to 1.0 (unusually hot).
            // During warmup (<2000 bars), uses whatever history is available.
            _atrHistory.Enqueue(atr);
            while (_atrHistory.Count > ATR_HISTORY_SIZE)
                _atrHistory.Dequeue();

            if (_atrHistory.Count >= 50)  // need some minimum history
            {
                int countBelow = 0;
                foreach (var h in _atrHistory)
                    if (h <= atr) countBelow++;
                f["atr_percentile_2000bar"] = (double)countBelow / _atrHistory.Count;
            }
            else
            {
                f["atr_percentile_2000bar"] = 0.5;  // neutral default during warmup
            }

            // Feature 2: h1_alignment_agreement
            // Does MTF alignment direction agree with H1 slope direction?
            //   +1 = agreement (both bullish or both bearish)
            //   -1 = disagreement (MTF says bull, H1 says bear, or vice versa)
            //    0 = one or both are neutral (no strong signal either way)
            //
            // This directly addresses the SHORT fold-failure: SHORT model loses
            // when MTF alignment is bearish but H1 macro slope is positive.
            // The individual features exist but the model struggles to discover
            // the interaction — exposing it explicitly helps.
            double h1Slope = f["slope_sma_h1_200"];
            int mtfSign = 0;
            if (alignScore >= 2)  mtfSign = +1;   // clear bullish alignment
            else if (alignScore <= -2) mtfSign = -1;  // clear bearish alignment

            int h1Sign = 0;
            if (h1Slope > 0.00005)  h1Sign = +1;    // H1 trending up
            else if (h1Slope < -0.00005) h1Sign = -1; // H1 trending down

            if (mtfSign == 0 || h1Sign == 0)
                f["h1_alignment_agreement"] = 0;      // one side is neutral
            else
                f["h1_alignment_agreement"] = (mtfSign == h1Sign) ? 1 : -1;

            // --- H4 regime (v0.6.1) -----------------------------------------
            // Replaces failed v0.6 local-structure features. The ML had no
            // direct way to see H4 macro trend persistence — only the
            // instantaneous distance dist_sma_h4_200. These features add the
            // direction and duration of the H4 regime so the model can
            // recognize sustained bearish stretches that kill LONG.
            int h4Align = (px > smaH4_200.Result.Last(1)) ? 1 : -1;

            // mtf_with_h4_score: extends mtf_alignment_score to include H4.
            // Range -5 to +5. -5 = price below SMA200 on M5/M15/M30/H1/H4.
            f["mtf_with_h4_score"] = alignScore + h4Align;

            // h4_alignment_duration: signed run length of H4 alignment side.
            // +N = bull-aligned for N bars, -N = bear-aligned for N bars.
            // Direct signal for "stale setup": LONG fights macro when this
            // is deeply negative.
            if (h4Align > 0)
            {
                _h4RunLength = (_prevH4Align > 0) ? _h4RunLength + 1 : 1;
            }
            else
            {
                _h4RunLength = (_prevH4Align < 0) ? _h4RunLength - 1 : -1;
            }
            _prevH4Align = h4Align;
            f["h4_alignment_duration"] = Math.Max(-200, Math.Min(200, _h4RunLength));

            return f;
        }

        private double SmaSlopeAt(IndicatorDataSeries s, int atIdx, int lookback)
        {
            if (atIdx - lookback < 0) return 0;
            var now  = s[atIdx];
            var prev = s[atIdx - lookback];
            return prev == 0 ? 0 : (now - prev) / prev;
        }

        private double SmaSlopeHtf(IndicatorDataSeries s, int lookback)
        {
            if (s.Count <= lookback + 1) return 0;
            var now  = s.Last(1);
            var prev = s.Last(1 + lookback);
            return prev == 0 ? 0 : (now - prev) / prev;
        }

        /// <summary>
        /// Reset all stateful fields. Call on OnStart().
        /// </summary>
        public void Reset()
        {
            _prevM15Alignment = "";
            _lastFlipBarIdx = -1;
            _lastFlipDirection = 0;
            _prevAlignmentScore = 0;
            _alignmentRunLength = 0;
            _prevH4Align = 0;
            _h4RunLength = 0;
            _atrHistory.Clear();
        }
    }
}
