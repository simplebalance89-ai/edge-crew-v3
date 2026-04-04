variable "cluster_name" {
  type = string
}

variable "region" {
  type = string
}

variable "network" {
  type = string
}

variable "subnet" {
  type = string
}

variable "node_count" {
  type    = number
  default = 3
}

variable "min_node_count" {
  type    = number
  default = 2
}

variable "max_node_count" {
  type    = number
  default = 10
}

variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "project_id" {
  type    = string
  default = ""
}
