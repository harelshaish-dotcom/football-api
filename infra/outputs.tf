output "github_actions_role_arn" {
  description = "Goes into the workflow as role-to-assume"
  value       = aws_iam_role.github_actions.arn
}

output "ecs_task_execution_role_arn" {
  value = data.aws_iam_role.ecs_task_execution.arn
}

output "ecs_infrastructure_role_arn" {
  value = data.aws_iam_role.ecs_infrastructure.arn
}
