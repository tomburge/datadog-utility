Examples
========

First-Time Setup
-----------------

.. code-block:: bash

   # 1. Configure credentials
   cp .env.example .env
   # edit .env ...

   # 2. Preview
   ddutil apply --dry-run

   # 3. Apply
   ddutil apply

   # 4. Verify
   ddutil status

Multiple Environments
----------------------

Maintain one ``.env`` file per environment and pass it explicitly:

.. code-block:: bash

   ddutil --env-file envs/dev.env apply
   ddutil --env-file envs/staging.env status
   ddutil --env-file envs/prod.env apply --dry-run

IAM Role Tags
--------------

.. code-block:: bash

   # Via .env
   DD_IAM_TAGS=ApplicationName=datadog,Environment=prod,CostCenter=platform,ManagedBy=ddutil
   ddutil apply

   # Via CLI flag
   ddutil apply --tags "ApplicationName=datadog,Environment=prod"

   # Check for tag drift
   ddutil status

When tags are out of sync, ``status`` shows a diff table with expected vs. actual values.
Run ``apply`` again to reconcile the drift.

Restrict Monitoring Scope
--------------------------

.. code-block:: bash

   # Monitor only specific regions
   ddutil apply --regions us-east-1,eu-west-1

   # Monitor only specific services
   ddutil apply --services AWS/Lambda,AWS/EC2,AWS/RDS

   # Enable X-Ray tracing for Lambda and AppSync
   ddutil apply --traces AWS/Lambda,AWS/AppSync

   # Combine via .env
   # DD_REGIONS=us-east-1
   # DD_SERVICES=AWS/Lambda,AWS/EC2
   ddutil apply

AWS-Only and DataDog-Only Operations
------------------------------------

.. code-block:: bash

   # Apply only AWS IAM role/policy/tag changes
   ddutil apply --aws-only

   # Apply only DataDog integration changes
   ddutil apply --dd-only

   # Check only AWS IAM status
   ddutil status --aws-only

   # Check only DataDog integration status
   ddutil status --dd-only

JSON Output for Automation
---------------------------

.. code-block:: bash

   # Pipe to jq for targeted checks
   ddutil status --output json | jq '.sync_status'
   ddutil status --output json | jq '.issues'
   ddutil status --output json | jq '.iam_tags_match'

GovCloud
--------

.. code-block:: bash

   ddutil apply --partition aws-us-gov --profile govcloud --account-id 123456789012

China Partition
---------------

.. code-block:: bash

   ddutil apply --partition aws-cn --profile china --account-id 123456789012
