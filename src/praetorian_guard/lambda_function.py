import json
import logging
import os
import boto3

# --- Configuration ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
SSM_CLIENT = boto3.client("ssm")

# This mapping is the core logic.
# It maps a failed Control ID to its corresponding SSM Automation Document.
REMEDIATION_PLAYBOOK_MAP = {
    "NIST-800-53-CM-6": "PraetoriumNexus-CM-6-S3-Public-Access-Fix",
    # Add other control-to-playbook mappings here
    # "NIST-800-53-AC-2": "PraetoriumNexus-AC-2-IAM-User-Cleanup",
}

# --- Logging ---
logger = logging.getLogger("praetorian_guard")
logger.setLevel(LOG_LEVEL)

def lambda_handler(event, context):
    """
    Handles SQS messages from KSI_Engine containing CCE payloads.
    Parses the payload and triggers the correct remediation playbook.
    """
    logger.info(f"Received {len(event.get('Records', []))} event record(s).")

    for record in event.get("Records", []):
        try:
            cce_payload = json.loads(record.get("body", "{}"))

            # Log CCE payload for auditability
            logger.info(f"Processing CCE payload: {json.dumps(cce_payload)}")

            control_id = cce_payload.get("control_id")
            target_id = cce_payload.get("target_id")
            status = cce_payload.get("status")

            # Only act on "FAIL" status
            if status != "FAIL":
                logger.info(f"Skipping payload for {target_id} with status '{status}'. No action needed.")
                continue

            # Find the correct playbook
            playbook_name = REMEDIATION_PLAYBOOK_MAP.get(control_id)
            if not playbook_name:
                logger.error(f"No remediation playbook found for control_id '{control_id}'. Cannot remediate.")
                continue

            # Get the target parameter (e.g., S3 Bucket ARN)
            # The target_id is often the resource ARN. The playbook will need
            # a specific parameter, like just the bucket name.
            # For S3 ARN: "arn:aws:s3:::<bucket-name>"
            if target_id and target_id.startswith("arn:aws:s3:::"):
                target_param = {"BucketName": [target_id.split(":::")[-1]]}
            else:
                logger.error(f"Could not parse target_id '{target_id}' into a valid parameter.")
                continue

            logger.warning(f"Executing remediation playbook '{playbook_name}' for target '{target_id}'...")

            # --- AUTOMATED ENFORCEMENT (KSI-CNA-08) ---
            response = SSM_CLIENT.start_automation_execution(
                DocumentName=playbook_name,
                Parameters=target_param,
                Tags=[
                    {"Key": "TriggeredBy", "Value": "Praetorian_Guard_Lambda"},
                    {"Key": "ControlID", "Value": control_id},
                    {"Key": "TargetID", "Value": target_id}
                ]
            )
            # --- End Enforcement ---

            logger.info(f"Successfully triggered automation. ExecutionId: {response['AutomationExecutionId']}")

        except json.JSONDecodeError:
            logger.error(f"Failed to decode SQS message body: {record.get('body')}")
        except Exception as e:
            logger.error(f"Error processing record: {e}", exc_info=True)
            # Do not re-raise, as this would cause the SQS message to be re-processed indefinitely.
            # The SQS queue should be configured with a Dead-Letter Queue (DLQ)
            # to handle persistent failures.

    return {
        "statusCode": 200,
        "body": "Processing complete."
    }
