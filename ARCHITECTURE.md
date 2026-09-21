# Architecture

```text
Derived client landmark features
          ↓
 Flask assessment API ──→ active in-memory session
          ↓                         ↓
 Personalized baseline scorer ─→ review timeline/report
```

The MVP excludes raw video and facial identity storage by design. The scorer measures only changes from a calibration distribution and returns LOW_RISK, REVIEW, or HIGH_RISK review-signal bands. Context may lower a score; it cannot make a result more punitive.
