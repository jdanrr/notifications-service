# Ambiente de producción.
environment = "prod"
region      = "us-east-1"

event_bus_name = "kenko-prod-bus"
auth_source    = "kenko.auth"

# Eventos de Authentication que enruta la regla en prod.
auth_detail_types = ["UserRegistered", "PasswordResetRequested"]

# Retención más larga en prod para dar tiempo a depurar.
visibility_timeout_seconds   = 60
message_retention_seconds    = 345600
dlq_message_retention_seconds = 1209600
max_receive_count            = 3
receive_wait_time_seconds    = 20
