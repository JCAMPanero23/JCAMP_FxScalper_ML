# Phase 4 — Trading cBot (JCAMP_FxScalper_ML)

**Date:** 2026-04-18
**Status:** Ready to build
**Deliverable:** A cTrader cBot that computes features on each M5 bar close,
calls the FastAPI service for a prediction, and trades when `p_win_long > 0.65`

---

## The #1 Risk: Train/Serve Feature Skew

Before anything else, understand this: **if the trading cBot computes features
even slightly differently from DataCollector, the model receives garbage inputs
and all the CV/holdout validation is worthless.**

This is not hypothetical. It's the most common failure mode in production ML
systems. Examples of how it happens:

- DataCollector reads `closedBarIdx` (bar at Count-2). Trading cBot reads
  `Count-1` (the forming bar). Off by one bar = every feature is wrong.
- DataCollector uses `Last(1)` for HTF indicators. Trading cBot uses
  `LastValue`. Different bar = different values.
- DataCollector computes `atr_percentile_2000bar` with a Queue that accumulates
  from bar 1. Trading cBot starts fresh on every run = no history = wrong percentile.
- Rounding differences between float operations in different execution contexts.

**The mitigation is architectural:** extract ALL feature computation into a
single shared file (`JCAMP_Features.cs`) that BOTH DataCollector and
FxScalper_ML use. Not "same logic" — literally the SAME FILE, copied into
both cBot project folders.

---

## Architecture

```
cbot/
├── JCAMP_Features.cs              ← SHARED (identical copy in both)
├── JCAMP_DataCollector/
│   └── JCAMP_DataCollector.cs     ← Uses JCAMP_Features for computation
│                                     Writes features + labels to CSV
├── JCAMP_FxScalper_ML/
│   └── JCAMP_FxScalper_ML.cs      ← Uses JCAMP_Features for computation
│                                     Calls FastAPI, executes trades
└── JCAMP_FeatureSkewTest/
    └── JCAMP_FeatureSkewTest.cs   ← Runs both, diffs CSVs (Phase 4.5)
```

---

## Step 1: Extract JCAMP_Features.cs (Shared Module)

This file contains EVERYTHING related to feature computation. It takes
indicator values as inputs and returns a `Dictionary<string, double>` — the
exact same dict that DataCollector currently builds in `ComputeFeatures()`.

### What Goes In JCAMP_Features.cs

```csharp
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
// Version: v0.4 (46 features)
// Last updated: 2026-04-18
// =============================================================================

using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace JCAMP.Shared
{
    public class FeatureComputer
    {
        // Feature names in exact order (must match Python config.py)
        public static readonly string[] FEATURE_NAMES = new string[]
        {
            "dist_sma_m5_50", "dist_sma_m5_100", "dist_sma_m5_200",
            "dist_sma_m5_275", "dist_sma_m15_200", "dist_sma_m30_200",
            "dist_sma_h1_200", "dist_sma_h4_200",
            "slope_sma_m5_200", "slope_sma_h1_200",
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
        };

        // ----- Stateful fields (persist across bars) -----
        private string _prevM15Alignment = "";
        private int _lastFlipBarIdx = -1;
        private int _lastFlipDirection = 0;
        private int _prevAlignmentScore = 0;
        private int _alignmentRunLength = 0;

        private const int ATR_HISTORY_SIZE = 2000;
        private readonly Queue<double> _atrHistory = new Queue<double>();

        /// <summary>
        /// Compute all 46 features for the just-closed M5 bar.
        /// This method MUST produce identical output to DataCollector v0.4.
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
        /// <returns>Dictionary of 46 features, or null if warmup incomplete</returns>
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
            // ---- PASTE THE ENTIRE ComputeFeatures() BODY FROM DataCollector HERE ----
            // This includes:
            //   - Price vs SMAs (ATR-normalized)
            //   - SMA slopes
            //   - Momentum (RSI, ADX, DI)
            //   - Volatility (ATR, BB width)
            //   - Recent bar shape (bar0-bar4)
            //   - Swing structure
            //   - Time / session
            //   - Spread
            //   - MTF alignment (v0.3)
            //   - Regime features (v0.4)
            //
            // The ENTIRE body of ComputeFeatures from JCAMP_DataCollector.cs
            // goes here VERBATIM. Do not modify any calculation.
            //
            // The only change: replace indicator field references
            // (e.g., _smaM5_50) with the method parameters (e.g., smaM5_50).
            // This is a mechanical rename, not a logic change.

            var f = new Dictionary<string, double>();
            var px = bars.ClosePrices[closedBarIdx];
            var atr = atrM5.Result[closedBarIdx];
            if (atr <= 0) return null;

            // ... (full body from DataCollector ComputeFeatures)
            // ... (Claude Code: copy the ENTIRE method body here,
            //      replacing _smaM5_50 → smaM5_50, etc.)

            return f;
        }

        // ---- Helper methods (also from DataCollector) ----

        public double SmaSlopeAt(IndicatorDataSeries s, int atIdx, int lookback)
        {
            if (atIdx - lookback < 0) return 0;
            var now = s[atIdx];
            var prev = s[atIdx - lookback];
            return prev == 0 ? 0 : (now - prev) / prev;
        }

        public double SmaSlopeHtf(IndicatorDataSeries s, int lookback)
        {
            if (s.Count <= lookback + 1) return 0;
            var now = s.Last(1);
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
            _atrHistory.Clear();
        }
    }
}
```

