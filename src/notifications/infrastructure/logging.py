"""Configuracion de logging.

Regla: nunca registrar datos personales (email completo, documento, direccion).
Solo se registran identificadores del evento (event_id, correlation_id) y
el resultado del procesamiento.
"""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT, stream=sys.stdout)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
