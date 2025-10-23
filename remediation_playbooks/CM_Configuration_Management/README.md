# Playbook: CM-6 S3 Public Access Fix

This directory contains the GRC-as-Code playbook for remediating failures related to **NIST 800-53 Control CM-6 (Configuration Management)**, specifically for S3 buckets with public access enabled.

## `cm-6_s3_public_access_fix.yml`

This AWS SSM Automation Document ensures that a target S3 bucket has the "Block all public access" setting enabled. It is a critical security control to prevent unintentional data exposure.

### Playbook Details

-   **Schema Version:** `0.3`
-   **Action:** `aws:executeAwsApi`
-   **API Call:** `s3:PutPublicAccessBlock`

### Parameters

The playbook requires the following parameters to be passed during execution:

| Parameter Name           | Type   | Description                                                                                                                              |
| ------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `BucketName`             | String | (Required) The name of the S3 bucket to remediate (e.g., `my-insecure-bucket`).                                                          |
| `AutomationAssumeRole`   | String | (Required) The ARN of the IAM role that SSM will assume to execute the playbook's actions. This role must have the permissions listed below. |

### Required IAM Permissions

The IAM role specified in `AutomationAssumeRole` **must** have the following permission to successfully execute this playbook:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:PutBucketPublicAccessBlock",
            "Resource": "arn:aws-us-gov:s3:::*"
        }
    ]
}
```

This ensures the principle of least privilege. The execution role only has the permission to fix the specific misconfiguration it is designed to address. The Terraform configuration in this repository automatically creates a compliant role named `PraetoriumNexus-CM6-S3-Fix-Role`.
