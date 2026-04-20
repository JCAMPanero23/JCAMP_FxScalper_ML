# FastAPI v05 Configuration

## Configuration Overview

This document verifies and documents the FastAPI configuration for v05 model deployment.

### Model Configuration

| Setting | Value |
|---------|-------|
| **Model File** | `eurusd_long_v05_holdout.joblib` |
| **Model Path** | `models/eurusd_long_v05_holdout.joblib` |
| **Model Size** | 6.7 MB |
| **Version String** | `eurusd_long_v05_20260420` |
| **Model Type** | LightGBM (trained on v0.4 features) |

### Feature Configuration

| Metric | Value |
|--------|-------|
| **Total Features** | 46 |
| **Feature Order** | Exact match with JCAMP_Features.cs |
| **Feature Validation** | PASSED - All 46 features present and correct |

### Feature List (46 features in exact order)

#### Price vs SMAs - ATR-normalized distances (8 features)
```
0. dist_sma_m5_50
1. dist_sma_m5_100
2. dist_sma_m5_200
3. dist_sma_m5_275
4. dist_sma_m15_200
5. dist_sma_m30_200
6. dist_sma_h1_200
7. dist_sma_h4_200
```

#### SMA Slopes (2 features)
```
8. slope_sma_m5_200
9. slope_sma_h1_200
```

#### Momentum (6 features)
```
10. rsi_m5
11. rsi_m15
12. rsi_m30
13. adx_m5
14. di_plus_m5
15. di_minus_m5
```

#### Volatility (5 features)
```
16. atr_m5
17. atr_m15
18. atr_h1
19. atr_ratio_m5_h1
20. bb_width
```

#### Recent Bar Shape - ATR-normalized (10 features)
```
21. bar0_body
22. bar0_range
23. bar1_body
24. bar1_range
25. bar2_body
26. bar2_range
27. bar3_body
28. bar3_range
29. bar4_body
30. bar4_range
```

#### Swing Structure (2 features)
```
31. dist_swing_high
32. dist_swing_low
```

#### Time / Session Context (5 features)
```
33. hour_utc
34. dow
35. sess_asia
36. sess_london
37. sess_ny
```

#### Cost Context (1 feature)
```
38. spread_pips
```

#### MTF Alignment (5 features)
```
39. mtf_alignment_score
40. mtf_stacking_score
41. bars_since_tf_fast_flip
42. tf_fast_flip_direction
43. mtf_alignment_duration
```

#### Regime Quality (2 features)
```
44. atr_percentile_2000bar
45. h1_alignment_agreement
```

## Verification Checklist

- ✓ MODEL_PATH updated to v05 model file
- ✓ VERSION string updated to v05 (eurusd_long_v05_20260420)
- ✓ FEATURE_NAMES array contains exactly 46 features
- ✓ All feature names match JCAMP_Features.cs exactly
- ✓ Feature order matches JCAMP_Features.cs exactly (indices 0-45)
- ✓ Model file exists at configured path
- ✓ Model file is readable and properly formatted (6.7 MB)

## Compatibility

This configuration ensures:

1. **Feature Alignment**: FEATURE_NAMES in config.py matches JCAMP_Features.cs
2. **Model Compatibility**: v05 model trained on these exact 46 features
3. **cBot Integration**: JCAMP_FxScalper_ML cBot computes features in same order
4. **Data Pipeline**: FastAPI receives properly-ordered feature vectors from cBot

## API Endpoint Format

### Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "eurusd_long_v05_20260420",
  "features": 46
}
```

### Prediction Endpoint
```bash
POST http://localhost:8000/predict
Content-Type: application/json

{
  "symbol": "EURUSD",
  "timestamp": "2024-01-15T10:00:00Z",
  "features": {
    "dist_sma_m5_50": 0.5,
    "dist_sma_m5_100": 0.3,
    "dist_sma_m5_200": 0.2,
    ... (all 46 features required)
  }
}
```

Expected response:
```json
{
  "symbol": "EURUSD",
  "timestamp": "2024-01-15T10:00:00Z",
  "model_version": "eurusd_long_v05_20260420",
  "p_win_long": 0.72,
  "decision": "BUY",
  "confidence": 0.92
}
```

- `p_win_long`: Float between 0.0 and 1.0 (probability of winning)
- `decision`: "BUY", "SELL", or "HOLD" (based on threshold)
- `confidence`: Float between 0.0 and 1.0 (proximity to decision boundary)

## Integration Requirements

### For cBot (JCAMP_FxScalper_ML)

1. Ensure JCAMP_Features.cs is up-to-date (v0.4 with 46 features)
2. Features must be computed in the exact order specified in FEATURE_NAMES
3. Feature values must be properly normalized (distances in ATR, etc.)
4. Send predictions to this FastAPI service for each closed M5 bar

### For DataCollector

1. Feature computation must match JCAMP_Features.cs exactly
2. Training data features must be in same order as FEATURE_NAMES
3. No missing or extra features in training data
4. Feature skew testing recommended before model deployment

## Model Threshold

- **Default Threshold**: 0.65 (p_win_long >= 0.65 → BUY signal)
- **Can be adjusted** in main.py based on backtesting results
- v05 model trained on v0.4 features with regime quality improvements

## Status

- **Config Status**: VERIFIED
- **Model Status**: READY
- **Feature Status**: VERIFIED (46/46 match JCAMP_Features.cs)
- **Deployment Status**: Ready for testing with cBot

---

*Last Updated: 2026-04-20*
*Config Version: v05*
*Model Version: eurusd_long_v05_holdout.joblib*
