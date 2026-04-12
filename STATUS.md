# Status

**Current phase:** 1 — DataCollector
**Last completed:** Smoke test Jan 2023 — PASSED (6,242 rows, clean features, balanced labels)
**Next task:** Full historical run Jan 2023 → present

## Phase 1 checklist
- [x] DataCollector v0.1 written
- [x] v0.2 patches (bar indexing, HTF, chronological sort)
- [x] Smoke test Jan 2023 — verify CSV cleanliness (PASSED: no NaN/Inf, good label balance)
- [ ] Full historical run Jan 2023 → present (~75k rows expected)
- [ ] Move CSV to laptop for Phase 2

## Notes
- Broker: FP Markets cTrader Raw, $500 starting capital
- VPS: TBD (Vultr or IONOS London, Windows, ~$7-10/mo)
- Held-out test set: Oct 2025 – Mar 2026 — DO NOT touch until end of Phase 2