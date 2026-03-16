#########################################################################################
### Imports
#########################################################################################
import json
from botocore.exceptions import ClientError  # type: ignore
from ..logs import logger


#########################################################################################
### Functions
#########################################################################################
def attach_policies_to_role(
    client,
    managed_policies: list[str],
    role_name: str,
) -> bool:
    status = True
    for policy_arn in managed_policies:
        try:
            client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            logger.debug(
                f"Successfully attached policy {policy_arn} to role {role_name}"
            )
        except ClientError as e:
            logger.error(
                f"Failed to attach policy {policy_arn} to role {role_name}: {e}"
            )
            status = False
    return status


def build_policy_document(
    actions: list[str],
    effect: str,
    resources: list[str],
) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": effect.capitalize(),
                "Action": actions,
                "Resource": resources,
            }
        ],
    }


def build_trust_policy_document(
    account_id: str,
    actions: list[str] = ["sts:AssumeRole"],
    resource: str = "root",
) -> dict:
    statements: list[dict] = [
        {
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{account_id}:{resource}"},
            "Action": actions,
        }
    ]
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": statements,
    }
    return trust_policy


def create_role(
    client,
    role_name: str,
    trust_policy: dict,
) -> bool:
    try:
        client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )
        logger.debug(f"Successfully created role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to create role {role_name}: {e}")
        return False


def delete_role(client, role_name: str) -> bool:
    try:
        client.delete_role(RoleName=role_name)
        logger.debug(f"Successfully deleted role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete role {role_name}: {e}")
        return False


def get_role(client, role_name: str):
    """Get role details. Returns role dict if exists, None otherwise."""
    try:
        response = client.get_role(RoleName=role_name)
        logger.debug(f"Role exists: {role_name}")
        return response.get("Role")
    except client.exceptions.NoSuchEntityException as e:
        logger.debug(f"Role does not exist: {role_name}")
        return None
    except ClientError as e:
        logger.error(f"Failed to get role {role_name}: {e}")
        return None


def update_role_policy(
    client,
    actions: list[str],
    role_name: str,
    policy_name: str = "datadog",
) -> bool:
    try:
        client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(build_policy_document(actions, "Allow", ["*"])),
        )
        logger.debug(f"Successfully updated policy {policy_name} for role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to update policy {policy_name} for role {role_name}: {e}")
        return False


def update_role_trust_policy(
    client,
    role_name: str,
    trust_policy: dict,
) -> bool:
    try:
        client.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust_policy),
        )
        logger.debug(f"Successfully updated role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to update role {role_name}: {e}")
        return False


def create_or_update_dd_role(
    client,
    dd_account_id: str,
    role_name: str,
    external_id: str = "",
    managed_policies: list[str] = [],
    policy_actions: list[str] = [],
    trust_policy_actions: list[str] = ["sts:AssumeRole"],
    trust_policy_resource: str = "root",
) -> bool:
    status = False

    # Check if role exists
    logger.debug(f"Checking if role {role_name} exists")
    role = get_role(client, role_name)

    if role and not external_id:
        logger.debug(f"Role {role_name} already exists, skipping creation")
        return True

    if external_id:
        logger.debug(f"Updating {role_name} trust policy with External ID")
        trust_policy = build_trust_policy_document(
            account_id=dd_account_id,
            actions=trust_policy_actions,
            resource=trust_policy_resource,
        )
        trust_policy["Statement"][0]["Condition"] = {
            "StringEquals": {"sts:ExternalId": external_id}
        }
        logger.debug(
            f"Updated trust policy document: {json.dumps(trust_policy, indent=2)}"
        )
        status = update_role_trust_policy(client, role_name, trust_policy)

    if not status:
        attach_response = False
        create_role_response = False

        # If not, create role with trust policy
        logger.debug("Building trust policy document for role")
        trust_policy = build_trust_policy_document(
            account_id=dd_account_id,
            actions=trust_policy_actions,
            resource=trust_policy_resource,
        )
        logger.debug(f"Trust policy document: {json.dumps(trust_policy, indent=2)}")

        logger.debug(f"Creating role {role_name}...")
        create_role_response = create_role(
            client=client,
            role_name=role_name,
            trust_policy=trust_policy,
        )

        # Attach managed policies to role
        if create_role_response:
            logger.debug(
                f"Attaching {len(managed_policies)} managed policies to role {role_name}"
            )
            attach_response = attach_policies_to_role(
                client=client, managed_policies=managed_policies, role_name=role_name
            )

        if attach_response:
            # Create role policy with necessary permissions
            logger.debug(f"Creating and attaching inline policy to role {role_name}")
            status = update_role_policy(
                client=client,
                actions=policy_actions,
                policy_name="datadog",
                role_name=role_name,
            )

    logger.debug(
        f"Role {role_name} creation/update status: {'IAM Role Complete' if status else 'IAM Role Incomplete'}"
    )

    return status


def list_attached_policies(client, role_name: str) -> list[str]:
    """List all managed policies attached to a role."""
    try:
        response = client.list_attached_role_policies(RoleName=role_name)
        policy_arns = [
            policy["PolicyArn"] for policy in response.get("AttachedPolicies", [])
        ]
        logger.debug(f"Found {len(policy_arns)} attached policies for role {role_name}")
        return policy_arns
    except ClientError as e:
        logger.error(f"Failed to list attached policies for role {role_name}: {e}")
        return []


