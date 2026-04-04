# Memorystore Redis Module

resource "google_redis_instance" "cache" {
  name               = var.instance_name
  tier               = var.tier
  memory_size_gb     = var.memory_size_gb
  region             = var.region
  authorized_network = var.network
  
  redis_version     = "REDIS_7_0"
  display_name      = "Edge Crew Cache"
  
  persistence_config {
    persistence_mode    = "RDB"
    rdb_snapshot_period = "ONE_HOUR"
  }
  
  maintenance_policy {
    weekly_maintenance_window {
      day = "TUESDAY"
      start_time {
        hours   = 2
        minutes = 0
      }
    }
  }
  
  labels = {
    environment = "prod"
    app         = "edge-crew"
  }
}