### Implementation Instructions for Claude Code

1. **Open** `cbot/JCAMP_DataCollector.cs` (the current v0.4 file)
2. **Copy** the ENTIRE body of `ComputeFeatures()` (everything between `{` and `return f;`)
3. **Paste** into the `Compute()` method of `JCAMP_Features.cs`
4. **Mechanically rename** all private field references to parameter names:
   - `_smaM5_50` → `smaM5_50`
   - `_smaM5_100` → `smaM5_100`
   - `_smaM5_200` → `smaM5_200`
   - `_smaM5_275` → `smaM5_275`
   - `_smaM15_200` → `smaM15_200`
   - `_smaM30_200` → `smaM30_200`
   - `_smaH1_200` → `smaH1_200`
   - `_smaH4_200` → `smaH4_200`
   - `_rsiM5` → `rsiM5`
   - `_rsiM15` → `rsiM15`
   - `_rsiM30` → `rsiM30`
   - `_adxM5` → `adxM5`
   - `_atrM5_14` → `atrM5`
   - `_atrM15_14` → `atrM15`
   - `_atrH1_14` → `atrH1`
   - `_bbM5` → `bbM5`
5. **Move** `SmaSlopeAt` and `SmaSlopeHtf` into the class
6. **Move** the stateful fields (`_prevM15Alignment`, `_lastFlipBarIdx`,
   `_lastFlipDirection`, `_prevAlignmentScore`, `_alignmentRunLength`,
   `_atrHistory`, `ATR_HISTORY_SIZE`) into the class
7. **Do NOT change any calculation logic.** This is a refactor, not a rewrite.

---

## Step 2: Refactor DataCollector to Use Shared Module

After extracting `JCAMP_Features.cs`, refactor DataCollector to delegate
feature computation to it:

```csharp
// In JCAMP_DataCollector.cs:

// Add at class level:
private JCAMP.Shared.FeatureComputer _featureComputer;

// In OnStart():
_featureComputer = new JCAMP.Shared.FeatureComputer();

// Replace ComputeFeatures(closedBarIdx) call with:
var feat = _featureComputer.Compute(
    Bars, closedBarIdx, Symbol,
    _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275,
    _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200,
    _rsiM5, _rsiM15, _rsiM30,
    _adxM5, _atrM5_14, _atrM15_14, _atrH1_14, _bbM5);

// Remove: ComputeFeatures method, SmaSlopeAt, SmaSlopeHtf,
//         and all MTF/regime state fields (now in FeatureComputer)
```

