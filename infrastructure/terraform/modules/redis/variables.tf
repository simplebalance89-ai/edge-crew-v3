variable "instance_name" {
  type = string
}

variable "region" {
  type = string
}

variable "tier" {
  type    = string
  default = "STANDARD_HA"
}

variable "memory_size_gb" {
  type    = number
  default = 5
}

variable "network" {
  type = string
}
