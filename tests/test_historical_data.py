from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

from app.services.historical_data import (
    DatasetNotFoundError,
    InvalidDatasetError,
    LocalCsvHistoricalDataProvider,
    UnsafeDatasetPathError,
)


class LocalSettings:
    def __init__(self, data_dir):
        self.resolved_paul_data_dir = data_dir.resolve()


def settings_for(tmp_path):
    return LocalSettings(tmp_path)


def write_dataset(tmp_path, dataset_id, rows):
    path = tmp_path / "historical" / dataset_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("timestamp,open,high,low,close,volume\n" + "\n".join(rows) + "\n")
    return path


def test_loads_valid_csv_and_normalizes_utc(tmp_path):
    write_dataset(
        tmp_path,
        "btc_mxn/1h/bitso-2026-07.csv",
        [
            "2026-07-01T00:00:00Z,10,12,9,11,1",
            "1782867600,11,13,10,12,2",
        ],
    )
    provider = LocalCsvHistoricalDataProvider(settings_for(tmp_path))
    dataset = provider.load_dataset("btc_mxn/1h/bitso-2026-07.csv")
    assert dataset.book == "btc_mxn"
    assert dataset.timeframe == "1h"
    assert dataset.candles[0].timestamp.tzinfo == timezone.utc
    assert provider.list_datasets() == ["btc_mxn/1h/bitso-2026-07.csv"]
    assert (
        len(
            provider.get_candles(
                "btc_mxn/1h/bitso-2026-07.csv",
                start_at=datetime(2026, 7, 1, 0, 30, tzinfo=timezone.utc),
            )
        )
        == 1
    )


@pytest.mark.parametrize(
    "dataset_id",
    ["../secret.csv", "/tmp/secret.csv", "btc_mxn/../../x.csv", "btc_mxn/1h/file.txt"],
)
def test_rejects_unsafe_dataset_paths(tmp_path, dataset_id):
    provider = LocalCsvHistoricalDataProvider(settings_for(tmp_path))
    with pytest.raises(UnsafeDatasetPathError):
        provider.load_dataset(dataset_id)


def test_missing_dataset_raises_safe_error(tmp_path):
    provider = LocalCsvHistoricalDataProvider(settings_for(tmp_path))
    with pytest.raises(DatasetNotFoundError):
        provider.load_dataset("btc_mxn/1h/missing.csv")


@pytest.mark.parametrize(
    "row",
    [
        "2026-07-01T00:00:00Z,10,9,8,11,1",
        "2026-07-01T00:00:00Z,10,12,11,9,1",
        "2026-07-01T00:00:00Z,10,12,9,11,-1",
    ],
)
def test_invalid_ohlcv_values_raise_domain_error(tmp_path, row):
    write_dataset(tmp_path, "btc_mxn/1h/bad.csv", [row])
    provider = LocalCsvHistoricalDataProvider(settings_for(tmp_path))
    with pytest.raises(InvalidDatasetError):
        provider.load_dataset("btc_mxn/1h/bad.csv")


def test_rejects_duplicate_or_unordered_timestamps(tmp_path):
    write_dataset(
        tmp_path,
        "btc_mxn/1h/bad.csv",
        [
            "2026-07-01T01:00:00Z,10,12,9,11,1",
            "2026-07-01T00:00:00Z,11,13,10,12,1",
        ],
    )
    provider = LocalCsvHistoricalDataProvider(settings_for(tmp_path))
    with pytest.raises(InvalidDatasetError):
        provider.validate_dataset("btc_mxn/1h/bad.csv")
