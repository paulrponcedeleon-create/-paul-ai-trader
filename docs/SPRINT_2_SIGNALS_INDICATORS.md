# Sprint 2 — Signals and indicators

The existing momentum rule was extracted into `app.services.signals`, with reusable indicator helpers in `app.services.indicators`. `app.services.strategy` remains as a compatibility layer that reexports `Action`, `Signal`, and `momentum_signal`.

The functional thresholds and reasons of `momentum_signal` are preserved.
