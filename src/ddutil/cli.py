"""
DataDog AWS Integration CLI

A command-line interface for managing DataDog AWS integrations.
"""

#########################################################################################
### Imports
#########################################################################################
import os
import sys
import warnings
from pathlib import Path
from typing import Literal, Optional, overload

try:
    from ._version import __version__  # type: ignore
except ImportError:
    __version__ = "0.0.0.dev0"

try:
    from importlib.resources import files
except ImportError:
    # Python < 3.9
    from importlib_resources import files  # type: ignore

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .common.aws.auth import create_client, create_session
from .common.aws.iam import (
    create_or_update_dd_role,
    ensure_role_policies,
    delete_dd_role,
    get_role,
    get_inline_policy_actions,
    get_role_tags,
    list_attached_policies,
    list_inline_policies,
    sync_role_tags,
)
from .common.datadog.aws import crud_dd_account, get_dd_account
from .common.logs import logger
from .common.utils import set_env_variables

# DataDog API imports for status command
import certifi  # type: ignore
from datadog_api_client import Configuration  # type: ignore


#########################################################################################
### Initialize
#########################################################################################
console = Console()

# Default .env loading happens in the cli() group callback so --env-file can override it


#########################################################################################
### Helper Functions
#########################################################################################
def show_license(ctx, param, value):
    """Display license information and exit."""
    if not value or ctx.resilient_parsing:
        return

    console.print(
        "\n[bold cyan]DataDog AWS Integration Utility - License Information[/bold cyan]\n"
    )

    # Try to get license files from installed package, fall back to development path
    license_file = None
    licenses_dir = None
    use_fallback = False

    try:
        # For installed package
        package_files = files("ddutil")
        potential_license = package_files / "LICENSE"
        potential_licenses_dir = package_files / "licenses"

        # Check if files actually exist (for editable installs, files() succeeds but files don't exist there)
        if isinstance(potential_license, Path) and potential_license.exists():
            license_file = potential_license
            licenses_dir = potential_licenses_dir
        else:
            use_fallback = True
    except (TypeError, FileNotFoundError, ModuleNotFoundError, AttributeError):
        use_fallback = True

    if use_fallback:
        # For development (running from source) or editable install
        project_root = Path(__file__).parent.parent.parent
        license_file = project_root / "LICENSE"
        licenses_dir = project_root / "licenses"

    # Display main LICENSE
    try:
        # Try reading as a resource (installed) or file path (development)
        if isinstance(license_file, Path):
            license_content = license_file.read_text(encoding="utf-8")
        elif license_file is not None:
            # importlib.resources Traversable
            license_content = license_file.read_text()
        console.print("[bold green]Main License (MIT):[/bold green]\n")
        console.print(license_content)
        console.print("\n" + "=" * 80 + "\n")
    except (FileNotFoundError, AttributeError, OSError):
        console.print("[yellow]Main LICENSE file not found.[/yellow]\n")

    # Display 3rd party licenses
    console.print("[bold green]Third-Party Licenses:[/bold green]\n")

    try:
        # Try to list license files
        license_files = []
        if isinstance(licenses_dir, Path):
            # For development (pathlib.Path)
            if licenses_dir.exists():
                license_files = sorted(licenses_dir.glob("*"))
        else:
            # For installed package (importlib.resources Traversable)
            try:
                license_files = sorted([f for f in licenses_dir.iterdir() if f.name != "__pycache__"], key=lambda x: x.name)  # type: ignore
            except (AttributeError, OSError):
                pass

        if license_files:
            for lic_file in license_files:
                console.print(f"  • [cyan]{lic_file.name}[/cyan]")

            console.print(f"\nThird-party license files are located in the package.\n")
            console.print(
                "Please review these files for complete license terms of dependencies.\n"
            )
        else:
            console.print(
                "[yellow]No third-party license files found in licenses directory.[/yellow]\n"
            )
    except (FileNotFoundError, AttributeError, OSError):
        console.print("[yellow]No third-party licenses directory found.[/yellow]\n")

    ctx.exit()


@overload
def get_config_value(
    cli_value: Optional[str] = None,
    env_var: Optional[str] = None,
    default: str = ...,
    required: bool = True,
    param_name: str = "parameter",
) -> str: ...


@overload
def get_config_value(
    cli_value: Optional[str] = None,
    env_var: Optional[str] = None,
    default: Optional[str] = None,
    required: Literal[True] = True,
    param_name: str = "parameter",
) -> str: ...


@overload
def get_config_value(
    cli_value: Optional[str] = None,
    env_var: Optional[str] = None,
    default: Optional[str] = None,
    required: Literal[False] = False,
    param_name: str = "parameter",
) -> Optional[str]: ...


def get_config_value(
    cli_value: Optional[str] = None,
    env_var: Optional[str] = None,
    default: Optional[str] = None,
    required: bool = True,
    param_name: str = "parameter",
) -> Optional[str]:
    """Get configuration value from CLI args or environment variables.

    Priority: CLI args > Environment variables > Default value
    """
    # Priority: CLI args > Environment variables > Default
    if cli_value:
        return cli_value

    if env_var and os.getenv(env_var):
        return os.getenv(env_var)

    if default is not None:
        return default

    if required:
        console.print(
            f"[red]Error: Required {param_name} not provided. "
            f"Use CLI flag or set {env_var} environment variable.[/red]"
        )
        sys.exit(1)

    return None


def get_list_config(
    cli_value: Optional[str] = None,
    env_var: Optional[str] = None,
    default: Optional[list] = None,
) -> list:
    """Get list configuration from CLI args (comma-separated) or environment variables."""
    if cli_value:
        return [item.strip() for item in cli_value.split(",") if item.strip()]

    env_value = os.getenv(env_var) if env_var else None
    if env_value:
        return [item.strip() for item in env_value.split(",") if item.strip()]

    return default or []


def get_tags_from_env(
    cli_value: Optional[str] = None,
) -> list[dict]:
    """Parse IAM role tags from CLI arg or DD_IAM_TAGS env var.

    Format: ``Key=Value,Key2=Value2`` (1-50 pairs).
    Returns a list of ``{"Key": ..., "Value": ...}`` dicts consumed by boto3.
    """
    raw = cli_value or os.getenv("DD_IAM_TAGS", "")
    if not raw:
        return []

    tags: list[dict] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            console.print(
                f"[yellow]Warning: Skipping invalid tag (expected Key=Value): {pair!r}[/yellow]"
            )
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            console.print(
                f"[yellow]Warning: Skipping tag with empty key: {pair!r}[/yellow]"
            )
            continue
        tags.append({"Key": key, "Value": value})

    if len(tags) > 50:
        console.print("[red]Error: IAM roles support a maximum of 50 tags.[/red]")
        sys.exit(1)

    return tags


def _configure_logging(verbose: bool, quiet: bool) -> None:
    """Reconfigure loguru based on verbosity flags."""
    if verbose:
        logger.remove()
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time}</green> | <level>{level}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
        )
    elif quiet:
        logger.remove()
        logger.add(
            sys.stderr,
            level="ERROR",
            format="<green>{time}</green> | <level>{level}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
        )


def get_bool_config(
    cli_value: Optional[str] = None,
    env_var: Optional[str] = None,
    default: bool = True,
) -> bool:
    """Get boolean configuration from CLI args or environment variables.

    Accepts: true/false, yes/no, 1/0, on/off (case-insensitive)
    """
    if cli_value is not None:
        return cli_value.lower() in ("true", "yes", "1", "on")

    env_value = os.getenv(env_var) if env_var else None
    if env_value:
        return env_value.lower() in ("true", "yes", "1", "on")

    return default


