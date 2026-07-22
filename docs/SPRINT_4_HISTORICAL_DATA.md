# Sprint 4 — Historical data layer

Adds domain models and `LocalCsvHistoricalDataProvider` for CSV datasets under `PAUL_DATA_DIR/historical/` using logical dataset IDs such as `btc_mxn/1h/bitso-2026-07.csv`.

The provider rejects arbitrary paths, absolute paths, traversal, and access outside the historical root. CSV files must include `timestamp,open,high,low,close,volume` and are validated for UTC timestamps, numeric OHLCV values, strict chronological order, unique timestamps, and valid OHLC ranges.
