# Security and Configuration Audit

## Safe defaults

`app/config.py` defaults `live_trading` to `False`, leaves Bitso credentials empty, defaults runtime broker to `paper`, and rejects non-paper runtime brokers when live trading is disabled. Session cookies are configured through settings and can resolve secure-cookie behavior by environment.

## Authentication/session model

- `SessionMiddleware` is configured in `create_app()` using `session_secret`, cookie name, max age, SameSite and secure-cookie settings.
- `app/api/dependencies.py` provides authentication checks.
- Legacy `/api/*` endpoints in `app/main.py` explicitly call `require_auth(request)`.
- Auth router exposes `/login` and `/logout`.

## Live-trading controls

- Live guard requires `LIVE_TRADING=true`, credentials, explicit arming and validation token before live orders.
- Tests assert simulation mode never calls Bitso order placement.
- Bitso live sell path is explicitly blocked in `BitsoClient.place_market_order()`.

## Environment/deploy

- `.env.example`, `render.yaml` and `render-v2.yaml` define expected configuration.
- `render-v2.yaml` keeps `LIVE_TRADING=false`.

## Findings

1. Default live-trading posture is safe.
2. Credentials are read from environment/settings and are not hardcoded.
3. Status/report endpoints need an explicit v3 policy: public health/readiness may remain open, but operational endpoints should consistently require auth.
4. CSRF protection for session-authenticated POST forms/API calls is not visible in the baseline.
5. Security headers beyond cache-control on selected endpoints are not centrally configured.
6. v3 should document route authentication classes and browser-session protections.

## Evidence commands

- `sed -n '1,180p' app/config.py app/main.py app/api/dependencies.py app/api/routes/auth.py`
- `sed -n '1,180p' app/live/guard.py app/live/validation.py app/brokers/bitso.py`
- `rg -n "LIVE_TRADING|live_trading|session_secret|SessionMiddleware|require_auth|csrf|Authorization|bitso_api" app tests docs render*.yaml .env.example -S`
