output "cluster_name" { value = module.eks.cluster_name }
output "db_endpoint" { value = aws_db_instance.pg.address }
output "documents_bucket" { value = aws_s3_bucket.documents.bucket }
output "secret_name" { value = aws_secretsmanager_secret.app.name }
output "ecr_repositories" { value = { for k, r in aws_ecr_repository.repo : k => r.repository_url } }
