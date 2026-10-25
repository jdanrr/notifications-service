# Terraform — Notifications

Infraestructura de consumo de eventos del microservicio **Notifications**.

Notifications es solo consumidor: crea sus propias colas, DLQs y reglas de
EventBridge, y no publica eventos.

El bus de EventBridge ya existe y es dueño de otro equipo. Este código solo
lo referencia con un `data` source, nunca lo crea.

## Recursos

| Recurso | Nombre |
|---|---|
| Regla de EventBridge | `kenko-dev-auth-to-notifications` |
| Cola principal SQS | `kenko-dev-notifications-authentication` |
| Dead-letter queue | `kenko-dev-notifications-authentication-dlq` |
| Regla de EventBridge | `kenko-dev-appointments-to-notifications` |
| Cola principal SQS | `kenko-dev-notifications-appointments` |
| Dead-letter queue | `kenko-dev-notifications-appointments-dlq` |

| Evento (`source` / `detail-type`) | Regla | Cola | DLQ |
|---|---|---|---|
| `kenko.auth` / `UserRegistered`, `PasswordResetRequested` | `kenko-dev-auth-to-notifications` | `kenko-dev-notifications-authentication` | `kenko-dev-notifications-authentication-dlq` |
| `kenko.appointments` / `AppointmentScheduled`, `AppointmentRescheduled`, `AppointmentCancelled` | `kenko-dev-appointments-to-notifications` | `kenko-dev-notifications-appointments` | `kenko-dev-notifications-appointments-dlq` |

Los nombres se derivan de `project` + `environment`, con el patrón
`{project}-{env}-{consumer}-{producer}[-dlq]`.

## Uso

El estado vive localmente (sin backend remoto).

```bash
terraform init
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

Para producción:

```bash
terraform plan  -var-file=envs/prod.tfvars
terraform apply -var-file=envs/prod.tfvars
```

Cada ambiente se aplica por separado. Revisar el plan antes de aplicar.

## Agregar un evento de Authentication

Agregar el `detail-type` a `auth_detail_types` en el `.tfvars` del ambiente
y aplicar. La regla se reconstruye sola; no toca editar recursos.

```hcl
auth_detail_types = ["UserRegistered", "UserEmailVerified"]
```

## Agregar un evento de Appointments

Agregar el `detail-type` a `appointments_detail_types` en el `.tfvars` del ambiente
y aplicar. La regla se reconstruye sola; no toca editar recursos.

```hcl
appointments_detail_types = ["AppointmentScheduled", "AppointmentRescheduled", "AppointmentCancelled"]
```

## Verificación

```bash
aws events describe-rule --name kenko-dev-auth-to-notifications --event-bus-name kenko-dev-bus
aws sqs get-queue-attributes --queue-url <queue_url> --attribute-names ApproximateNumberOfMessages
```

## Limpieza

```bash
terraform destroy -var-file=envs/dev.tfvars
```