**VERIFICATION:** After refactoring, run DataCollector on Jan 2023 and diff
the output CSV against the pre-refactor v0.4 CSV. They must be IDENTICAL
(byte-for-byte on feature columns). If any difference exists, the refactor
introduced a bug — fix before proceeding.

---

## Step 3: Build JCAMP_FxScalper_ML.cs (Trading cBot)

```csharp
// =============================================================================
// JCAMP_FxScalper_ML v1.0
// -----------------------------------------------------------------------------
// ML-filtered M5 LONG scalper. Computes features on each M5 bar close,
// calls FastAPI for p_win_long, trades when p_win > threshold.
//
// LONG ONLY (v1.0). SHORT model did not pass Gate A.
//
// Author : JCamp
// Target : cTrader Automate, EURUSD M5
// Requires: FastAPI prediction service running on localhost:8000
// =============================================================================

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;
using JCAMP.Shared;  // ← Shared feature module

namespace cAlgo.Robots
{
    [Robot(AccessRights = AccessRights.FullAccess, AddIndicators = true)]
    public class JCAMP_FxScalper_ML : Robot
    {
        #region Parameters

        [Parameter("=== ML SETTINGS ===", DefaultValue = "")]
        public string MLHeader { get; set; }

        [Parameter("ML Threshold", DefaultValue = 0.65, MinValue = 0.50, MaxValue = 0.90, Step = 0.05)]
        public double MLThreshold { get; set; }

        [Parameter("API URL", DefaultValue = "http://localhost:8000/predict")]
        public string ApiUrl { get; set; }

        [Parameter("API Timeout (ms)", DefaultValue = 5000, MinValue = 1000, MaxValue = 30000)]
        public int ApiTimeoutMs { get; set; }

        [Parameter("=== RISK MANAGEMENT ===", DefaultValue = "")]
        public string RiskHeader { get; set; }

        [Parameter("Risk Per Trade %", DefaultValue = 1.0, MinValue = 0.5, MaxValue = 2.0, Step = 0.25)]
        public double RiskPercent { get; set; }

        [Parameter("SL ATR Multiplier", DefaultValue = 1.5)]
        public double SlAtrMult { get; set; }

        [Parameter("TP ATR Multiplier", DefaultValue = 3.0)]
        public double TpAtrMult { get; set; }

        [Parameter("Daily Loss Limit (R)", DefaultValue = -2.0)]
        public double DailyLossLimitR { get; set; }

        [Parameter("Monthly DD Limit %", DefaultValue = 6.0)]
        public double MonthlyDDPercent { get; set; }

        [Parameter("Max Consecutive Losses", DefaultValue = 8)]
        public int MaxConsecLosses { get; set; }

        [Parameter("Max Positions", DefaultValue = 1)]
        public int MaxPositions { get; set; }

        [Parameter("Enable Trading", DefaultValue = false)]
        public bool EnableTrading { get; set; }

        #endregion

        #region Private Fields

        private const string BOT_VERSION = "1.0.0";
        private const string BOT_LABEL = "JCAMP_FxScalper_ML";

        // Shared feature computer (SAME code as DataCollector)
        private FeatureComputer _features;

        // Indicators (same setup as DataCollector)
        private SimpleMovingAverage _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275;
        private RelativeStrengthIndex _rsiM5;
        private DirectionalMovementSystem _adxM5;
        private AverageTrueRange _atrM5_14;
        private BollingerBands _bbM5;

        private Bars _m15, _m30, _h1, _h4;
        private SimpleMovingAverage _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200;
        private RelativeStrengthIndex _rsiM15, _rsiM30;
        private AverageTrueRange _atrM15_14, _atrH1_14;

        // HTTP client for API calls
        private HttpClient _httpClient;

        // Risk tracking
        private double _dailyRLoss = 0.0;
        private int _dailyLossingTrades = 0;
        private DateTime _lastTradingDay = DateTime.MinValue;
        private int _consecutiveLosses = 0;
        private double _monthStartEquity = 0.0;
        private int _lastTradingMonth = 0;
        private bool _dailyLimitHit = false;
        private bool _monthlyLimitHit = false;
        private bool _consecLimitHit = false;

        #endregion

        #region Initialization

        protected override void OnStart()
        {
            Print("========================================");
            Print($"JCAMP FxScalper ML v{BOT_VERSION}");
            Print($"Mode: {(EnableTrading ? "LIVE" : "SIMULATION")}");
            Print($"Threshold: {MLThreshold}");
            Print($"API: {ApiUrl}");
            Print("========================================");

            // Validate timeframe
            if (TimeFrame != TimeFrame.Minute5)
            {
                Print("ERROR: Must run on M5!");
                Stop();
                return;
            }

            // Init indicators (IDENTICAL to DataCollector OnStart)
            _m15 = MarketData.GetBars(TimeFrame.Minute15);
            _m30 = MarketData.GetBars(TimeFrame.Minute30);
            _h1  = MarketData.GetBars(TimeFrame.Hour);
            _h4  = MarketData.GetBars(TimeFrame.Hour4);

            _smaM5_50  = Indicators.SimpleMovingAverage(Bars.ClosePrices, 50);
            _smaM5_100 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 100);
            _smaM5_200 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 200);
            _smaM5_275 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 275);
            _rsiM5     = Indicators.RelativeStrengthIndex(Bars.ClosePrices, 14);
            _adxM5     = Indicators.DirectionalMovementSystem(14);
            _atrM5_14  = Indicators.AverageTrueRange(14, MovingAverageType.Simple);
            _bbM5      = Indicators.BollingerBands(Bars.ClosePrices, 20, 2,
                                                    MovingAverageType.Simple);

            _smaM15_200 = Indicators.SimpleMovingAverage(_m15.ClosePrices, 200);
            _smaM30_200 = Indicators.SimpleMovingAverage(_m30.ClosePrices, 200);
            _smaH1_200  = Indicators.SimpleMovingAverage(_h1.ClosePrices,  200);
            _smaH4_200  = Indicators.SimpleMovingAverage(_h4.ClosePrices,  200);
            _rsiM15     = Indicators.RelativeStrengthIndex(_m15.ClosePrices, 14);
            _rsiM30     = Indicators.RelativeStrengthIndex(_m30.ClosePrices, 14);
            _atrM15_14  = Indicators.AverageTrueRange(_m15, 14,
                                                       MovingAverageType.Simple);
            _atrH1_14   = Indicators.AverageTrueRange(_h1, 14,
                                                       MovingAverageType.Simple);

            // Init shared feature computer
            _features = new FeatureComputer();

            // Init HTTP client
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromMilliseconds(ApiTimeoutMs);

            // Init risk tracking
            _monthStartEquity = Account.Equity;
            _lastTradingMonth = Server.Time.Month;
        }

        #endregion

        #region Main Loop

        protected override void OnBar()
        {
            // Warmup check (same as DataCollector)
            if (Bars.ClosePrices.Count < 300) return;
            if (_h4.ClosePrices.Count < 200) return;

            int closedBarIdx = Bars.ClosePrices.Count - 2;

            // Reset daily counters
            CheckDayReset();
            CheckMonthReset();

            // Check risk limits
            if (_dailyLimitHit || _monthlyLimitHit || _consecLimitHit)
            {
                // Still compute features (to keep state current) but don't trade
                _features.Compute(Bars, closedBarIdx, Symbol,
                    _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275,
                    _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200,
                    _rsiM5, _rsiM15, _rsiM30,
                    _adxM5, _atrM5_14, _atrM15_14, _atrH1_14, _bbM5);
                return;
            }

            // Skip if already in a position
            if (Positions.FindAll(BOT_LABEL, SymbolName).Length >= MaxPositions)
            {
                // Still compute features to keep state current
                _features.Compute(Bars, closedBarIdx, Symbol,
                    _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275,
                    _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200,
                    _rsiM5, _rsiM15, _rsiM30,
                    _adxM5, _atrM5_14, _atrM15_14, _atrH1_14, _bbM5);
                return;
            }

            // 1) Compute features (shared module)
            var feat = _features.Compute(Bars, closedBarIdx, Symbol,
                _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275,
                _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200,
                _rsiM5, _rsiM15, _rsiM30,
                _adxM5, _atrM5_14, _atrM15_14, _atrH1_14, _bbM5);

            if (feat == null) return;

            // 2) Call FastAPI for prediction
            double pWinLong = CallPredictApi(feat);
            if (pWinLong < 0) return; // API error

            // 3) Check threshold
            if (pWinLong <= MLThreshold) return;

            // 4) Calculate position size and levels
            double atr = _atrM5_14.Result[closedBarIdx];
            double slPips = Math.Max(SlAtrMult * atr / Symbol.PipSize, 5.0);
            double tpPips = TpAtrMult * atr / Symbol.PipSize;

            double riskAmount = Account.Equity * (RiskPercent / 100.0);
            double pipValue = Symbol.PipValue;
            double lots = Math.Round(riskAmount / (slPips * pipValue), 2);
            lots = Math.Max(lots, Symbol.VolumeInUnitsMin / Symbol.LotSize);
            double volume = Symbol.NormalizeVolumeInUnits(
                lots * Symbol.LotSize, RoundingMode.Down);

            // 5) Execute trade
            if (!EnableTrading) return;

            var result = ExecuteMarketOrder(
                TradeType.Buy, SymbolName, volume,
                BOT_LABEL, slPips, tpPips);

            if (result.IsSuccessful)
            {
                Print($"[ENTRY] LONG @ {result.Position.EntryPrice:F5} | " +
                      $"SL={slPips:F1} pips | TP={tpPips:F1} pips | " +
                      $"Lots={lots:F2} | p_win={pWinLong:F3}");
            }
            else
            {
                Print($"[ERROR] Order failed: {result.Error}");
            }
        }

        #endregion

        #region API Client

        private double CallPredictApi(Dictionary<string, double> features)
        {
            try
            {
                // Build JSON request
                var sb = new StringBuilder();
                sb.Append("{\"symbol\":\"").Append(SymbolName).Append("\",");
                sb.Append("\"timestamp\":\"").Append(Server.Time.ToString("o")).Append("\",");
                sb.Append("\"features\":{");

                bool first = true;
                foreach (var name in FeatureComputer.FEATURE_NAMES)
                {
                    if (!first) sb.Append(",");
                    sb.Append("\"").Append(name).Append("\":");
                    sb.Append(features[name].ToString("G17")); // full precision
                    first = false;
                }
                sb.Append("}}");

                var content = new StringContent(
                    sb.ToString(), Encoding.UTF8, "application/json");

                var response = _httpClient.PostAsync(ApiUrl, content).Result;

                if (!response.IsSuccessStatusCode)
                {
                    Print($"[API] Error: HTTP {response.StatusCode}");
                    return -1;
                }

                var json = response.Content.ReadAsStringAsync().Result;

                // Simple JSON parsing (avoid dependency on Json library)
                // Look for "p_win_long": 0.xxxxx
                int idx = json.IndexOf("\"p_win_long\":");
                if (idx < 0) { Print("[API] Missing p_win_long in response"); return -1; }

                int valStart = idx + "\"p_win_long\":".Length;
                int valEnd = json.IndexOfAny(new[] { ',', '}' }, valStart);
                string valStr = json.Substring(valStart, valEnd - valStart).Trim();

                if (double.TryParse(valStr, System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out double pWin))
                {
                    return pWin;
                }

                Print($"[API] Failed to parse p_win_long: '{valStr}'");
                return -1;
            }
            catch (Exception ex)
            {
                Print($"[API] Exception: {ex.Message}");
                return -1;
            }
        }

        #endregion

        #region Risk Management

        private void CheckDayReset()
        {
            if (Server.Time.Date != _lastTradingDay.Date)
            {
                _dailyRLoss = 0;
                _dailyLossingTrades = 0;
                _dailyLimitHit = false;
                _lastTradingDay = Server.Time;
            }
        }

        private void CheckMonthReset()
        {
            if (Server.Time.Month != _lastTradingMonth)
            {
                _monthStartEquity = Account.Equity;
                _lastTradingMonth = Server.Time.Month;
                _monthlyLimitHit = false;
            }

            // Check monthly DD
            double ddPercent = ((_monthStartEquity - Account.Equity) /
                                _monthStartEquity) * 100;
            if (ddPercent >= MonthlyDDPercent)
            {
                if (!_monthlyLimitHit)
                {
                    Print($"[RISK] Monthly DD limit hit: {ddPercent:F1}% >= {MonthlyDDPercent}%");
                    _monthlyLimitHit = true;

                    // Close all positions
                    foreach (var pos in Positions.FindAll(BOT_LABEL, SymbolName))
                        ClosePosition(pos);
                }
            }
        }

        protected override void OnPositionClosed(Position position)
        {
            if (position.Label != BOT_LABEL) return;

            double atr = _atrM5_14.Result.LastValue;
            double riskPips = SlAtrMult * atr / Symbol.PipSize;
            double rMultiple = position.Pips / riskPips;

            if (position.NetProfit < 0)
            {
                _dailyRLoss += rMultiple; // rMultiple is negative
                _dailyLossingTrades++;
                _consecutiveLosses++;

                Print($"[EXIT] LOSS {rMultiple:+F2}R | Daily: {_dailyRLoss:F2}R | " +
                      $"Consec: {_consecutiveLosses}");

                // Check daily limit
                if (_dailyRLoss <= DailyLossLimitR)
                {
                    Print($"[RISK] Daily loss limit hit: {_dailyRLoss:F2}R");
                    _dailyLimitHit = true;
                }

                // Check consecutive limit
                if (_consecutiveLosses >= MaxConsecLosses)
                {
                    Print($"[RISK] Consecutive loss limit hit: {_consecutiveLosses}");
                    _consecLimitHit = true;
                }
            }
            else
            {
                _consecutiveLosses = 0; // Reset on win
                Print($"[EXIT] WIN {rMultiple:+F2}R | Daily: {_dailyRLoss:F2}R");
            }
        }

        #endregion

        #region OnStop

        protected override void OnStop()
        {
            _httpClient?.Dispose();
            Print("========================================");
            Print($"JCAMP FxScalper ML v{BOT_VERSION} STOPPED");
            Print("========================================");
        }

        #endregion
    }
}
```

