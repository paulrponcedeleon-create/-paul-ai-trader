from __future__ import annotations

import os
import subprocess
import sys


def run_migrations() -> bool:
    print("[render-rescue] Running database migrations before web startup...", flush=True)
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        print(
            "[render-rescue] Migration exceeded 90 seconds. Starting the web in rescue mode.",
            flush=True,
        )
        return False
    except subprocess.CalledProcessError as exc:
        print(
            f"[render-rescue] Migration failed with exit code {exc.returncode}. "
            "Starting the web in rescue mode so /health and the login page remain available.",
            flush=True,
        )
        return False
    print("[render-rescue] Database migrations completed.", flush=True)
    return True


def main() -> None:
    environment = os.environ.copy()
    migration_ok = run_migrations()
    environment["RENDER_MIGRATION_STATUS"] = "ok" if migration_ok else "failed"
    if not migration_ok:
        environment["RUNTIME_AUTO_START"] = "false"

    port = environment.get("PORT", "10000")
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]
    print(
        f"[render-rescue] Starting web server on port {port}; "
        f"migration_status={environment['RENDER_MIGRATION_STATUS']}; "
        f"runtime_auto_start={environment.get('RUNTIME_AUTO_START', 'true')}",
        flush=True,
    )
    os.execvpe(command[0], command, environment)


if __name__ == "__main__":
    main()
