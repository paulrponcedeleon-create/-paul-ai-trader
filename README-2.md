# Paul AI Trader v0.2

MVP web para Bitso con dashboard móvil, análisis básico, simulación y motor de riesgo.

## Estado actual
- Consulta ticker y libros públicos.
- Consulta balance, órdenes abiertas, trades y comisiones con API privada.
- Firma HMAC-SHA256 compatible con Bitso.
- Simulación activada por defecto.
- Aprobación manual obligatoria.
- Límites por orden, pérdida diaria y órdenes abiertas.
- Dashboard adaptable a iPhone.

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```
Abre `http://127.0.0.1:8000`.

## Crear las claves en Bitso
1. Activa 2FA.
2. En Perfil > API, crea una clave.
3. Para la primera conexión activa únicamente **View balances**.
4. No actives **Make withdrawals**.
5. Guarda API Key y Secret; Bitso muestra el Secret una sola vez.
6. Colócalas en `.env`.

## Prueba segura recomendada
- Mantén `BITSO_BASE_URL=https://stage.bitso.com/api/v3`.
- Mantén `LIVE_TRADING=false`.
- Prueba saldo y análisis.
- Después prueba órdenes simuladas.
- Solo al validar todo, crea una API de producción con `View balances` y `Place orders`.

## Producción
Cambiar a:
```env
BITSO_BASE_URL=https://bitso.com/api/v3
LIVE_TRADING=true
```
No lo hagas antes de revisar logs, límites y pruebas.

## Importante
La estrategia incluida es deliberadamente simple; sirve para probar infraestructura, no para prometer ganancias. La siguiente versión debe añadir velas históricas, backtesting, persistencia, cálculo real de P&L, trailing stops y aprobación desde celular.
