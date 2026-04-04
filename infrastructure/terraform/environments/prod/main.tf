# Edge Crew v3.0 - Production Infrastructure (GKE)

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
  
  backend "gcs" {
    bucket = "edge-crew-terraform-state"
    prefix = "prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  cluster_name = "edge-crew-prod"
  namespace    = "edge-crew"
}

# Enable APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "compute.googleapis.com",
    "cloudsql.googleapis.com",
    "redis.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "secretmanager.googleapis.com",
  ])
  
  service            = each.value
  disable_on_destroy = false
}

# VPC Network
module "network" {
  source = "../../modules/network"
  
  network_name = "edge-crew-network"
  region       = var.region
}

# GKE Cluster
module "gke" {
  source = "../../modules/gke"
  
  cluster_name   = local.cluster_name
  region         = var.region
  network        = module.network.network_name
  subnet         = module.network.subnet_name
  node_count     = 3
  machine_type   = "e2-standard-4"  # 4 vCPU, 16 GB
  min_node_count = 2
  max_node_count = 10
  
  depends_on = [google_project_service.apis]
}

# Cloud SQL (PostgreSQL + TimescaleDB)
module "postgres" {
  source = "../../modules/postgres"
  
  instance_name = "edge-crew-postgres"
  region        = var.region
  database_version = "POSTGRES_15"
  tier          = "db-g1-small"
  
  database_name = "edgecrew"
  username      = "edgecrew"
}

# Memorystore (Redis)
module "redis" {
  source = "../../modules/redis"
  
  instance_name = "edge-crew-redis"
  region        = var.region
  tier          = "STANDARD_HA"
  memory_size_gb = 5
  
  depends_on = [google_project_service.apis]
}

# Secrets
resource "google_secret_manager_secret" "api_keys" {
  for_each = toset([
    "azure-sweden-key",
    "azure-nc-key",
    "azure-gce-key",
    "deepseek-api-key",
    "grok-api-key",
    "kimi-api-key",
    "anthropic-api-key",
    "odds-api-key",
  ])
  
  secret_id = each.value
  
  replication {
    auto {}
  }
}

# Outputs
output "cluster_endpoint" {
  value     = module.gke.endpoint
  sensitive = true
}

output "postgres_connection" {
  value     = module.postgres.connection_name
  sensitive = true
}

output "redis_host" {
  value = module.redis.host
}
