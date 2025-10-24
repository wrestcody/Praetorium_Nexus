# -----------------------------------------------------------------------------
# Input Variables
#
# This file defines the input variables for the Terraform module.
# These variables allow for the customization of the deployment without
# modifying the core infrastructure code.
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
