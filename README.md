# Notifications

Microservicio de **notificaciones** de Kenko Salud (portal tipo EPS, Colombia).

Es **solo consumidor**: no publica eventos. Lee mensajes de colas SQS que
alimenta EventBridge y envía correos con AWS SES. Usa arquitectura hexagonal.

> **Estado:** dos flujos de Authentication funcionando
> (`UserRegistered` → bienvenida, `PasswordResetRequested` → restablecer
> contraseña). **81 tests, sin llamadas a AWS.**
> `Dockerfile` y `docker-compose.yml` están **vacíos** (pendientes) y el
> endpoint `/health` de FastAPI **aún no existe**.

---

## Arquitectura

```
EventBridge (kenko-dev-bus)
   └─ regla kenko-dev-auth-to-notifications
        └─ SQS kenko-dev-notifications-authentication
             └─ worker (este servicio)
                  └─ SES → correo
```

**El bus es único por ambiente y ya existe**: se referencia con un `data`
source, nunca se crea. **Las colas, las DLQ y las reglas de Notifications las
creamos nosotros** con Terraform (ver `terraform/`).

### Capas (hexagonal)

```
domain/            Núcleo: errores y NotificationLog. Sin dependencias externas.
application/       Casos de uso, puertos (interfaces), dispatcher. Sin boto3.
  ports/             EmailSender · TemplateRenderer · NotificationLogRepository
  use_cases/auth/    send_welcome_email · send_password_reset_email
  use_cases/appointments/ send_appointment_scheduled_email · send_appointment_rescheduled_email · send_appointment_cancelled_email
  dispatcher.py      idempotencia + clasificación de errores
infrastructure/    Adaptadores.
  inbound/sqs/       poller (SQS) · worker (loop) · envelope · router · mappers · schemas
  outbound/          email/ses_email_sender · rendering/jinja_renderer · persistence/*
  templates/         plantillas Jinja2 (.j2) y assets
  config.py          settings por variables de entorno
  container.py       wiring (sin framework de DI)
main.py            Punto de entrada: arranca el worker
```

**Regla de dependencias:** `domain` ← `application` ← `infrastructure`.
El caso de uso no importa `boto3`, Pydantic ni Jinja: habla con los puertos, y
los adaptadores concretos los inyecta `container.py`.

---

## Cómo funciona el worker

`main.py` → `Settings()` (lee `.env`) → `build_worker()` → registra señales →
`worker.run()`, un loop:

1. **`poller.receive()`** — `sqs receive_message` con **long polling**
   (`WaitTimeSeconds=20`, lote de 1). Si la cola está vacía espera hasta 20 s
   en lugar de volver de inmediato: menos llamadas y menor costo.
2. Si no llegó nada → vuelve a 1.
3. Si llegó mensaje → **`_process(message)`**: parsea el sobre, resuelve la
   ruta, y delega la decisión en `Dispatcher`.

### Qué decide el Dispatcher

El worker solo hace I/O de cola. La idempotencia y la clasificación viven en
`application/dispatcher.py`, donde se prueban con fakes y sin SQS real.

| Resultado | ¿Borra el mensaje? | ¿Registra? |
|---|---|---|
| Envío exitoso (`sent`) | ✅ | ✅ `status=sent` (lo registra el caso de uso) |
| Duplicado (`event_id` ya enviado) | ✅ | no hace falta |
| **Fallo permanente** | ✅ **solo si el registro funcionó** | ✅ `status=failed` + `failure_reason` |
| **Fallo transitorio** | ❌ **no** | ❌ |
| Error inesperado | ❌ **no** | ❌ |

No borrar en el caso transitorio activa los reintentos de SQS: el mensaje
reaparece tras el *visibility timeout* (60 s), SQS lo entrega de nuevo y, al
superar `maxReceiveCount=3`, va a la **DLQ** en lugar de perderse.

Si falla el **borrado** o la **consulta de idempotencia** (BD caída), tampoco
se borra: es más seguro reintentar que arriesgar un doble envío.

### `template_name` vive en la ruta, no en el worker

```python
router.register(
    "kenko.auth",
    "PasswordResetRequested",
    _handler(password_reset_use_case, envelope_to_password_reset_command),
    template_name=PASSWORD_RESET_TEMPLATE,   # "password_reset"
)
```

| Situación | `template` registrado en el fallo |
|---|---|
| Ruta encontrada | el de esa ruta (`welcome`, `password_reset`, …) |
| Sin ruta registrada | `unknown` |

Así, cuando convivan varios eventos en la misma cola, cada fallo queda con
**su** plantilla y la traza no miente.

### Apagado ordenado

`main.py` engancha `SIGTERM` y `SIGINT` (Ctrl+C) a `worker.stop()`, que solo
marca un flag `Event`. El loop lo respeta al terminar el `receive()` actual y
antes de procesar cada mensaje, así que **nunca se corta un envío a medias**.
Sale con código 0 e imprime `worker detenido`.

---

## Puesta en marcha

