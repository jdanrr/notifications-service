"""Ensamblaje de adaptadores y caso de uso (sin framework de DI).

Si no hay DATABASE_URL se usa un repositorio en memoria: sirve para
desarrollo y pruebas, pero la idempotencia no sobrevive a un reinicio.
"""

import logging
from pathlib import Path

import boto3

from notifications.application.dispatcher import Dispatcher
from notifications.application.models import WelcomeBrandConfig
from notifications.application.use_cases.appointments.send_appointment_cancelled_email import (
    TEMPLATE_NAME as APPOINTMENT_CANCELLED_TEMPLATE,
)
from notifications.application.use_cases.appointments.send_appointment_cancelled_email import (
    SendAppointmentCancelledEmailUseCase,
)
from notifications.application.use_cases.appointments.send_appointment_rescheduled_email import (
    TEMPLATE_NAME as APPOINTMENT_RESCHEDULED_TEMPLATE,
)
from notifications.application.use_cases.appointments.send_appointment_rescheduled_email import (
    SendAppointmentRescheduledEmailUseCase,
)
from notifications.application.use_cases.appointments.send_appointment_scheduled_email import (
    TEMPLATE_NAME as APPOINTMENT_SCHEDULED_TEMPLATE,
)
from notifications.application.use_cases.appointments.send_appointment_scheduled_email import (
    SendAppointmentScheduledEmailUseCase,
)
from notifications.application.use_cases.auth.send_password_reset_email import (
    TEMPLATE_NAME as PASSWORD_RESET_TEMPLATE,
)
from notifications.application.use_cases.auth.send_password_reset_email import (
    SendPasswordResetEmailUseCase,
)
from notifications.application.use_cases.auth.send_welcome_email import (
    TEMPLATE_NAME as WELCOME_TEMPLATE,
)
from notifications.application.use_cases.auth.send_welcome_email import (
    SendWelcomeEmailUseCase,
)
from notifications.domain.notification_log import NotificationLog, NotificationStatus
from notifications.infrastructure.config import Settings
from notifications.infrastructure.inbound.sqs.mappers import (
    envelope_to_appointment_cancelled_command,
    envelope_to_appointment_rescheduled_command,
    envelope_to_appointment_scheduled_command,
    envelope_to_password_reset_command,
    envelope_to_welcome_command,
)
from notifications.infrastructure.inbound.sqs.poller import SqsPoller
from notifications.infrastructure.inbound.sqs.router import EventRouter
from notifications.infrastructure.inbound.sqs.worker import EventsWorker
from notifications.infrastructure.outbound.email.ses_email_sender import SesEmailSender
from notifications.infrastructure.outbound.rendering.jinja_renderer import JinjaTemplateRenderer

logger = logging.getLogger(__name__)

# Logo que el sender embebe en cada correo (CID). Vive en el repo para no
# depender de un hosting externo.
LOGO_PATH = Path(__file__).resolve().parent / "templates" / "static" / "img" / "kenko_limpio.png"


def load_logo() -> bytes:
    """Lee el logo embebido. Falla en seco al arrancar si falta: sin el
    archivo todos los correos saldrian con la imagen rota."""
    try:
        return LOGO_PATH.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"no se pudo leer el logo embebido {LOGO_PATH}") from exc


class InMemoryNotificationLogRepository:
    """Respaldo sin base de datos. Solo desarrollo/pruebas."""

    def __init__(self) -> None:
        self._sent: set[str] = set()
        self.records: list[NotificationLog] = []

    def has_been_sent(self, event_id: str) -> bool:
        return event_id in self._sent

    def record(self, log: NotificationLog) -> None:
        self.records.append(log)
        if log.status == NotificationStatus.SENT:
            self._sent.add(log.event_id)


def build_repository(settings: Settings):
    if not settings.database_url:
        logger.warning(
            "DATABASE_URL no configurada: se usa repositorio en memoria "
            "(la idempotencia no sobrevive reinicios)"
        )
        return InMemoryNotificationLogRepository()

    from notifications.infrastructure.outbound.persistence.database import (
        Base,
        build_engine,
        build_session_factory,
    )
    from notifications.infrastructure.outbound.persistence.sql_notification_log_repository import (
        SqlNotificationLogRepository,
    )

    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return SqlNotificationLogRepository(build_session_factory(engine))


