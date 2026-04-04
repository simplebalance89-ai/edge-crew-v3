# Cloud SQL PostgreSQL + TimescaleDB Module

resource "google_sql_database_instance" "primary" {
  name             = var.instance_name
  database_version = var.database_version
  region           = var.region
  
  settings {
    tier = var.tier
    
    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
    }
    
    maintenance_window {
      day  = 7  # Sunday
      hour = 2
    }
    
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
    
    ip_configuration {
      ipv4_enabled    = true
      private_network = var.private_network
      
      authorized_networks {
        name  = "gke-cluster"
        value = var.authorized_network
      }
    }
    
    database_flags {
      name  = "cloudsql.enable_pgaudit"
      value = "on"
    }
  }
  
  deletion_protection = true
}

resource "google_sql_database" "database" {
  name     = var.database_name
  instance = google_sql_database_instance.primary.name
}

resource "google_sql_user" "user" {
  name     = var.username
  instance = google_sql_database_instance.primary.name
  password = var.password
}

# Create timescaledb extension
resource "null_resource" "setup_timescaledb" {
  depends_on = [google_sql_database.database]
  
  provisioner "local-exec" {
    command = <<EOF
      gcloud sql connect ${var.instance_name} --user=${var.username} --database=${var.database_name} --quiet << 'EOSQL'
      CREATE EXTENSION IF NOT EXISTS timescaledb;
EOSQL
    EOF
  }
}
