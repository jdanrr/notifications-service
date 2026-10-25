output "queue_name" {
  description = "Nombre de la cola principal de Authentication."
  value       = aws_sqs_queue.this.name
}

output "queue_arn" {
  description = "ARN de la cola principal de Authentication."
  value       = aws_sqs_queue.this.arn
}

output "queue_url" {
  description = "URL de la cola principal de Authentication."
  value       = aws_sqs_queue.this.url
}

output "dlq_arn" {
  description = "ARN de la dead-letter queue de Authentication."
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_url" {
  description = "URL de la dead-letter queue de Authentication."
  value       = aws_sqs_queue.dlq.url
}

output "rule_arn" {
  description = "ARN de la regla que enruta Authentication a Notifications."
  value       = aws_cloudwatch_event_rule.auth_to_notifications.arn
}

output "event_bus_arn" {
  description = "ARN del bus de EventBridge utilizado."
  value       = data.aws_cloudwatch_event_bus.this.arn
}

output "appointments_queue_name" {
  description = "Nombre de la cola principal de Appointments."
  value       = aws_sqs_queue.appointments.name
}

output "appointments_queue_arn" {
  description = "ARN de la cola principal de Appointments."
  value       = aws_sqs_queue.appointments.arn
}

output "appointments_queue_url" {
  description = "URL de la cola principal de Appointments."
  value       = aws_sqs_queue.appointments.url
}

output "appointments_dlq_arn" {
  description = "ARN de la dead-letter queue de Appointments."
  value       = aws_sqs_queue.appointments_dlq.arn
}

output "appointments_dlq_url" {
  description = "URL de la dead-letter queue de Appointments."
  value       = aws_sqs_queue.appointments_dlq.url
}

output "appointments_rule_arn" {
  description = "ARN de la regla que enruta Appointments a Notifications."
  value       = aws_cloudwatch_event_rule.appointments_to_notifications.arn
}
