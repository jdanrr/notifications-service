# Regla sobre el bus existente. El patrón se arma en locals (queues.tf) a
# partir de las variables, para agregar detail-type sin tocar recursos.
resource "aws_cloudwatch_event_rule" "auth_to_notifications" {
  name           = "${var.project}-${var.environment}-auth-to-notifications"
  description    = "Enruta los eventos de Authentication hacia las colas de Notifications."
  event_bus_name = data.aws_cloudwatch_event_bus.this.name
  event_pattern  = local.event_pattern
}

resource "aws_cloudwatch_event_target" "this" {
  rule           = aws_cloudwatch_event_rule.auth_to_notifications.name
  event_bus_name = data.aws_cloudwatch_event_bus.this.name
  arn            = aws_sqs_queue.this.arn

  # Si EventBridge no puede entregar el evento, reintenta y luego lo manda
  # a la DLQ en vez de perderlo.
  retry_policy {
    maximum_retry_attempts       = var.target_retry_attempts
    maximum_event_age_in_seconds = var.target_max_event_age
  }

  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }
}

# Regla de Appointments. Lleva el evento completo a la cola (sin input_path),
# igual que la de Auth, para que el worker tenga un único formato que parsear.
resource "aws_cloudwatch_event_rule" "appointments_to_notifications" {
  name           = "${var.project}-${var.environment}-appointments-to-notifications"
  description    = "Enruta los eventos de Appointments hacia las colas de Notifications."
  event_bus_name = data.aws_cloudwatch_event_bus.this.name
  event_pattern  = local.appointments_event_pattern
}

resource "aws_cloudwatch_event_target" "appointments" {
  rule           = aws_cloudwatch_event_rule.appointments_to_notifications.name
  event_bus_name = data.aws_cloudwatch_event_bus.this.name
  arn            = aws_sqs_queue.appointments.arn

  retry_policy {
    maximum_retry_attempts       = var.target_retry_attempts
    maximum_event_age_in_seconds = var.target_max_event_age
  }

  dead_letter_config {
    arn = aws_sqs_queue.appointments_dlq.arn
  }
}
