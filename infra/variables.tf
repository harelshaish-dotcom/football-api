variable "aws_region" {
  type        = string
  description = "Region the ECR repo and ECS service live in"
  default     = "eu-central-1"
}

variable "github_repository" {
  type        = string
  description = "owner/repo allowed to assume the deploy role"
  default     = "harelshaish-dotcom/football-api"
}

variable "ecr_repository" {
  type        = string
  description = "ECR repository the pipeline pushes images to"
  default     = "football-api"
}

variable "ecs_task_execution_role_name" {
  type        = string
  description = "Existing role ECS uses to pull images and write logs"
  default     = "ecsTaskExecutionRole"
}

variable "ecs_infrastructure_role_name" {
  type        = string
  description = "Existing role Express Mode uses to manage the ALB and networking"
  default     = "ecsInfrastructureRoleForExpressServices"
}

variable "github_owner_id" {
  type        = number
  description = "Numeric GitHub user/org ID, used in the immutable OIDC subject claim"
  default     = 234176880
}

variable "github_repository_id" {
  type        = number
  description = "Numeric GitHub repository ID, used in the immutable OIDC subject claim"
  default     = 1346615291
}