---

## Step 4: Feature Skew Test (Phase 4.5)

**Purpose:** Verify that FxScalper_ML computes IDENTICAL features to DataCollector.

**Method:**
1. Run DataCollector on a 1-month backtest (e.g., Jan 2024) → CSV-A
2. Modify FxScalper_ML to also log features to CSV (add a temporary CSV
   writer that writes the same columns) → CSV-B
3. Diff CSV-A and CSV-B column by column
4. Maximum allowed difference per cell: 0.000001 (floating point tolerance)
5. If ANY cell differs by more than tolerance → STOP, debug, fix

```bash
# Quick diff approach (after both CSVs are generated):
python -c "
import pandas as pd
a = pd.read_csv('datacollector_jan2024.csv')
b = pd.read_csv('fxscalper_jan2024.csv')
# Compare feature columns only (skip labels)
feat_cols = [c for c in a.columns if c not in ['timestamp','symbol',
    'outcome_long','outcome_short','bars_to_outcome_long','bars_to_outcome_short']]
diff = (a[feat_cols] - b[feat_cols]).abs()
max_diff = diff.max().max()
print(f'Max absolute difference: {max_diff}')
if max_diff > 0.000001:
    print('FAIL: Feature skew detected!')
    print(diff.max().sort_values(ascending=False).head(10))
else:
    print('PASS: Features are identical.')
"
```

