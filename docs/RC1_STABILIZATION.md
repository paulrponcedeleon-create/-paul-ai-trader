# RC1 — Stabilization and Full Validation

## Alcance

RC1 se enfocó exclusivamente en estabilización, validación y corrección de errores reales de v0.1 Foundation y v0.2 Professional Strategy Platform. No se inició v0.3 ni se agregaron módulos prohibidos.

## Entorno probado

- Rama temporal: `work`, derivada funcionalmente de `v2-dashboard`.
- Python declarado: `3.12.13`.
- Red: instalación bloqueada por proxy/túnel con HTTP 403 hacia PyPI.

## Dependencias

`requirements.txt` contiene dependencias runtime: FastAPI, Uvicorn, HTTPX, Pydantic, Pydantic Settings, SQLAlchemy, Alembic, Psycopg y Pytest. Se agregó `requirements-dev.txt` con herramientas de validación: `pytest-cov`, `ruff` y `mypy`.

## Comandos ejecutados y resultados reales

- `python -m pip install -r requirements.txt -r requirements-dev.txt`: falló por bloqueo de red `Tunnel connection failed: 403 Forbidden`.
- `python -m compileall app tests migrations/versions`: pasó.
- `python -m pytest ...`: no ejecutó tests porque falta `fastapi` en el entorno.
- `python -m alembic ...`: no ejecutó migraciones porque falta `alembic` en el entorno.
- `ruff check app tests`: pasó.
- `ruff format --check app tests`: pasó después de formatear.
- `mypy app`: ejecutado; no se considera bloqueante porque faltan dependencias instaladas y no existe configuración mypy estable.

## Fallos encontrados

- `.python-version` apuntaba a `3.12.11`, versión no instalada en el entorno de validación.
- Faltaban dependencias dev declaradas para cobertura, lint y typing.
- `ruff check` detectó un import muerto y un nombre ambiguo.
- `ruff format --check` detectó archivos sin formato uniforme.
- Faltaba prueba RC1 end-to-end reproducible para CSV → provider → strategy → backtest → repository → reports.

## Correcciones realizadas

- Actualización de `.python-version` a `3.12.13`.
- Creación de `requirements-dev.txt`.
- Corrección de lint en `backtesting.py` e `indicators.py`.
- Formateo con Ruff de `app` y `tests`.
- Creación de prueba end-to-end RC1 para datasets temporales, estrategias, repositorio, API, OpenAPI, reportes y walk-forward.

## Cobertura obtenida

No se obtuvo cobertura real porque `pytest` no pudo cargar `tests/conftest.py` sin `fastapi` instalado.

## Validación de migraciones

La validación Alembic no pudo ejecutarse porque `alembic` no está instalado. La intención validada por inspección se mantiene: la migración crea `backtest_runs` y `backtest_trades`, y el downgrade elimina únicamente esas tablas nuevas.

## Validación de API

Se agregó prueba reproducible para `GET /health`, `GET /ready`, `GET /strategies`, `GET /strategies/{name}`, `POST /backtests`, `GET /backtests`, `GET /backtests/{id}`, `DELETE /backtests/{id}`, `POST /walk-forward` y `GET /openapi.json`. No pudo ejecutarse por falta de dependencias.

## Prueba end-to-end

La prueba `tests/test_rc1_integration.py` crea un dataset CSV temporal bajo `PAUL_DATA_DIR/historical/` y recorre: HistoricalDataProvider → StrategyFactory → Strategy → BacktestEngine → BrokerSimulator → BacktestMetrics → BacktestRepository → JSON/CSV/Markdown.

## Limitaciones pendientes

- Instalar dependencias en un entorno con acceso a PyPI o cache interno.
- Ejecutar suite completa, cobertura, Alembic y TestClient en CI real.
- Revisar mypy con dependencias instaladas y configuración dedicada si se decide hacerlo bloqueante.

## Criterios de aprobación RC1

RC1 no debe declararse aprobada hasta que las dependencias puedan instalarse y pasen: suite completa, cobertura, validación Alembic, validación FastAPI/OpenAPI y prueba end-to-end.

## RC1.1 Offline Validation

### Causa del bloqueo original

La suite no podía recolectarse sin dependencias de infraestructura porque `tests/conftest.py` importaba `fastapi.testclient`, `app.config`, `app.main` y `UnifiedMarketService` al cargar pytest. En este entorno faltan `fastapi`, `sqlalchemy`, `alembic`, `pydantic`, `pydantic-settings` y `httpx` porque PyPI está bloqueado por proxy HTTP 403.

### Refactor de conftest

Los imports de FastAPI, app config y aplicación se movieron dentro de las fixtures que realmente los necesitan. Las fixtures API usan `pytest.importorskip` local, por lo que la ausencia de FastAPI/Pydantic ya no bloquea la colección ni ejecución de pruebas puras.

