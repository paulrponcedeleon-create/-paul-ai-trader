# Mobile Lite

`/api/mobile` is the server-rendered fallback dashboard for slow mobile sessions.

- Navigation uses real links with `?tab=`.
- No polling intervals are used.
- Each page performs only the requests needed for the selected section.
- Every request has a six-second timeout.
- Simulation and `LIVE_TRADING=false` protections remain unchanged.
