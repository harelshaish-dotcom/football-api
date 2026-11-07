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