### Clasificación de pruebas

- Grupo A — puras/unit: `tests/test_signals.py`, `tests/test_historical_data.py`, `tests/test_backtesting.py`, partes puras de `tests/test_strategy_platform.py`, partes puras de `tests/test_rc1_integration.py`, pruebas visuales/static sin infraestructura.
- Grupo B — database: `tests/test_backtest_persistence.py`, pruebas de repositorios/modelos, y las partes DB de `tests/test_rc1_integration.py`.
- Grupo C — api: `tests/test_ready.py`, `tests/test_api_security.py`, `tests/test_auth.py`, `tests/test_markets.py`, `tests/test_persistence.py`, y las partes FastAPI/OpenAPI de `tests/test_rc1_integration.py`.

### Comandos ejecutados

- `python -m pytest --collect-only`: recolectó 42 tests; 10 módulos/pruebas quedaron omitidos por dependencias ausentes.
- `python -m pytest -m unit`: 35 passed, 11 skipped, 6 deselected.
- `python -m pytest -m "not api and not database"`: 37 passed, 13 skipped, 2 deselected.
- `python -m pytest -m api`: 11 skipped, 41 deselected.
- `python -m pytest -m database`: 11 skipped, 41 deselected.
- `python -m pytest`: 37 passed, 15 skipped.
- `python -m pytest -m unit --cov=app --cov-report=term-missing`: no ejecutó cobertura porque `pytest-cov` no está instalado.
- `ruff check app tests`: passed.
- `ruff format --check app tests`: passed.
- `python -m compileall app tests migrations/versions`: passed.
- `git diff --check`: passed.

### Pruebas puras ejecutadas

Se ejecutaron señales, indicadores, estrategias, BacktestEngine sin persistencia, BrokerSimulator, métricas, HistoricalDataProvider CSV con settings local sin Pydantic, WalkForwardEngine sin persistencia y reportes JSON/CSV/Markdown.

### Resultados

- Passed puro/core: 37 usando `not api and not database`; 35 bajo marcador `unit` estricto.
- Failed puro/core: 0 después de correcciones.
- Skipped: dependencias ausentes o pruebas estáticas que no aplican en el entorno.

### Fallos reales encontrados

- `tests/conftest.py` acoplaba toda la colección a FastAPI/Pydantic.
- `app.services.historical_data` importaba `app.config` en import-time, acoplando pruebas CSV puras a Pydantic.
- `tests/test_backtesting.py` esperaba P&L incorrecto: no descontaba la comisión de entrada además de la comisión de salida.
- `tests/test_backtesting.py` conservaba una aserción obsoleta de Sprint 5 que prohibía endpoints de backtesting, aunque v0.2 ya los requiere.

### Correcciones

- Lazy imports en `tests/conftest.py`.
- Lazy import de settings en `LocalCsvHistoricalDataProvider` solo cuando no se inyecta configuración.
- Marcadores pytest `unit`, `integration`, `api`, `database` declarados en `pytest.ini`.
- `pytest.importorskip` aplicado solo en módulos/pruebas que requieren dependencias ausentes.
- E2E puro agregado/aislado para CSV → provider → estrategias → backtest → broker/métricas → reportes sin SQLAlchemy/FastAPI.
- Validación walk-forward pura rolling/anchored.
- Corrección del test de P&L para incluir entry fee y exit fee.
- Reemplazo de la aserción obsoleta sobre endpoints de backtesting por una comprobación de ausencia de endpoints live/Bitso live.

### Dependencias pendientes

`fastapi`, `sqlalchemy`, `alembic`, `pydantic`, `pydantic-settings`, `httpx` y `pytest-cov` siguen pendientes por bloqueo de instalación. API, DB, migraciones y cobertura no quedan aprobadas en este entorno.

### Auditoría de archivos formateados

Los archivos fuera del alcance estratégico modificados por RC1 fueron revisados con diff y diff ignorando espacios. Las diferencias observadas corresponden a formato Ruff y a cambios funcionales ya pertenecientes al alcance v0.1/v0.2, como readiness, configuración, backtesting y endpoints requeridos. No se identificó una modificación funcional no relacionada que requiriera revert.

### Modificaciones funcionales revertidas

No se revirtió ninguna modificación funcional: no se encontró un cambio funcional fuera de alcance que alterara mercados, portafolio, capital, Bitso, acciones, RFQ o persistencia simulada.

### Estado real de RC1

Clasificación RC1.1: **A. RC1 CORE VALIDATED**. El núcleo puro pasó offline. RC1 completa sigue pendiente hasta ejecutar API, persistencia, migraciones y cobertura en un entorno con dependencias instaladas.
