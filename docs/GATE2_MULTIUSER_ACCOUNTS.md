# Gate 2 — Cuentas familiares multiusuario

## Cuenta independiente

Cada usuario tiene:

- nombre de usuario y contraseña con hash `scrypt`;
- $5,000 MXN simulados iniciales;
- posiciones, ejecuciones, capital y rendimiento separados por `user_id`;
- Runtime del bot independiente;
- interruptores para Bot automático, IA exploratoria y aprendizaje comunitario.

Un usuario no puede consultar, cerrar ni modificar posiciones de otra cuenta.

## Aprendizaje

El aprendizaje funciona en dos niveles:

1. **Individual:** cada usuario aprende de sus operaciones Manuales, del Bot y de IA, conservando el origen.
2. **Comunitario:** solo los usuarios que lo permiten aportan métricas cerradas agregadas. La respuesta no contiene nombres, usuarios, claves ni identificadores de operaciones.

Los portafolios nunca se mezclan.

## Registro

La cuenta principal continúa siendo `paul` y su contraseña inicial procede de `APP_PASSWORD`.

Las cuentas familiares se crean con:

- usuario;
- nombre visible;
- contraseña propia;
- código familiar configurado en `USER_REGISTRATION_CODE`.

En producción, si el código familiar conserva un valor débil o de ejemplo, el registro se desactiva automáticamente.

## Bitso opcional

Conectar Bitso no es obligatorio para usar la simulación o el bot.

Cuando un usuario lo conecta:

1. la app valida la clave mediante una consulta privada de saldo;
2. cifra API key y secret con `CREDENTIAL_ENCRYPTION_KEY`;
3. guarda solo el texto cifrado en PostgreSQL;
4. nunca vuelve a mostrar las claves completas;
5. utiliza esa conexión únicamente en endpoints de consulta de la cuenta.

Se recomienda crear una API Bitso sin retiros y de solo lectura. Esta fase no habilita órdenes reales y conserva `LIVE_TRADING=false`.

## Migración

La revisión `20260724_0012` crea `user_accounts` y agrega `user_id` a:

- `simulated_orders`;
- `simulated_order_events`.

Los registros históricos quedan asignados a la cuenta principal `owner`.

## Compatibilidad validada

Los contratos públicos existentes de `/health` y `/api/release` se conservan. Las rutas de Runtime mantienen compatibilidad con pruebas internas de una sola instancia, mientras que las sesiones reales utilizan motores aislados por usuario. La salida comunitaria contiene únicamente agregados anónimos.
