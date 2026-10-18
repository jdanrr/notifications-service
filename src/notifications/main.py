"""Punto de entrada del worker de Notifications.

Uso: uv run python -m notifications.main
"""

import signal
import sys

from pydantic import ValidationError

from notifications.domain.errors import NotificationError
from notifications.infrastructure.config import Settings
from notifications.infrastructure.container import build_worker
from notifications.infrastructure.logging import configure_logging


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as exc:
        print("Configuracion invalida (revisa las variables de entorno):", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 2

    configure_logging(settings.log_level)
    worker = build_worker(settings)

    # SIGTERM (docker stop / k8s) y Ctrl+C: terminar el ciclo actual y salir.
    signal.signal(signal.SIGTERM, lambda *_: worker.stop())
    signal.signal(signal.SIGINT, lambda *_: worker.stop())

    try:
        worker.run()
    except NotificationError as exc:
        print(f"Error de dominio no recuperable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
