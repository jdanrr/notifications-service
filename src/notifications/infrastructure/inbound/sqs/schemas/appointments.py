"""Esquemas de los eventos de Appointments (source kenko.appointments).

Solo declaran los campos que Notifications consume. El resto se ignora.
Los tres eventos comparten usuario y cita; reprogramada agrega la cita
anterior. Las fechas y horas viajan como texto y se muestran tal cual.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from notifications.infrastructure.inbound.sqs.schemas.common import EventMetadata


class Physician(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str | None = None


class MedicalCenter(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str | None = None
    location: str | None = None


class AppointmentInfo(BaseModel):
    """Bloque `appointment` (y `previousAppointment`) del evento."""

    # extra="ignore": agregar campos al evento no rompe al consumidor.
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    appointment_id: str = Field(alias="appointmentId")
    type: str
    date: str
    weekday: str | None = None
    start_time: str = Field(alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    physician: Physician | None = None
    medical_center: MedicalCenter | None = Field(default=None, alias="medicalCenter")


class AppointmentBaseData(BaseModel):
    """Campos comunes de `data` en los tres eventos."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    user_id: str = Field(alias="userId")
    email: EmailStr
    first_name: str = Field(alias="firstName")

    @field_validator("first_name")
    @classmethod
    def first_name_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("firstName no puede estar vacio")
        return limpio


class AppointmentScheduledData(AppointmentBaseData):
    appointment: AppointmentInfo


class AppointmentRescheduledData(AppointmentBaseData):
    appointment: AppointmentInfo
    previous_appointment: AppointmentInfo | None = Field(default=None, alias="previousAppointment")


class AppointmentCancelledData(AppointmentBaseData):
    appointment: AppointmentInfo


class AppointmentScheduledDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: AppointmentScheduledData


class AppointmentRescheduledDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: AppointmentRescheduledData


class AppointmentCancelledDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    metadata: EventMetadata
    data: AppointmentCancelledData
