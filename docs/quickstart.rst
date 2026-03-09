Quick Start
===========

1. Set Up Environment Variables
--------------------------------

.. code-block:: bash

   cp .env.example .env

Edit ``.env`` with at minimum:

.. code-block:: text

   # Required
   DD_API_KEY=your_datadog_api_key
   DD_APP_KEY=your_datadog_app_key
   DD_ACCOUNT_ID=your_datadog_account_id
   AWS_ACCOUNT_ID=123456789012

See :doc:`configuration` for the full list of available variables.

2. Preview Changes (Dry-Run)
-----------------------------

.. code-block:: bash

   ddutil apply --dry-run

This shows exactly what will be created or modified without making any changes.

3. Apply the Integration
-------------------------

.. code-block:: bash

   ddutil apply

The tool will:

1. Create or update the IAM role and inline/managed policies
2. Create or update the DataDog AWS account integration
3. On first creation, patch the IAM trust policy with the External ID returned by DataDog
4. Sync any configured IAM role tags

4. Verify the Integration
--------------------------

.. code-block:: bash

   ddutil status

The status command compares live AWS and DataDog state against your ``.env`` configuration
and reports any drift.
