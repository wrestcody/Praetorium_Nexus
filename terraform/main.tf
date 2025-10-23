terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.3"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# IAM Role and Policy for AER Lambda
# -----------------------------------------------------------------------------

resource "aws_iam_role" "praetorian_guard_role" {
  name               = "praetorian_guard_lambda_role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json
  tags               = var.tags
}

resource "aws_iam_policy" "praetorian_guard_policy" {
  name        = "praetorian_guard_lambda_policy"
  description = "Least privilege policy for the AER Lambda to read SQS and trigger SSM remediations."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Required for CloudWatch Logging
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws-us-gov:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/praetorian_guard_lambda:*"
      },
      {
        # Required for the SQS Event Source Mapping
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.ksi_engine_sqs_queue_arn
      },
      {
        # Required to trigger the GRC-as-Code remediation playbooks
        Effect = "Allow"
        Action = "ssm:StartAutomationExecution"
        # Scoped to only allow execution of documents tagged for GRC
        Resource = "arn:aws-us-gov:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:automation-definition/*"
        Condition = {
          StringEquals = {
            "ssm:AutomationDefinitionSource" = "OwnedByMe"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "praetorian_guard_attach" {
  role       = aws_iam_role.praetorian_guard_role.name
  policy_arn = aws_iam_policy.praetorian_guard_policy.arn
}

# -----------------------------------------------------------------------------
# AER Lambda Function
# -----------------------------------------------------------------------------

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "../src/praetorian_guard"
  output_path = "praetorian_guard.zip"
}

resource "aws_lambda_function" "praetorian_guard_lambda" {
  function_name    = "praetorian_guard_lambda"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  role             = aws_iam_role.praetorian_guard_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  tags             = var.tags

  environment {
    variables = {
      LOG_LEVEL = "INFO"
      # --- Add this line ---
      CM6_S3_EXECUTION_ROLE_ARN = aws_iam_role.cm6_s3_fix_execution_role.arn
    }
  }
}

# -----------------------------------------------------------------------------
# SQS Event Source Mapping (The Trigger)
# -----------------------------------------------------------------------------

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = var.ksi_engine_sqs_queue_arn
  function_name    = aws_lambda_function.praetorian_guard_lambda.arn
  batch_size       = 1 # Process one failure at a time
}

# -----------------------------------------------------------------------------
# GRC-as-Code Playbook Execution Roles
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ssm_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ssm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cm6_s3_fix_execution_role" {
  name               = "PraetoriumNexus-CM6-S3-Fix-Role"
  assume_role_policy = data.aws_iam_policy_document.ssm_assume_role_policy.json
  tags = merge(var.tags, {
    "Playbook" = "cm-6_s3_public_access_fix"
  })
}

resource "aws_iam_policy" "cm6_s3_fix_policy" {
  name        = "PraetoriumNexus-CM6-S3-Fix-Policy"
  description = "Grants *only* the permission to apply S3 public access blocks."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:PutBucketPublicAccessBlock"
        Resource = "arn:aws-us-gov:s3:::*" # S3 requires * for this action
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cm6_s3_fix_attach" {
  role       = aws_iam_role.cm6_s3_fix_execution_role.name
  policy_arn = aws_iam_policy.cm6_s3_fix_policy.arn
}

# -----------------------------------------------------------------------------
# Terraform Outputs
# -----------------------------------------------------------------------------

output "cm6_s3_fix_execution_role_arn" {
  description = "The ARN of the IAM role for the CM-6 SSM playbook."
  value       = aws_iam_role.cm6_s3_fix_execution_role.arn
}
