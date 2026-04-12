// =============================================================================
// JCAMP_DataCollector v0.2
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
