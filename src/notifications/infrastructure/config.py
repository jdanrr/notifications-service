"""Configuracion por variables de entorno. Nada hardcodeado ni en el repo."""

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"
    # Una o varias colas separadas por coma. Un solo worker las rota.
    sqs_queue_urls: Annotated[list[str], NoDecode]
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

    @field_validator("sqs_queue_urls", mode="before")
    @classmethod
    def split_queue_urls(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            value = [url.strip() for url in value.split(",")]
        urls = [url for url in value if url]
        if not urls:
            raise ValueError("SQS_QUEUE_URLS debe traer al menos una cola")
        return urls