def get_services_from_env() -> list[str]:
    """Build list of enabled AWS services from DD_SERVICE_* environment variables.

    Returns list of DataDog service names (e.g., 'AWS/Lambda', 'AWS/EC2', 'Glue').
    """
    # Mapping of environment variable suffixes to DataDog service names
    service_mapping = {
        # SageMaker
        "SAGEMAKER_ENDPOINTS": "/aws/sagemaker/Endpoints",
        "SAGEMAKER_PROCESSING_JOBS": "/aws/sagemaker/ProcessingJobs",
        "SAGEMAKER_TRAINING_JOBS": "/aws/sagemaker/TrainingJobs",
        "SAGEMAKER_TRANSFORM_JOBS": "/aws/sagemaker/TransformJobs",
        "SAGEMAKER": "AWS/SageMaker",
        "SAGEMAKER_LABELING_JOBS": "AWS/Sagemaker/LabelingJobs",
        "SAGEMAKER_MODEL_BUILDING_PIPELINE": "AWS/Sagemaker/ModelBuildingPipeline",
        "SAGEMAKER_WORKTEAM": "AWS/SageMaker/Workteam",
        # Amazon Services
        "AMAZON_MWAA": "AmazonMWAA",
        "AMAZON_MQ": "AWS/AmazonMQ",
        # Core AWS Services
        "API_GATEWAY": "AWS/ApiGateway",
        "APPLICATION_ELB": "AWS/ApplicationELB",
        "APP_RUNNER": "AWS/AppRunner",
        "APP_STREAM": "AWS/AppStream",
        "APP_SYNC": "AWS/AppSync",
        "ATHENA": "AWS/Athena",
        "AUTO_SCALING": "AWS/AutoScaling",
        "BACKUP": "AWS/Backup",
        "BEDROCK": "AWS/Bedrock",
        "BILLING": "AWS/Billing",
        "BUDGETING": "AWS/Budgeting",
        # Data Services
        "CASSANDRA": "AWS/Cassandra",
        "DAX": "AWS/DAX",
        "DYNAMODB": "AWS/DynamoDB",
        "ELASTICACHE": "AWS/ElastiCache",
        "RDS": "AWS/RDS",
        "RDS_PROXY": "AWS/RDS/Proxy",
        "REDSHIFT": "AWS/Redshift",
        "DOCDB": "AWS/DocDB",
        "NEPTUNE": "AWS/Neptune",
        "MEMORYDB": "AWS/MemoryDB",
        # Security & Certificates
        "CERTIFICATE_MANAGER": "AWS/CertificateManager",
        "CLOUDFRONT": "AWS/CloudFront",
        "CLOUDHSM": "AWS/CloudHSM",
        "DDOS_PROTECTION": "AWS/DDoSProtection",
        "WAFV2": "AWS/WAFV2",
        "WAF": "WAF",
        # Search & Analytics
        "CLOUDSEARCH": "AWS/CloudSearch",
        "OPENSEARCH": "AWS/ES",
        "AOSS": "AWS/AOSS",
        # Developer Tools
        "CODEBUILD": "AWS/CodeBuild",
        "CODEWHISPERER": "AWS/CodeWhisperer",
        # Identity & Cognito
        "COGNITO": "AWS/Cognito",
        "CONFIG": "AWS/Config",
        "CONNECT": "AWS/Connect",
        # Migration & Database
        "DMS": "AWS/DMS",
        "DX": "AWS/DX",
        # Compute
        "EC2": "AWS/EC2",
        "EC2_API": "AWS/EC2/API",
        "EC2_INFRASTRUCTURE_PERFORMANCE": "AWS/EC2/InfrastructurePerformance",
        "EC2_SPOT": "AWS/EC2Spot",
        "ECR": "AWS/ECR",
        "ECS": "AWS/ECS",
        "LAMBDA": "AWS/Lambda",
        # Storage
        "EBS": "AWS/EBS",
        "EFS": "AWS/EFS",
        "S3": "AWS/S3",
        "S3_STORAGE_LENS": "AWS/S3/Storage-Lens",
        "FSX": "AWS/FSx",
        "STORAGE_GATEWAY": "AWS/StorageGateway",
        # Elastic Services
        "ELASTIC_BEANSTALK": "AWS/ElasticBeanstalk",
        "ELASTIC_INFERENCE": "AWS/ElasticInference",
        "ELASTIC_MAPREDUCE": "AWS/ElasticMapReduce",
        "ELASTIC_TRANSCODER": "AWS/ElasticTranscoder",
        # Load Balancing
        "ELB": "AWS/ELB",
        "NETWORK_ELB": "AWS/NetworkELB",
        # Event & Integration Services
        "EVENTBRIDGE_PIPES": "AWS/EventBridge/Pipes",
        "EVENTS": "AWS/Events",
        "FIREHOSE": "AWS/Firehose",
        # Game & Global Services
        "GAMELIFT": "AWS/GameLift",
        "GLOBAL_ACCELERATOR": "AWS/GlobalAccelerator",
        # Security & Monitoring
        "INSPECTOR": "AWS/Inspector",
        "IOT": "AWS/IoT",
        # Streaming & Messaging
        "KAFKA": "AWS/Kafka",
        "KINESIS": "AWS/Kinesis",
        "KINESIS_ANALYTICS": "AWS/KinesisAnalytics",
        "KMS": "AWS/KMS",
        "SNS": "AWS/SNS",
        "SQS": "AWS/SQS",
        # Logging & Observability
        "LOGS": "AWS/Logs",
        "X_RAY": "AWS/X-Ray",
        # Lex & AI
        "LEX": "AWS/Lex",
        # Media Services
        "MEDIA_CONNECT": "AWS/MediaConnect",
        "MEDIA_CONVERT": "AWS/MediaConvert",
        "MEDIA_LIVE": "AWS/MediaLive",
        "MEDIA_PACKAGE": "AWS/MediaPackage",
        "MEDIA_STORE": "AWS/MediaStore",
        "MEDIA_TAILOR": "AWS/MediaTailor",
        # Machine Learning
        "ML": "AWS/ML",
        # Networking
        "NAT_GATEWAY": "AWS/NATGateway",
        "NETWORK_MANAGER": "AWS/Network Manager",
        "NETWORK_FIREWALL": "AWS/NetworkFirewall",
        "NETWORK_MONITOR": "AWS/NetworkMonitor",
        "VPN": "AWS/VPN",
        "TRANSIT_GATEWAY": "AWS/TransitGateway",
        # Compute Services
        "PCS": "AWS/PCS",
        # AI Services
        "POLLY": "AWS/Polly",
        "REKOGNITION": "AWS/Rekognition",
        "TEXTRACT": "AWS/Textract",
        "TRANSLATE": "AWS/Translate",
        # Private Link
        "PRIVATELINK_ENDPOINTS": "AWS/PrivateLinkEndpoints",
        "PRIVATELINK_SERVICES": "AWS/PrivateLinkServices",
        # DNS & Routing
        "ROUTE53": "AWS/Route53",
        "ROUTE53_RESOLVER": "AWS/Route53Resolver",
        # Workflow & Orchestration
        "SCHEDULER": "AWS/Scheduler",
        "STATES": "AWS/States",
        "SWF": "AWS/SWF",
        # Usage & Support
        "TRUSTED_ADVISOR": "AWS/TrustedAdvisor",
        "USAGE": "AWS/Usage",
        # Email
        "SES": "AWS/SES",
        # ETL & Data Processing
        "GLUE": "Glue",
        # WorkSpaces
        "WORKSPACES": "AWS/WorkSpaces",
    }

    enabled_services = []
    for env_suffix, service_name in service_mapping.items():
        env_var = f"DD_SERVICE_{env_suffix}"
        if get_bool_config(env_var=env_var, default=False):
            enabled_services.append(service_name)

    return enabled_services


def get_traces_from_env() -> list[str]:
    """Build list of enabled AWS services for X-Ray tracing from DD_TRACE_* environment variables.

    Returns list of DataDog service names (e.g., 'AWS/Lambda', 'AWS/ApiGateway').
    """
    # Mapping of environment variable suffixes to DataDog service names
    trace_mapping = {
        "LAMBDA": "AWS/Lambda",
        "APP_SYNC": "AWS/AppSync",
    }

    enabled_traces = []
    for env_suffix, service_name in trace_mapping.items():
        env_var = f"DD_TRACE_{env_suffix}"
        if get_bool_config(env_var=env_var, default=False):
            if service_name not in enabled_traces:
                enabled_traces.append(service_name)

    return enabled_traces


def resolve_target_scope(
    aws_only: bool, dd_only: bool, command_name: str
) -> tuple[bool, bool]:
    """Resolve which integration sides should run for a command."""
    if aws_only and dd_only:
        raise click.UsageError(
            f"{command_name}: --aws-only and --dd-only are mutually exclusive"
        )
    run_aws = not dd_only
    run_dd = not aws_only
    return run_aws, run_dd