**This test is NON-NEGOTIABLE.** Do not skip it. Do not proceed to demo
trading without a passing skew test.

---

## Step 5: Deployment Sequence

After all code is written and the skew test passes:

### 5a. Demo Forward Test (2 weeks minimum)

1. Deploy FastAPI on VPS (or laptop)
2. Run FxScalper_ML on cTrader demo account, EURUSD M5
3. Set `EnableTrading = true`
4. Monitor for 2 weeks
5. Check:
   - Zero unhandled exceptions
   - API responds consistently (check healthcheck logs)
   - Trades match expected frequency (~2-5 per day based on CV)
   - No obvious errors in position sizing
   - R-multiples per trade are reasonable (wins ~+2R, losses ~-1R)

### 5b. Live Deployment ($500)

Only after demo passes:

1. Switch to FP Markets live account
2. Confirm `RiskPercent = 1.0` (risking $5 per trade)
3. Set `MonthlyDDPercent = 6.0`
4. Set `MaxConsecLosses = 8`
5. Monitor daily for first week, then weekly

---

## Risk Parameters Summary (Updated from PRD)

| Parameter | PRD Original | v1.0 Actual | Reason |
|-----------|-------------|-------------|--------|
| Risk % | 1.0% | 1.0% | Unchanged |
| SL | 1.5×ATR | 1.5×ATR | Unchanged |
| TP | 3.0×ATR | 3.0×ATR | Unchanged |
| Daily loss limit | -2R | -2R | Unchanged |
| Monthly DD | 8% | **6%** | Tighter — LONG only, smaller buffer |
| Consec loss limit | 6 | **8** | Relaxed — holdout showed 16 max |
| ML threshold | 0.55 | **0.65** | Gate A threshold |
| Directions | LONG + SHORT | **LONG only** | SHORT failed Gate A |

