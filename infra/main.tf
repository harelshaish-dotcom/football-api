terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
    tls = { source = "hashicorp/tls", version = "~> 4.0" }
  }

  backend "s3" {
    bucket       = "football-api-tfstate-246332569326"
    key          = "infra/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  github_owner = split("/", var.github_repository)[0]
  github_repo  = split("/", var.github_repository)[1]

  # GitHub is moving the OIDC `sub` claim to an immutable form that embeds
  # numeric IDs, so a rename cannot hand someone else your trust:
  #   repo:OWNER@OWNER_ID/REPO@REPO_ID:ref:refs/heads/main
  # Both forms are listed so the role works whichever one GitHub emits.
  oidc_subjects = [
    "repo:${var.github_repository}:*",
    "repo:${local.github_owner}@${var.github_owner_id}/${local.github_repo}@${var.github_repository_id}:*",
  ]
}

# The two roles the ECS console already created. Looked up, not created, so
# Terraform fails with a clear message if a name is wrong.
data "aws_iam_role" "ecs_task_execution" {
  name = var.ecs_task_execution_role_name
}

data "aws_iam_role" "ecs_infrastructure" {
  name = var.ecs_infrastructure_role_name
}

# Fetch GitHub's certificate instead of hardcoding a thumbprint that rotates.
data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

# Who may assume the role: only workflow runs from your repository.
data "aws_iam_policy_document" "github_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Without this condition ANY GitHub repo on earth could assume the role.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.oidc_subjects
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "github-actions-ecs-role"
  description        = "Assumed by GitHub Actions to build and deploy football-api"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role.json
}

data "aws_iam_policy_document" "ecr_push" {
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this call is account-wide and cannot be scoped to one repo
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [
      "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${var.ecr_repository}"
    ]
  }
}

resource "aws_iam_policy" "ecr_push" {
  name   = "GitHubActionsECRPolicy"
  policy = data.aws_iam_policy_document.ecr_push.json
}

data "aws_iam_policy_document" "ecs_deploy" {
  statement {
    effect = "Allow"
    actions = [
      "ecs:CreateCluster",
      "ecs:RegisterTaskDefinition",
      "ecs:CreateExpressGatewayService",
      "ecs:UpdateExpressGatewayService",
      "ecs:DescribeExpressGatewayService",
      "ecs:DescribeClusters",
      "ecs:DescribeServices",
      "ecs:ListServiceDeployments",
      "ecs:UpdateService",
      "ecs:DescribeServiceDeployments",
    ]
    resources = ["*"]
  }

  # Handing a role to another service is itself a permission. Scoped to the two
  # roles Express Mode needs, and only when ECS is the one receiving them.
  statement {
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = [
      data.aws_iam_role.ecs_task_execution.arn,
      data.aws_iam_role.ecs_infrastructure.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "ecs_deploy" {
  name   = "GitHubActionsECSExpressPolicy"
  policy = data.aws_iam_policy_document.ecs_deploy.json
}

resource "aws_iam_role_policy_attachment" "ecr_push" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.ecr_push.arn
}

resource "aws_iam_role_policy_attachment" "ecs_deploy" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.ecs_deploy.arn
}

# ---------------------------------------------------------------------------
# S3 bucket for user uploads
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "uploads" {
  bucket = var.uploads_bucket
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Private by default. Serve files through presigned URLs rather than making
# the bucket public — a public bucket is the classic way user uploads leak.
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Permissions so GitHub Actions can run Terraform itself
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "terraform" {
  # Remote state, plus the .tflock file that use_lockfile creates.
  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.state_bucket}"]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::${var.state_bucket}/infra/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }

  # Reading and updating the IAM resources this configuration owns.
  # Deliberately no Delete* actions: CI must not be able to destroy the very
  # role it authenticates with, or the OIDC provider behind it.
  statement {
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListRoleTags",
      "iam:GetOpenIDConnectProvider",
      "iam:CreateRole",
      "iam:UpdateRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:TagRole",
      "iam:CreatePolicy",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicyVersion",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:CreateOpenIDConnectProvider",
      "iam:TagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = ["*"]
  }

  # Scoped to this one bucket by resource rather than by action. Enumerating
  # every s3:Get*Configuration the provider reads on refresh is a losing game.
  statement {
    effect  = "Allow"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${var.uploads_bucket}",
      "arn:aws:s3:::${var.uploads_bucket}/*",
    ]
  }
}

resource "aws_iam_policy" "terraform" {
  name   = "GitHubActionsTerraformPolicy"
  policy = data.aws_iam_policy_document.terraform.json
}

resource "aws_iam_role_policy_attachment" "terraform" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.terraform.arn
}