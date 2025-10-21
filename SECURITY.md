# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it to us by emailing `security@example.com`. We will investigate all reports and do our best to address them in a timely manner.

## Secret Management

The API key is currently stored in the `app/auth.py` file. In a production environment, this would be stored securely in a secret management system, such as HashiCorp Vault or AWS Secrets Manager.

## Secure and Auditable API

The API is secured using an API key, which must be included in the `X-API-Key` header of all requests. All transactions are logged for audit purposes.
