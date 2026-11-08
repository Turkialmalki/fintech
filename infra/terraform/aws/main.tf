# Reference AWS footprint. Cloud specifics are confined to this folder; the application only needs
# PostgreSQL 16 + pgvector, Redis, S3-compatible object storage, a Kubernetes cluster and a secret store.
# Equivalent stacks: Azure (AKS, Flexible Server + pgvector, Azure Cache, Blob via S3 gateway, Key Vault),
# GCP (GKE, Cloud SQL + pgvector, Memorystore, GCS interoperability, Secret Manager).

data "aws_availability_zones" "az" {}

module "vpc" {
  source          = "terraform-aws-modules/vpc/aws"
  version         = "~> 5.13"
  name            = "rip-${var.environment}"
  cidr            = var.vpc_cidr
  azs             = slice(data.aws_availability_zones.az.names, 0, 3)
  private_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i in range(3) : cidrsubnet(var.vpc_cidr, 8, 200 + i)]
  database_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 8, 210 + i)]
  enable_nat_gateway = true
  single_nat_gateway = var.environment != "production"
}

resource "aws_kms_key" "rip" {
  description         = "rip ${var.environment} encryption key"
  enable_key_rotation = true
}

module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 20.31"
  cluster_name    = "rip-${var.environment}"
  cluster_version = var.eks_version
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  enable_irsa     = true
  cluster_encryption_config = { resources = ["secrets"], provider_key_arn = aws_kms_key.rip.arn }
  eks_managed_node_groups = merge({
    app = { instance_types = ["m6i.large"], min_size = 2, max_size = 8, desired_size = 3 }
  }, var.enable_gpu_inference ? {
    gpu = {
      instance_types = ["g6e.12xlarge"], ami_type = "AL2_x86_64_GPU", min_size = 0, max_size = 2, desired_size = 1
      labels = { workload = "gpu-inference" }
      taints = { gpu = { key = "nvidia.com/gpu", value = "true", effect = "NO_SCHEDULE" } }
    }
  } : {})
}

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_security_group" "db" {
  name   = "rip-${var.environment}-db"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_db_parameter_group" "pg" {
  name   = "rip-${var.environment}-pg16"
  family = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

# RDS PostgreSQL 16 supports the pgvector extension (CREATE EXTENSION vector, run by the first migration).
resource "aws_db_instance" "pg" {
  identifier                   = "rip-${var.environment}"
  engine                       = "postgres"
  engine_version               = "16.4"
  instance_class               = var.db_instance_class
  allocated_storage            = 100
  max_allocated_storage        = 1000
  db_name                      = "rip"
  username                     = "rip"
  password                     = random_password.db.result
  db_subnet_group_name         = module.vpc.database_subnet_group_name
  vpc_security_group_ids       = [aws_security_group.db.id]
  parameter_group_name         = aws_db_parameter_group.pg.name
  storage_encrypted            = true
  kms_key_id                   = aws_kms_key.rip.arn
  multi_az                     = var.environment == "production"
  backup_retention_period      = var.environment == "production" ? 30 : 7
  deletion_protection          = var.environment == "production"
  performance_insights_enabled = true
  copy_tags_to_snapshot        = true
  skip_final_snapshot          = var.environment != "production"
  final_snapshot_identifier    = "rip-${var.environment}-final"
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "rip-${var.environment}"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "rip-${var.environment}"
  description                = "rip rate limiting / cache"
  engine                     = "redis"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = var.environment == "production" ? 2 : 1
  automatic_failover_enabled = var.environment == "production"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}

resource "aws_s3_bucket" "documents" {
  bucket = "rip-${var.environment}-documents-${data.aws_caller_identity.me.account_id}"
}
data "aws_caller_identity" "me" {}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.rip.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    id     = "retention"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

resource "aws_ecr_repository" "repo" {
  for_each             = toset(["rip-api", "rip-mcp", "rip-web"])
  name                 = each.key
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name       = "rip/${var.environment}"
  kms_key_id = aws_kms_key.rip.arn
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL = "postgresql+psycopg://rip:${random_password.db.result}@${aws_db_instance.pg.address}:5432/rip?sslmode=require"
    REDIS_URL    = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
    JWT_SECRET   = random_password.jwt.result
    S3_BUCKET    = aws_s3_bucket.documents.bucket
  })
  lifecycle { ignore_changes = [secret_string] }   # model API keys are added out-of-band
}
