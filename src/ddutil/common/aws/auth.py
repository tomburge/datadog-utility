#########################################################################################
### Imports
#########################################################################################
import boto3  # type: ignore
from ..logs import logger


#########################################################################################
### Authentication
#########################################################################################
def assume_role(
    session,
    role_arn,
    role_session_name,
    duration_seconds=3600,
    external_id=None,
):
    """
    Assumes an IAM role in a different AWS account and returns a new session.

    Parameters:
        session (boto3.Session): The current Boto3 session used to assume the role.
        role_arn (str): The ARN of the role to assume.
        role_session_name (str): An identifier for the assumed role session.
        duration_seconds (int, optional): The duration, in seconds, for the assumed role session. Defaults to 3600 (1 hour).
        external_id (str, optional): An optional external ID to provide when assuming the role.

    Returns:
        boto3.Session: A new Boto3 session using the assumed role credentials.
    """
    try:
        # STS Client
        sts_client = session.client("sts")

        # Assume Role Parameters
        assume_role_params = {
            "RoleArn": role_arn,
            "RoleSessionName": role_session_name,
            "DurationSeconds": duration_seconds,
        }

        if external_id:
            assume_role_params["ExternalId"] = external_id

        # Assume Role
        response = sts_client.assume_role(**assume_role_params)

        # Extract Credentials
        credentials = response["Credentials"]

        # Create Boto3 Session
        assumed_session = create_session(
            access_key=credentials["AccessKeyId"],
            secret_key=credentials["SecretAccessKey"],
            session_token=credentials["SessionToken"],
        )

        return assumed_session
    except Exception as e:
        logger.error(f"Failed to assume role {role_arn}: {e}")


#########################################################################################
### Create Boto3 Client
#########################################################################################
def create_client(region_name=None, service_name=None, session=None):
    """
    Creates a reusable Boto3 client, optionally using a specified session.

    Parameters:
        service_name (str): The name of the AWS service (e.g., 's3', 'ec2').
        region_name (str, optional): The AWS region (e.g., 'us-east-1'). Defaults to None.
        session (boto3.Session, optional): An optional Boto3 Session object. If not provided, the default session is used.

    Returns:
        boto3.Client: A Boto3 client for the specified service.
    """
    try:
        if not service_name:
            raise ValueError("Service name is required")
        if session:
            # Use the provided session to create the client
            client = session.client(service_name, region_name=region_name)
        else:
            # Use the default session
            client = boto3.client(service_name, region_name=region_name)
        return client
    except Exception as e:
        logger.error(f"Failed to create Boto3 client for {service_name}: {e}")


#########################################################################################
### Create Boto3 Session
#########################################################################################
def create_session(
    access_key: str | None = None,
    profile_name: str | None = None,
    region_name: str | None = None,
    secret_key: str | None = None,
    session_token: str | None = None,
):
    """
    Creates a Boto3 session based on the provided method of authentication.

    Parameters:
        profile_name (str, optional): The AWS CLI profile name to use. Defaults to None.
        access_key (str, optional): The AWS access key ID. Defaults to None.
        secret_key (str, optional): The AWS secret access key. Defaults to None.
        session_token (str, optional): The AWS session token for temporary credentials. Defaults to None.
        region_name (str, optional): The AWS region name. Defaults to None.

    Returns:
        boto3.Session: A Boto3 session object configured with the specified parameters.
    """
    try:
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
        elif access_key and secret_key:
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=region_name,
            )
        else:
            # Use the default session
            session = boto3.Session()
        return session
    except Exception as e:
        logger.error(f"Failed to create Boto3 session: {e}")
