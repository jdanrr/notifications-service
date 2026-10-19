"""Ensamblaje de adaptadores y caso de uso (sin framework de DI).

Si no hay DATABASE_URL se usa un repositorio en memoria: sirve para
desarrollo y pruebas, pero la idempotencia no sobrevive a un reinicio.
"""

import logging

import boto3

from notifications.application.models import WelcomeBrandConfig
from notifications.application.use_cases.auth.send_welcome_email import (
    SendWelcomeEmailUseCase,
)
from notifications.domain.notification_log import NotificationLog, NotificationStatus
from notifications.infrastructure.config import Settings
from notifications.infrastructure.inbound.sqs.mappers import envelope_to_welcome_command
from notifications.infrastructure.inbound.sqs.poller import SqsPoller
from notifications.infrastructure.inbound.sqs.router import EventRouter
from notifications.infrastructure.inbound.sqs.worker import AuthEventsWorker
from notifications.infrastructure.outbound.email.ses_email_sender import SesEmailSender
from notifications.infrastructure.outbound.rendering.jinja_renderer import JinjaTemplateRenderer

logger = logging.getLogger(__name__)


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


def build_worker(settings: Settings) -> AuthEventsWorker:
    session = boto3.Session(region_name=settings.aws_region)

    renderer = JinjaTemplateRenderer()
    sender = SesEmailSender(client=session.client("ses"), sender=settings.ses_sender)
    repository = build_repository(settings)

    use_case = SendWelcomeEmailUseCase(
        renderer=renderer,
        sender=sender,
        repository=repository,
        brand=WelcomeBrandConfig(
            app_name=settings.app_name,
            portal_url=settings.kenko_portal_url,
            support_email=settings.kenko_support_email,
            logo_url=settings.logo_url,
        ),
    )

    router = build_router(use_case)

    poller = SqsPoller(
        client=session.client("sqs"),
        queue_url=settings.sqs_queue_url,
        batch_size=settings.receive_batch_size,
        wait_time_seconds=settings.receive_wait_time_seconds,
    )

    return AuthEventsWorker(poller=poller, router=router, repository=repository)


def build_router(use_case: SendWelcomeEmailUseCase) -> EventRouter:
    """Registra los eventos de Authentication que Notifications consume.

    Punto unico de declaracion: el test de sincronizacion compara las claves
    de este router contra `auth_detail_types` en terraform/envs/*.tfvars, asi
    que un evento enrutado sin handler (o un handler sin enrutamiento) falla
    el build en vez de descartar eventos en silencio.

    Para agregar un evento nuevo: registrarlo aqui Y en el .tfvars del ambiente.
    """
    router = EventRouter()
    router.register("kenko.auth", "UserRegistered", _handler(use_case))
    return router


def _handler(use_case: SendWelcomeEmailUseCase):
    def handle(envelope) -> str:
        return use_case.execute(envelope_to_welcome_command(envelope))

    return handle
