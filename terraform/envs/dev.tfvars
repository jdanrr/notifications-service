# Ambiente de desarrollo.
environment = "dev"
region      = "us-east-1"

# Eventos de Authentication que enruta la regla en dev.
auth_detail_types = ["UserRegistered", "PasswordResetRequested"]

# Parámetros más permisivos para desarrollo.
visibility_timeout_seconds   = 60
message_retention_seconds    = 86400
dlq_message_retention_seconds = 1209600
max_receive_count            = 3
receive_wait_time_seconds    = 20
