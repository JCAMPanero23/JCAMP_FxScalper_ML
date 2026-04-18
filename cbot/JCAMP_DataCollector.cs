// =============================================================================
// JCAMP_DataCollector v0.4
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
using cAlgo.Robots;

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

        // ----- Shared feature computer (v0.4 refactor) ----------------------
        private FeatureComputer _featureComputer;

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

            // ---- Init shared feature computer --------------------------------
            _featureComputer = new FeatureComputer();
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
            var feat = _featureComputer.Compute(
                Bars, closedBarIdx, Symbol,
                _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275,
                _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200,
                _rsiM5, _rsiM15, _rsiM30,
                _adxM5, _atrM5_14, _atrM15_14, _atrH1_14, _bbM5);
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
