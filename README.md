# Praetorium\_Nexus: Automated Enforcement & Remediation (AER) Engine

`Praetorium_Nexus` is the automated enforcement and remediation component of the FedRAMP GRC ecosystem. It fulfills the **KSI-CNA-08** mandate (*Use automated services to... automatically enforce secure operations*).

This repository listens for "compliance drift" signals from producers (like `KSI_Engine`) and automatically executes GRC-as-Code playbooks to return systems to a known-good state.

This project demonstrates the "build-first" GRC Engineering philosophy by treating compliance remediation as a solvable engineering problem, automated via code.

## Core Mission & Architecture

1.  **Receive:** An SQS Queue (provisioned by `KSI_Engine`) receives a CCE JSON payload when a compliance check *fails*.
2.  **Triage:** An `aws_lambda_event_source_mapping` triggers the `praetorian_guard_lambda` (defined in `/terraform/main.tf`).
3.  **Execute:** The Lambda (defined in `/src/praetorian_guard`) parses the CCE payload, identifies the failed `control_id`, and maps it to the correct SSM Automation Document.
4.  **Enforce:** The Lambda triggers an `ssm:StartAutomationExecution` call, passing the `target_id` (e.g., the S3 bucket name) to the playbook.
5.  **Audit:** The playbook (e.g., `cm-6_s3_public_access_fix.yml`) executes with a least-privilege IAM role to fix the misconfiguration. All actions are logged in CloudWatch and SSM Automation history for a complete audit trail.

![Praetorium Nexus Architecture Diagram](https://i.imgur.com/example-architecture-diagram.png) *(Note: Placeholder for architecture diagram)*

## GRC-as-Code Playbook Directory

All remediation playbooks are stored as AWS SSM Automation Documents (YAML) and organized by their corresponding NIST 800-53 control family. This provides a "control-to-code" mapping that is auditable, version-controlled, and testable.

```

/remediation\_playbooks
├── AC\_Access\_Control/
│   └── ac-2\_iam\_user\_cleanup.yml
├── CM\_Configuration\_Management/
│   └── cm-6\_s3\_public\_access\_fix.yml
├── SC\_System\_Communications\_Protection/
...

```

## Deployment

This engine is deployed via Terraform.

1.  Ensure the `ksi_engine_sqs_queue_arn` variable in `terraform/main.tf` is set to the output ARN from the `KSI_Engine` deployment.
2.  Run `terraform init` and `terraform apply` from within the `/terraform` directory.
3.  The remediation playbooks (SSM Documents) must be deployed separately (e.g., via a CI/CD pipeline or a separate Terraform configuration).
