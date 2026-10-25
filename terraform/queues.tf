# Nombres derivados: {project}-{env}-{consumer}-{producer}[-dlq]
# El productor es "authentication" porque la cola agrupa todos los eventos
# de Authentication que consume Notifications, no solo UserRegistered.
locals {
  consumer   = "notifications"
  producer   = "authentication"
  queue_name = "${var.project}-${var.environment}-${local.consumer}-${local.producer}"
  dlq_name   = "${local.queue_name}-dlq"

  # ARN de la cola principal construido como string para romper el ciclo con
  # aws_sqs_queue.this (ella misma referencia la DLQ en su redrive_policy).
  queue_arn = "arn:aws:sqs:${var.region}:${data.aws_caller_identity.this.account_id}:${local.queue_name}"

  # Patrón de la regla. Las listas se generan desde variables para poder
  # agregar eventos sin editar este archivo.
  event_pattern = jsonencode({
    source      = [var.auth_source]
    detail-type = var.auth_detail_types
  })
}

# Cola de mensajes fallidos. Existe antes que la principal porque la
# principal la referencia en su redrive policy.
resource "aws_sqs_queue" "dlq" {
  name                      = local.dlq_name
  message_retention_seconds = var.dlq_message_retention_seconds

  # Cifrado en reposo gestionado por SQS (SSE-SQS), sin gestión de claves.
  sqs_managed_sse_enabled = true

  # Solo la cola principal puede enviar mensajes a esta DLQ.
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [local.queue_arn]
  })
}

resource "aws_sqs_queue" "this" {
  name                       = local.queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = var.receive_wait_time_seconds

  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

# Mínimo privilegio: solo EventBridge puede hacer SendMessage, y solo si el
# origen es exactamente esta regla.
resource "aws_sqs_queue_policy" "this" {
  queue_url = aws_sqs_queue.this.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgeSendMessage"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.this.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.auth_to_notifications.arn
          }
        }
      }
    ]
  })
}

# EventBridge también envía los eventos que no pudo entregar a su propia
# DLQ de target, así que esa cola necesita el mismo permiso.
resource "aws_sqs_queue_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgeSendMessage"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.dlq.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.auth_to_notifications.arn
          }
        }
      }
    ]
  })
}

# Consumo de Appointments. Duplica el esquema de Auth con el productor
# "appointments": mismos parámetros, cifrado y permisos, otra regla.
locals {
  appointments_producer   = "appointments"
  appointments_queue_name = "${var.project}-${var.environment}-${local.consumer}-${local.appointments_producer}"
  appointments_dlq_name   = "${local.appointments_queue_name}-dlq"
  appointments_queue_arn  = "arn:aws:sqs:${var.region}:${data.aws_caller_identity.this.account_id}:${local.appointments_queue_name}"
  appointments_event_pattern = jsonencode({
    source      = [var.appointments_source]
    detail-type = var.appointments_detail_types
  })
}

resource "aws_sqs_queue" "appointments_dlq" {
  name                      = local.appointments_dlq_name
  message_retention_seconds = var.dlq_message_retention_seconds

  # Cifrado en reposo gestionado por SQS (SSE-SQS), sin gestión de claves.
  sqs_managed_sse_enabled = true

  # Solo la cola principal puede enviar mensajes a esta DLQ.
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [local.appointments_queue_arn]
  })
}

resource "aws_sqs_queue" "appointments" {
  name                       = local.appointments_queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = var.receive_wait_time_seconds

  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.appointments_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

# Mínimo privilegio: solo EventBridge puede hacer SendMessage, y solo si el
# origen es exactamente la regla de Appointments.
resource "aws_sqs_queue_policy" "appointments" {
  queue_url = aws_sqs_queue.appointments.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgeSendMessage"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.appointments.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.appointments_to_notifications.arn
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "appointments_dlq" {
  queue_url = aws_sqs_queue.appointments_dlq.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgeSendMessage"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.appointments_dlq.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.appointments_to_notifications.arn
          }
        }
      }
    ]
  })
}
