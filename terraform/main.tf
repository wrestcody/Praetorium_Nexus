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
# Variables
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "The AWS region to deploy resources in."
  type        = string
  default     = "us-gov-west-1"
}

variable "ksi_engine_sqs_queue_arn" {
  description = "The ARN of the SQS queue that the KSI_Engine sends failure messages to."
  type        = string
  # This ARN will be provided by the KSI_Engine's output
}

variable "tags" {
  description = "A map of tags to assign to all resources."
  type        = map(string)
  default = {
    "Project"     = "Praetorium_Nexus"
    "Environment" = "GRC-Automation"
    "ManagedBy"   = "Terraform"
  }
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
