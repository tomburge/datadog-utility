# DataDog AWS Integration CLI

A command-line tool for managing DataDog AWS integrations with ease.

## Features

- 🚀 Single `apply` command — auto-detects create vs. update for both IAM role and DataDog account
- 🔧 Automated IAM role and policy creation/reconciliation
- 🏷️ IAM role tag management with drift detection
- ✅ Comprehensive status checking and configuration validation
  - IAM role, policy, and tag verification
  - DataDog account configuration validation
  - Settings comparison (regions, services, metrics, resources, traces)
- 🗑️ Clean deletion of integrations
- 🎨 Rich terminal output with colour-coded tables
- ⚙️ Flexible configuration via `.env` files or CLI arguments
- 🔒 Dry-run mode to preview changes before applying
- 📝 Verbose logging for debugging
- 📊 JSON output support for automation
- 🔐 Support for AWS standard, GovCloud, and China partitions

## Build Status

[![Test Build](https://github.com/tomburge/datadog-utility/actions/workflows/test-build.yml/badge.svg)](https://github.com/tomburge/datadog-utility/actions/workflows/test-build.yml)

[![Publish to TestPyPI](https://github.com/tomburge/datadog-utility/actions/workflows/publish-test.yml/badge.svg)](https://github.com/tomburge/datadog-utility/actions/workflows/publish-test.yml)

[![Publish to PyPI](https://github.com/tomburge/datadog-utility/actions/workflows/publish.yml/badge.svg?event=release)](https://github.com/tomburge/datadog-utility/actions/workflows/publish.yml)

## Installation

### Using pip (Recommended)

```bash
pip install ddutil
```

### Using UV

[UV](https://github.com/astral-sh/uv) is a fast Python package manager that installs `ddutil` as an isolated tool:

```text
# Install UV if you haven't already

# Linux/MacOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install ddutil from PyPI
uv tool install ddutil
```

### From Source

```text
git clone https://github.com/tomburge/datadog-utility.git
cd datadog-utility

# With UV
uv venv
uv pip install -e .

# With pip
python -m venv .venv

# Linux/MacOS
source .venv/bin/activate
pip install -e .

# Windows
.venv\Scripts\activate
pip install -e .
```

After installation the `ddutil` command is available globally.

## Quick Start

### 1. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with at minimum:

```text
# Required
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key
DD_ACCOUNT_ID=your_datadog_account_id
AWS_ACCOUNT_ID=123456789012
```

### 2. Preview the Changes (Dry-Run)

```text
ddutil apply --dry-run
```

### 3. Apply the Integration

```text
ddutil apply
```

The tool will:

1. Create or update the IAM role and inline/managed policies
2. Create or update the DataDog AWS account integration
3. On first creation, patch the IAM trust policy with the External ID returned by DataDog
4. Sync any configured IAM role tags

## Usage

### Global Options

`--version`, `--license`, and `--env-file` must be placed **before** the subcommand name. `--verbose` and `--quiet` can be placed either before **or** after the subcommand:

| Option | Short | Position | Description |
| -- | -- | -- | -- |
| `--version` | | before | Show version and exit |
| `--license` | | before | Show license information and exit |
| `--verbose` | `-v` | before or after | Enable debug-level output |
| `--quiet` | `-q` | before or after | Suppress all non-error output |
| `--env-file PATH` | | before | Load a specific `.env` file (overrides auto-load of `.env`) |

```bash
ddutil --help
ddutil --version
# verbose before or after the subcommand — both work
ddutil --verbose apply
ddutil apply --verbose
ddutil --env-file prod.env apply
```

### Commands

| Command | Description |
| -- | -- |
| `apply` | Create or update the DataDog AWS integration |
| `status` | Validate and compare live state against `.env` configuration |
| `delete` | Remove the IAM role and DataDog account integration |

---

### `apply`

Creates or updates both the IAM role and the DataDog account integration.  Auto-detects whether each component exists and creates or updates accordingly.

```bash
ddutil apply [OPTIONS]
```

| Option | Env Var | Default | Description |
| -- | -- | -- | -- |
| `--account-id TEXT` | `AWS_ACCOUNT_ID` | *(required)* | AWS account ID |
| `--profile TEXT` | `AWS_PROFILE` | *(boto3 default chain)* | AWS CLI profile name |
| `--dd-account-id TEXT` | `DD_ACCOUNT_ID` | *(required)* | DataDog account ID |
| `--role-name TEXT` | `DD_IAM_ROLE_NAME` | `datadog-integration-role` | IAM role name |
| `--tags TEXT` | `DD_IAM_TAGS` | | IAM role tags — `Key=Value,Key2=Value2` (1–50 pairs) |
| `--managed-policies TEXT` | `DD_MANAGED_POLICIES` | ReadOnlyAccess + SecurityAudit | Comma-separated managed policy ARNs |
| `--policy-actions TEXT` | `DD_POLICY_ACTIONS` | *(32 default actions)* | Additional IAM inline policy actions |
| `--partition TEXT` | `DD_PARTITION` | `aws` | AWS partition (`aws`, `aws-cn`, `aws-us-gov`) |
| `--regions TEXT` | `DD_REGIONS` | *(all regions)* | Comma-separated regions to monitor |
| `--services TEXT` | `DD_SERVICES` | *(from `DD_SERVICE_*`)* | Comma-separated AWS service namespaces |
| `--traces TEXT` | `DD_TRACES` | *(from `DD_TRACE_*`)* | Comma-separated services for X-Ray tracing |
| `--metric-automute BOOL` | `DD_METRIC_AUTOMUTE` | `true` | Auto-mute monitors on EC2 shutdowns |
| `--metric-collect-cloudwatch BOOL` | `DD_METRIC_COLLECT_CLOUDWATCH` | `true` | Collect CloudWatch alarms |
| `--metric-collect-custom BOOL` | `DD_METRIC_COLLECT_CUSTOM` | `false` | Collect custom metrics |
| `--metric-collect-metrics BOOL` | `DD_METRIC_COLLECT_METRICS` | `true` | Enable metric collection |
| `--metric-enable BOOL` | `DD_METRIC_ENABLE` | `true` | Enable metrics globally |
| `--resource-collect-cspm BOOL` | `DD_RESOURCE_COLLECT_CSPM` | `false` | Enable Cloud Security Posture Management |
| `--resource-collect-extended BOOL` | `DD_RESOURCE_COLLECT_EXTENDED` | `true` | Enable extended resource collection |
| `--dry-run` | | `false` | Preview changes without applying |
| `--env-file PATH` | | | Path to `.env` file |

**Examples:**

```bash
# Apply using .env file defaults
ddutil apply

# Preview without making changes
ddutil apply --dry-run

# Override specific values
ddutil apply --account-id 123456789012 --profile prod

# Apply with IAM role tags
ddutil apply --tags "ApplicationName=datadog,Environment=prod,CostCenter=platform"

# Specify monitored regions and services
ddutil apply --regions us-east-1,us-west-2 --services AWS/Lambda,AWS/EC2,AWS/RDS

# Enable X-Ray tracing for Lambda and AppSync
ddutil apply --traces AWS/Lambda,AWS/AppSync

# AWS GovCloud
ddutil apply --partition aws-us-gov --profile govcloud

# Use a different .env file
ddutil apply --env-file envs/prod.env
```

---

### `status`

Checks live AWS and DataDog state and compares it against the configuration in `.env`.

```bash
ddutil status [OPTIONS]
```

| Option | Env Var | Default | Description |
| -- | -- | -- | -- |
| `--account-id TEXT` | `AWS_ACCOUNT_ID` | *(required)* | AWS account ID |
| `--profile TEXT` | `AWS_PROFILE` | *(boto3 default chain)* | AWS CLI profile name |
| `--role-name TEXT` | `DD_IAM_ROLE_NAME` | `datadog-integration-role` | IAM role name |
| `--dd-account-id TEXT` | `DD_ACCOUNT_ID` | | DataDog account ID |
| `--output`, `-o` | | `text` | Output format: `text` or `json` |
| `--env-file PATH` | | | Path to `.env` file |

**Sync status values:**

| Status | Meaning |
| -- | -- |
| `Synced` | IAM role and DataDog account exist and config matches `.env` |
| `Out Of Sync` | Both sides exist but one or more settings differ |
| `Partial` | Only one of IAM role / DataDog account exists |
| `Not Configured` | Neither side exists |
| `Unknown` | AWS or DataDog connectivity failed — cannot determine state |

**Validated settings:**

- IAM role existence and ARN
- Attached managed policies vs. expected
- IAM role tags vs. `DD_IAM_TAGS`
- DataDog account registration and External ID
- Role name consistency between IAM and DataDog
- AWS partition
- Monitored regions and service namespaces
- Metric settings (automute, CloudWatch alarms, custom metrics, enabled)
- Resource settings (CSPM, extended collection)

**Examples:**

```bash
# Basic status check
ddutil status

# Check specific account with verbose output
ddutil --verbose status --account-id 123456789012

# Machine-readable JSON output
ddutil status --output json

# Use a specific .env file
ddutil status --env-file envs/prod.env
```

---

### `delete`

Removes the DataDog account integration and deletes the IAM role along with all attached and inline policies.

```bash
ddutil delete [OPTIONS]
```

| Option | Env Var | Default | Description |
| -- | -- | -- | -- |
| `--account-id TEXT` | `AWS_ACCOUNT_ID` | *(required)* | AWS account ID |
| `--profile TEXT` | `AWS_PROFILE` | *(boto3 default chain)* | AWS CLI profile name |
| `--role-name TEXT` | `DD_IAM_ROLE_NAME` | `datadog-integration-role` | IAM role name |
| `--confirm` | | `false` | Skip interactive confirmation prompt |
| `--env-file PATH` | | | Path to `.env` file |

**Examples:**

```bash
# Interactive (prompts for confirmation)
ddutil delete

# Skip confirmation — useful for automation
ddutil delete --confirm

# Delete a non-default role name
ddutil delete --role-name custom-datadog-role --confirm

# Use a specific AWS profile
ddutil delete --profile aws-prod --confirm
```

---

## Configuration

### Configuration Priority

1. **CLI argument** — highest priority
2. **Environment variable** (from `.env` or shell)

### Environment Variables Reference

Copy `.env.example` to `.env` and fill in your values.

#### Required

| Variable | Description |
| -- | -- |
| `DD_API_KEY` | DataDog API key |
| `DD_APP_KEY` | DataDog application key |
| `AWS_ACCOUNT_ID` | AWS account ID to integrate |
| `DD_ACCOUNT_ID` | DataDog account ID (required by `apply`) |

#### AWS / IAM

| Variable | Default | Description |
| -- | -- | -- |
| `AWS_PROFILE` | *(default credential chain)* | AWS CLI profile name |
| `DD_IAM_ROLE_NAME` | `datadog-integration-role` | IAM role name |
| `DD_IAM_TAGS` | | Comma-separated `Key=Value` tag pairs (1–50) |
| `DD_MANAGED_POLICIES` | `ReadOnlyAccess,SecurityAudit` | Managed policy ARNs |
| `DD_POLICY_ACTIONS` | *(32 default actions)* | Extra IAM inline policy actions |

**Tag format:** `ApplicationName=datadog,Environment=sandbox,CostCenter=platform`

#### DataDog / Integration

| Variable | Default | Description |
| -- | -- | -- |
| `DD_SITE` | `datadoghq.com` | DataDog site (e.g. `datadoghq.eu`) |
| `DD_PARTITION` | `aws` | AWS partition (`aws`, `aws-cn`, `aws-us-gov`) |
| `DATADOG_VERIFY_SSL` | `true` | SSL verification for DataDog API calls |

#### Monitoring

| Variable | Default | Description |
| -- | -- | -- |
| `DD_REGIONS` | *(all)* | Comma-separated regions |
| `DD_SERVICES` | *(from `DD_SERVICE_*`)* | Comma-separated service overrides |
| `DD_TRACES` | *(from `DD_TRACE_*`)* | Comma-separated X-Ray tracing overrides |

#### Service Toggles

Individual services can be enabled or disabled without listing every namespace:

```bash
# Toggle specific services on or off
DD_SERVICE_LAMBDA=true
DD_SERVICE_EC2=true
DD_SERVICE_RDS=false

# Override all toggles with an explicit list
DD_SERVICES=AWS/Lambda,AWS/EC2
```

See `.env.example` for the full list of 113 `DD_SERVICE_*` variables grouped by category.

#### Trace Toggles

```bash
DD_TRACE_LAMBDA=true
DD_TRACE_APP_SYNC=false

# Override all toggles
DD_TRACES=AWS/Lambda
```

#### Metric Settings

| Variable | Default | Description |
| -- | -- | -- |
| `DD_METRIC_AUTOMUTE` | `true` | Auto-mute monitors on EC2 shutdowns |
| `DD_METRIC_COLLECT_CLOUDWATCH` | `true` | Collect CloudWatch alarms |
| `DD_METRIC_COLLECT_CUSTOM` | `false` | Collect custom metrics |
| `DD_METRIC_COLLECT_METRICS` | `true` | Enable metric collection |
| `DD_METRIC_ENABLE` | `true` | Enable metrics globally |

#### Resource Settings

| Variable | Default | Description |
| -- | -- | -- |
| `DD_RESOURCE_COLLECT_CSPM` | `false` | Cloud Security Posture Management |
| `DD_RESOURCE_COLLECT_EXTENDED` | `true` | Extended resource collection |

#### Application

| Variable | Default | Description |
| -- | -- | -- |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Examples

### First-time setup

```bash
# 1. Configure credentials
cp .env.example .env
# edit .env ...

# 2. Preview
ddutil apply --dry-run

# 3. Apply
ddutil apply

# 4. Verify
ddutil status
```

### Working with multiple environments

```bash
# Maintain one .env per environment
ddutil --env-file envs/dev.env apply
ddutil --env-file envs/staging.env status
ddutil --env-file envs/prod.env apply --dry-run
```

### IAM role tags

```bash
# Via .env
DD_IAM_TAGS=ApplicationName=datadog,Environment=prod,CostCenter=platform,ManagedBy=ddutil
ddutil apply

# Via CLI flag
ddutil apply --tags "ApplicationName=datadog,Environment=prod"

# Check tag drift
ddutil status  # shows "Tags Match Expected: No" and a diff table when out of sync
```

### Restrict monitoring scope

```bash
# Monitor only specific regions
ddutil apply --regions us-east-1,eu-west-1

# Monitor only specific services
ddutil apply --services AWS/Lambda,AWS/EC2,AWS/RDS

# Single region + services in .env
DD_REGIONS=us-east-1
DD_SERVICES=AWS/Lambda,AWS/EC2
ddutil apply
```

### JSON output for automation

```bash
# Pipe to jq for targeted checks
ddutil status --output json | jq '.sync_status'
ddutil status --output json | jq '.issues'
ddutil status --output json | jq '.iam_tags_match'
```

### GovCloud

```bash
ddutil apply --partition aws-us-gov --profile govcloud --account-id 123456789012
```

---

## Development

### Project Structure

```text
datadog-utility/
├── src/
│   └── ddutil/
│       ├── __init__.py
│       ├── cli.py            # All CLI commands and helpers
│       └── common/
│           ├── aws/
│           │   ├── auth.py   # boto3 session/client creation
│           │   └── iam.py    # IAM role CRUD, tag sync
│           ├── datadog/
│           │   └── aws.py    # DataDog API interactions
│           ├── logs.py
│           └── utils.py
├── .env.example
├── pyproject.toml
└── README.md
```

### Running Locally

```bash
uv venv
uv pip install -e .
ddutil --help
```

---

## Troubleshooting

**Missing required variables:**

```bash
ddutil apply --dry-run   # shows which required vars are missing
```

**AWS authentication errors:**

```bash
# Verify your profile works independently
aws sts get-caller-identity --profile your-profile

# Pass it explicitly
ddutil apply --profile your-profile

# Or let boto3 use the default credential chain (env vars, instance profile, etc.)
# simply omit --profile and do not set AWS_PROFILE
```

**DataDog API errors:**

```bash
ddutil --verbose status   # shows raw API error details
```

**Configuration drift:**

```bash
# status shows a comparison table for every mismatch
ddutil status

# Fix with apply
ddutil apply
```

**SSL certificate errors (internal CA):**

```bash
# Point to your CA bundle
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
ddutil apply

# Or disable SSL verification (not recommended for production)
DATADOG_VERIFY_SSL=false ddutil apply
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