### 1. Dependencias

```bash
uv sync --extra dev
```

Crea `.venv` con `boto3`, `jinja2`, `pydantic-settings`, `sqlalchemy`,
`psycopg2-binary`, `email-validator` + `pytest` y `ruff`.

### 2. Variables de entorno

```bash
cp .env.example .env
```

`.env` está en `.gitignore` y **nunca se commitea**. Las credenciales de AWS
**no van aquí**: se leen de `~/.aws`.

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `SQS_QUEUE_URL` | ✅ | — | Cola a consumir |
| `SES_SENDER` | ✅ | — | Remitente verificado en SES |
| `KENKO_PORTAL_URL` | ✅ | — | Enlace "Ingresar al portal" en el pie |
| `KENKO_SUPPORT_EMAIL` | ✅ | — | Soporte en el pie del correo |
| `LOGO_URL` | ✅ | — | URL pública del logo (**PNG**; los clientes de correo no soportan SVG) |
| `AWS_REGION` | | `us-east-1` | Región |
| `APP_NAME` | | `Kenko` | Marca en los textos |
| `LOG_LEVEL` | | `INFO` | Nivel de logging |
| `RECEIVE_BATCH_SIZE` | | `1` | Mensajes por `receive` (1–5) |
| `RECEIVE_WAIT_TIME_SECONDS` | | `20` | Long polling (0–20) |
| `DATABASE_URL` | | *(vacío)* | Si se omite usa repositorio en memoria |

Si falta una requerida, el proceso **no arranca**: imprime
`Configuracion invalida` y sale con código `2`.

### 3. Levantar el worker

```bash
cd "/Users/joserodriguez/Documents/UCatólica/5to Semestre/Prod. de Software/notifications-service"
PYTHONPATH=src .venv/bin/python -m notifications.main
```

> **Por qué `PYTHONPATH=src`:** el `.pth` que genera `uv sync` tiene el flag
> `hidden` de macOS (`UF_HIDDEN`) y **CPython 3.13 salta los `.pth` ocultos**,
> por lo que `import notifications` falla. pytest usa el mismo mecanismo
> (`pythonpath = ["src"]` en `pyproject.toml`). Si regeneras el venv y el flag
> no reaparece, podrás usar `uv run python -m notifications.main`.

En background:

```bash
PYTHONPATH=src .venv/bin/python -m notifications.main > /tmp/kenko_worker.log 2>&1 &
echo $! > /tmp/kenko_worker.pid
tail -f /tmp/kenko_worker.log
```

Al arrancar verás el warning de `DATABASE_URL` (esperado sin BD) y
`worker iniciado`.

### 3b. Segunda instancia (cola de Appointments)

Cada worker lee **una sola cola** (`SQS_QUEUE_URL`). Para consumir las dos
colas se levantan dos procesos con el mismo código; las variables reales
tienen prioridad sobre el `.env`, así que basta con sobrescribir la URL:

```bash
SQS_QUEUE_URL="$(cd terraform && terraform output -raw appointments_queue_url)" \
  PYTHONPATH=src .venv/bin/python -m notifications.main > /tmp/kenko_worker_appointments.log 2>&1 &
echo $! > /tmp/kenko_worker_appointments.pid
tail -f /tmp/kenko_worker_appointments.log
```

La primera instancia sigue usando el `SQS_QUEUE_URL` del `.env` (cola de
Authentication). Ambas comparten el mismo router: cada una ignora los
eventos que no son de su cola simplemente porque nunca los recibe.

### 4. Detenerlo

**Ctrl+C**, o si está en background:

```bash
kill -TERM "$(cat /tmp/kenko_worker.pid)"
```

---

## Probar de punta a punta

Con el worker corriendo, en **otra terminal**:

```bash
aws events put-events --entries '[{
  "EventBusName": "kenko-dev-bus",
  "Source": "kenko.auth",
  "DetailType": "PasswordResetRequested",
  "Detail": "{\"metadata\":{\"eventId\":\"pr-0001\",\"eventVersion\":\"1\",\"occurredAt\":\"2026-10-19T02:00:00.000Z\",\"correlationId\":\"pr-corr-0001\"},\"data\":{\"userId\":\"u-1\",\"email\":\"tu-email-verificado@example.com\",\"firstName\":\"Prueba\",\"resetUrl\":\"http://localhost:8080/reset#token=EJEMPLO\",\"expiresAt\":\"2030-10-19T03:00:00.000Z\"}}"
}]'
```

**`expiresAt` debe ser futuro**: si ya venció, el caso de uso lo descarta como
`expired` y no envía nada (por diseño). Usa un email registrado en SES (la
cuenta está en sandbox).

Log esperado:

```
INFO ...send_password_reset_email PASSWORD_RESET enviado event_id=pr-0001 correlation_id=pr-corr-0001
INFO ...dispatcher procesado event_id=pr-0001 correlation_id=pr-corr-0001 resultado=sent
```

### Errores típicos

