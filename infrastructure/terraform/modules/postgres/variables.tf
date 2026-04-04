variable "instance_name" {
  type = string
}

variable "region" {
  type = string
}

variable "database_version" {
  type    = string
  default = "POSTGRES_15"
}

variable "tier" {
  type    = string
  default = "db-g1-small"
}

variable "database_name" {
  type = string
}

variable "username" {
  type = string
}

variable "password" {
  type    = string
  default = null
}

variable "private_network" {
  type    = string
  default = ""
}

variable "authorized_network" {
  type    = string
  default = "0.0.0.0/0"
}
