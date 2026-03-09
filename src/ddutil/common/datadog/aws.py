#########################################################################################
### Imports
#########################################################################################
import os
import certifi  # type: ignore
from ..logs import logger
from datadog_api_client import ApiClient, Configuration  # type: ignore
from datadog_api_client.v2.api.aws_integration_api import AWSIntegrationApi  # type: ignore
from datadog_api_client.v2.model.aws_account_create_request import AWSAccountCreateRequest  # type: ignore
from datadog_api_client.v2.model.aws_account_create_request_attributes import AWSAccountCreateRequestAttributes  # type: ignore
from datadog_api_client.v2.model.aws_account_create_request_data import AWSAccountCreateRequestData  # type: ignore
from datadog_api_client.v2.model.aws_account_update_request import AWSAccountUpdateRequest  # type: ignore
from datadog_api_client.v2.model.aws_account_update_request_attributes import AWSAccountUpdateRequestAttributes  # type: ignore
from datadog_api_client.v2.model.aws_account_update_request_data import AWSAccountUpdateRequestData  # type: ignore
from datadog_api_client.v2.model.aws_account_partition import AWSAccountPartition  # type: ignore
from datadog_api_client.v2.model.aws_account_type import AWSAccountType  # type: ignore
from datadog_api_client.v2.model.aws_auth_config_role import AWSAuthConfigRole  # type: ignore
from datadog_api_client.v2.model.aws_lambda_forwarder_config import AWSLambdaForwarderConfig  # type: ignore
from datadog_api_client.v2.model.aws_lambda_forwarder_config_log_source_config import AWSLambdaForwarderConfigLogSourceConfig  # type: ignore
from datadog_api_client.v2.model.aws_log_source_tag_filter import AWSLogSourceTagFilter  # type: ignore
from datadog_api_client.v2.model.aws_logs_config import AWSLogsConfig  # type: ignore
from datadog_api_client.v2.model.aws_metrics_config import AWSMetricsConfig  # type: ignore
from datadog_api_client.v2.model.aws_namespace_tag_filter import AWSNamespaceTagFilter  # type: ignore
from datadog_api_client.v2.model.aws_regions import AWSRegions  # type: ignore
from datadog_api_client.v2.model.aws_regions_include_only import AWSRegionsIncludeOnly  # type: ignore
from datadog_api_client.v2.model.aws_resources_config import AWSResourcesConfig  # type: ignore
from datadog_api_client.v2.model.aws_traces_config import AWSTracesConfig  # type: ignore
from datadog_api_client.v2.model.aws_namespace_filters import AWSNamespaceFilters  # type: ignore
from datadog_api_client.v2.model.aws_namespace_filters_exclude_only import AWSNamespaceFiltersExcludeOnly  # type: ignore
from datadog_api_client.v2.model.aws_namespace_filters_include_only import AWSNamespaceFiltersIncludeOnly  # type: ignore
from datadog_api_client.v2.model.aws_namespace_tag_filter import AWSNamespaceTagFilter  # type: ignore
from datadog_api_client.v2.model.x_ray_services_list import XRayServicesList  # type: ignore
from datadog_api_client.v2.model.x_ray_services_include_all import XRayServicesIncludeAll  # type: ignore
from datadog_api_client.v2.model.x_ray_services_include_only import XRayServicesIncludeOnly  # type: ignore


#########################################################################################
### Maps
#########################################################################################
partitions_map = {
    "aws": AWSAccountPartition.AWS,
    "aws-cn": AWSAccountPartition.AWS_CN,
    "aws-us-gov": AWSAccountPartition.AWS_US_GOV,
}


#########################################################################################
### Functions
#########################################################################################
def build_body(
    account_id: str,
    role_name: str,
    operation: str = "create",
    metric_settings: dict[str, bool] = {},
    partition: str = "aws",
    regions: list[str] = [],
    resource_settings: dict[str, bool] = {},
    services: list[str] = [],
    traces: list[str] = [],
):
    # Account Logs Config # TODO

    # Account Tags # TODO

    # Common configuration
    aws_regions = (
        AWSRegions(
            include_all=True,
        )
        if len(regions) == 0
        else AWSRegionsIncludeOnly(
            include_only=regions,
        )
    )

    namespace_filters = (
        AWSNamespaceFiltersExcludeOnly(
            exclude_only=[
                "AWS/SQS",
                "AWS/ElasticMapReduce",
                "AWS/Usage",
            ],
        )
        if len(services) == 0
        else AWSNamespaceFiltersIncludeOnly(
            include_only=services,
        )
    )

    traces_config = (
        AWSTracesConfig()
        if len(traces) == 0
        else AWSTracesConfig(
            XRayServicesIncludeOnly(
                include_only=traces,
            )
        )
    )

    # Return appropriate request type based on operation
    if operation == "update":
        return AWSAccountUpdateRequest(
            data=AWSAccountUpdateRequestData(
                attributes=AWSAccountUpdateRequestAttributes(
                    # account_tags=[],
                    auth_config=AWSAuthConfigRole(
                        role_name=role_name,
                    ),
                    aws_account_id=account_id,
                    aws_partition=partitions_map.get(
                        partition.lower(), AWSAccountPartition.AWS
                    ),
                    aws_regions=aws_regions,
                    metrics_config=AWSMetricsConfig(
                        automute_enabled=metric_settings.get("automute", True),
                        collect_cloudwatch_alarms=metric_settings.get(
                            "collect_cloudwatch", True
                        ),
                        collect_custom_metrics=metric_settings.get(
                            "collect_custom", False
                        ),
                        enabled=metric_settings.get("enable", True),
                        namespace_filters=namespace_filters,
                        # tag_filters=[],
                    ),
                    resources_config=AWSResourcesConfig(
                        cloud_security_posture_management_collection=resource_settings.get(
                            "collect_cspm", False
                        ),
                        extended_collection=resource_settings.get(
                            "collect_extended", True
                        ),
                    ),
                    traces_config=traces_config,
                ),
                type=AWSAccountType.ACCOUNT,
            )
        )
    else:
        return AWSAccountCreateRequest(
            data=AWSAccountCreateRequestData(
                attributes=AWSAccountCreateRequestAttributes(
                    # account_tags=[],
                    auth_config=AWSAuthConfigRole(
                        role_name=role_name,
                    ),
                    aws_account_id=account_id,
                    aws_partition=partitions_map.get(
                        partition.lower(), AWSAccountPartition.AWS
                    ),
                    aws_regions=aws_regions,
                    metrics_config=AWSMetricsConfig(
                        automute_enabled=metric_settings.get("automute", True),
                        collect_cloudwatch_alarms=metric_settings.get(
                            "collect_cloudwatch", True
                        ),
                        collect_custom_metrics=metric_settings.get(
                            "collect_custom", False
                        ),
                        enabled=metric_settings.get("enable", True),
                        namespace_filters=namespace_filters,
                        # tag_filters=[],
                    ),
                    resources_config=AWSResourcesConfig(
                        cloud_security_posture_management_collection=resource_settings.get(
                            "collect_cspm", False
                        ),
                        extended_collection=resource_settings.get(
                            "collect_extended", True
                        ),
                    ),
                    traces_config=traces_config,
                ),
                type=AWSAccountType.ACCOUNT,
            )
        )