---

## IMPORTANT: Feature State During Non-Trading Bars

Notice in the OnBar() code: even when the bot can't trade (risk limit hit,
position already open), it STILL calls `_features.Compute()`. This is
critical because the feature computer has stateful fields:

- `_atrHistory` (rolling ATR percentile queue)
- `_prevM15Alignment` (flip detection)
- `_alignmentRunLength` (duration tracking)

If you skip `Compute()` on bars where you don't trade, these states go stale
and the next prediction uses wrong values. **Always compute, even if you
don't trade.** The compute cost is negligible (<1ms per bar).

---

## Checklist for Claude Code

### Step 1: Extract shared module
- [ ] Create `cbot/JCAMP_Features.cs` with full `FeatureComputer` class
- [ ] Copy `ComputeFeatures` body from DataCollector VERBATIM
- [ ] Rename field references to method parameters (mechanical, not logical)
- [ ] Include `SmaSlopeAt`, `SmaSlopeHtf` helper methods
- [ ] Include all stateful fields and `Reset()` method
- [ ] Include `FEATURE_NAMES` array in correct order

### Step 2: Refactor DataCollector
- [ ] Import `JCAMP.Shared.FeatureComputer`
- [ ] Replace `ComputeFeatures` call with `_featureComputer.Compute(...)`
- [ ] Remove duplicated code (old `ComputeFeatures`, helpers, state fields)
- [ ] Verify compilation
- [ ] Run on Jan 2023, diff output against pre-refactor CSV (must be identical)

### Step 3: Build trading cBot
- [ ] Create `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs`
- [ ] Import shared `FeatureComputer`
- [ ] Implement `OnBar` with feature compute → API call → trade logic
- [ ] Implement `CallPredictApi` with HTTP POST and JSON parsing
- [ ] Implement risk management (daily, monthly, consecutive)
- [ ] Implement `OnPositionClosed` for R-tracking
- [ ] Always compute features even when not trading (state maintenance)
- [ ] Verify compilation

### Step 4: Skew test
- [ ] Run DataCollector on Jan 2024 → CSV-A
- [ ] Add temporary CSV logging to FxScalper_ML
- [ ] Run FxScalper_ML on Jan 2024 → CSV-B
- [ ] Diff CSV-A vs CSV-B: max difference < 0.000001
- [ ] Remove temporary CSV logging from FxScalper_ML after test passes

### Step 5: Documentation
- [ ] Update STATUS.md with Phase 4 completion
- [ ] Update README.md with deployment instructions
- [ ] Document the skew test result (pass/fail, max difference)
