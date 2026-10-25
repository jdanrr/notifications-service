variable "project" {
  description = "Nombre corto del proyecto. Define el prefijo de todos los recursos."
  type        = string
  default     = "kenko"
}

variable "environment" {
  description = "Ambiente desplegado. Define el segmento de entorno de todos los recursos."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "Región de AWS donde vive el bus y se crean las colas."
  type        = string
  default     = "us-east-1"
}

variable "event_bus_name" {
  description = "Nombre del bus de EventBridge existente que enruta los eventos. No se crea desde este módulo."
  type        = string
  default     = "kenko-dev-bus"
}

variable "auth_source" {
  description = "Valor del campo `source` del sobre de EventBridge emitido por Authentication."
  type        = string
  default     = "kenko.auth"
}

variable "auth_detail_types" {
  description = "Lista de `detail-type` de Authentication que enruta la regla. Agregar eventos futuros aquí, sin tocar recursos."
  type        = list(string)
  default     = ["UserRegistered"]
}

variable "appointments_source" {
  description = "Valor del campo `source` del sobre de EventBridge emitido por Appointments."
  type        = string
  default     = "kenko.appointments"
}

variable "appointments_detail_types" {
  description = "Lista de `detail-type` de Appointments que enruta la regla. Agregar eventos futuros aquí, sin tocar recursos."
  type        = list(string)
  default     = ["AppointmentScheduled", "AppointmentRescheduled", "AppointmentCancelled"]
}

variable "visibility_timeout_seconds" {
  description = "Segundos durante los que un mensaje entregado queda oculto. Debe ser mayor que el tiempo máximo que tarda el worker en enviar el correo con SES."
  type        = number
  default     = 60
}

variable "message_retention_seconds" {
  description = "Segundos que un mensaje no procesado permanece en la cola principal antes de eliminarse."
  type        = number
  default     = 86400
}

variable "dlq_message_retention_seconds" {
  description = "Segundos que un mensaje fallido permanece en la DLQ antes de eliminarse. Más largo que la principal para dar tiempo a depurarlo."
  type        = number
  default     = 1209600
}

variable "max_receive_count" {
  description = "Veces que un mensaje puede fallar antes de pasarse a la DLQ."
  type        = number
  default     = 3
}

variable "receive_wait_time_seconds" {
  description = "Long polling: segundos que ReceiveMessage espera si no hay mensajes disponibles."
  type        = number
  default     = 20
}

variable "target_max_event_age" {
  description = "Segundos máximo que EventBridge reintenta un evento antes de descartarlo o enviarlo a su DLQ."
  type        = number
  default     = 1800
}

variable "target_retry_attempts" {
  description = "Intentos de reintento del target de EventBridge antes de fallar."
  type        = number
  default     = 185
}
