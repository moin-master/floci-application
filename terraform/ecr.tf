# ---------- ECR: image registry for the API ----------
resource "aws_ecr_repository" "api" {
  name                 = "stock-api"
  force_delete         = true
  image_tag_mutability = "MUTABLE"
}
