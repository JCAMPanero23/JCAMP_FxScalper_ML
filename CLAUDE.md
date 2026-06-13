# JCAMP FxScalper ML — Claude Code Notes

## After Every `git pull` — Copy cBot Files

The source of truth for cBot code is `cbot/JCAMP_FxScalper_ML/`. After pulling, copy the two `.cs` files to cTrader:

```powershell
Copy-Item "cbot\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML.cs" -Destination "C:\Users\Alienware\Documents\cAlgo\Sources\Robots\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML.cs" -Force
Copy-Item "cbot\JCAMP_FxScalper_ML\JCAMP_Features.cs" -Destination "C:\Users\Alienware\Documents\cAlgo\Sources\Robots\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML\JCAMP_Features.cs" -Force
```

### Source → Destination Mapping

| Source (this repo) | Destination (cTrader) |
|---|---|
| `cbot/JCAMP_FxScalper_ML/JCAMP_FxScalper_ML.cs` | `C:\Users\Alienware\Documents\cAlgo\Sources\Robots\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML.cs` |
| `cbot/JCAMP_FxScalper_ML/JCAMP_Features.cs` | `C:\Users\Alienware\Documents\cAlgo\Sources\Robots\JCAMP_FxScalper_ML\JCAMP_FxScalper_ML\JCAMP_Features.cs` |

After copying, rebuild in cTrader Automate.

## Project Structure

```
cbot/JCAMP_FxScalper_ML/   ← cBot source (source of truth)
predict_service/            ← FastAPI ML service (localhost:8000)
```

## ML Service

- Start: `cd predict_service && uvicorn main:app --port 8000`
- Health check: `curl http://localhost:8000/health`
