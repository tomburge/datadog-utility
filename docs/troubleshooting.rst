Troubleshooting
===============

Missing Required Variables
---------------------------

.. code-block:: bash

   ddutil apply --dry-run

Dry-run mode validates configuration before making any changes and will report exactly which
required variables are missing.

AWS Authentication Errors
--------------------------

.. code-block:: bash

   # Verify your profile works independently
   aws sts get-caller-identity --profile your-profile

   # Pass it explicitly to ddutil
   ddutil apply --profile your-profile

   # Or rely on the default credential chain (env vars, instance profile, etc.)
   # by omitting --profile and not setting AWS_PROFILE

DataDog API Errors
-------------------

.. code-block:: bash

   # Show raw API error details
   ddutil --verbose status

Configuration Drift
--------------------

.. code-block:: bash

   # status shows a comparison table for every mismatch
   ddutil status

   # Fix all drift with apply
   ddutil apply

First-Time ``--dd-only`` Apply
------------------------------

If you run ``ddutil apply --dd-only`` for a brand-new integration, DataDog may return
an External ID that must be written into the IAM role trust policy.

Because ``--dd-only`` intentionally skips AWS writes, run this next:

.. code-block:: bash

   ddutil apply --aws-only

This updates the IAM trust policy with the External ID and completes the setup.

SSL Certificate Errors (Internal CA)
--------------------------------------

If your environment uses a custom or internal certificate authority:

.. code-block:: bash

   export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
   ddutil apply

You can also set ``DATADOG_VERIFY_SSL=false`` in your ``.env`` to disable SSL verification
for DataDog API calls, though this is not recommended for production environments.