def create_dd_account(configuration, body):
    with ApiClient(configuration) as api_client:
        api_instance = AWSIntegrationApi(api_client)
        response = api_instance.create_aws_account(body=body)
        return response


def delete_dd_account(configuration, aws_account_config_id):
    with ApiClient(configuration) as api_client:
        api_instance = AWSIntegrationApi(api_client)
        response = api_instance.delete_aws_account(
            aws_account_config_id=aws_account_config_id,
        )
        return response


def get_dd_account(configuration, account_id):
    with ApiClient(configuration) as api_client:
        api_instance = AWSIntegrationApi(api_client)
        response = api_instance.list_aws_accounts(
            aws_account_id=account_id,
        )
        return response


def update_dd_account(configuration, aws_account_config_id, body):
    with ApiClient(configuration) as api_client:
        api_instance = AWSIntegrationApi(api_client)
        response = api_instance.update_aws_account(
            aws_account_config_id=aws_account_config_id, body=body
        )
        return response


def crud_dd_account(
    account_id: str,
    action: str,
    role_name: str,
    metric_settings: dict[str, bool] = {},
    partition: str = "aws",
    regions: list[str] = [],
    resource_settings: dict[str, bool] = {},
    services: list[str] = [],
    traces: list[str] = [],
) -> dict[str, str]:
    # Handle SSL configuration for Python 3.13+ with corporate SSL inspection
    ssl_ca_cert = os.environ.get("REQUESTS_CA_BUNDLE", certifi.where())
    verify_ssl = os.environ.get("DATADOG_VERIFY_SSL", "true").lower() != "false"

    if not verify_ssl:
        logger.warning(
            "SSL verification is DISABLED. This is not recommended for production."
        )

    configuration = Configuration(ssl_ca_cert=ssl_ca_cert if verify_ssl else None)
    configuration.verify_ssl = verify_ssl

    def handle_create():
        body = build_body(
            account_id=account_id,
            role_name=role_name,
            operation="create",
            metric_settings=metric_settings,
            partition=partition,
            regions=regions,
            resource_settings=resource_settings,
            services=services,
            traces=traces,
        )
        response = create_dd_account(configuration, body)
        logger.debug(f"Create account response: {response}")
        return {
            "external_id": response.get("data", {})
            .get("attributes", {})
            .get("auth_config", {})
            .get("external_id"),
        }

    def handle_delete():
        # Get account to retrieve aws_account_config_id
        get_response = get_dd_account(configuration, account_id)
        logger.debug(f"Get account response: {get_response}")

        if not get_response.data:
            logger.error(f"Account {account_id} not found for deletion")
            return {"error": f"Account {account_id} not found for deletion"}

        aws_account_config_id = get_response.data[0].id
        response = delete_dd_account(configuration, aws_account_config_id)
        logger.debug(f"Delete account response: {response}")
        return {"status": "deleted"}

    def handle_update():
        # Get account to retrieve aws_account_config_id
        get_response = get_dd_account(configuration, account_id)
        logger.debug(f"Get account response: {get_response}")

        if not get_response.data:
            logger.error(f"Account {account_id} not found for update")
            return {"error": f"Account {account_id} not found for update"}

        aws_account_config_id = get_response.data[0].id

        body = build_body(
            account_id=account_id,
            role_name=role_name,
            operation="update",
            metric_settings=metric_settings,
            partition=partition,
            regions=regions,
            resource_settings=resource_settings,
            services=services,
            traces=traces,
        )
        response = update_dd_account(configuration, aws_account_config_id, body)
        logger.debug(f"Update account response: {response}")
        return {
            "external_id": response.get("data", {})
            .get("attributes", {})
            .get("auth_config", {})
            .get("external_id"),
        }

    # Dispatch dictionary
    dispatch = {
        "create": handle_create,
        "update": handle_update,
        "delete": handle_delete,
    }

    # Execute the appropriate handler
    handler = dispatch.get(action)
    if handler:
        return handler()
    else:
        logger.error(
            f"Invalid action: {action}. Valid actions are: {list(dispatch.keys())}"
        )
        return {
            "error": f"Invalid action: {action}. Valid actions are: {list(dispatch.keys())}"
        }
