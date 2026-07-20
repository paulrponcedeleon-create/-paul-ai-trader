# Paul AI Trader v1

Aplicación web privada, optimizada para celular, que consulta mercados de Bitso, muestra señales transparentes y permite simulación controlada.

## Estado de seguridad

- `LIVE_TRADING=false` por defecto.
- No habilita retiros.
- No ejecuta operaciones reales salvo que se configure explícitamente.
- Toda orden pasa por límites deterministas de riesgo.
- Ninguna señal garantiza ganancias.

## Desplegar en Render

Render detecta `render.yaml`. También puedes configurar manualmente:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

Variables privadas recomendadas:

- `APP_PASSWORD`
- `SESSION_SECRET`
- `BITSO_API_KEY`
- `BITSO_API_SECRET`

Mantén `LIVE_TRADING=false` durante pruebas.

## Ejecutar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.
