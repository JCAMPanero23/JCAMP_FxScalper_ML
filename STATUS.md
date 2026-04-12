# Status

**Current phase:** 1 — DataCollector ✓ COMPLETE
**Last completed:** Full historical run verified — 243,216 rows, all checks PASSED
**Next phase:** Phase 2 — Python ML pipeline

## Phase 1 checklist ✓ COMPLETE
- [x] DataCollector v0.1 written
- [x] v0.2 patches (bar indexing, HTF, chronological sort)
- [x] Smoke test Jan 2023 — PASSED (6,242 rows)
- [x] Full historical run Jan 2023 → Apr 2026 — PASSED (243,216 rows, 3.25 years)
- [x] CSV verification — no NaN/Inf, balanced labels, sane feature distributions
- [ ] Move CSV to laptop for Phase 2

## Phase 1 Results
- **Dataset:** 243,216 M5 bars (EURUSD)
- **Date range:** Jan 2, 2023 → Apr 10, 2026 (1,194 days)
- **File size:** 96 MB
- **Features:** 39 features + 4 labels
- **Label balance:** ~30% win, ~64% loss, ~5% timeout (both directions)
- **Data splits:**
  - Train/CV: 204,392 rows (84.0%) - Jan 2023 to Sep 2025
  - Held-out test: 36,845 rows (15.1%) - Oct 2025 to Mar 2026 **[TOUCH ONCE ONLY]**
  - Live forward: 1,979 rows (0.8%) - Apr 2026 onward

## Notes
- Broker: FP Markets cTrader Raw, $500 starting capital
- VPS: TBD (Vultr or IONOS London, Windows, ~$7-10/mo)
- **CRITICAL:** Held-out test set (Oct 2025 – Mar 2026) must NOT be used for hyperparameter tuning