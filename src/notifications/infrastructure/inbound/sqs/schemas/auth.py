"""Esquemas de los eventos de Authentication (source kenko.auth).

Solo declaran los campos que Notifications consume. El resto se ignora.
"""

from urllib.parse import urlsplit

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from notifications.infrastructure.inbound.sqs.schemas.common import EventMetadata


class Person(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: str = Field(alias="firstName")


class Contact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str | None = None
    email_verified: bool = Field(default=False, alias="emailVerified")


class UserRegisteredData(BaseModel):
    person: Person
    contact: Contact


class UserRegisteredDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    metadata: EventMetadata
    data: UserRegisteredData


class PasswordResetRequestedData(BaseModel):
    """data de PasswordResetRequested: plano, sin anidamiento."""

    # extra="ignore": agregar campos al evento no rompe al consumidor.
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    user_id: str = Field(alias="userId")
    email: EmailStr
    first_name: str = Field(alias="firstName")
    reset_url: str = Field(alias="resetUrl")
    expires_at: AwareDatetime = Field(alias="expiresAt")

    @field_validator("first_name")
    @classmethod
    def first_name_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("firstName no puede estar vacio")
        return limpio

    @field_validator("reset_url")
    @classmethod
    def reset_url_debe_ser_http_s(cls, value: str) -> str:
        # urlsplit acepta localhost:8080 (necesario en dev).
        partes = urlsplit(value)
        if partes.scheme not in ("http", "https") or not partes.netloc:
            raise ValueError("resetUrl debe ser una URL http(s) valida")
        return value


class PasswordResetRequestedDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: PasswordResetRequestedData
