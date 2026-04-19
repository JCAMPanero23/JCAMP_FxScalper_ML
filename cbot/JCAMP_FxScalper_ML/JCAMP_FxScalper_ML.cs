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
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;
using cAlgo.Robots;

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

        [Parameter("TP ATR Multiplier", DefaultValue = 4.5)]
        public double TpAtrMult { get; set; }

        [Parameter("Timeout Bars", DefaultValue = 72, MinValue = 5)]
        public int TimeoutBars { get; set; }

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

        private FeatureComputer _features;
        private HttpClient _httpClient;

        // Indicators (same as DataCollector)
        private SimpleMovingAverage _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275;
        private RelativeStrengthIndex _rsiM5;
        private DirectionalMovementSystem _adxM5;
        private AverageTrueRange _atrM5_14;
        private BollingerBands _bbM5;

        private Bars _m15, _m30, _h1, _h4;
        private SimpleMovingAverage _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200;
        private RelativeStrengthIndex _rsiM15, _rsiM30;
        private AverageTrueRange _atrM15_14, _atrH1_14;

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

            // Init HTF bars
            _m15 = MarketData.GetBars(TimeFrame.Minute15);
            _m30 = MarketData.GetBars(TimeFrame.Minute30);
            _h1  = MarketData.GetBars(TimeFrame.Hour);
            _h4  = MarketData.GetBars(TimeFrame.Hour4);

            // Init M5 indicators
            _smaM5_50  = Indicators.SimpleMovingAverage(Bars.ClosePrices, 50);
            _smaM5_100 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 100);
            _smaM5_200 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 200);
            _smaM5_275 = Indicators.SimpleMovingAverage(Bars.ClosePrices, 275);
            _rsiM5     = Indicators.RelativeStrengthIndex(Bars.ClosePrices, 14);
            _adxM5     = Indicators.DirectionalMovementSystem(14);
            _atrM5_14  = Indicators.AverageTrueRange(14, MovingAverageType.Simple);
            _bbM5      = Indicators.BollingerBands(Bars.ClosePrices, 20, 2,
                                                    MovingAverageType.Simple);

            // Init HTF indicators
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
            _features.Reset();  // Initialize stateful fields (atrHistory, etc.)

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

            // CRITICAL FIX #1: Compute features ONCE unconditionally at the top
            // Stateful trackers (atr_percentile, mtf_alignment_duration, bars_since_flip)
            // must be updated on EVERY bar, including bars where position is open or
            // risk limits are hit. Skipping bars creates gaps in rolling windows.
            var feat = _features.Compute(Bars, closedBarIdx, Symbol,
                _smaM5_50, _smaM5_100, _smaM5_200, _smaM5_275,
                _smaM15_200, _smaM30_200, _smaH1_200, _smaH4_200,
                _rsiM5, _rsiM15, _rsiM30,
                _adxM5, _atrM5_14, _atrM15_14, _atrH1_14, _bbM5);

            if (feat == null) return;

            // Check risk limits — pass features to management logic
            if (_dailyLimitHit || _monthlyLimitHit || _consecLimitHit)
            {
                return; // Features already computed; just don't trade
            }

            // Manage open position (if exists) — pass pre-computed features
            var openPos = Positions.FindAll(BOT_LABEL, SymbolName);
            if (openPos.Length >= MaxPositions)
            {
                ManageOpenTrade(openPos[0], feat, closedBarIdx);
                return;
            }

            // Entry logic: call API with fresh features, execute trade if signal > threshold
            double pWinLong = CallPredictApi(feat);
            if (pWinLong < 0) return; // API error

            // Check threshold
            if (pWinLong <= MLThreshold) return;

            // Calculate position size and levels
            double atr = _atrM5_14.Result[closedBarIdx];
            double slPips = Math.Max(SlAtrMult * atr / Symbol.PipSize, 5.0);
            double tpPips = TpAtrMult * atr / Symbol.PipSize;

            double riskAmount = Account.Equity * (RiskPercent / 100.0);
            double pipValue = Symbol.PipValue;
            double lots = Math.Round(riskAmount / (slPips * pipValue), 2);
            lots = Math.Max(lots, Symbol.VolumeInUnitsMin / Symbol.LotSize);
            double volume = Symbol.NormalizeVolumeInUnits(
                lots * Symbol.LotSize, RoundingMode.Down);

            // Execute trade
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

        /// <summary>
        /// Manage open position using already-computed features for this bar.
        /// Called only when position is open. Features are FRESH (computed at OnBar top).
        /// </summary>
        private void ManageOpenTrade(Position pos, Dictionary<string, double> features, int closedBarIdx)
        {
            // Placeholder for future +2R re-score logic
            // When profit >= +2R: re-score with current features to decide TP extension
            // For v1.0: just hold position with original TP
            // Future: extend TP to 6.0×ATR if p_win_long >= threshold at +2R milestone
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
