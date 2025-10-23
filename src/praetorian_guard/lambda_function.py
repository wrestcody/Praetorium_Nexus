import json
import logging
import os
import boto3

# --- Configuration ---
# Set up logging for clear, actionable output. The log level is configurable
# via a Lambda environment variable, defaulting to "INFO".
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("praetorian_guard")
logger.setLevel(LOG_LEVEL)

# Initialize the AWS SDK client for Systems Manager (SSM).
# This client is reused for all invocations of the function in the same execution environment.
SSM_CLIENT = boto3.client("ssm")

# This mapping is the core logic of the AER Engine. It acts as a router,
# mapping a specific, failed compliance control ID (e.g., from NIST 800-53)
# to its corresponding remediation playbook. Each entry specifies:
#   - "DocumentName": The name of the AWS SSM Automation Document to execute.
#   - "RoleEnvVar": The name of the environment variable that holds the ARN
#                   of the least-privilege IAM role for that specific playbook.
REMEDIATION_PLAYBOOK_MAP = {
    "NIST-800-53-CM-6": {
        "DocumentName": "PraetoriumNexus-CM-6-S3-Public-Access-Fix",
        "RoleEnvVar": "CM6_S3_EXECUTION_ROLE_ARN"
    },
    # Example of how to extend the engine with another playbook:
    # "NIST-800-53-AC-2": {
    #     "DocumentName": "PraetoriumNexus-AC-2-IAM-User-Cleanup",
    #     "RoleEnvVar": "AC2_IAM_EXECUTION_ROLE_ARN"
    # },
}

def lambda_handler(event, context):
    """
    Handles compliance failure notifications from an SQS queue.

    This function is triggered by messages from the KSI_Engine. It parses the
    compliance failure payload (CCE format), identifies the failed control and
    the target resource, and then triggers the correct, pre-approved SSM
    Automation Document to perform remediation.

    The function is designed to be idempotent and resilient. It only acts on
    messages with a "FAIL" status and includes robust error handling to prevent
    infinite reprocessing of malformed messages, recommending the use of a
    Dead-Letter Queue (DLQ) for the source SQS queue.

    Args:
        event (dict): The event payload from the SQS trigger. Expected to contain
                      one or more records, each with a 'body' that is a JSON
                      string in the CCE (Compliance Check Engine) format.
        context (object): The Lambda runtime information. Not used in this function.

    Returns:
        dict: A response object with a status code and a body, indicating
              that the processing is complete.
    """
    logger.info(f"Received {len(event.get('Records', []))} event record(s).")

    # Process each message from the SQS batch.
    for record in event.get("Records", []):
        try:
            # The message body from SQS is a JSON string, so it must be parsed.
            cce_payload = json.loads(record.get("body", "{}"))
            logger.info(f"Processing CCE payload: {json.dumps(cce_payload)}")

            # Extract key information from the compliance payload.
            control_id = cce_payload.get("control_id")
            target_id = cce_payload.get("target_id") # The resource that failed the check.
            status = cce_payload.get("status")

            # The engine's primary function is to act on failures. Ignore other statuses.
            if status != "FAIL":
                logger.info(f"Skipping payload for {target_id} with status '{status}'. No action needed.")
                continue

            # --- Dynamic Playbook and Role Lookup ---
            # Use the control_id to find the correct playbook and its execution role from the map.
            playbook_info = REMEDIATION_PLAYBOOK_MAP.get(control_id)
            if not playbook_info:
                logger.error(f"No remediation playbook found for control_id '{control_id}'. Cannot remediate.")
                continue

            playbook_name = playbook_info["DocumentName"]
            role_env_var = playbook_info["RoleEnvVar"]
            # Retrieve the specific, least-privilege role ARN from the Lambda's environment variables.
            automation_assume_role_arn = os.environ.get(role_env_var)

            if not automation_assume_role_arn:
                logger.error(f"Environment variable '{role_env_var}' not set for playbook '{playbook_name}'. Cannot execute.")
                continue
            # --- End Lookup ---

            # --- Parameter Parsing ---
            # This section translates the generic 'target_id' from the CCE payload
            # into the specific named parameter that the SSM document expects.
            if target_id and target_id.startswith("arn:aws:s3:::"):
                # Example: "arn:aws:s3:::my-test-bucket" -> {"BucketName": ["my-test-bucket"]}
                target_param = {"BucketName": [target_id.split(":::")[-1]]}
            else:
                logger.error(f"Could not parse target_id '{target_id}' into a valid parameter for any known playbook.")
                continue

            logger.warning(f"Executing remediation playbook '{playbook_name}' for target '{target_id}'...")

            # --- AUTOMATED ENFORCEMENT (KSI-CNA-08) ---
            # Trigger the SSM Automation Document. The 'AutomationAssumeRole' is a critical
            # security control, ensuring the playbook runs with only the permissions
            # defined in its dedicated role, not the Lambda's broader permissions.
            response = SSM_CLIENT.start_automation_execution(
                DocumentName=playbook_name,
                Parameters={
                    **target_param,
                    "AutomationAssumeRole": [automation_assume_role_arn] # Pass the dedicated execution role
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
            logger.error(f"An unexpected error occurred while processing record: {e}", exc_info=True)
            # Do not re-raise. This prevents the message from being re-processed
            # and potentially causing an infinite loop. The SQS queue's DLQ
            # should be configured to capture these failed messages for analysis.

    return {
        "statusCode": 200,
        "body": "Processing complete."
    }