#########################################################################################
### CLI Commands
#########################################################################################
@click.group()
@click.version_option(version=__version__, prog_name="ddutil")
@click.option(
    "--license",
    is_flag=True,
    callback=show_license,
    is_eager=True,
    expose_value=False,
    help="Show license information and exit",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.option(
    "--env-file",
    default=".env",
    show_default=True,
    help="Path to .env file to load",
    type=click.Path(dir_okay=False),
)
@click.pass_context
def cli(ctx, verbose, quiet, env_file):
    """DataDog AWS Integration Utility

    Manage DataDog integrations for AWS accounts with ease.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["env_file"] = (
        env_file  # subcommands load it so --env-file works at either position
    )

    # Adjust logging level based on flags
    _configure_logging(verbose, quiet)


@cli.command()
@click.option("--account-id", help="AWS Account ID")
@click.option("--profile", help="AWS CLI profile name")
@click.option("--role-name", help="IAM role name for DataDog integration")
@click.option("--dd-account-id", help="DataDog account ID")
@click.option("--regions", help="Comma-separated list of AWS regions")
@click.option("--services", help="Comma-separated list of AWS services to monitor")
@click.option("--traces", help="Comma-separated list of AWS services for X-Ray tracing")
@click.option(
    "--managed-policies", help="Comma-separated list of AWS managed policy ARNs"
)
@click.option("--policy-actions", help="Comma-separated list of additional IAM actions")
@click.option(
    "--partition", help="AWS partition (aws, aws-cn, aws-us-gov)", default="aws"
)
@click.option("--metric-automute", help="Enable/disable automuting (true/false)")
@click.option(
    "--metric-collect-cloudwatch", help="Collect CloudWatch alarms (true/false)"
)
@click.option("--metric-collect-custom", help="Collect custom metrics (true/false)")
@click.option("--metric-collect-metrics", help="Enable metric collection (true/false)")
@click.option("--metric-enable", help="Enable metrics collection globally (true/false)")
@click.option("--resource-collect-cspm", help="Enable CSPM collection (true/false)")
@click.option(
    "--resource-collect-extended",
    help="Enable extended resource collection (true/false)",
)
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--aws-only", is_flag=True, help="Apply AWS IAM changes only")
@click.option("--dd-only", is_flag=True, help="Apply DataDog integration changes only")
@click.option(
    "--tags",
    help="Comma-separated IAM role tags in Key=Value format (e.g. Env=prod,Team=ops)",
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output"
)
@click.option(
    "--quiet", "-q", is_flag=True, default=False, help="Suppress non-error output"
)
@click.option(
    "--env-file",
    default=None,
    help="Path to .env file to load",
    type=click.Path(dir_okay=False),
)
@click.pass_context
def apply(
    ctx,
    account_id,
    profile,
    role_name,
    dd_account_id,
    regions,
    services,
    traces,
    managed_policies,
    policy_actions,
    partition,
    metric_automute,
    metric_collect_cloudwatch,
    metric_collect_custom,
    metric_collect_metrics,
    metric_enable,
    resource_collect_cspm,
    resource_collect_extended,
    dry_run,
    aws_only,
    dd_only,
    tags,
    verbose,
    quiet,
    env_file,
):
    """Create or update DataDog integration for an AWS account.

    Checks whether the IAM role and DataDog account integration already exist and
    creates or updates each as needed.

    Example:
        ddutil apply --account-id 123456789 --profile aws-prod --dd-account-id YOUR_DD_ACCOUNT
    """
    load_dotenv(dotenv_path=env_file or ctx.obj.get("env_file", ".env"), override=True)

    if verbose or quiet:
        ctx.obj["verbose"] = verbose or ctx.obj.get("verbose", False)
        ctx.obj["quiet"] = quiet and not ctx.obj.get("verbose", False)
        _configure_logging(ctx.obj["verbose"], ctx.obj["quiet"])

    if not ctx.obj.get("quiet"):
        console.print("[bold blue]Applying DataDog Integration[/bold blue]")

    logger.debug("Apply command invoked")

    run_aws, run_dd = resolve_target_scope(aws_only, dd_only, "apply")
    target_label = "AWS + DataDog"
    if run_aws and not run_dd:
        target_label = "AWS only"
    elif run_dd and not run_aws:
        target_label = "DataDog only"

    # Get configuration values (CLI args > Environment variables > Defaults)
    aws_account_id = get_config_value(
        cli_value=account_id,
        env_var="AWS_ACCOUNT_ID",
        required=run_dd,
        param_name="AWS Account ID",
    )
    aws_profile = get_config_value(
        cli_value=profile,
        env_var="AWS_PROFILE",
        default=None,
        required=False,
        param_name="AWS Profile",
    )
    iam_role_name = get_config_value(
        cli_value=role_name,
        env_var="DD_IAM_ROLE_NAME",
        default="datadog-integration-role",
        required=False,
        param_name="IAM Role Name",
    )
    dd_acct_id = get_config_value(
        cli_value=dd_account_id,
        env_var="DD_ACCOUNT_ID",
        required=run_aws,
        param_name="DataDog Account ID",
    )

    # Get list-based configurations
    dd_regions = get_list_config(cli_value=regions, env_var="DD_REGIONS")
    dd_services = (
        get_list_config(cli_value=services, env_var="DD_SERVICES")
        or get_services_from_env()
    )
    dd_traces = (
        get_list_config(cli_value=traces, env_var="DD_TRACES") or get_traces_from_env()
    )

    # Get managed policies
    default_managed_policies = [
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
        "arn:aws:iam::aws:policy/SecurityAudit",
    ]
    aws_managed_policies = get_list_config(
        cli_value=managed_policies,
        env_var="DD_MANAGED_POLICIES",
        default=default_managed_policies,
    )

    # Get IAM role tags
    iam_role_tags = get_tags_from_env(cli_value=tags)

    # Get policy actions
    default_policy_actions = [
        "appconfig:Get*",
        "appconfig:List*",
        "app-integrations:List*",
        "b2bi:List*",
        "bcm-data-exports:Get*",
        "bcm-data-exports:List*",
        "bedrock:List*",
        "codeartifact:Describe*",
        "codeartifact:List*",
        "controltower:Get*",
        "controltower:List*",
        "cur:Describe*",
        "emr-containers:List*",
        "geo:List*",
        "iotfleetwise:List*",
        "kendra:List*",
        "macie2:List*",
        "managedblockchain:List*",
        "medialive:List*",
        "mediatailor:List*",
        "network-firewall:List*",
        "proton:List*",
        "redshift-serverless:List*",
        "social-messaging:List*",
        "support:Describe*",
        "support:Refresh*",
        "textract:List*",
        "wisdom:List*",
        "workspaces-web:List*",
        "events:CreateEventBus",
        "logs:DeleteSubscriptionFilter",
        "logs:PutSubscriptionFilter",
        "s3:PutBucketNotification",
        "sns:Publish",
    ]
    aws_policy_actions = get_list_config(
        cli_value=policy_actions,
        env_var="DD_POLICY_ACTIONS",
        default=default_policy_actions,
    )

    dd_partition = get_config_value(
        cli_value=partition, env_var="DD_PARTITION", default="aws", required=False
    )

    # Get metric settings
    metric_settings = {
        "automute": get_bool_config(
            cli_value=metric_automute,
            env_var="DD_METRIC_AUTOMUTE",
            default=True,
        ),
        "collect_cloudwatch": get_bool_config(
            cli_value=metric_collect_cloudwatch,
            env_var="DD_METRIC_COLLECT_CLOUDWATCH",
            default=True,
        ),
        "collect_custom": get_bool_config(
            cli_value=metric_collect_custom,
            env_var="DD_METRIC_COLLECT_CUSTOM",
            default=False,
        ),
        "collect_metrics": get_bool_config(
            cli_value=metric_collect_metrics,
            env_var="DD_METRIC_COLLECT_METRICS",
            default=True,
        ),
        "enable": get_bool_config(
            cli_value=metric_enable,
            env_var="DD_METRIC_ENABLE",
            default=True,
        ),
    }

    # Get resource settings
    resource_settings = {
        "collect_cspm": get_bool_config(
            cli_value=resource_collect_cspm,
            env_var="DD_RESOURCE_COLLECT_CSPM",
            default=False,
        ),
        "collect_extended": get_bool_config(
            cli_value=resource_collect_extended,
            env_var="DD_RESOURCE_COLLECT_EXTENDED",
            default=True,
        ),
    }

    # DataDog environment variables (API keys)
    dd_env_vars = {}
    if os.getenv("DD_API_KEY"):
        dd_env_vars["DD_API_KEY"] = os.getenv("DD_API_KEY")
    if os.getenv("DD_APP_KEY"):
        dd_env_vars["DD_APP_KEY"] = os.getenv("DD_APP_KEY")
    if os.getenv("DD_SITE"):
        dd_env_vars["DD_SITE"] = os.getenv("DD_SITE")
    if os.getenv("DATADOG_VERIFY_SSL"):
        dd_env_vars["DATADOG_VERIFY_SSL"] = os.getenv("DATADOG_VERIFY_SSL")

    if dry_run:
        console.print("\n[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        table = Table(title="Apply Configuration Summary")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("AWS Account ID", aws_account_id)
        table.add_row("AWS Profile", aws_profile)
        table.add_row("IAM Role Name", iam_role_name)
        table.add_row("Target", target_label)
        if run_aws:
            table.add_row("DataDog Account ID", dd_acct_id)
            table.add_row("Managed Policies", str(len(aws_managed_policies)))
            table.add_row("Policy Actions", str(len(aws_policy_actions)))
        if run_dd:
            table.add_row("Partition", dd_partition)
            table.add_row("Regions", ", ".join(dd_regions) if dd_regions else "All")
            table.add_row(
                "Services", ", ".join(dd_services) if dd_services else "Default"
            )
            table.add_row("Traces", ", ".join(dd_traces) if dd_traces else "None")
            table.add_row("Metric Automute", str(metric_settings["automute"]))
            table.add_row(
                "Metric Collect CloudWatch", str(metric_settings["collect_cloudwatch"])
            )
            table.add_row(
                "Metric Collect Custom", str(metric_settings["collect_custom"])
            )
            table.add_row(
                "Metric Collect Metrics", str(metric_settings["collect_metrics"])
            )
            table.add_row("Metric Enable", str(metric_settings["enable"]))
            table.add_row(
                "Resource Collect CSPM", str(resource_settings["collect_cspm"])
            )
            table.add_row(
                "Resource Collect Extended", str(resource_settings["collect_extended"])
            )

        console.print(table)
        console.print("\n[yellow]Run without --dry-run to apply changes[/yellow]")
        return

    try:
        iam_client = None
        if run_aws:
            # Create AWS session and clients
            logger.debug(f"Creating base session using profile {aws_profile}")
            base_session = create_session(profile_name=aws_profile)

            logger.debug("Creating IAM client")
            iam_client = create_client(
                region_name="us-east-1",
                service_name="iam",
                session=base_session,
            )

            # Check whether the IAM role already exists to decide create vs update
            existing_role = get_role(iam_client, iam_role_name)
            if existing_role:
                console.print(
                    f"[cyan]IAM role {iam_role_name} exists — updating policies[/cyan]"
                )
            else:
                console.print(
                    f"[cyan]IAM role {iam_role_name} not found — creating[/cyan]"
                )

            role_response = create_or_update_dd_role(
                client=iam_client,
                dd_account_id=dd_acct_id,
                managed_policies=aws_managed_policies,
                policy_actions=aws_policy_actions,
                role_name=iam_role_name,
            )

            if not role_response:
                console.print("[red]Failed to create/update IAM role[/red]")
                sys.exit(1)

            if existing_role:
                # Reconcile attached/inline policies when the role already existed
                policy_response = ensure_role_policies(
                    client=iam_client,
                    role_name=iam_role_name,
                    managed_policies=aws_managed_policies,
                    policy_actions=aws_policy_actions,
                )
                if not policy_response:
                    console.print(
                        "[yellow]Warning: Some policies may not have been updated correctly[/yellow]"
                    )

            # Sync IAM role tags (create or update path)
            if iam_role_tags:
                tag_response = sync_role_tags(
                    client=iam_client,
                    role_name=iam_role_name,
                    tags=iam_role_tags,
                )
                if not tag_response:
                    console.print(
                        "[yellow]Warning: Failed to sync IAM role tags[/yellow]"
                    )
                else:
                    console.print(
                        f"[cyan]Synced {len(iam_role_tags)} tag(s) to IAM role {iam_role_name}[/cyan]"
                    )

        dd_account_exists = False
        if run_dd:
            # Set DataDog environment variables
            logger.debug("Setting DataDog environment variables")
            set_env_variables(dd_env_vars)

            # Check whether the DataDog account integration already exists
            ssl_ca_cert = os.environ.get("REQUESTS_CA_BUNDLE", certifi.where())
            verify_ssl = os.environ.get("DATADOG_VERIFY_SSL", "true").lower() != "false"
            if not verify_ssl:
                console.print(
                    "[yellow]Warning: SSL verification is disabled (DATADOG_VERIFY_SSL=false)[/yellow]"
                )
                warnings.filterwarnings("ignore", message="Unverified HTTPS request")
            configuration = Configuration(
                ssl_ca_cert=ssl_ca_cert if verify_ssl else None
            )
            configuration.verify_ssl = verify_ssl

            dd_existing = get_dd_account(configuration, aws_account_id)
            dd_account_exists = bool(dd_existing and dd_existing.data)

            if dd_account_exists:
                console.print(
                    "[cyan]DataDog account integration exists — updating[/cyan]"
                )
                dd_action = "update"
            else:
                console.print(
                    "[cyan]DataDog account integration not found — creating[/cyan]"
                )
                dd_action = "create"

            crud_response = crud_dd_account(
                account_id=aws_account_id,
                action=dd_action,
                metric_settings=metric_settings,
                partition=dd_partition,
                regions=dd_regions,
                resource_settings=resource_settings,
                role_name=iam_role_name,
                services=dd_services,
                traces=dd_traces,
            )

            if crud_response.get("error"):
                console.print(f"[red]Error: {crud_response.get('error')}[/red]")
                sys.exit(1)

            # On a fresh create, patch the IAM role trust policy with the External ID
            if not dd_account_exists:
                external_id = crud_response.get("external_id", "")
                if external_id and run_aws and iam_client:
                    console.print(
                        "[cyan]Updating IAM role trust policy with External ID[/cyan]"
                    )
                    create_or_update_dd_role(
                        client=iam_client,
                        dd_account_id=dd_acct_id,
                        external_id=external_id,
                        managed_policies=aws_managed_policies,
                        policy_actions=aws_policy_actions,
                        role_name=iam_role_name,
                    )
                elif external_id and not run_aws:
                    console.print(
                        "[yellow]Warning: DataDog integration was created, but IAM trust policy was not updated because --dd-only was used.[/yellow]"
                    )

        if run_aws and run_dd:
            console.print(
                "[bold green]✓ DataDog integration applied successfully![/bold green]"
            )
        elif run_aws:
            console.print(
                "[bold green]✓ AWS IAM configuration applied successfully![/bold green]"
            )
        else:
            console.print(
                "[bold green]✓ DataDog configuration applied successfully![/bold green]"
            )

    except Exception as e:
        console.print(f"[bold red]Error during apply: {e}[/bold red]")
        logger.exception("Apply failed")
        sys.exit(1)


@cli.command()
@click.option("--account-id", help="AWS Account ID")
@click.option("--profile", help="AWS CLI profile name")
@click.option("--role-name", help="IAM role name for DataDog integration")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output"
)
@click.option(
    "--quiet", "-q", is_flag=True, default=False, help="Suppress non-error output"
)
@click.option(
    "--env-file",
    default=None,
    help="Path to .env file to load",
    type=click.Path(dir_okay=False),
)
@click.pass_context
def delete(ctx, account_id, profile, role_name, confirm, verbose, quiet, env_file):
    """Delete DataDog integration for an AWS account.

    This command deletes the IAM role and removes the account from DataDog.

    Example:
        ddutil delete --account-id 123456789 --role-name datadog-integration-role --confirm
    """
    load_dotenv(dotenv_path=env_file or ctx.obj.get("env_file", ".env"), override=True)

    if verbose or quiet:
        ctx.obj["verbose"] = verbose or ctx.obj.get("verbose", False)
        ctx.obj["quiet"] = quiet and not ctx.obj.get("verbose", False)
        _configure_logging(ctx.obj["verbose"], ctx.obj["quiet"])

    if not ctx.obj.get("quiet"):
        console.print("[bold red]Deleting DataDog Integration[/bold red]")

    aws_account_id = get_config_value(
        cli_value=account_id,
        env_var="AWS_ACCOUNT_ID",
        required=True,
        param_name="AWS Account ID",
    )
    aws_profile = get_config_value(
        cli_value=profile,
        env_var="AWS_PROFILE",
        default=None,
        required=False,
        param_name="AWS Profile",
    )
    iam_role_name = get_config_value(
        cli_value=role_name,
        env_var="DD_IAM_ROLE_NAME",
        default="datadog-integration-role",
        required=False,
        param_name="IAM Role Name",
    )

    if not confirm:
        console.print(f"\n[yellow]This will delete:[/yellow]")
        console.print(f"  • IAM Role: [cyan]{iam_role_name}[/cyan]")
        console.print(
            f"  • DataDog integration for account: [cyan]{aws_account_id}[/cyan]\n"
        )

        if not click.confirm("Are you sure you want to proceed with deletion?"):
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    try:
        # Create AWS session and clients
        logger.debug(f"Creating base session using profile {aws_profile}")
        base_session = create_session(profile_name=aws_profile)

        logger.debug("Creating IAM client")
        iam_client = create_client(
            region_name="us-east-1",
            service_name="iam",
            session=base_session,
        )

        # DataDog environment variables (API keys)
        dd_env_vars = {}
        if os.getenv("DD_API_KEY"):
            dd_env_vars["DD_API_KEY"] = os.getenv("DD_API_KEY")
        if os.getenv("DD_APP_KEY"):
            dd_env_vars["DD_APP_KEY"] = os.getenv("DD_APP_KEY")
        if os.getenv("DD_SITE"):
            dd_env_vars["DD_SITE"] = os.getenv("DD_SITE")
        if os.getenv("DATADOG_VERIFY_SSL"):
            dd_env_vars["DATADOG_VERIFY_SSL"] = os.getenv("DATADOG_VERIFY_SSL")

        # Set DataDog environment variables
        logger.debug("Setting DataDog environment variables")
        set_env_variables(dd_env_vars)

        # Delete DataDog account integration
        console.print("[cyan]Deleting DataDog account integration[/cyan]")
        crud_response = crud_dd_account(
            account_id=aws_account_id,
            action="delete",
            role_name=iam_role_name,  # Not used in delete but required param
        )

        if crud_response.get("error"):
            console.print(f"[yellow]Warning: {crud_response.get('error')}[/yellow]")
        else:
            console.print("[green]✓ DataDog account integration deleted[/green]")

        # Delete IAM role
        console.print(f"[cyan]Deleting IAM role: {iam_role_name}[/cyan]")
        role_response = delete_dd_role(
            client=iam_client,
            role_name=iam_role_name,
        )

        if not role_response:
            console.print(
                "[yellow]Warning: Failed to delete IAM role (may not exist)[/yellow]"
            )
        else:
            console.print(f"[green]✓ IAM role {iam_role_name} deleted[/green]")

        console.print(
            "\n[bold green]✓ DataDog integration deleted successfully![/bold green]"
        )

    except Exception as e:
        console.print(f"[bold red]Error during deletion: {e}[/bold red]")
        logger.exception("Deletion failed")
        sys.exit(1)


@cli.command()
@click.option("--account-id", help="AWS Account ID")
@click.option("--profile", help="AWS CLI profile name")
@click.option("--role-name", help="IAM role name for DataDog integration")
@click.option("--dd-account-id", help="DataDog account ID")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.option("--aws-only", is_flag=True, help="Check AWS IAM status only")
@click.option("--dd-only", is_flag=True, help="Check DataDog integration status only")
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output"
)
@click.option(
    "--quiet", "-q", is_flag=True, default=False, help="Suppress non-error output"
)
@click.option(
    "--env-file",
    default=None,
    help="Path to .env file to load",
    type=click.Path(dir_okay=False),
)
@click.pass_context
def status(
    ctx,
    account_id,
    profile,
    role_name,
    dd_account_id,
    output,
    aws_only,
    dd_only,
    verbose,
    quiet,
    env_file,
):
    """Check the status of DataDog integration.

    This command validates that the IAM role and DataDog account are configured correctly.

    Example:
        ddutil status --account-id 123456789
    """
    load_dotenv(dotenv_path=env_file or ctx.obj.get("env_file", ".env"), override=True)

    if verbose or quiet:
        ctx.obj["verbose"] = verbose or ctx.obj.get("verbose", False)
        ctx.obj["quiet"] = quiet and not ctx.obj.get("verbose", False)
        _configure_logging(ctx.obj["verbose"], ctx.obj["quiet"])

    if not ctx.obj.get("quiet"):
        console.print("[bold blue]Checking DataDog Integration Status[/bold blue]\n")

    run_aws, run_dd = resolve_target_scope(aws_only, dd_only, "status")

    # Get configuration values
    aws_account_id = get_config_value(
        cli_value=account_id,
        env_var="AWS_ACCOUNT_ID",
        required=run_dd,
        param_name="AWS Account ID",
    )
    aws_profile = get_config_value(
        cli_value=profile,
        env_var="AWS_PROFILE",
        default=None,
        required=False,
        param_name="AWS Profile",
    )
    iam_role_name = get_config_value(
        cli_value=role_name,
        env_var="DD_IAM_ROLE_NAME",
        default="datadog-integration-role",
        required=False,
        param_name="IAM Role Name",
    )
    dd_acct_id = get_config_value(
        cli_value=dd_account_id,
        env_var="DD_ACCOUNT_ID",
        required=run_aws,
        param_name="DataDog Account ID",
    )

    # Expected default managed policies
    default_managed_policies = [
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
        "arn:aws:iam::aws:policy/SecurityAudit",
    ]
    expected_managed_policies = get_list_config(
        env_var="DD_MANAGED_POLICIES",
        default=default_managed_policies,
    )

    default_policy_actions = [
        "appconfig:Get*",
        "appconfig:List*",
        "app-integrations:List*",
        "b2bi:List*",
        "bcm-data-exports:Get*",
        "bcm-data-exports:List*",
        "bedrock:List*",
        "codeartifact:Describe*",
        "codeartifact:List*",
        "controltower:Get*",
        "controltower:List*",
        "cur:Describe*",
        "emr-containers:List*",
        "geo:List*",
        "iotfleetwise:List*",
        "kendra:List*",
        "macie2:List*",
        "managedblockchain:List*",
        "medialive:List*",
        "mediatailor:List*",
        "network-firewall:List*",
        "proton:List*",
        "redshift-serverless:List*",
        "social-messaging:List*",
        "support:Describe*",
        "support:Refresh*",
        "textract:List*",
        "wisdom:List*",
        "workspaces-web:List*",
        "events:CreateEventBus",
        "logs:DeleteSubscriptionFilter",
        "logs:PutSubscriptionFilter",
        "s3:PutBucketNotification",
        "sns:Publish",
    ]
    expected_policy_actions = get_list_config(
        env_var="DD_POLICY_ACTIONS",
        default=default_policy_actions,
    )

    # Get expected configuration from .env or defaults
    expected_regions = get_list_config(env_var="DD_REGIONS")

    # Get expected services from DD_SERVICES env var or individual DD_SERVICE_* boolean vars
    expected_services_from_env = get_list_config(env_var="DD_SERVICES")
    if expected_services_from_env:
        expected_services = expected_services_from_env
    else:
        expected_services = get_services_from_env()

    # Get expected traces from DD_TRACES env var or individual DD_TRACE_* boolean vars
    expected_traces_from_env = get_list_config(env_var="DD_TRACES")
    if expected_traces_from_env:
        expected_traces = expected_traces_from_env
    else:
        expected_traces = get_traces_from_env()

    expected_partition = get_config_value(
        env_var="DD_PARTITION", default="aws", required=False
    )

    # Get expected metric settings
    expected_metric_settings = {
        "automute": get_bool_config(env_var="DD_METRIC_AUTOMUTE", default=True),
        "collect_cloudwatch": get_bool_config(
            env_var="DD_METRIC_COLLECT_CLOUDWATCH", default=True
        ),
        "collect_custom": get_bool_config(
            env_var="DD_METRIC_COLLECT_CUSTOM", default=False
        ),
        "collect_metrics": get_bool_config(
            env_var="DD_METRIC_COLLECT_METRICS", default=True
        ),
        "enable": get_bool_config(env_var="DD_METRIC_ENABLE", default=True),
    }

    # Get expected resource settings
    expected_resource_settings = {
        "collect_cspm": get_bool_config(
            env_var="DD_RESOURCE_COLLECT_CSPM", default=False
        ),
        "collect_extended": get_bool_config(
            env_var="DD_RESOURCE_COLLECT_EXTENDED", default=True
        ),
    }

    status_data = {
        "check_scope": "both" if run_aws and run_dd else ("aws" if run_aws else "dd"),
        "aws_account_id": aws_account_id,
        "iam_role_name": iam_role_name,
        "iam_role_exists": False,
        "iam_role_arn": None,
        "iam_attached_policies": [],
        "iam_inline_policies": [],
        "iam_policies_match": False,
        "iam_inline_policy_actions": [],
        "iam_inline_policy_actions_match": False,
        "iam_role_tags": [],
        "expected_iam_tags": [],
        "expected_policy_actions": expected_policy_actions,
        "iam_tags_match": True,
        "dd_account_exists": False,
        "dd_account_id": None,
        "dd_role_name": None,
        "dd_external_id": None,
        "dd_partition": None,
        "dd_regions": [],
        "dd_services": [],
        "dd_metric_settings": {},
        "dd_resource_settings": {},
        "expected_partition": expected_partition,
        "expected_regions": expected_regions,
        "expected_services": expected_services,
        "expected_metric_settings": expected_metric_settings,
        "expected_resource_settings": expected_resource_settings,
        "config_matches": True,
        "sync_status": "unknown",
        "iam_check_failed": False,
        "dd_check_failed": False,
        "issues": [],
    }

    try:
        if run_aws:
            # Check IAM role
            logger.debug(f"Checking IAM role: {iam_role_name}")

            try:
                base_session = create_session(profile_name=aws_profile)
                iam_client = create_client(
                    region_name="us-east-1",
                    service_name="iam",
                    session=base_session,
                )
            except Exception as e:
                logger.debug(f"Caught AWS connection error: {e}")
                status_data["issues"].append(f"Failed to connect to AWS: {str(e)}")
                status_data["iam_check_failed"] = True
                console.print(
                    f"[yellow]Warning: Could not connect to AWS: {e}[/yellow]"
                )
                console.print(
                    "[yellow]Skipping IAM role check. Configure AWS credentials to check IAM role status.[/yellow]\n"
                )
                iam_client = None

            if iam_client:
                try:
                    role = get_role(iam_client, iam_role_name)
                    if role:
                        status_data["iam_role_exists"] = True
                        status_data["iam_role_arn"] = role.get("Arn")

                        # Get attached policies
                        attached_policies = list_attached_policies(
                            iam_client, iam_role_name
                        )
                        status_data["iam_attached_policies"] = attached_policies

                        # Get inline policies
                        inline_policies = list_inline_policies(
                            iam_client, iam_role_name
                        )
                        status_data["iam_inline_policies"] = inline_policies

                        inline_policy_actions = get_inline_policy_actions(
                            iam_client, iam_role_name
                        )
                        status_data["iam_inline_policy_actions"] = inline_policy_actions

                        inline_policy_actions_match = set(inline_policy_actions) == set(
                            expected_policy_actions
                        )
                        status_data["iam_inline_policy_actions_match"] = (
                            inline_policy_actions_match
                        )

                        if "datadog" not in inline_policies:
                            status_data["issues"].append(
                                "Missing inline policy: datadog"
                            )
                        elif not inline_policy_actions_match:
                            missing_actions = set(expected_policy_actions) - set(
                                inline_policy_actions
                            )
                            extra_actions = set(inline_policy_actions) - set(
                                expected_policy_actions
                            )
                            if missing_actions:
                                status_data["issues"].append(
                                    "Missing inline policy actions: "
                                    f"{', '.join(sorted(missing_actions))}"
                                )
                            if extra_actions:
                                status_data["issues"].append(
                                    "Unexpected inline policy actions: "
                                    f"{', '.join(sorted(extra_actions))}"
                                )

                        # Check if managed policies match expected
                        policies_match = set(attached_policies) == set(
                            expected_managed_policies
                        )
                        status_data["iam_policies_match"] = policies_match

                        if not policies_match:
                            missing = set(expected_managed_policies) - set(
                                attached_policies
                            )
                            extra = set(attached_policies) - set(
                                expected_managed_policies
                            )
                            if missing:
                                status_data["issues"].append(
                                    f"Missing managed policies: {', '.join(missing)}"
                                )
                            if extra:
                                status_data["issues"].append(
                                    f"Unexpected managed policies: {', '.join(extra)}"
                                )

                        # Fetch actual tags and compare to expected
                        expected_iam_tags = get_tags_from_env()
                        status_data["expected_iam_tags"] = expected_iam_tags
                        actual_tags = get_role_tags(iam_client, iam_role_name)
                        status_data["iam_role_tags"] = actual_tags

                        if expected_iam_tags:
                            expected_map = {
                                t["Key"]: t["Value"] for t in expected_iam_tags
                            }
                            actual_map = {t["Key"]: t["Value"] for t in actual_tags}
                            tags_match = expected_map == actual_map
                            status_data["iam_tags_match"] = tags_match

                            if not tags_match:
                                missing_keys = set(expected_map) - set(actual_map)
                                extra_keys = set(actual_map) - set(expected_map)
                                changed_keys = {
                                    k
                                    for k in expected_map
                                    if k in actual_map
                                    and expected_map[k] != actual_map[k]
                                }
                                if missing_keys:
                                    status_data["issues"].append(
                                        f"Missing IAM role tags: {', '.join(sorted(missing_keys))}"
                                    )
                                if extra_keys:
                                    status_data["issues"].append(
                                        f"Unexpected IAM role tags: {', '.join(sorted(extra_keys))}"
                                    )
                                if changed_keys:
                                    status_data["issues"].append(
                                        f"IAM role tag value mismatch: {', '.join(sorted(changed_keys))}"
                                    )
                    else:
                        status_data["issues"].append(
                            f"IAM role '{iam_role_name}' does not exist"
                        )
                except Exception as e:
                    logger.debug(f"Error checking IAM role: {e}")
                    status_data["issues"].append(f"Failed to check IAM role: {str(e)}")
                    status_data["iam_check_failed"] = True
                    console.print(
                        f"[yellow]Warning: Could not check IAM role: {e}[/yellow]\n"
                    )

        # Check DataDog account if DD credentials are available
        if run_dd and os.getenv("DD_API_KEY") and os.getenv("DD_APP_KEY"):
            logger.debug(f"Checking DataDog account: {aws_account_id}")

            # Configure DataDog API client
            ssl_ca_cert = os.environ.get("REQUESTS_CA_BUNDLE", certifi.where())
            verify_ssl = os.environ.get("DATADOG_VERIFY_SSL", "true").lower() != "false"
            if not verify_ssl:
                console.print(
                    "[yellow]Warning: SSL verification is disabled (DATADOG_VERIFY_SSL=false)[/yellow]"
                )
                warnings.filterwarnings("ignore", message="Unverified HTTPS request")

            configuration = Configuration(
                ssl_ca_cert=ssl_ca_cert if verify_ssl else None
            )
            configuration.verify_ssl = verify_ssl

            try:
                dd_response = get_dd_account(configuration, aws_account_id)

                if dd_response and dd_response.data:
                    status_data["dd_account_exists"] = True
                    dd_account = dd_response.data[0]
                    attrs = dd_account.attributes

                    status_data["dd_account_id"] = dd_account.id

                    # Get partition
                    if hasattr(attrs, "aws_partition") and attrs.aws_partition:
                        status_data["dd_partition"] = str(attrs.aws_partition).lower()
                        if status_data["dd_partition"] != expected_partition:
                            status_data["config_matches"] = False
                            status_data["issues"].append(
                                f"Partition mismatch: Expected={expected_partition}, Actual={status_data['dd_partition']}"
                            )

                    # Get role name from auth config
                    if hasattr(attrs, "auth_config") and attrs.auth_config:
                        status_data["dd_role_name"] = getattr(
                            attrs.auth_config, "role_name", None
                        )
                        status_data["dd_external_id"] = getattr(
                            attrs.auth_config, "external_id", None
                        )

                        # Check if role names match
                        if (
                            status_data["dd_role_name"]
                            and status_data["dd_role_name"] != iam_role_name
                        ):
                            status_data["config_matches"] = False
                            status_data["issues"].append(
                                f"Role name mismatch: IAM={iam_role_name}, DataDog={status_data['dd_role_name']}"
                            )

                    # Get and validate regions
                    if hasattr(attrs, "aws_regions") and attrs.aws_regions:
                        if hasattr(attrs.aws_regions, "include_only"):
                            status_data["dd_regions"] = (
                                attrs.aws_regions.include_only or []
                            )
                        else:
                            status_data["dd_regions"] = []  # All regions

                    # Compare regions
                    if expected_regions:
                        actual_regions = set(status_data["dd_regions"])
                        expected_regions_set = set(expected_regions)
                        if actual_regions != expected_regions_set:
                            status_data["config_matches"] = False
                            missing_regions = expected_regions_set - actual_regions
                            extra_regions = actual_regions - expected_regions_set
                            if missing_regions:
                                status_data["issues"].append(
                                    f"Missing regions: {', '.join(sorted(missing_regions))}"
                                )
                            if extra_regions:
                                status_data["issues"].append(
                                    f"Unexpected regions: {', '.join(sorted(extra_regions))}"
                                )

                    # Get and validate metrics configuration
                    if hasattr(attrs, "metrics_config") and attrs.metrics_config:
                        metrics_config = attrs.metrics_config

                        # Extract metric settings
                        status_data["dd_metric_settings"] = {
                            "automute": getattr(
                                metrics_config, "automute_enabled", None
                            ),
                            "collect_cloudwatch": getattr(
                                metrics_config, "collect_cloudwatch_alarms", None
                            ),
                            "collect_custom": getattr(
                                metrics_config, "collect_custom_metrics", None
                            ),
                            "enabled": getattr(metrics_config, "enabled", None),
                        }

                        # Compare metric settings
                        for key, expected_value in expected_metric_settings.items():
                            if key == "collect_metrics":
                                continue  # Skip this one, not directly mappable
                            if key == "enable":
                                actual_key = "enabled"
                            else:
                                actual_key = key

                            actual_value = status_data["dd_metric_settings"].get(
                                actual_key
                            )
                            if (
                                actual_value is not None
                                and actual_value != expected_value
                            ):
                                status_data["config_matches"] = False
                                status_data["issues"].append(
                                    f"Metric setting mismatch - {key}: Expected={expected_value}, Actual={actual_value}"
                                )

                        # Get services from namespace filters
                        if hasattr(metrics_config, "namespace_filters"):
                            ns_filters = metrics_config.namespace_filters
                            if hasattr(ns_filters, "include_only"):
                                status_data["dd_services"] = (
                                    ns_filters.include_only or []
                                )
                            elif hasattr(ns_filters, "exclude_only"):
                                status_data["dd_services"] = []  # Default mode

                        # Compare services
                        if expected_services:
                            actual_services = set(status_data["dd_services"])
                            expected_services_set = set(expected_services)
                            if actual_services != expected_services_set:
                                status_data["config_matches"] = False
                                missing_services = (
                                    expected_services_set - actual_services
                                )
                                extra_services = actual_services - expected_services_set
                                if missing_services:
                                    status_data["issues"].append(
                                        f"Missing services: {', '.join(sorted(missing_services))}"
                                    )
                                if extra_services:
                                    status_data["issues"].append(
                                        f"Unexpected services: {', '.join(sorted(extra_services))}"
                                    )

                    # Get and validate resources configuration
                    if hasattr(attrs, "resources_config") and attrs.resources_config:
                        resources_config = attrs.resources_config

                        # Extract resource settings
                        status_data["dd_resource_settings"] = {
                            "collect_cspm": getattr(
                                resources_config,
                                "cloud_security_posture_management_collection",
                                None,
                            ),
                            "collect_extended": getattr(
                                resources_config, "extended_collection", None
                            ),
                        }

                        # Compare resource settings
                        for key, expected_value in expected_resource_settings.items():
                            actual_value = status_data["dd_resource_settings"].get(key)
                            if (
                                actual_value is not None
                                and actual_value != expected_value
                            ):
                                status_data["config_matches"] = False
                                status_data["issues"].append(
                                    f"Resource setting mismatch - {key}: Expected={expected_value}, Actual={actual_value}"
                                )
                else:
                    status_data["issues"].append(
                        f"DataDog account for AWS account {aws_account_id} not found"
                    )

            except Exception as e:
                status_data["issues"].append(f"Failed to query DataDog API: {str(e)}")
                status_data["dd_check_failed"] = True
        elif run_dd:
            status_data["issues"].append(
                "DataDog API credentials (DD_API_KEY, DD_APP_KEY) not configured"
            )
            status_data["dd_check_failed"] = True

        # Determine overall sync status
        iam_check_failed = status_data["iam_check_failed"]
        dd_check_failed = status_data["dd_check_failed"]

        if run_aws and not run_dd:
            if iam_check_failed:
                status_data["sync_status"] = "unknown"
            elif status_data["iam_role_exists"]:
                status_data["sync_status"] = (
                    "synced" if len(status_data["issues"]) == 0 else "out_of_sync"
                )
            else:
                status_data["sync_status"] = "not_configured"
        elif run_dd and not run_aws:
            if dd_check_failed:
                status_data["sync_status"] = "unknown"
            elif status_data["dd_account_exists"]:
                status_data["sync_status"] = (
                    "synced" if len(status_data["issues"]) == 0 else "out_of_sync"
                )
            else:
                status_data["sync_status"] = "not_configured"
        else:
            if iam_check_failed or dd_check_failed:
                # One or both sides couldn't be checked — can't determine true state
                status_data["sync_status"] = "unknown"
            elif status_data["iam_role_exists"] and status_data["dd_account_exists"]:
                if len(status_data["issues"]) == 0:
                    status_data["sync_status"] = "synced"
                else:
                    status_data["sync_status"] = "out_of_sync"
            elif status_data["iam_role_exists"] or status_data["dd_account_exists"]:
                status_data["sync_status"] = "partial"
            else:
                status_data["sync_status"] = "not_configured"

        # Output results
        if output == "json":
            import json

            console.print(json.dumps(status_data, indent=2))
        else:
            # Text output with tables
            # Overall status
            status_icon = {
                "synced": "[+]",
                "out_of_sync": "[!]",
                "partial": "[!]",
                "not_configured": "[X]",
                "unknown": "[?]",
            }
            status_color = {
                "synced": "green",
                "out_of_sync": "yellow",
                "partial": "yellow",
                "not_configured": "red",
                "unknown": "yellow",
            }

            console.print(f"[bold]AWS Account ID:[/bold] {aws_account_id}")
            if status_data["check_scope"] != "both":
                scope_name = "AWS" if status_data["check_scope"] == "aws" else "DataDog"
                console.print(f"[bold]Scope:[/bold] {scope_name} only")
            console.print(
                f"[bold]Sync Status:[/bold] [{status_color[status_data['sync_status']]}]{status_icon[status_data['sync_status']]} {status_data['sync_status'].replace('_', ' ').title()}[/{status_color[status_data['sync_status']]}]\n"
            )

            if run_aws:
                # IAM Role table
                iam_table = Table(title="IAM Role Status")
                iam_table.add_column("Property", style="cyan")
                iam_table.add_column("Value", style="green")

                iam_table.add_row("Role Name", iam_role_name)
                iam_table.add_row(
                    "Exists",
                    (
                        "[green]Yes[/green]"
                        if status_data["iam_role_exists"]
                        else "[red]No[/red]"
                    ),
                )
                if status_data["iam_role_arn"]:
                    iam_table.add_row("ARN", status_data["iam_role_arn"])
                if status_data["iam_attached_policies"]:
                    iam_table.add_row(
                        "Managed Policies",
                        f"{len(status_data['iam_attached_policies'])} attached",
                    )
                if status_data["iam_inline_policies"]:
                    iam_table.add_row(
                        "Inline Policies",
                        f"{len(status_data['iam_inline_policies'])} policies",
                    )
                if status_data["iam_inline_policies"]:
                    iam_table.add_row(
                        "Inline Actions Match Expected",
                        (
                            "[green]Yes[/green]"
                            if status_data["iam_inline_policy_actions_match"]
                            else "[yellow]No[/yellow]"
                        ),
                    )
                iam_table.add_row(
                    "Policies Match Expected",
                    (
                        "[green]Yes[/green]"
                        if status_data["iam_policies_match"]
                        else "[yellow]No[/yellow]"
                    ),
                )
                if status_data["iam_role_tags"]:
                    iam_table.add_row(
                        "Tags",
                        f"{len(status_data['iam_role_tags'])} tag(s)",
                    )
                if status_data["expected_iam_tags"]:
                    iam_table.add_row(
                        "Tags Match Expected",
                        (
                            "[green]Yes[/green]"
                            if status_data["iam_tags_match"]
                            else "[yellow]No[/yellow]"
                        ),
                    )

                console.print(iam_table)

                # Tag comparison table
                if (
                    not status_data["iam_tags_match"]
                    and status_data["expected_iam_tags"]
                ):
                    console.print()
                    tag_table = Table(title="IAM Role Tag Comparison")
                    tag_table.add_column("Key", style="cyan")
                    tag_table.add_column("Expected", style="green")
                    tag_table.add_column("Actual", style="yellow")

                    expected_map = {
                        t["Key"]: t["Value"] for t in status_data["expected_iam_tags"]
                    }
                    actual_map = {
                        t["Key"]: t["Value"] for t in status_data["iam_role_tags"]
                    }
                    all_keys = sorted(set(expected_map) | set(actual_map))
                    for key in all_keys:
                        exp_val = expected_map.get(key, "[dim](not set)[/dim]")
                        act_val = actual_map.get(key, "[dim](not set)[/dim]")
                        if exp_val != act_val:
                            tag_table.add_row(key, exp_val, act_val)

                    console.print(tag_table)

                console.print()

            if run_dd:
                # DataDog Account table
                dd_table = Table(title="DataDog Integration Status")
                dd_table.add_column("Property", style="cyan")
                dd_table.add_column("Value", style="green")

                dd_table.add_row(
                    "Account Registered",
                    (
                        "[green]Yes[/green]"
                        if status_data["dd_account_exists"]
                        else "[red]No[/red]"
                    ),
                )
                if status_data["dd_account_id"]:
                    dd_table.add_row("DataDog Account ID", status_data["dd_account_id"])
                if status_data["dd_role_name"]:
                    dd_table.add_row("Role Name", status_data["dd_role_name"])
                if status_data["dd_external_id"]:
                    dd_table.add_row(
                        "External ID", status_data["dd_external_id"][:20] + "..."
                    )
                if status_data["dd_partition"]:
                    dd_table.add_row("Partition", status_data["dd_partition"])
                if status_data["dd_regions"]:
                    dd_table.add_row(
                        "Regions",
                        ", ".join(status_data["dd_regions"][:5])
                        + (
                            f" (+{len(status_data['dd_regions']) - 5} more)"
                            if len(status_data["dd_regions"]) > 5
                            else ""
                        ),
                    )
                if status_data["dd_services"]:
                    dd_table.add_row(
                        "Services",
                        ", ".join(status_data["dd_services"][:5])
                        + (
                            f" (+{len(status_data['dd_services']) - 5} more)"
                            if len(status_data["dd_services"]) > 5
                            else ""
                        ),
                    )
                dd_table.add_row(
                    "Config Matches Expected",
                    (
                        "[green]Yes[/green]"
                        if status_data["config_matches"]
                        else "[yellow]No[/yellow]"
                    ),
                )

                console.print(dd_table)

            # Configuration Comparison table (if mismatches exist)
            if (
                run_dd
                and not status_data["config_matches"]
                and status_data["dd_account_exists"]
            ):
                console.print()
                config_table = Table(title="Configuration Comparison")
                config_table.add_column("Setting", style="cyan")
                config_table.add_column("Expected", style="green")
                config_table.add_column("Actual", style="yellow")

                # Partition comparison
                if (
                    status_data["dd_partition"]
                    and status_data["dd_partition"] != expected_partition
                ):
                    config_table.add_row(
                        "Partition", expected_partition, status_data["dd_partition"]
                    )

                # Regions comparison
                if expected_regions:
                    expected_regions_str = ", ".join(expected_regions[:5])
                    if len(expected_regions) > 5:
                        expected_regions_str += f" (+{len(expected_regions) - 5})"
                    actual_regions_str = (
                        ", ".join(status_data["dd_regions"][:5])
                        if status_data["dd_regions"]
                        else "None"
                    )
                    if len(status_data["dd_regions"]) > 5:
                        actual_regions_str += (
                            f" (+{len(status_data['dd_regions']) - 5})"
                        )
                    if set(expected_regions) != set(status_data["dd_regions"]):
                        config_table.add_row(
                            "Regions", expected_regions_str, actual_regions_str
                        )

                # Services comparison
                if expected_services:
                    expected_services_str = ", ".join(expected_services[:5])
                    if len(expected_services) > 5:
                        expected_services_str += f" (+{len(expected_services) - 5})"
                    actual_services_str = (
                        ", ".join(status_data["dd_services"][:5])
                        if status_data["dd_services"]
                        else "None"
                    )
                    if len(status_data["dd_services"]) > 5:
                        actual_services_str += (
                            f" (+{len(status_data['dd_services']) - 5})"
                        )
                    if set(expected_services) != set(status_data["dd_services"]):
                        config_table.add_row(
                            "Services", expected_services_str, actual_services_str
                        )

                # Metric settings comparison
                for key, expected_value in expected_metric_settings.items():
                    if key == "collect_metrics":
                        continue
                    actual_key = "enabled" if key == "enable" else key
                    actual_value = status_data["dd_metric_settings"].get(actual_key)
                    if actual_value is not None and actual_value != expected_value:
                        config_table.add_row(
                            f"Metric: {key}", str(expected_value), str(actual_value)
                        )

                # Resource settings comparison
                for key, expected_value in expected_resource_settings.items():
                    actual_value = status_data["dd_resource_settings"].get(key)
                    if actual_value is not None and actual_value != expected_value:
                        config_table.add_row(
                            f"Resource: {key}", str(expected_value), str(actual_value)
                        )

                console.print(config_table)

            # Issues
            if status_data["issues"]:
                console.print("\n[bold yellow]Issues Found:[/bold yellow]")
                for issue in status_data["issues"]:
                    console.print(f"  • [yellow]{issue}[/yellow]")
            else:
                console.print(
                    "\n[bold green][OK] No issues found - integration is properly configured[/bold green]"
                )

    except Exception as e:
        console.print(f"[bold red]Error checking status: {e}[/bold red]")
        logger.exception("Status check failed")
        sys.exit(1)


#########################################################################################
### Entry Point
#########################################################################################
def main():
    """Main entry point for the CLI."""
    try:
        cli(obj={})
    except click.ClickException:
        # Let Click handle its own exceptions (they have nice formatting)
        raise
    except click.Abort:
        # Handle Ctrl+C gracefully
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except SystemExit:
        # Let sys.exit() pass through normally
        raise
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        # Check if verbose flag is present
        verbose = "--verbose" in sys.argv or "-v" in sys.argv

        if verbose:
            # Let the full traceback show
            raise
        else:
            # Show clean error message without traceback
            console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
            console.print("\n[dim]Run with --verbose flag to see full traceback[/dim]")
            sys.exit(1)


if __name__ == "__main__":
    main()
