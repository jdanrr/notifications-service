"""Configuracion por variables de entorno. Nada hardcodeado ni en el repo."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"
    sqs_queue_url: str
    ses_sender: str

    # Marca / contenido de los correos
    app_name: str = "Kenko"
    kenko_portal_url: str
    kenko_support_email: str
    logo_url: str

    # Worker
    log_level: str = "INFO"
    receive_batch_size: int = 1
    receive_wait_time_seconds: int = 20

    # Persistencia opcional (si se omite: repositorio en memoria)
    database_url: str | None = None
