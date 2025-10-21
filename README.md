# Praetorium_Nexus

Praetorium_Nexus is the strategic command post for the GRC-Copilot ecosystem. It serves as a secure single source of truth, an API ingestion hub, and a risk visualization platform.

## Three-Part Architecture

The GRC-Copilot ecosystem consists of three components:

1.  **KSI_Engine**: The source of compliance data.
2.  **Vanguard_Agent**: Enriches the compliance data with AI-powered risk scoring and natural language summaries.
3.  **Praetorium_Nexus**: Ingests the enriched data from the Vanguard_Agent and provides a centralized platform for visualizing and managing risk.

Praetorium_Nexus is designed to support FedRAMP ATOs by providing continuously verified, auditable data.

## Deployment

The application is designed to be deployed to AWS Fargate using the Terraform configuration in the `deployment` directory.

### Security Rationale

The deployment is configured with security in mind:

*   **Least Privilege IAM Role**: The ECS task is assigned a least-privilege IAM role that only grants the necessary permissions for CloudWatch logging and networking.
*   **Secrets Management**: The API keys are stored in environment variables within the task definition. In a production environment, this should be integrated with AWS Secrets Manager for enhanced security.