def detach_all_policies(client, role_name: str) -> bool:
    """Detach all managed policies from a role."""
    try:
        policy_arns = list_attached_policies(client, role_name)
        for policy_arn in policy_arns:
            client.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            logger.debug(f"Detached policy {policy_arn} from role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to detach policies from role {role_name}: {e}")
        return False


def list_inline_policies(client, role_name: str) -> list[str]:
    """List all inline policy names for a role."""
    try:
        response = client.list_role_policies(RoleName=role_name)
        policy_names = response.get("PolicyNames", [])
        logger.debug(f"Found {len(policy_names)} inline policies for role {role_name}")
        return policy_names
    except ClientError as e:
        logger.error(f"Failed to list inline policies for role {role_name}: {e}")
        return []


def get_inline_policy(client, role_name: str, policy_name: str):
    """Get the policy document for an inline policy."""
    try:
        response = client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
        return response.get("PolicyDocument")
    except ClientError as e:
        logger.error(
            f"Failed to get inline policy {policy_name} for role {role_name}: {e}"
        )
        return None


def extract_policy_actions(policy_document: dict | None) -> list[str]:
    """Return a sorted unique list of actions from an IAM policy document."""
    if not policy_document:
        return []

    statements = policy_document.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]

    actions: set[str] = set()
    for statement in statements:
        if not isinstance(statement, dict):
            continue

        statement_actions = statement.get("Action", [])
        if isinstance(statement_actions, str):
            actions.add(statement_actions)
            continue

        if isinstance(statement_actions, list):
            for action in statement_actions:
                if isinstance(action, str):
                    actions.add(action)

    return sorted(actions)


def get_inline_policy_actions(
    client, role_name: str, policy_name: str = "datadog"
) -> list[str]:
    """Return the normalized action list for a role inline policy."""
    policy_document = get_inline_policy(client, role_name, policy_name)
    return extract_policy_actions(policy_document)


def delete_inline_policies(client, role_name: str) -> bool:
    """Delete all inline policies from a role."""
    try:
        policy_names = list_inline_policies(client, role_name)
        for policy_name in policy_names:
            client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            logger.debug(f"Deleted inline policy {policy_name} from role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete inline policies from role {role_name}: {e}")
        return False


def ensure_role_policies(
    client,
    role_name: str,
    managed_policies: list[str],
    policy_actions: list[str],
    policy_name: str = "datadog",
) -> bool:
    """Ensure role has the correct managed and inline policies."""
    # Get currently attached policies
    current_policies = set(list_attached_policies(client, role_name))
    desired_policies = set(managed_policies)

    # Detach policies that shouldn't be there
    policies_to_detach = current_policies - desired_policies
    for policy_arn in policies_to_detach:
        try:
            client.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            logger.debug(f"Detached unwanted policy {policy_arn} from role {role_name}")
        except ClientError as e:
            logger.error(f"Failed to detach policy {policy_arn}: {e}")
            return False

    # Attach missing policies
    policies_to_attach = desired_policies - current_policies
    for policy_arn in policies_to_attach:
        try:
            client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            logger.debug(f"Attached policy {policy_arn} to role {role_name}")
        except ClientError as e:
            logger.error(f"Failed to attach policy {policy_arn}: {e}")
            return False

    # Update inline policy
    return update_role_policy(client, policy_actions, role_name, policy_name)


def get_role_tags(client, role_name: str) -> list[dict]:
    """Get all tags on an IAM role as a list of {"Key": ..., "Value": ...} dicts."""
    try:
        response = client.list_role_tags(RoleName=role_name)
        return response.get("Tags", [])
    except ClientError as e:
        logger.error(f"Failed to get tags for role {role_name}: {e}")
        return []


def sync_role_tags(
    client,
    role_name: str,
    tags: list[dict],
) -> bool:
    """Sync tags on an IAM role.

    Removes any tags not in the desired set and adds/updates all desired tags.
    Tags must be a list of {"Key": ..., "Value": ...} dicts (1-50 entries).
    """
    if not tags:
        return True

    try:
        # Fetch current tags
        response = client.list_role_tags(RoleName=role_name)
        current_tags: dict[str, str] = {
            t["Key"]: t["Value"] for t in response.get("Tags", [])
        }

        desired_keys = {t["Key"] for t in tags}
        keys_to_remove = [k for k in current_tags if k not in desired_keys]

        if keys_to_remove:
            client.untag_role(RoleName=role_name, TagKeys=keys_to_remove)
            logger.debug(f"Removed {len(keys_to_remove)} tags from role {role_name}")

        client.tag_role(RoleName=role_name, Tags=tags)
        logger.debug(f"Applied {len(tags)} tags to role {role_name}")
        return True
    except ClientError as e:
        logger.error(f"Failed to sync tags for role {role_name}: {e}")
        return False


def delete_dd_role(client, role_name: str) -> bool:
    """Delete a DataDog IAM role and all its policies."""
    try:
        # Check if role exists
        role = get_role(client, role_name)
        if not role:
            logger.debug(f"Role {role_name} does not exist, nothing to delete")
            return True

        # Detach all managed policies
        logger.debug(f"Detaching managed policies from role {role_name}")
        if not detach_all_policies(client, role_name):
            return False

        # Delete all inline policies
        logger.debug(f"Deleting inline policies from role {role_name}")
        if not delete_inline_policies(client, role_name):
            return False

        # Delete the role
        logger.debug(f"Deleting role {role_name}")
        return delete_role(client, role_name)

    except ClientError as e:
        logger.error(f"Failed to delete role {role_name}: {e}")
        return False
