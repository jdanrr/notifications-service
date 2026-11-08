"""Esquemas de los eventos de Documents (source kenko.documents).

Solo declaran los campos que Notifications consume. El resto se ignora.
`DocumentsUpdated` no se declara: es auditoría y nadie lo consume.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from notifications.infrastructure.inbound.sqs.schemas.common import EventMetadata


class FileRef(BaseModel):
    """Referencia al PDF guardado en S3 (`file` del evento)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    bucket: str
    key: str
    file_name: str = Field(alias="fileName")

    @field_validator("bucket", "key", "file_name")
    @classmethod
    def referencia_no_vacia(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("referencia al archivo incompleta")
        return limpio


class CertificateGeneratedData(BaseModel):
    """data de CertificateGenerated: plano, sin anidamiento."""

    # extra="ignore": agregar campos al evento no rompe al consumidor.
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: EmailStr
    first_name: str = Field(alias="firstName")
    issued_at: str | None = Field(default=None, alias="issuedAt")
    file: FileRef

    @field_validator("first_name")
    @classmethod
    def first_name_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("firstName no puede estar vacio")
        return limpio


class CertificateGeneratedDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: CertificateGeneratedData


class AuthorizationStatusChangedData(BaseModel):
    """data de AuthorizationStatusChanged: plano, sin anidamiento."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: EmailStr
    first_name: str = Field(alias="firstName")
    authorization_type: str = Field(alias="authorizationType")
    status: str
    changed_at: str | None = Field(default=None, alias="changedAt")
    file: FileRef

    @field_validator("first_name", "authorization_type", "status")
    @classmethod
    def texto_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("campo de texto no puede estar vacio")
        return limpio


class AuthorizationStatusChangedDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: AuthorizationStatusChangedData


class MedicalHistoryPdfGeneratedData(BaseModel):
    """data de MedicalHistoryPdfGenerated: plano, sin anidamiento."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: EmailStr
    first_name: str = Field(alias="firstName")
    generated_at: str | None = Field(default=None, alias="generatedAt")
    file: FileRef

    @field_validator("first_name")
    @classmethod
    def first_name_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("firstName no puede estar vacio")
        return limpio


class MedicalHistoryPdfGeneratedDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: MedicalHistoryPdfGeneratedData
