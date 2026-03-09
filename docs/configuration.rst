Configuration
=============

Priority
--------

Configuration values are resolved in the following order (highest to lowest):

1. **CLI argument**
2. **Environment variable** (from ``.env`` or shell)

Environment Variables Reference
--------------------------------

Copy ``.env.example`` to ``.env`` and fill in the values relevant to your environment.

Required
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Description
   * - ``DD_API_KEY``
     - DataDog API key
   * - ``DD_APP_KEY``
     - DataDog application key
   * - ``AWS_ACCOUNT_ID``
     - AWS account ID to integrate
   * - ``DD_ACCOUNT_ID``
     - DataDog account ID (required by ``apply``)

AWS / IAM
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Variable
     - Default
     - Description
   * - ``AWS_PROFILE``
     - *(default credential chain)*
     - AWS CLI profile name
   * - ``DD_IAM_ROLE_NAME``
     - ``datadog-integration-role``
     - IAM role name
   * - ``DD_IAM_TAGS``
     -
     - Comma-separated ``Key=Value`` tag pairs (1–50)
   * - ``DD_MANAGED_POLICIES``
     - ``ReadOnlyAccess,SecurityAudit``
     - Managed policy ARNs
   * - ``DD_POLICY_ACTIONS``
     - *(32 default actions)*
     - Extra IAM inline policy actions

**Tag format:** ``ApplicationName=datadog,Environment=sandbox,CostCenter=platform``

DataDog / Integration
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Variable
     - Default
     - Description
   * - ``DD_SITE``
     - ``datadoghq.com``
     - DataDog site (e.g. ``datadoghq.eu``)
   * - ``DD_PARTITION``
     - ``aws``
     - AWS partition (``aws``, ``aws-cn``, ``aws-us-gov``)
   * - ``DATADOG_VERIFY_SSL``
     - ``true``
     - SSL verification for DataDog API calls

Monitoring
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Variable
     - Default
     - Description
   * - ``DD_REGIONS``
     - *(all)*
     - Comma-separated regions to monitor
   * - ``DD_SERVICES``
     - *(from* ``DD_SERVICE_*`` *)*
     - Comma-separated service namespace overrides
   * - ``DD_TRACES``
     - *(from* ``DD_TRACE_*`` *)*
     - Comma-separated X-Ray tracing overrides

Service Toggles
~~~~~~~~~~~~~~~

Individual services can be enabled or disabled without listing every namespace:

.. code-block:: bash

   # Toggle specific services on or off
   DD_SERVICE_LAMBDA=true
   DD_SERVICE_EC2=true
   DD_SERVICE_RDS=false

   # Override all toggles with an explicit list
   DD_SERVICES=AWS/Lambda,AWS/EC2

See ``.env.example`` for the full list of 113 ``DD_SERVICE_*`` variables grouped by category.

Trace Toggles
~~~~~~~~~~~~~

.. code-block:: bash

   DD_TRACE_LAMBDA=true
   DD_TRACE_APP_SYNC=false

   # Override all toggles
   DD_TRACES=AWS/Lambda

Metric Settings
~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Variable
     - Default
     - Description
   * - ``DD_METRIC_AUTOMUTE``
     - ``true``
     - Auto-mute monitors on EC2 shutdowns
   * - ``DD_METRIC_COLLECT_CLOUDWATCH``
     - ``true``
     - Collect CloudWatch alarms
   * - ``DD_METRIC_COLLECT_CUSTOM``
     - ``false``
     - Collect custom metrics
   * - ``DD_METRIC_COLLECT_METRICS``
     - ``true``
     - Enable metric collection
   * - ``DD_METRIC_ENABLE``
     - ``true``
     - Enable metrics globally

Resource Settings
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Variable
     - Default
     - Description
   * - ``DD_RESOURCE_COLLECT_CSPM``
     - ``false``
     - Cloud Security Posture Management
   * - ``DD_RESOURCE_COLLECT_EXTENDED``
     - ``true``
     - Extended resource collection

Application
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Variable
     - Default
     - Description
   * - ``LOG_LEVEL``
     - ``INFO``
     - Logging level (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``)