def build_worker(settings: Settings) -> EventsWorker:
    session = boto3.Session(region_name=settings.aws_region)

    renderer = JinjaTemplateRenderer()
    sender = SesEmailSender(
        client=session.client("ses"), sender=settings.ses_sender, logo=load_logo()
    )
    repository = build_repository(settings)

    brand = WelcomeBrandConfig(
        app_name=settings.app_name,
        portal_url=settings.kenko_portal_url,
        support_email=settings.kenko_support_email,
        logo_url=settings.logo_url,
    )

    welcome_use_case = SendWelcomeEmailUseCase(
        renderer=renderer,
        sender=sender,
        repository=repository,
        brand=brand,
    )
    password_reset_use_case = SendPasswordResetEmailUseCase(
        renderer=renderer,
        sender=sender,
        repository=repository,
        brand=brand,
    )
    appointment_scheduled_use_case = SendAppointmentScheduledEmailUseCase(
        renderer=renderer,
        sender=sender,
        repository=repository,
        brand=brand,
    )
    appointment_rescheduled_use_case = SendAppointmentRescheduledEmailUseCase(
        renderer=renderer,
        sender=sender,
        repository=repository,
        brand=brand,
    )
    appointment_cancelled_use_case = SendAppointmentCancelledEmailUseCase(
        renderer=renderer,
        sender=sender,
        repository=repository,
        brand=brand,
    )

    router = build_router(
        welcome_use_case,
        password_reset_use_case,
        appointment_scheduled_use_case,
        appointment_rescheduled_use_case,
        appointment_cancelled_use_case,
    )
    dispatcher = Dispatcher(repository)

    poller = SqsPoller(
        client=session.client("sqs"),
        queue_urls=settings.sqs_queue_urls,
        batch_size=settings.receive_batch_size,
        wait_time_seconds=settings.receive_wait_time_seconds,
    )

    return EventsWorker(poller=poller, router=router, dispatcher=dispatcher)


AUTH_SOURCE = "kenko.auth"
APPOINTMENTS_SOURCE = "kenko.appointments"


def build_router(
    welcome_use_case: SendWelcomeEmailUseCase,
    password_reset_use_case: SendPasswordResetEmailUseCase,
    appointment_scheduled_use_case: SendAppointmentScheduledEmailUseCase,
    appointment_rescheduled_use_case: SendAppointmentRescheduledEmailUseCase,
    appointment_cancelled_use_case: SendAppointmentCancelledEmailUseCase,
) -> EventRouter:
    """Registra los eventos de Authentication y Appointments que consume Notifications.

    Punto unico de declaracion: el test de sincronizacion compara las claves
    de este router contra `auth_detail_types` y `appointments_detail_types`
    en terraform/envs/*.tfvars, asi que un evento enrutado sin handler (o un
    handler sin enrutamiento) falla el build en vez de descartar eventos en
    silencio.

    Para agregar un evento nuevo: registrarlo aqui Y en el .tfvars del ambiente.
    """
    router = EventRouter()
    router.register(
        AUTH_SOURCE,
        "UserRegistered",
        _handler(welcome_use_case, envelope_to_welcome_command),
        template_name=WELCOME_TEMPLATE,
    )
    router.register(
        AUTH_SOURCE,
        "PasswordResetRequested",
        _handler(password_reset_use_case, envelope_to_password_reset_command),
        template_name=PASSWORD_RESET_TEMPLATE,
    )
    router.register(
        APPOINTMENTS_SOURCE,
        "AppointmentScheduled",
        _handler(appointment_scheduled_use_case, envelope_to_appointment_scheduled_command),
        template_name=APPOINTMENT_SCHEDULED_TEMPLATE,
    )
    router.register(
        APPOINTMENTS_SOURCE,
        "AppointmentRescheduled",
        _handler(appointment_rescheduled_use_case, envelope_to_appointment_rescheduled_command),
        template_name=APPOINTMENT_RESCHEDULED_TEMPLATE,
    )
    router.register(
        APPOINTMENTS_SOURCE,
        "AppointmentCancelled",
        _handler(appointment_cancelled_use_case, envelope_to_appointment_cancelled_command),
        template_name=APPOINTMENT_CANCELLED_TEMPLATE,
    )
    return router


def _handler(use_case, mapper):
    def handle(envelope) -> str:
        return use_case.execute(mapper(envelope))

    return handle
