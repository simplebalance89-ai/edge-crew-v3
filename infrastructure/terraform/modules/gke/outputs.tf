output "endpoint" {
  value = google_container_cluster.primary.endpoint
}

output "name" {
  value = google_container_cluster.primary.name
}

output "ca_certificate" {
  value     = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive = true
}
