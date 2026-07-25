# Hotfix de estabilidad móvil

- Fuerza versiones nuevas de todos los recursos estáticos para evitar caché viejo de Safari.
- Agrega navegación de respaldo por click y touch antes de cargar los demás scripts.
- Limita a dos solicitudes simultáneas.
- Cancela consultas después de ocho segundos.
- Reutiliza respuestas GET por quince segundos para evitar consultas duplicadas.
- Carga módulos pesados únicamente cuando su pestaña está activa.
- Mantiene las órdenes manuales disponibles desde Mercados.
- No modifica usuarios, capital, posiciones ni órdenes.
- Mantiene LIVE_TRADING=false.
