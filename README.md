# Notifications

Microservicio de **notificaciones** de Kenko Salud (portal tipo EPS, Colombia).

Es **solo consumidor**: no publica eventos. Recibe mensajes de colas SQS que
alimenta EventBridge y envía correos con AWS SES. Usa arquitectura hexagonal.

> **Estado:** en implementación. Hoy solo está funcionando el flujo de
> **bienvenida** (`UserRegistered` → correo de bienvenida). Los archivos
> `Dockerfile` y `docker-compose.yml` están **vacíos** (sin configurar) y el
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

El bus y las reglas pertenecen a otros equipos/este repo de infra; **las colas,
las DLQ y las reglas de EventBridge de Notifications las creamos nosotros con
Terraform** (ver `terraform/`).

### Capas (hexagonal)

```
domain/            Núcleo: errores y entidad NotificationLog. Sin dependencias.
application/       Casos de uso + puertos (interfaces). Sin boto3.
  ports/             EmailSender, TemplateRenderer, NotificationLogRepository
  use_cases/auth/    send_welcome_email
infrastructure/    Adaptadores.
  inbound/sqs/       poller (SQS) · worker (loop) · envelope · router · mappers · schemas
  outbound/          email/ses_email_sender · rendering/jinja_renderer · persistence/*
  templates/         plantillas Jinja2 (.j2) y assets
  config.py          settings por variables de entorno
  container.py       wiring (sin framework de DI)
main.py            Punto de entrada: arranca el worker
```

**Regla:** el caso de uso no importa `boto3`. Habla con los puertos; los
adaptadores concretos (SES, Jinja2, SQLAlchemy) los inyecta `container.py`.

---

## Cómo funciona el worker

`main.py` → `Settings()` (lee `.env`) → `build_worker()` → registra señales →
`worker.run()`, un loop:

1. **`poller.receive()`** — `sqs receive_message` con **long polling**
   (`WaitTimeSeconds=20`, lote de 1). Si la cola está vacía espera hasta 20 s
   en lugar de volver de inmediato: menos llamadas y costo más bajo.
2. Si no llegó nada → vuelve a 1.
3. Si llegó mensaje → **`_process(message)`**.

### Política de borrado del mensaje

| Resultado | ¿Borra el mensaje? | ¿Registra? |
|---|---|---|
| Envío exitoso (`sent`) | ✅ | ✅ `status=sent` |
| Duplicado (event_id ya enviado) | ✅ | no hace falta |
| **Fallo permanente** (sin email, `MessageRejected`, body corrupto, plantilla rota) | ✅ **solo si el registro funcionó** | ✅ `status=failed` |
| **Fallo transitorio** (throttling, red, timeout) | ❌ **no** | ❌ |
| Error inesperado | ❌ **no** | ❌ |

No borrar en el caso transitorio es lo que activa los reintentos de SQS: el
mensaje reaparece tras el *visibility timeout* (60 s), SQS lo entrega de nuevo
y, al superar `maxReceiveCount=3`, lo mueve a la **DLQ** en vez de perderlo.

Si falla el **borrado** (por red), tampoco hay problema: el mensaje se
reentrega y la **idempotencia por `event_id`** evita el correo duplicado.

### Apagado ordenado

`main.py` engancha `SIGTERM` y `SIGINT` (Ctrl+C) a `worker.stop()`, que solo
marca un flag `Event`. El loop lo respeta al terminar el `receive()` actual y
antes de procesar cada mensaje, así que **nunca se corta un envío a medias**.
Sale con código 0 e imprime `worker detenido`.

### Idempotencia

SQS entrega **al menos una vez**. Antes de enviar se consulta
`has_been_sent(event_id)` en `notification_log`; si ya existe, se devuelve
`duplicate` y no se reenvía.

---

## Puesta en marcha

### 1. Dependencias

```bash
uv sync --extra dev
```

Crea `.venv` con `boto3`, `jinja2`, `pydantic-settings`, `sqlalchemy`,
`psycopg2-binary` + `pytest` y `ruff`.

### 2. Variables de entorno

```bash
cp .env.example .env
```

