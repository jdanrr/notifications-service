provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      Service     = "notifications"
      ManagedBy   = "terraform"
    }
  }
}

# El bus ya existe y es dueño de otro equipo. Solo lo referenciamos para
# validar que está disponible antes de crear reglas que apunten a él.
data "aws_cloudwatch_event_bus" "this" {
  name = var.event_bus_name
}