| Síntoma | Causa | Solución |
|---|---|---|
| El evento "sale bien" pero el worker no reacciona y las métricas de Events están vacías | **`EventBusName` omitido**: el CLI envía al bus `default` | Incluir `"EventBusName": "kenko-dev-bus"` |
| Mensaje en la DLQ sin que el worker lo procesara | Se usó `receive-message` para **inspeccionar**: cada `receive` consume un intento | Inspeccionar solo con `get-queue-attributes` |
| Correo con asunto y texto pero sin fecha local | `expiresAt` ya vencido → se registra `failed/expired` | Usar un `expiresAt` futuro |
| `ModuleNotFoundError: No module named 'notifications'` | `.pth` oculto (flag de macOS) | `PYTHONPATH=src` |

### Estado de la cola (sin gastar reintentos)

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/137696817246/kenko-dev-notifications-authentication" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

---

## Tests y lint

```bash
uv run pytest -q      # 81 tests, sin llamar a AWS (fakes + botocore Stubber)
uv run ruff check .
uv run ruff format .
```

| Área | Tests |
|---|---|
| Schema de `PasswordResetRequested` | 16 — válido, sin email, email inválido, `resetUrl` no-http(s), sin `expiresAt`, sin zona, campos extra, `firstName` vacío |
| Caso de uso de restablecimiento | 8 — plantilla, asunto, contexto, conversión a Bogotá, enlace vencido, errores SES |
| Plantillas de restablecimiento (HTML/texto) | 7 — contenido, autoescape solo en HTML, `StrictUndefined` |
| Router | 9 — ambas rutas, mapper correcto, evento desconocido, source ajeno |
| Dispatcher | 9 — idempotencia, permanente/transitorio/inesperado, fallo de BD, truncado |
| Sincronización Terraform ↔ router | 5 — `tfvars` y `build_router()` no pueden desincronizarse |
| Resto (welcome, envelope, renderer, SES, dominio) | 27 |

**Privacidad:** ningún log imprime `resetUrl`, el token ni el email; solo
`event_id` y `correlation_id`. `resetUrl` no se guarda en `notification_log`.

---

## Infraestructura (Terraform)

```bash
cd terraform
terraform init
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

| Recurso | Nombre |
|---|---|
| Regla EventBridge | `kenko-dev-auth-to-notifications` |
| Cola principal | `kenko-dev-notifications-authentication` |
| Dead-letter queue | `kenko-dev-notifications-authentication-dlq` |

Nombres derivados con patrón `{project}-{env}-{consumer}-{producer}[-dlq]`.
Útiles: `terraform output queue_url`, `terraform output rule_arn`.

### Agregar un evento de Authentication

Dos cambios **en el mismo paso** (el test de sincronización lo obliga):

1. `terraform/envs/<ambiente>.tfvars` → añadir a `auth_detail_types`
2. `container.build_router()` → registrar handler + `template_name`

```hcl
auth_detail_types = ["UserRegistered", "PasswordResetRequested"]
```

Después `terraform apply`. Si solo haces uno de los dos, **los tests fallan**:
eso es intencional, evita descartar eventos en silencio o dejar código muerto.

---

## Decisiones de diseño

**Worker como proceso principal, FastAPI aparte.** Un consumidor no tiene API
pública: `/health` es para el orquestador. Si el *thread* del worker se cuelga
pero FastAPI sigue vivo, `/health` respondería 200 mientras no se consume nada.
Plan: FastAPI después, como proceso separado (misma imagen, distinto `command`).

**Un proceso por cola, código genérico.** Terraform agrupa **por productor**:
`...-notifications-authentication`, `-profile`, `-documents`, `-appointments`.
Cada cola puede recibir varios `detail-type`. Recomendación: worker por cola
(aislamiento, escalado independiente, SQS reparte entre réplicas).

**Dispatcher en `application/`.** La clasificación de errores y la
idempotencia no dependen de SQS ni Pydantic, así que se prueban con fakes.

**`resetUrl` tal cual.** El enlace llega completo (token en el fragmento
`#token=`); Notifications no construye el link ni usa `FRONTEND_BASE_URL`.

**`expires_at` en UTC, se muestra en `America/Bogota`** con formato
`dd/mm/YYYY HH:MM` fijo (sin depender del locale del servidor).

---

## Estructura del repo

```
.
├── src/notifications/
│   ├── main.py                 Entrypoint del worker
│   ├── domain/                 errores, NotificationLog
│   ├── application/            commands, models, dispatcher, ports, use_cases/
│   └── infrastructure/         config, container, inbound/, outbound/, templates/
├── migrations/                 Alembic (pendiente)
├── terraform/                  Colas, DLQs, reglas EventBridge, IAM
├── tests/                      conftest, fakes, fixtures, unit/
├── .env.example                Plantilla de variables de entorno
├── pyproject.toml              Dependencias, pytest y ruff
└── Dockerfile                  (vacío — pendiente)
```

No se hacen commits desde este flujo de trabajo; eso lo decides tú.
