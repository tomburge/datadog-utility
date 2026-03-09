ddutil
======

A command-line tool for managing DataDog AWS integrations.

.. image:: https://github.com/tomburge/datadog-utility/actions/workflows/test-build.yml/badge.svg
   :target: https://github.com/tomburge/datadog-utility/actions/workflows/test-build.yml
   :alt: Test Build

.. image:: https://github.com/tomburge/datadog-utility/actions/workflows/publish-test.yml/badge.svg
   :target: https://github.com/tomburge/datadog-utility/actions/workflows/publish-test.yml
   :alt: Publish to TestPyPI

.. image:: https://github.com/tomburge/datadog-utility/actions/workflows/publish.yml/badge.svg?event=release
   :target: https://github.com/tomburge/datadog-utility/actions/workflows/publish.yml
   :alt: Publish to PyPI

----

**ddutil** automates the creation, update, and deletion of DataDog AWS account integrations.
It manages the IAM role and inline/managed policies required by DataDog, registers the
integration via the DataDog API, and keeps both sides in sync with your configuration.

Features
--------

- Single ``apply`` command — auto-detects create vs. update for both IAM role and DataDog account
- Automated IAM role and policy creation/reconciliation
- IAM role tag management with drift detection
- Comprehensive status checking and configuration validation

  - IAM role, policy, and tag verification
  - DataDog account configuration validation
  - Settings comparison (regions, services, metrics, resources, traces)

- Clean deletion of integrations
- Rich terminal output with colour-coded tables
- Flexible configuration via ``.env`` files or CLI arguments
- Dry-run mode to preview changes before applying
- Verbose logging for debugging
- JSON output support for automation
- Support for AWS standard, GovCloud, and China partitions

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Reference

   commands
   configuration

.. toctree::
   :maxdepth: 1
   :caption: Guides

   examples
   troubleshooting
