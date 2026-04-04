output "connection_name" {
  value = google_sql_database_instance.primary.connection_name
}

output "public_ip" {
  value = google_sql_database_instance.primary.public_ip_address
}

output "database" {
  value = google_sql_database.database.name
}

output "username" {
  value = google_sql_user.user.name
}
