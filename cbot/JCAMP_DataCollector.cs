// =============================================================================
// JCAMP_DataCollector v0.3
// -----------------------------------------------------------------------------
// Purpose: Pure observation cBot. Logs M5 features + triple-barrier outcomes
//          to CSV for offline ML training (LightGBM in Python).
// Trading: NONE. This bot never places orders.
//
// Author : JCamp
// Target : cTrader Automate (cAlgo API, .NET 6+)
// Symbol : EURUSD (run as separate instances per pair)
// TF     : M5 (set chart to M5 before running)
//
// CHANGELOG
//   v0.3 (2026-04-14)
//     - FEATURE: Added 5 MTF alignment features derived from v4.6.0 logic.
//       mtf_alignment_score, mtf_stacking_score, bars_since_tf_fast_flip,
//       tf_fast_flip_direction, mtf_alignment_duration. Uses M5/M15/M30/H1
//       with SMA 275 on M5 and SMA 200 on HTFs (existing indicators).
//     - STATE: Added _prevM15Alignment, _lastFlipBarIdx, _lastFlipDirection
//       for cross-bar tracking. Reset on OnStart.
//   v0.4 (2026-04-16)
//     - FEATURE: Added 2 regime-quality features based on fold diagnosis.
//       atr_percentile_2000bar (rolling ATR percentile for volatility context),
//       h1_alignment_agreement (interaction: MTF direction vs H1 macro slope).
//     - STATE: Added _atrHistory ring buffer for rolling percentile calc.
//     - RATIONALE: Fold diagnosis showed SHORT fails when MTF alignment
//       disagrees with H1 slope. LONG fails partly due to vol regime blindness.
//       See PHASE2_FOLD_DIAGNOSIS.md for full analysis.
//   v0.2 (2026-04-12)
//     - FIX: Off-by-one bar indexing. OnBar() fires when a NEW bar opens, so
//            the just-closed bar is at Count-2, not Count-1. Previously bar0
//            features were always 0 (reading the empty forming bar) and the
//            entry price was the open of the next bar instead of the close
//            of the bar we intended to enter on. All feature reads, label
//            entry prices, and the bar0..bar4 loop now use closedBarIdx.
//     - FIX: HTF indicators now use Last(1) (most recent CLOSED HTF bar)
//            instead of LastValue (the still-forming HTF bar).
//     - FIX: AccessRights.FileSystem deprecated in .NET 6+, use FullAccess.
//     - CLEANUP: Removed unused _adxM15 field.
//     - CLEANUP: Resolved rows now sorted by entry time before write so the
//                CSV stays chronological even when long/short outcomes
//                resolve at different times.
//     - DEFAULT: OutputFolder moved to user Documents to avoid UAC issues.
//   v0.1 (2026-04-12)
//     - Initial release.
// =============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(AccessRights = AccessRights.FullAccess, AddIndicators = true)]
    public class JCAMP_DataCollector : Robot
    {
        // ----- Parameters -----------------------------------------------------
        [Parameter("Output Folder", DefaultValue = @"C:\Users\Jcamp_Laptop\Documents\JCAMP_Data\")]
        public string OutputFolder { get; set; }

        [Parameter("SL ATR Multiplier", DefaultValue = 1.5, MinValue = 0.5)]
        public double SlAtrMult { get; set; }

        [Parameter("TP ATR Multiplier", DefaultValue = 3.0, MinValue = 0.5)]
        public double TpAtrMult { get; set; }

        [Parameter("Max Bars To Outcome", DefaultValue = 48, MinValue = 5)]
        public int MaxBarsToOutcome { get; set; }   // 48 M5 bars = 4 hours

        [Parameter("Commission Per Lot Per Side USD", DefaultValue = 3.0)]
        public double CommissionPerLot { get; set; }

        // ----- Indicator handles ---------------------------------------------
        private SimpleMovingAverage _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275;
        private RelativeStrengthIndex _rsiM5;
        private DirectionalMovementSystem _adxM5;
        private AverageTrueRange _atrM5_14;
        private BollingerBands _bbM5;

        // Higher TF series + indicators
        private Bars _m15, _m30, _h1, _h4;
        private SimpleMovingAverage _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200;
        private RelativeStrengthIndex _rsiM15, _rsiM30;
        private AverageTrueRange _atrM15_14, _atrH1_14;

        // ----- Pending bars queue (for forward-looking labels) ---------------
        private readonly Queue<PendingBar> _pending = new Queue<PendingBar>();
        private StreamWriter _csv;
        private bool _headerWritten = false;

        // ----- MTF state tracking (v0.3) --------------------------------------
        // Track M15 alignment across bars to detect flips (v4.6.0-style trigger)
        private string _prevM15Alignment = "";
        private int    _lastFlipBarIdx   = -1;     // M5 bar index where M15 last flipped
        private int    _lastFlipDirection = 0;     // +1 = flipped to BUY, -1 = flipped to SELL

        // Track MTF alignment state persistence across bars
        private int _prevAlignmentScore  = 0;      // last bar's alignment score
        private int _alignmentRunLength  = 0;      // signed: + if bull-aligned run, - if bear-aligned run

        // ----- Regime tracking (v0.4) -----------------------------------------
        // Ring buffer for rolling ATR percentile (last 2000 M5 bars ≈ 7 trading days)
        private const int ATR_HISTORY_SIZE = 2000;
        private readonly Queue<double> _atrHistory = new Queue<double>();

        protected override void OnStart()
        {
            // ---- Init higher TF bars ----------------------------------------
            _m15 = MarketData.GetBars(TimeFrame.Minute15);
            _m30 = MarketData.GetBars(TimeFrame.Minute30);
            _h1  = MarketData.GetBars(TimeFrame.Hour);
            _h4  = MarketData.GetBars(TimeFrame.Hour4);

            // ---- M5 indicators ----------------------------------------------
            _smaM5_50  = Indicators.SimpleMovingAverage(Bars.ClosePrices, 50);
            _smaM5_100 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 100);
            _smaM5_200 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 200);
            _smaM5_275 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 275);
            _rsiM5     = Indicators.RelativeStrengthIndex(Bars.ClosePrices, 14);
            _adxM5     = Indicators.DirectionalMovementSystem(14);
            _atrM5_14  = Indicators.AverageTrueRange(14, MovingAverageType.Simple);
            _bbM5      = Indicators.BollingerBands(Bars.ClosePrices, 20, 2, MovingAverageType.Simple);

            // ---- HTF indicators ---------------------------------------------
            _smaM15_200 = Indicators.SimpleMovingAverage(_m15.ClosePrices, 200);
            _smaM30_200 = Indicators.SimpleMovingAverage(_m30.ClosePrices, 200);
            _smaH1_200  = Indicators.SimpleMovingAverage(_h1.ClosePrices,  200);
            _smaH4_200  = Indicators.SimpleMovingAverage(_h4.ClosePrices,  200);
            _rsiM15     = Indicators.RelativeStrengthIndex(_m15.ClosePrices, 14);
            _rsiM30     = Indicators.RelativeStrengthIndex(_m30.ClosePrices, 14);
            _atrM15_14  = Indicators.AverageTrueRange(_m15, 14, MovingAverageType.Simple);
            _atrH1_14   = Indicators.AverageTrueRange(_h1,  14, MovingAverageType.Simple);
            // Note: cAlgo's DMS is computed on the bot's primary series.
            // For M15 ADX, attach an indicator instance to _m15 — left as TODO
            // for v0.2 (requires custom indicator wrapper). For v0.1 we use M5 ADX only.

            // ---- CSV file ----------------------------------------------------
            Directory.CreateDirectory(OutputFolder);
            var fname = $"DataCollector_{Symbol.Name}_M5_{Server.Time:yyyyMMdd_HHmmss}.csv";
            _csv = new StreamWriter(Path.Combine(OutputFolder, fname));
            Print($"DataCollector started. Logging to {fname}");

            // ---- Reset MTF tracking state ------------------------------------
            _prevM15Alignment    = "";
            _lastFlipBarIdx      = -1;
            _lastFlipDirection   = 0;
            _prevAlignmentScore  = 0;
            _alignmentRunLength  = 0;
        }

        protected override void OnBar()
        {
            // Need enough warmup before computing features
            if (Bars.ClosePrices.Count < 300) return;
            if (_h4.ClosePrices.Count < 200) return;

            // OnBar fires when a NEW bar opens. The just-closed bar is at index Count-2.
            // Index Count-1 is the brand-new forming bar (open == close == 0 body).
            int closedBarIdx = Bars.ClosePrices.Count - 2;

            // 1) Snapshot features for the bar that just closed
            var feat = ComputeFeatures(closedBarIdx);
            if (feat == null) return;

            // 2) Queue it for forward-looking outcome resolution
            _pending.Enqueue(new PendingBar
            {
                EntryBarIndex = closedBarIdx,
                EntryTime     = Bars.OpenTimes[closedBarIdx],
                EntryPrice    = Bars.ClosePrices[closedBarIdx],
                AtrAtEntry    = _atrM5_14.Result[closedBarIdx],
                Features      = feat
            });

            // 3) Resolve any pending bars whose outcome window is complete
            ResolvePendingBars(closedBarIdx);
        }

        // ---------------------------------------------------------------------
        // FEATURES — keep this list short and clean. Let ML find what matters.
        // All reads reference closedBarIdx (the just-closed M5 bar).
        // For HTF indicators, we use LastValue since their "current" bar at
        // M5-bar-close time is the still-forming HTF bar — Last(1) gives us
        // the most recently completed HTF bar, which is the correct snapshot.
        // ---------------------------------------------------------------------
        private Dictionary<string, double> ComputeFeatures(int closedBarIdx)
        {
            var f   = new Dictionary<string, double>();
            var px  = Bars.ClosePrices[closedBarIdx];
            var atr = _atrM5_14.Result[closedBarIdx];
            if (atr <= 0) return null;

            // --- Price vs SMAs (ATR-normalized distances) -------------------
            f["dist_sma_m5_50"]   = (px - _smaM5_50.Result[closedBarIdx])  / atr;
            f["dist_sma_m5_100"]  = (px - _smaM5_100.Result[closedBarIdx]) / atr;
            f["dist_sma_m5_200"]  = (px - _smaM5_200.Result[closedBarIdx]) / atr;
            f["dist_sma_m5_275"]  = (px - _smaM5_275.Result[closedBarIdx]) / atr;
            // HTF: use Last(1) = most recently CLOSED HTF bar
            f["dist_sma_m15_200"] = (px - _smaM15_200.Result.Last(1)) / atr;
            f["dist_sma_m30_200"] = (px - _smaM30_200.Result.Last(1)) / atr;
            f["dist_sma_h1_200"]  = (px - _smaH1_200.Result.Last(1))  / atr;
            f["dist_sma_h4_200"]  = (px - _smaH4_200.Result.Last(1))  / atr;

            // --- SMA slopes (5-bar % change, computed at closed bar) --------
            f["slope_sma_m5_200"] = SmaSlopeAt(_smaM5_200.Result, closedBarIdx, 5);
            f["slope_sma_h1_200"] = SmaSlopeHtf(_smaH1_200.Result, 5);

            // --- Momentum ----------------------------------------------------
            f["rsi_m5"]      = _rsiM5.Result[closedBarIdx];
            f["rsi_m15"]     = _rsiM15.Result.Last(1);
            f["rsi_m30"]     = _rsiM30.Result.Last(1);
            f["adx_m5"]      = _adxM5.ADX[closedBarIdx];
            f["di_plus_m5"]  = _adxM5.DIPlus[closedBarIdx];
            f["di_minus_m5"] = _adxM5.DIMinus[closedBarIdx];

            // --- Volatility regime ------------------------------------------
            f["atr_m5"]          = atr;
            f["atr_m15"]         = _atrM15_14.Result.Last(1);
            f["atr_h1"]          = _atrH1_14.Result.Last(1);
            f["atr_ratio_m5_h1"] = atr / Math.Max(_atrH1_14.Result.Last(1), 1e-9);
            f["bb_width"]        = (_bbM5.Top[closedBarIdx] - _bbM5.Bottom[closedBarIdx]) / atr;

            // --- Recent bar shape (last 5 closed bars, ATR-normalized) ------
            // bar0 = the just-closed bar, bar1 = one before, etc.
            for (int i = 0; i < 5; i++)
            {
                var idx = closedBarIdx - i;
                if (idx < 0) return null;
                var body  = (Bars.ClosePrices[idx] - Bars.OpenPrices[idx]) / atr;
                var range = (Bars.HighPrices[idx]  - Bars.LowPrices[idx])  / atr;
                f[$"bar{i}_body"]  = body;
                f[$"bar{i}_range"] = range;
            }

            // --- Swing structure (50-bar lookback before closed bar) --------
            double hi = double.MinValue, lo = double.MaxValue;
            int lookback = Math.Min(50, closedBarIdx);
            for (int i = 1; i <= lookback; i++)
            {
                var idx = closedBarIdx - i;
                if (Bars.HighPrices[idx] > hi) hi = Bars.HighPrices[idx];
                if (Bars.LowPrices[idx]  < lo) lo = Bars.LowPrices[idx];
            }
            f["dist_swing_high"] = (hi - px) / atr;
            f["dist_swing_low"]  = (px - lo) / atr;

            // --- Time / session context (use closed bar's open time) --------
            var t = Bars.OpenTimes[closedBarIdx];
            f["hour_utc"]    = t.Hour;
            f["dow"]         = (int)t.DayOfWeek;
            f["sess_asia"]   = (t.Hour >= 0  && t.Hour < 8)  ? 1 : 0;
            f["sess_london"] = (t.Hour >= 8  && t.Hour < 16) ? 1 : 0;
            f["sess_ny"]     = (t.Hour >= 13 && t.Hour < 21) ? 1 : 0;

            // --- Cost context ------------------------------------------------
            f["spread_pips"] = Symbol.Spread / Symbol.PipSize;

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

        // ---------------------------------------------------------------------
        // TRIPLE-BARRIER LABELING
        // For each pending bar, walk forward bar-by-bar until SL or TP hit
        // (or MaxBarsToOutcome timeout). Resolve LONG and SHORT independently.
        // ---------------------------------------------------------------------
        private void ResolvePendingBars(int currentClosedIdx)
        {
            var resolved = new List<PendingBar>();
            foreach (var pb in _pending)
            {
                int barsElapsed = currentClosedIdx - pb.EntryBarIndex;
                if (barsElapsed < 1) continue;
                if (barsElapsed > MaxBarsToOutcome || (pb.LongResolved && pb.ShortResolved))
                {
                    if (!pb.LongResolved)  { pb.OutcomeLong  = "timeout"; pb.LongResolved  = true; pb.BarsToOutcomeLong  = barsElapsed; }
                    if (!pb.ShortResolved) { pb.OutcomeShort = "timeout"; pb.ShortResolved = true; pb.BarsToOutcomeShort = barsElapsed; }
                    resolved.Add(pb);
                    continue;
                }

                // Check the most recent closed bar against barriers
                double hi = Bars.HighPrices[currentClosedIdx];
                double lo = Bars.LowPrices[currentClosedIdx];

                double longSl  = pb.EntryPrice - SlAtrMult * pb.AtrAtEntry;
                double longTp  = pb.EntryPrice + TpAtrMult * pb.AtrAtEntry;
                double shortSl = pb.EntryPrice + SlAtrMult * pb.AtrAtEntry;
                double shortTp = pb.EntryPrice - TpAtrMult * pb.AtrAtEntry;

                // LONG
                if (!pb.LongResolved)
                {
                    bool slHit = lo <= longSl;
                    bool tpHit = hi >= longTp;
                    if (slHit && tpHit) { pb.OutcomeLong = "loss"; pb.LongResolved = true; } // pessimistic
                    else if (tpHit)     { pb.OutcomeLong = "win";  pb.LongResolved = true; }
                    else if (slHit)     { pb.OutcomeLong = "loss"; pb.LongResolved = true; }
                    if (pb.LongResolved) pb.BarsToOutcomeLong = barsElapsed;
                }

                // SHORT (mirror)
                if (!pb.ShortResolved)
                {
                    bool slHit = hi >= shortSl;
                    bool tpHit = lo <= shortTp;
                    if (slHit && tpHit) { pb.OutcomeShort = "loss"; pb.ShortResolved = true; }
                    else if (tpHit)     { pb.OutcomeShort = "win";  pb.ShortResolved = true; }
                    else if (slHit)     { pb.OutcomeShort = "loss"; pb.ShortResolved = true; }
                    if (pb.ShortResolved) pb.BarsToOutcomeShort = barsElapsed;
                }

                if (pb.LongResolved && pb.ShortResolved) resolved.Add(pb);
            }

            // Sort resolved rows by entry time so the CSV stays chronological
            resolved.Sort((a, b) => a.EntryTime.CompareTo(b.EntryTime));
            foreach (var r in resolved) WriteRow(r);

            if (resolved.Count > 0)
            {
                var keep = _pending.Where(p => !resolved.Contains(p)).ToList();
                _pending.Clear();
                foreach (var p in keep) _pending.Enqueue(p);
            }
        }

        private void WriteRow(PendingBar pb)
        {
            if (!_headerWritten)
            {
                var headers = new List<string> { "timestamp", "symbol" };
                headers.AddRange(pb.Features.Keys);
                headers.AddRange(new[] {
                    "outcome_long", "bars_to_outcome_long",
                    "outcome_short", "bars_to_outcome_short"
                });
                _csv.WriteLine(string.Join(",", headers));
                _headerWritten = true;
            }

            var sb = new StringBuilder();
            sb.Append(pb.EntryTime.ToString("yyyy-MM-dd HH:mm:ss")).Append(",");
            sb.Append(Symbol.Name).Append(",");
            foreach (var kv in pb.Features) sb.Append(kv.Value.ToString("F6")).Append(",");
            sb.Append(pb.OutcomeLong).Append(",").Append(pb.BarsToOutcomeLong).Append(",");
            sb.Append(pb.OutcomeShort).Append(",").Append(pb.BarsToOutcomeShort);
            _csv.WriteLine(sb.ToString());
            _csv.Flush();
        }

        protected override void OnStop()
        {
            // Flush any remaining pending bars as timeouts
            foreach (var pb in _pending)
            {
                if (!pb.LongResolved)  { pb.OutcomeLong  = "timeout"; }
                if (!pb.ShortResolved) { pb.OutcomeShort = "timeout"; }
                WriteRow(pb);
            }
            _csv?.Flush();
            _csv?.Close();
            Print("DataCollector stopped. CSV closed.");
        }

        private class PendingBar
        {
            public int    EntryBarIndex;
            public DateTime EntryTime;
            public double EntryPrice;
            public double AtrAtEntry;
            public Dictionary<string, double> Features;

            public bool   LongResolved;
            public string OutcomeLong = "";
            public int    BarsToOutcomeLong;

            public bool   ShortResolved;
            public string OutcomeShort = "";
            public int    BarsToOutcomeShort;
        }
    }
}