`.env` está en `.gitignore` y **nunca se commitea**. Las credenciales de AWS
**no van aquí**: se leen de `~/.aws` (perfil `default`).

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `SQS_QUEUE_URL` | ✅ | — | Cola a consumir |
| `SES_SENDER` | ✅ | — | Remitente verificado en SES |
| `KENKO_PORTAL_URL` | ✅ | — | Enlace del botón "Ingresar al portal" |
| `KENKO_SUPPORT_EMAIL` | ✅ | — | Soporte en el pie del correo |
| `LOGO_URL` | ✅ | — | URL pública del logo (**PNG**; los clientes de correo no soportan SVG) |
| `AWS_REGION` | | `us-east-1` | Región |
| `APP_NAME` | | `Kenko` | Marca en los textos |
| `LOG_LEVEL` | | `INFO` | Nivel de logging |
| `RECEIVE_BATCH_SIZE` | | `1` | Mensajes por `receive` (1–5) |
| `RECEIVE_WAIT_TIME_SECONDS` | | `20` | Long polling (0–20) |
| `DATABASE_URL` | | *(vacío)* | Si se omite usa repositorio en memoria |

Si falta una requerida, el proceso **no arranca**: imprime
`Configuracion invalida` con el detalle y sale con código `2`.

### 3. Levantar el worker

```bash
cd "/Users/joserodriguez/Documents/UCatólica/5to Semestre/Prod. de Software/notifications-service"
PYTHONPATH=src .venv/bin/python -m notifications.main
```

> **Por qué `PYTHONPATH=src`:** el `.pth` generado por `uv sync` tiene el flag
> `hidden` de macOS (`UF_HIDDEN`) y **CPython 3.13 salta los `.pth` ocultos**,
> por lo que `import notifications` falla. La misma solución usa pytest
> (`pythonpath = ["src"]` en `pyproject.toml`). Si regeneras el venv
> (`rm -rf .venv && uv sync`) y el flag no reaparece, podrás usar
> `uv run python -m notifications.main` sin la variable.

Para verlo en background:

```bash
PYTHONPATH=src .venv/bin/python -m notifications.main > /tmp/kenko_worker.log 2>&1 &
echo $! > /tmp/kenko_worker.pid
tail -f /tmp/kenko_worker.log
```

Al arrancar verás:

```
WARNING ...container DATABASE_URL no configurada: se usa repositorio en memoria (la idempotencia no sobrevive reinicios)
INFO ...sqs.worker worker iniciado
```

El warning es esperado sin base de datos.

### 4. Detenerlo

**Ctrl+C** en la terminal, o si está en background:

```bash
kill -TERM "$(cat /tmp/kenko_worker.pid)"
```

Espera el ciclo actual y muestra `worker detenido`.

---

## Probar de punta a punta

Con el worker corriendo, en **otra terminal**:

```bash
aws events put-events --entries '[{
  "EventBusName": "kenko-dev-bus",
  "Source": "kenko.auth",
  "DetailType": "UserRegistered",
  "Detail": "{\"metadata\":{\"eventId\":\"test-0001\",\"eventVersion\":\"1\",\"occurredAt\":\"2026-10-18T00:00:00Z\",\"correlationId\":\"corr-0001\"},\"data\":{\"person\":{\"firstName\":\"Prueba\"},\"contact\":{\"email\":\"tu-email-verificado@example.com\"}}}"
}]'
```

Usa un email registrado en SES (la cuenta está en sandbox: solo identities
verificadas). En el log debería aparecer:

```
INFO ...send_welcome_email correo enviado event_id=test-0001 correlation_id=corr-0001
INFO ...sqs.worker procesado event_id=test-0001 correlation_id=corr-0001 resultado=sent
```

### Errores típicos

| Síntoma | Causa | Solución |
|---|---|---|
| El evento "sale bien" pero el worker no reacciona y las métricas de Events están vacías | **`EventBusName` omitido**: el CLI envía al bus `default` | Incluir `"EventBusName": "kenko-dev-bus"` |
| Mensaje a la DLQ con `ApproximateReceiveCount` alto sin que el worker lo haya procesado | Se usó `receive-message` para **inspeccionar** la cola: cada `receive` consume un intento | Inspeccionar solo con `get-queue-attributes`; **nunca** con `receive-message` |
| `ModuleNotFoundError: No module named 'notifications'` | `.pth` oculto (flag de macOS) | Usar `PYTHONPATH=src` |

### Estado de la cola (sin gastar reintentos)

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/137696817246/kenko-dev-notifications-authentication" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

---

## Tests y lint

```bash
uv run pytest -q      # 27 tests, sin llamar a AWS (fakes + botocore Stubber)
uv run ruff check .
uv run ruff format .
```

