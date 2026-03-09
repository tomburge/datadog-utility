Installation
============

Requirements
------------

- Python 3.12 or later
- AWS credentials configured (profile, environment variables, or instance profile)
- DataDog API key and application key

Using pip (Recommended)
-----------------------

.. code-block:: bash

   pip install ddutil

Using UV
--------

`UV <https://github.com/astral-sh/uv>`_ installs ``ddutil`` as an isolated tool.

**Linux/macOS:**

.. code-block:: bash

   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv tool install ddutil

**Windows:**

.. code-block:: powershell

   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   uv tool install ddutil

After installation, the ``ddutil`` command is available globally.

From Source
-----------

.. code-block:: bash

   git clone https://github.com/tomburge/datadog-utility.git
   cd datadog-utility

**With UV:**

.. code-block:: bash

   uv venv
   uv pip install -e .

**With pip:**

.. code-block:: bash

   python -m venv .venv

   # Linux/macOS
   source .venv/bin/activate

   # Windows
   .venv\Scripts\activate

   pip install -e .

After installation, the ``ddutil`` command is available in the activated environment.
