variable "environment" { type = string }
variable "region" {
  type    = string
  default = "me-central-1"
}
variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}
variable "db_instance_class" {
  type    = string
  default = "db.r6g.large"
}
variable "eks_version" {
  type    = string
  default = "1.31"
}
variable "enable_gpu_inference" {
  description = "Create a GPU node group for private model hosting (vLLM)."
  type        = bool
  default     = false
}
