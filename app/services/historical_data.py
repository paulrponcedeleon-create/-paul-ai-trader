from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class HistoricalDataError(Exception):
    pass


class DatasetNotFoundError(HistoricalDataError):
    pass


class InvalidDatasetError(HistoricalDataError):
    pass


class UnsafeDatasetPathError(HistoricalDataError):
    pass


@dataclass(frozen=True)
class HistoricalCandle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class HistoricalDataset:
    book: str
    timeframe: str
    source: str
    start_at: datetime
    end_at: datetime
    candles: tuple[HistoricalCandle, ...]
    metadata: dict[str, object]


class HistoricalDataProvider(Protocol):
    def list_datasets(self) -> list[str]: ...
    def load_dataset(self, dataset_id: str) -> HistoricalDataset: ...
    def get_candles(
        self,
        dataset_id: str,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[HistoricalCandle]: ...
    def validate_dataset(self, dataset_id: str) -> None: ...


REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


class LocalCsvHistoricalDataProvider:
    def __init__(self, app_settings: Any | None = None) -> None:
        if app_settings is None:
            from app.config import settings as default_settings

            app_settings = default_settings
        self.settings = app_settings
        self.root = (self.settings.resolved_paul_data_dir / "historical").resolve()

    def list_datasets(self) -> list[str]:
        if not self.root.exists():
            return []
        if not self.root.is_dir():
            raise InvalidDatasetError("El directorio histórico no es válido.")
        datasets: list[str] = []
        for path in self.root.glob("*/*/*.csv"):
            datasets.append(path.relative_to(self.root).as_posix())
        return sorted(datasets)

    def _safe_path(self, dataset_id: str) -> Path:
        if not dataset_id or dataset_id.startswith("/") or "\\" in dataset_id:
            raise UnsafeDatasetPathError("Dataset histórico no permitido.")
        parts = Path(dataset_id).parts
        if len(parts) != 3 or any(part in {"", ".", ".."} for part in parts):
            raise UnsafeDatasetPathError("Dataset histórico no permitido.")
        if not parts[2].endswith(".csv"):
            raise UnsafeDatasetPathError("Dataset histórico no permitido.")
        candidate = (self.root / Path(*parts)).resolve()
        if self.root not in candidate.parents:
            raise UnsafeDatasetPathError("Dataset histórico no permitido.")
        return candidate

    def load_dataset(self, dataset_id: str) -> HistoricalDataset:
        path = self._safe_path(dataset_id)
        if not path.exists() or not path.is_file():
            raise DatasetNotFoundError("Dataset histórico no encontrado.")
        candles = self._read_csv(path)
        book, timeframe, filename = Path(dataset_id).parts
        return HistoricalDataset(
            book=book,
            timeframe=timeframe,
            source=filename.removesuffix(".csv"),
            start_at=candles[0].timestamp,
            end_at=candles[-1].timestamp,
            candles=tuple(candles),
            metadata={"dataset_id": dataset_id, "rows": len(candles)},
        )

    def get_candles(
        self,
        dataset_id: str,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[HistoricalCandle]:
        candles = list(self.load_dataset(dataset_id).candles)
        if start_at is not None:
            start_at = _to_utc(start_at)
            candles = [candle for candle in candles if candle.timestamp >= start_at]
        if end_at is not None:
            end_at = _to_utc(end_at)
            candles = [candle for candle in candles if candle.timestamp <= end_at]
        return candles

    def validate_dataset(self, dataset_id: str) -> None:
        self.load_dataset(dataset_id)

    def _read_csv(self, path: Path) -> list[HistoricalCandle]:
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None or set(REQUIRED_COLUMNS) - set(
                    reader.fieldnames
                ):
                    raise InvalidDatasetError("CSV histórico con columnas incompletas.")
                candles = [_parse_row(row) for row in reader]
        except UnicodeDecodeError as exc:
            raise InvalidDatasetError("CSV histórico inválido.") from exc
        if not candles:
            raise InvalidDatasetError("Dataset histórico vacío.")
        previous: datetime | None = None
        seen: set[datetime] = set()
        for candle in candles:
            if candle.timestamp in seen:
                raise InvalidDatasetError("Timestamps duplicados.")
            if previous is not None and candle.timestamp <= previous:
                raise InvalidDatasetError(
                    "Timestamps fuera de orden cronológico estricto."
                )
            seen.add(candle.timestamp)
            previous = candle.timestamp
            if candle.high < max(candle.open, candle.close, candle.low):
                raise InvalidDatasetError("Precio high inválido.")
            if candle.low > min(candle.open, candle.close, candle.high):
                raise InvalidDatasetError("Precio low inválido.")
            if candle.volume < 0:
                raise InvalidDatasetError("Volumen inválido.")
        return candles


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_timestamp(raw: str) -> datetime:
    raw = raw.strip()
    try:
        if raw.isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        return _to_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError as exc:
        raise InvalidDatasetError("Timestamp histórico inválido.") from exc


def _parse_float(raw: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidDatasetError("Valor numérico histórico inválido.") from exc
    return value


def _parse_row(row: dict[str, str]) -> HistoricalCandle:
    return HistoricalCandle(
        timestamp=_parse_timestamp(row["timestamp"]),
        open=_parse_float(row["open"]),
        high=_parse_float(row["high"]),
        low=_parse_float(row["low"]),
        close=_parse_float(row["close"]),
        volume=_parse_float(row["volume"]),
    )
