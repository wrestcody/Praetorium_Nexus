import json
import logging
import os
import boto3

# --- Configuration ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
SSM_CLIENT = boto3.client("ssm")

# This mapping is the core logic.
# It maps a Control ID to its required SSM playbook and Execution Role ARN
REMEDIATION_PLAYBOOK_MAP = {
    "NIST-800-53-CM-6": {
        "DocumentName": "PraetoriumNexus-CM-6-S3-Public-Access-Fix",
        "RoleEnvVar": "CM6_S3_EXECUTION_ROLE_ARN"
    },
    # "NIST-800-53-AC-2": {
    #     "DocumentName": "PraetoriumNexus-AC-2-IAM-User-Cleanup",
    #     "RoleEnvVar": "AC2_IAM_EXECUTION_ROLE_ARN"
    # },
}

# --- Logging ---
logger = logging.getLogger("praetorian_guard")
logger.setLevel(LOG_LEVEL)

def lambda_handler(event, context):
    """
    Handles SQS messages from KSI_Engine containing CCE payloads.
    Parses the payload and triggers the correct remediation playbook
    using its specific, least-privilege IAM role.
    """
    logger.info(f"Received {len(event.get('Records', []))} event record(s).")

    for record in event.get("Records", []):
        try:
            cce_payload = json.loads(record.get("body", "{}"))
            logger.info(f"Processing CCE payload: {json.dumps(cce_payload)}")

            control_id = cce_payload.get("control_id")
            target_id = cce_payload.get("target_id")
            status = cce_payload.get("status")

            if status != "FAIL":
                logger.info(f"Skipping payload for {target_id} with status '{status}'. No action needed.")
                continue

            # --- Find the correct playbook and its execution role ---
            playbook_info = REMEDIATION_PLAYBOOK_MAP.get(control_id)
            if not playbook_info:
                logger.error(f"No remediation playbook found for control_id '{control_id}'. Cannot remediate.")
                continue

            playbook_name = playbook_info["DocumentName"]
            role_env_var = playbook_info["RoleEnvVar"]
            automation_assume_role_arn = os.environ.get(role_env_var)

            if not automation_assume_role_arn:
                logger.error(f"Environment variable '{role_env_var}' not set for playbook '{playbook_name}'. Cannot execute.")
                continue
            # --- End role lookup ---

            if target_id and target_id.startswith("arn:aws:s3:::"):
                target_param = {"BucketName": [target_id.split(":::")[-1]]}
            else:
                logger.error(f"Could not parse target_id '{target_id}' into a valid parameter.")
                continue

            logger.warning(f"Executing remediation playbook '{playbook_name}' for target '{target_id}'...")

            # --- AUTOMATED ENFORCEMENT (KSI-CNA-08) ---
            response = SSM_CLIENT.start_automation_execution(
                DocumentName=playbook_name,
                Parameters={
                    **target_param,
                    "AutomationAssumeRole": [automation_assume_role_arn] # Pass the execution role
                },
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

    return {
        "statusCode": 200,
        "body": "Processing complete."
    }