- `tests/fakes/` — implementaciones en memoria de los puertos.
- `tests/unit/infrastructure/test_ses_email_sender.py` — verifica el payload
  exacto de SES con `botocore.stub.Stubber`, sin red.
- `tests/unit/infrastructure/test_jinja_renderer.py` — autoescape: un
  `user_name` con `<script>` sale escapado en HTML y literal en texto plano.

---

## Infraestructura (Terraform)

```bash
cd terraform
terraform init
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

Recursos creados (región `us-east-1`, cuenta `137696817246`):

| Recurso | Nombre |
|---|---|
| Regla EventBridge | `kenko-dev-auth-to-notifications` |
| Cola principal | `kenko-dev-notifications-authentication` |
| Dead-letter queue | `kenko-dev-notifications-authentication-dlq` |

El bus `kenko-dev-bus` **ya existe y no se crea**: se referencia con un `data`
source. Nombres derivados con patrón `{project}-{env}-{consumer}-{producer}[-dlq]`.

Útiles:

```bash
terraform output queue_url
terraform output rule_arn
```

---

## Decisiones de diseño

### Worker como proceso principal, FastAPI aparte

Un servicio consumidor **no tiene API pública**: `/health` existe para el
orquestador, no para usuarios. El worker es síncrono y bloqueante (long
polling de 20 s), lo cual encaja mejor en un proceso propio que dentro de un
servidor asyncio.

El riesgo de correr ambos en el mismo proceso: si el *thread* del worker se
cuelga pero FastAPI sigue vivo, **`/health` responde 200 mientras el servicio
no consume nada** — una salud falsa.

Plan: mantener el worker como proceso principal y agregar FastAPI **después,
como proceso separado** (misma imagen, distinto `command` en
`docker-compose.yml`). Para que la salud del worker sea real, conviene
expolar un timestamp de "última recepción exitosa" en vez de solo "estoy vivo".

### Un proceso por cola, código genérico

Terraform agrupa **por productor**, no por evento:

```
kenko-dev-notifications-authentication   ← todo Authentication
kenko-dev-notifications-profile          ← todo Profile
kenko-dev-notifications-documents        ← todo Documents
kenko-dev-notifications-appointments     ← todo Appointments
```

Cada cola puede recibir **varios `detail-type`**; la regla acepta una lista por
variable, así que agregar un evento no toca recursos.

Recomendación: **un worker por cola** (mismo código, distinta `SQS_QUEUE_URL`),
porque así se aislan mensajes tóxicos entre productores, se escala cada cola
por separado y SQS reparte entre réplicas de la misma cola automáticamente.
El loop, el parseo y la política de borrado ya son genéricos; hoy solo el
nombre de la clase (`AuthEventsWorker`) es específico de Authentication.

### `template_name` vive en la ruta, no en el worker

`router.register(source, detail_type, handler, template_name=...)` guarda
también la plantilla que el evento debe reportar en `notification_log`:

```python
router.register(
    "kenko.auth",
    "UserRegistered",
    _handler(use_case),
    template_name=WELCOME_TEMPLATE,  # "welcome"
)
```

Al procesar, el worker toma el `template_name` **de la ruta resuelta**:

| Situación | `template` registrado en el fallo |
|---|---|
| Ruta encontrada | el de esa ruta (`welcome`, `password_reset`, …) |
| Sin ruta registrada | `unknown` |

Así, cuando convivan varios eventos en la misma cola, cada fallo queda con **su**
plantilla y la traza no miente. Los éxitos no pasan por aquí: los registra el
propio caso de uso con su constante `TEMPLATE_NAME`.

> **Pendiente:** renombrar `AuthEventsWorker` a algo genérico (p. ej.
> `QueueWorker`) al momento de generalizar a varias colas.

---

## Estructura del repo

```
.
├── src/notifications/
│   ├── main.py                 Entrypoint del worker
│   ├── domain/                 errores, NotificationLog
│   ├── application/            commands, models, ports, use_cases/
│   └── infrastructure/         config, container, inbound/, outbound/, templates/
├── migrations/                 Alembic (pendiente)
├── terraform/                  Colas, DLQs, reglas EventBridge, IAM
├── tests/                      conftest, fakes, fixtures, unit/, integration/
├── .env.example                Plantilla de variables de entorno
├── pyproject.toml              Dependencias, pytest y ruff
└── Dockerfile                  (vacío — pendiente)
```

No se hacen commits desde este flujo de trabajo; eso lo decides tú.
