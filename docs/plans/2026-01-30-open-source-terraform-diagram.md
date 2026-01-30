# Open Source Terraform Diagram Generator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the AWS infrastructure diagram generator into a generic, open-source tool that accepts any Terraform folder via CLI flag and includes all necessary open-source project scaffolding.

**Architecture:** Make the environment parameter optional, add direct folder parsing mode, extract hardcoded configurations to YAML files, add graceful icon fallback, and create complete open-source project structure (README, LICENSE, CONTRIBUTING, pyproject.toml).

**Tech Stack:** Python 3.9+, python-hcl2, PyYAML, argparse, setuptools/pyproject.toml

---

## Task 1: Add PyYAML Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add PyYAML to requirements**

```
python-hcl2>=4.3.0
PyYAML>=6.0
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add PyYAML dependency for config files"
```

---

## Task 2: Extract Aggregation Rules to YAML Config

**Files:**
- Create: `config/aggregation_rules.yaml`
- Modify: `aggregator.py`

**Step 1: Create config directory and aggregation_rules.yaml**

Create `config/aggregation_rules.yaml` with the content extracted from `aggregator.py` AGGREGATION_RULES dict. Structure:

```yaml
# Aggregation rules for grouping Terraform resources into logical services
# Format: service_name -> list of resource patterns

compute:
  ecs:
    primary: ["aws_ecs_cluster", "aws_ecs_service", "aws_ecs_task_definition"]
    secondary: ["aws_ecs_capacity_provider", "aws_appautoscaling_target", "aws_appautoscaling_policy"]
    in_vpc: true

  ec2:
    primary: ["aws_instance", "aws_launch_template", "aws_autoscaling_group"]
    secondary: ["aws_ami", "aws_ebs_volume"]
    in_vpc: true

networking:
  alb:
    primary: ["aws_lb", "aws_alb"]
    secondary: ["aws_lb_listener", "aws_lb_target_group", "aws_alb_listener", "aws_alb_target_group"]
    in_vpc: true

  vpc:
    primary: ["aws_vpc"]
    secondary: ["aws_subnet", "aws_route_table", "aws_internet_gateway", "aws_nat_gateway", "aws_route_table_association", "aws_eip"]
    in_vpc: true

  security_groups:
    primary: ["aws_security_group"]
    secondary: ["aws_security_group_rule", "aws_vpc_security_group_ingress_rule", "aws_vpc_security_group_egress_rule"]
    in_vpc: true

storage:
  s3:
    primary: ["aws_s3_bucket"]
    secondary: ["aws_s3_bucket_policy", "aws_s3_bucket_versioning", "aws_s3_bucket_lifecycle_configuration", "aws_s3_bucket_public_access_block", "aws_s3_bucket_server_side_encryption_configuration", "aws_s3_bucket_cors_configuration", "aws_s3_bucket_notification", "aws_s3_object"]
    in_vpc: false

database:
  dynamodb:
    primary: ["aws_dynamodb_table"]
    secondary: ["aws_dynamodb_table_item", "aws_dynamodb_global_table"]
    in_vpc: false

  rds:
    primary: ["aws_db_instance", "aws_rds_cluster"]
    secondary: ["aws_db_subnet_group", "aws_db_parameter_group", "aws_rds_cluster_instance"]
    in_vpc: true

  elasticache:
    primary: ["aws_elasticache_cluster", "aws_elasticache_replication_group"]
    secondary: ["aws_elasticache_subnet_group", "aws_elasticache_parameter_group"]
    in_vpc: true

messaging:
  sqs:
    primary: ["aws_sqs_queue"]
    secondary: ["aws_sqs_queue_policy"]
    in_vpc: false

  sns:
    primary: ["aws_sns_topic"]
    secondary: ["aws_sns_topic_subscription", "aws_sns_topic_policy"]
    in_vpc: false

  eventbridge:
    primary: ["aws_cloudwatch_event_rule", "aws_cloudwatch_event_bus"]
    secondary: ["aws_cloudwatch_event_target"]
    in_vpc: false

security:
  kms:
    primary: ["aws_kms_key"]
    secondary: ["aws_kms_alias"]
    in_vpc: false

  secrets_manager:
    primary: ["aws_secretsmanager_secret"]
    secondary: ["aws_secretsmanager_secret_version"]
    in_vpc: false

  iam:
    primary: ["aws_iam_role"]
    secondary: ["aws_iam_policy", "aws_iam_role_policy", "aws_iam_role_policy_attachment", "aws_iam_policy_attachment", "aws_iam_instance_profile"]
    in_vpc: false

edge:
  cloudfront:
    primary: ["aws_cloudfront_distribution"]
    secondary: ["aws_cloudfront_origin_access_identity", "aws_cloudfront_origin_access_control", "aws_cloudfront_cache_policy", "aws_cloudfront_response_headers_policy"]
    in_vpc: false

  waf:
    primary: ["aws_wafv2_web_acl"]
    secondary: ["aws_wafv2_web_acl_association", "aws_wafv2_ip_set", "aws_wafv2_rule_group"]
    in_vpc: false

  route53:
    primary: ["aws_route53_zone"]
    secondary: ["aws_route53_record"]
    in_vpc: false

  acm:
    primary: ["aws_acm_certificate"]
    secondary: ["aws_acm_certificate_validation"]
    in_vpc: false

auth:
  cognito:
    primary: ["aws_cognito_user_pool"]
    secondary: ["aws_cognito_user_pool_client", "aws_cognito_identity_pool", "aws_cognito_user_pool_domain"]
    in_vpc: false

monitoring:
  cloudwatch:
    primary: ["aws_cloudwatch_log_group"]
    secondary: ["aws_cloudwatch_log_stream", "aws_cloudwatch_metric_alarm", "aws_cloudwatch_dashboard"]
    in_vpc: false

serverless:
  lambda:
    primary: ["aws_lambda_function"]
    secondary: ["aws_lambda_permission", "aws_lambda_event_source_mapping", "aws_lambda_layer_version"]
    in_vpc: false

  api_gateway:
    primary: ["aws_api_gateway_rest_api", "aws_apigatewayv2_api"]
    secondary: ["aws_api_gateway_resource", "aws_api_gateway_method", "aws_api_gateway_integration", "aws_api_gateway_deployment", "aws_api_gateway_stage", "aws_apigatewayv2_stage", "aws_apigatewayv2_route", "aws_apigatewayv2_integration"]
    in_vpc: false

  step_functions:
    primary: ["aws_sfn_state_machine"]
    secondary: []
    in_vpc: false
```

**Step 2: Commit config file**

```bash
git add config/aggregation_rules.yaml
git commit -m "chore: extract aggregation rules to YAML config"
```

---

## Task 3: Extract Logical Connections to YAML Config

**Files:**
- Create: `config/logical_connections.yaml`

**Step 1: Create logical_connections.yaml**

```yaml
# Logical connections between services for diagram rendering
# Format: source -> target -> connection properties

connections:
  - source: cloudfront
    target: s3
    label: "Origin"
    type: data_flow

  - source: cloudfront
    target: alb
    label: "Origin"
    type: data_flow

  - source: waf
    target: cloudfront
    label: "Protect"
    type: default

  - source: waf
    target: alb
    label: "Protect"
    type: default

  - source: route53
    target: cloudfront
    label: "DNS"
    type: default

  - source: route53
    target: alb
    label: "DNS"
    type: default

  - source: acm
    target: cloudfront
    label: "TLS"
    type: default

  - source: acm
    target: alb
    label: "TLS"
    type: default

  - source: alb
    target: ecs
    label: "Route"
    type: data_flow

  - source: alb
    target: ec2
    label: "Route"
    type: data_flow

  - source: alb
    target: lambda
    label: "Route"
    type: data_flow

  - source: ecs
    target: dynamodb
    label: "Read/Write"
    type: data_flow

  - source: ecs
    target: s3
    label: "Read/Write"
    type: data_flow

  - source: ecs
    target: rds
    label: "Read/Write"
    type: data_flow

  - source: ecs
    target: elasticache
    label: "Cache"
    type: data_flow

  - source: ecs
    target: sqs
    label: "Queue"
    type: trigger

  - source: ecs
    target: sns
    label: "Publish"
    type: trigger

  - source: lambda
    target: dynamodb
    label: "Read/Write"
    type: data_flow

  - source: lambda
    target: s3
    label: "Read/Write"
    type: data_flow

  - source: lambda
    target: sqs
    label: "Process"
    type: trigger

  - source: sqs
    target: lambda
    label: "Trigger"
    type: trigger

  - source: sns
    target: sqs
    label: "Subscribe"
    type: trigger

  - source: sns
    target: lambda
    label: "Trigger"
    type: trigger

  - source: eventbridge
    target: lambda
    label: "Trigger"
    type: trigger

  - source: eventbridge
    target: sqs
    label: "Route"
    type: trigger

  - source: kms
    target: s3
    label: "Encrypt"
    type: encrypt

  - source: kms
    target: dynamodb
    label: "Encrypt"
    type: encrypt

  - source: kms
    target: sqs
    label: "Encrypt"
    type: encrypt

  - source: kms
    target: sns
    label: "Encrypt"
    type: encrypt

  - source: kms
    target: secrets_manager
    label: "Encrypt"
    type: encrypt

  - source: secrets_manager
    target: ecs
    label: "Inject"
    type: default

  - source: secrets_manager
    target: lambda
    label: "Inject"
    type: default

  - source: cognito
    target: api_gateway
    label: "Auth"
    type: default

  - source: cognito
    target: alb
    label: "Auth"
    type: default

  - source: api_gateway
    target: lambda
    label: "Invoke"
    type: trigger

  - source: step_functions
    target: lambda
    label: "Orchestrate"
    type: trigger
```

**Step 2: Commit**

```bash
git add config/logical_connections.yaml
git commit -m "chore: extract logical connections to YAML config"
```

---

## Task 4: Create Config Loader Module

**Files:**
- Create: `config_loader.py`

**Step 1: Write the test file**

Create `tests/test_config_loader.py`:

```python
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import ConfigLoader


class TestConfigLoader:
    def test_load_default_aggregation_rules(self):
        loader = ConfigLoader()
        rules = loader.get_aggregation_rules()

        assert "compute" in rules
        assert "ecs" in rules["compute"]
        assert "aws_ecs_cluster" in rules["compute"]["ecs"]["primary"]

    def test_load_default_logical_connections(self):
        loader = ConfigLoader()
        connections = loader.get_logical_connections()

        assert len(connections) > 0
        assert any(c["source"] == "cloudfront" and c["target"] == "s3" for c in connections)

    def test_custom_config_path(self, tmp_path):
        custom_config = tmp_path / "custom_rules.yaml"
        custom_config.write_text("""
compute:
  custom_service:
    primary: ["aws_custom_resource"]
    secondary: []
    in_vpc: false
""")
        loader = ConfigLoader(aggregation_rules_path=custom_config)
        rules = loader.get_aggregation_rules()

        assert "compute" in rules
        assert "custom_service" in rules["compute"]
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_config_loader.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'config_loader'"

**Step 3: Write the implementation**

Create `config_loader.py`:

```python
"""Configuration loader for Terraform Diagram Generator."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigLoader:
    """Loads configuration from YAML files with fallback to defaults."""

    def __init__(
        self,
        aggregation_rules_path: Optional[Path] = None,
        logical_connections_path: Optional[Path] = None
    ):
        self._config_dir = Path(__file__).parent / "config"
        self._aggregation_rules_path = aggregation_rules_path or self._config_dir / "aggregation_rules.yaml"
        self._logical_connections_path = logical_connections_path or self._config_dir / "logical_connections.yaml"

        self._aggregation_rules: Optional[Dict[str, Any]] = None
        self._logical_connections: Optional[List[Dict[str, Any]]] = None

    def get_aggregation_rules(self) -> Dict[str, Any]:
        """Load and return aggregation rules."""
        if self._aggregation_rules is None:
            self._aggregation_rules = self._load_yaml(self._aggregation_rules_path)
        return self._aggregation_rules

    def get_logical_connections(self) -> List[Dict[str, Any]]:
        """Load and return logical connections."""
        if self._logical_connections is None:
            data = self._load_yaml(self._logical_connections_path)
            self._logical_connections = data.get("connections", [])
        return self._logical_connections

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file and return parsed content."""
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_flat_aggregation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Return aggregation rules flattened to service_name -> config mapping."""
        rules = self.get_aggregation_rules()
        flat = {}
        for category, services in rules.items():
            for service_name, config in services.items():
                flat[service_name] = {
                    "category": category,
                    **config
                }
        return flat
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_config_loader.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add config_loader.py tests/test_config_loader.py
git commit -m "feat: add ConfigLoader for YAML configuration"
```

---

## Task 5: Update Aggregator to Use ConfigLoader

**Files:**
- Modify: `aggregator.py`

**Step 1: Read current aggregator.py**

Read the file to understand current AGGREGATION_RULES structure.

**Step 2: Update aggregator.py imports and initialization**

Add at top of file:

```python
from config_loader import ConfigLoader
```

**Step 3: Modify ResourceAggregator.__init__ to accept config**

Update the `__init__` method to accept an optional `ConfigLoader` and build the rules from YAML:

```python
def __init__(self, config_loader: Optional[ConfigLoader] = None):
    self._config = config_loader or ConfigLoader()
    self._aggregation_rules = self._build_aggregation_rules()
    self._logical_connections = self._config.get_logical_connections()
```

**Step 4: Add _build_aggregation_rules method**

```python
def _build_aggregation_rules(self) -> Dict[str, Dict[str, Any]]:
    """Build aggregation rules dict from config."""
    flat_rules = self._config.get_flat_aggregation_rules()
    result = {}
    for service_name, config in flat_rules.items():
        result[service_name] = {
            "primary": config.get("primary", []),
            "secondary": config.get("secondary", []),
            "in_vpc": config.get("in_vpc", False)
        }
    return result
```

**Step 5: Replace hardcoded AGGREGATION_RULES usage**

Replace `AGGREGATION_RULES` references with `self._aggregation_rules`.

**Step 6: Replace hardcoded LOGICAL_CONNECTIONS usage**

Replace `LOGICAL_CONNECTIONS` references with `self._logical_connections`, converting from list format to expected lookup format in the relevant methods.

**Step 7: Run existing tests (if any) or manual verification**

```bash
python -m pytest tests/ -v || python main.py --help
```

**Step 8: Commit**

```bash
git add aggregator.py
git commit -m "refactor: use ConfigLoader for aggregation rules"
```

---

## Task 6: Make Environment Parameter Optional in CLI

**Files:**
- Modify: `main.py`

**Step 1: Read current main.py**

Read to understand current argument structure.

**Step 2: Update argparse to make environment optional**

Change `-e, --environment` from required to optional with default `None`:

```python
parser.add_argument(
    '-e', '--environment',
    help='Environment name (dev, staging, prod). If not provided, parses the terraform directory directly.',
    default=None
)
```

**Step 3: Update main() logic to handle both modes**

```python
def main():
    args = parse_args()

    terraform_path = Path(args.terraform)
    icons_path = Path(args.icons) if args.icons else None
    output_path = Path(args.output)

    # Determine parsing mode
    if args.environment:
        # Environment mode: terraform_path/environment/
        parse_path = terraform_path / args.environment
        title = f"{args.environment.upper()} Environment"
    else:
        # Direct mode: terraform_path is the folder to parse
        parse_path = terraform_path
        title = terraform_path.name

    if not parse_path.exists():
        print(f"Error: Path does not exist: {parse_path}")
        sys.exit(1)

    # Continue with parsing...
```

**Step 4: Make icons path optional with graceful fallback**

```python
parser.add_argument(
    '-i', '--icons',
    help='AWS icons directory path (optional - falls back to colored boxes if not provided)',
    default=None
)
```

**Step 5: Run manual test**

```bash
python main.py --help
```

Verify both modes are documented.

**Step 6: Commit**

```bash
git add main.py
git commit -m "feat: make environment parameter optional for direct folder parsing"
```

---

## Task 7: Update Parser for Direct Folder Mode

**Files:**
- Modify: `parser.py`

**Step 1: Read current parser.py**

Read to understand `parse_environment` method.

**Step 2: Add parse_directory method**

Add a new method that parses a directory directly without environment assumption:

```python
def parse_directory(self, directory: Path) -> ParseResult:
    """Parse all Terraform files in a directory (non-environment mode).

    Args:
        directory: Path to directory containing .tf files

    Returns:
        ParseResult with all resources and relationships
    """
    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory}")

    resources = []
    module_calls = []

    # Parse all .tf files in directory
    tf_files = list(directory.glob("*.tf"))
    if not tf_files:
        print(f"Warning: No .tf files found in {directory}")

    for tf_file in tf_files:
        file_resources, file_modules = self._parse_tf_file(tf_file)
        resources.extend(file_resources)
        module_calls.extend(file_modules)

    # Parse modules recursively
    for module in module_calls:
        module_resources = self._parse_module(module, directory)
        resources.extend(module_resources)

    # Extract relationships
    relationships = self._extract_relationships(resources)

    return ParseResult(
        resources=resources,
        module_calls=module_calls,
        relationships=relationships
    )
```

**Step 3: Run verification**

```bash
python -c "from parser import TerraformParser; print('OK')"
```

**Step 4: Commit**

```bash
git add parser.py
git commit -m "feat: add parse_directory method for direct folder parsing"
```

---

## Task 8: Update Main to Use New Parser Method

**Files:**
- Modify: `main.py`

**Step 1: Update main() to call correct parser method**

```python
# Parse Terraform
parser = TerraformParser()

if args.environment:
    # Environment mode
    result = parser.parse_environment(terraform_path, args.environment)
else:
    # Direct folder mode
    result = parser.parse_directory(parse_path)
```

**Step 2: Run end-to-end test**

```bash
python main.py -t . -o test_output.html --help
```

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: integrate direct folder parsing in main"
```

---

## Task 9: Add Graceful Icon Fallback

**Files:**
- Modify: `icons.py`

**Step 1: Read current icons.py**

Understand the IconMapper class and fallback behavior.

**Step 2: Update IconMapper to handle None icons_path**

Update `__init__` to accept `None` and always use fallback:

```python
def __init__(self, icons_path: Optional[Path] = None):
    self.icons_path = icons_path
    self._icon_cache: Dict[str, str] = {}

    if icons_path and icons_path.exists():
        self._discover_icon_directories()
    else:
        self._resource_icons_path = None
        self._architecture_icons_path = None
        self._group_icons_path = None
```

**Step 3: Update get_icon method for graceful fallback**

Ensure `get_icon` returns a colored rectangle SVG when icons_path is None or icon not found.

**Step 4: Commit**

```bash
git add icons.py
git commit -m "feat: graceful icon fallback when icons path not provided"
```

---

## Task 10: Auto-discover Icon Directory Structure

**Files:**
- Modify: `icons.py`

**Step 1: Add icon directory discovery method**

Replace hardcoded date-based paths with pattern matching:

```python
def _discover_icon_directories(self) -> None:
    """Auto-discover AWS icon directory structure."""
    if not self.icons_path:
        return

    # Find Resource-Icons directory (pattern: Resource-Icons_*)
    resource_dirs = list(self.icons_path.glob("Resource-Icons_*"))
    self._resource_icons_path = resource_dirs[0] if resource_dirs else None

    # Find Architecture-Service-Icons directory
    arch_dirs = list(self.icons_path.glob("Architecture-Service-Icons_*"))
    self._architecture_icons_path = arch_dirs[0] if arch_dirs else None

    # Find Architecture-Group-Icons directory
    group_dirs = list(self.icons_path.glob("Architecture-Group-Icons_*"))
    self._group_icons_path = group_dirs[0] if group_dirs else None
```

**Step 2: Update icon resolution to use discovered paths**

Replace hardcoded paths in `_find_icon_file` method.

**Step 3: Commit**

```bash
git add icons.py
git commit -m "feat: auto-discover AWS icon directory structure"
```

---

## Task 11: Create pyproject.toml for Modern Python Packaging

**Files:**
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "terraform-diagram"
version = "1.0.0"
description = "Generate interactive architecture diagrams from Terraform configurations"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = [
    "terraform",
    "infrastructure",
    "diagram",
    "aws",
    "visualization",
    "architecture"
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Documentation",
    "Topic :: System :: Systems Administration",
]
dependencies = [
    "python-hcl2>=4.3.0",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "black>=23.0",
    "ruff>=0.1.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/terraform-diagram"
Documentation = "https://github.com/yourusername/terraform-diagram#readme"
Repository = "https://github.com/yourusername/terraform-diagram.git"
Issues = "https://github.com/yourusername/terraform-diagram/issues"

[project.scripts]
terraform-diagram = "terraform_diagram.main:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["terraform_diagram*"]

[tool.setuptools.package-data]
terraform_diagram = ["config/*.yaml"]

[tool.black]
line-length = 100
target-version = ["py39", "py310", "py311", "py312"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

**Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml for modern Python packaging"
```

---

## Task 12: Restructure as Python Package

**Files:**
- Create: `terraform_diagram/` directory
- Move: all `.py` files into `terraform_diagram/`
- Move: `config/` into `terraform_diagram/`
- Update: imports in all files

**Step 1: Create package directory structure**

```bash
mkdir -p terraform_diagram
mv __init__.py __main__.py main.py parser.py aggregator.py icons.py layout.py renderer.py config_loader.py terraform_diagram/
mv config terraform_diagram/
```

**Step 2: Update __init__.py**

```python
"""Terraform Diagram Generator - Create architecture diagrams from Terraform."""

__version__ = "1.0.0"

from .parser import TerraformParser
from .aggregator import ResourceAggregator
from .layout import LayoutEngine
from .renderer import SVGRenderer, HTMLRenderer
from .config_loader import ConfigLoader

__all__ = [
    "__version__",
    "TerraformParser",
    "ResourceAggregator",
    "LayoutEngine",
    "SVGRenderer",
    "HTMLRenderer",
    "ConfigLoader",
]
```

**Step 3: Update all relative imports**

In each file, change:
- `from parser import ...` to `from .parser import ...`
- `from aggregator import ...` to `from .aggregator import ...`
- etc.

**Step 4: Move tests directory**

```bash
mkdir -p tests
```

**Step 5: Verify package works**

```bash
python -m terraform_diagram --help
```

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: restructure as proper Python package"
```

---

## Task 13: Create README.md

**Files:**
- Create: `README.md`

**Step 1: Write comprehensive README**

```markdown
# Terraform Diagram Generator

Generate interactive architecture diagrams from your Terraform configurations. Supports AWS resources with automatic service grouping, relationship detection, and beautiful SVG/HTML output.

![Example Diagram](docs/example-diagram.png)

## Features

- **Automatic parsing** of Terraform HCL files
- **Smart resource grouping** into logical services (ECS, RDS, S3, etc.)
- **Relationship detection** based on resource references
- **Interactive HTML output** with drag-and-drop positioning
- **PNG/JPG export** directly from the browser
- **Customizable** via YAML configuration files
- **No cloud credentials required** - works entirely offline

## Installation

### From PyPI

```bash
pip install terraform-diagram
```

### From Source

```bash
git clone https://github.com/yourusername/terraform-diagram.git
cd terraform-diagram
pip install -e .
```

## Quick Start

### Basic Usage

Generate a diagram from a Terraform directory:

```bash
terraform-diagram -t ./infrastructure -o diagram.html
```

### With Environment Subdirectories

If your Terraform is organized by environment:

```bash
terraform-diagram -t ./infrastructure -e prod -o prod-diagram.html
```

### With AWS Icons

For beautiful AWS service icons, download the [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) and extract them:

```bash
terraform-diagram -t ./infrastructure -i ./AWS_Icons -o diagram.html
```

## Command Line Options

| Option | Required | Description |
|--------|----------|-------------|
| `-t, --terraform` | Yes | Path to Terraform directory |
| `-e, --environment` | No | Environment subdirectory (dev, staging, prod) |
| `-i, --icons` | No | Path to AWS icons directory |
| `-o, --output` | Yes | Output HTML file path |
| `-v, --verbose` | No | Enable debug output |

## Configuration

### Custom Aggregation Rules

Create `~/.terraform-diagram/aggregation_rules.yaml` to customize how resources are grouped:

```yaml
compute:
  my_custom_service:
    primary: ["aws_my_resource"]
    secondary: ["aws_my_helper"]
    in_vpc: true
```

### Custom Connections

Create `~/.terraform-diagram/logical_connections.yaml` to define service relationships:

```yaml
connections:
  - source: my_service
    target: another_service
    label: "Custom Connection"
    type: data_flow
```

## Supported Resources

The tool supports 100+ AWS resource types including:

- **Compute**: ECS, EC2, Lambda, Auto Scaling
- **Networking**: VPC, ALB/NLB, Route53, CloudFront
- **Storage**: S3, EBS, EFS
- **Database**: RDS, DynamoDB, ElastiCache
- **Messaging**: SQS, SNS, EventBridge
- **Security**: IAM, KMS, Secrets Manager, WAF
- **And many more...**

## Output

The generated HTML file includes:

- **Interactive diagram** with pan and zoom
- **Drag-and-drop** to reposition services
- **Click connections** to highlight data flows
- **Export buttons** for PNG and JPG
- **Save/Load layout** using browser storage

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README"
```

---

## Task 14: Create LICENSE File

**Files:**
- Create: `LICENSE`

**Step 1: Create MIT License file**

```
MIT License

Copyright (c) 2024 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 2: Commit**

```bash
git add LICENSE
git commit -m "docs: add MIT license"
```

---

## Task 15: Create CONTRIBUTING.md

**Files:**
- Create: `CONTRIBUTING.md`

**Step 1: Write contributing guidelines**

```markdown
# Contributing to Terraform Diagram Generator

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/terraform-diagram.git`
3. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
4. Install dev dependencies: `pip install -e ".[dev]"`
5. Create a branch: `git checkout -b feature/your-feature`

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

We use `black` for formatting and `ruff` for linting:

```bash
black terraform_diagram/
ruff check terraform_diagram/
```

### Adding New Resource Types

1. Add the resource mapping to `config/aggregation_rules.yaml`
2. Add icon mapping to `terraform_diagram/icons.py` in `TERRAFORM_TO_ICON`
3. Add any new connections to `config/logical_connections.yaml`
4. Add tests for the new resource type

## Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Add a clear description of changes
4. Reference any related issues

## Code of Conduct

Be respectful and constructive. We're all here to build something useful together.

## Questions?

Open an issue with your question and we'll help out!
```

**Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add contributing guidelines"
```

---

## Task 16: Create .gitignore

**Files:**
- Create: `.gitignore`

**Step 1: Write .gitignore**

```gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Testing
.tox/
.coverage
.pytest_cache/
htmlcov/
.hypothesis/

# Build outputs
*.html
!docs/**/*.html

# AWS Icons (user should download separately)
AWS_Icons/
AWS_ICONS/

# OS files
.DS_Store
Thumbs.db

# Local config
.terraform-diagram/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Task 17: Create Example Terraform Files

**Files:**
- Create: `examples/simple/main.tf`
- Create: `examples/simple/variables.tf`

**Step 1: Create examples directory**

```bash
mkdir -p examples/simple
```

**Step 2: Create example main.tf**

```hcl
# examples/simple/main.tf
# Simple AWS infrastructure for demonstration

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project}-vpc"
  }
}

resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = "${var.region}${count.index == 0 ? "a" : "b"}"

  tags = {
    Name = "${var.project}-public-${count.index + 1}"
  }
}

# Security Group
resource "aws_security_group" "web" {
  name        = "${var.project}-web-sg"
  description = "Security group for web servers"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.project}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.web.id]
  subnets            = aws_subnet.public[*].id
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project}-cluster"
}

# DynamoDB Table
resource "aws_dynamodb_table" "main" {
  name         = "${var.project}-data"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# S3 Bucket
resource "aws_s3_bucket" "assets" {
  bucket = "${var.project}-assets-${var.region}"
}

# SQS Queue
resource "aws_sqs_queue" "tasks" {
  name = "${var.project}-tasks"
}
```

**Step 3: Create example variables.tf**

```hcl
# examples/simple/variables.tf

variable "project" {
  description = "Project name"
  type        = string
  default     = "demo"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}
```

**Step 4: Commit**

```bash
git add examples/
git commit -m "docs: add example Terraform files"
```

---

## Task 18: Create Tests Directory Structure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Move: `tests/test_config_loader.py` (if created earlier)

**Step 1: Create test infrastructure**

Create `tests/__init__.py`:

```python
"""Tests for terraform-diagram."""
```

Create `tests/conftest.py`:

```python
"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def examples_dir() -> Path:
    """Return path to examples directory."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def simple_example(examples_dir) -> Path:
    """Return path to simple example."""
    return examples_dir / "simple"
```

**Step 2: Commit**

```bash
git add tests/
git commit -m "test: add test infrastructure"
```

---

## Task 19: Add Basic Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write the test**

```python
"""Integration tests for the full pipeline."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from terraform_diagram.parser import TerraformParser
from terraform_diagram.aggregator import ResourceAggregator
from terraform_diagram.layout import LayoutEngine
from terraform_diagram.renderer import SVGRenderer, HTMLRenderer


class TestFullPipeline:
    def test_parse_simple_example(self, simple_example):
        """Test parsing the simple example directory."""
        parser = TerraformParser()
        result = parser.parse_directory(simple_example)

        assert len(result.resources) > 0

        resource_types = {r.resource_type for r in result.resources}
        assert "aws_vpc" in resource_types
        assert "aws_ecs_cluster" in resource_types
        assert "aws_s3_bucket" in resource_types

    def test_aggregation(self, simple_example):
        """Test resource aggregation."""
        parser = TerraformParser()
        result = parser.parse_directory(simple_example)

        aggregator = ResourceAggregator()
        aggregated = aggregator.aggregate(result)

        assert len(aggregated.services) > 0

        service_names = {s.name for s in aggregated.services}
        assert "ecs" in service_names or any("ecs" in n for n in service_names)

    def test_full_pipeline_produces_html(self, simple_example, tmp_path):
        """Test the full pipeline produces valid HTML."""
        parser = TerraformParser()
        result = parser.parse_directory(simple_example)

        aggregator = ResourceAggregator()
        aggregated = aggregator.aggregate(result)

        layout = LayoutEngine()
        positioned = layout.calculate_layout(aggregated)

        svg_renderer = SVGRenderer()
        svg = svg_renderer.render(positioned)

        html_renderer = HTMLRenderer()
        html = html_renderer.render(svg, "Test Diagram")

        output_file = tmp_path / "test_diagram.html"
        output_file.write_text(html)

        assert output_file.exists()
        assert "<html" in html
        assert "<svg" in html
```

**Step 2: Run tests**

```bash
python -m pytest tests/test_integration.py -v
```

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full pipeline"
```

---

## Task 20: Update __init__.py Version and Final Cleanup

**Files:**
- Modify: `terraform_diagram/__init__.py`

**Step 1: Ensure version matches pyproject.toml**

```python
"""Terraform Diagram Generator - Create architecture diagrams from Terraform."""

__version__ = "1.0.0"
```

**Step 2: Run full test suite**

```bash
python -m pytest tests/ -v
```

**Step 3: Test CLI**

```bash
python -m terraform_diagram -t examples/simple -o test_output.html
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: finalize v1.0.0 release preparation"
```

---

## Task 21: Create GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create workflow file**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check terraform_diagram/

      - name: Test with pytest
        run: pytest tests/ -v --cov=terraform_diagram --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build package
        run: |
          pip install build
          python -m build

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

**Step 2: Commit**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow"
```

---

## Summary

This plan transforms the project into a proper open-source Python package with:

1. **CLI flexibility**: Environment parameter is now optional
2. **Configuration**: Externalized to YAML files
3. **Modern packaging**: pyproject.toml with proper metadata
4. **Documentation**: README, LICENSE, CONTRIBUTING
5. **Testing**: pytest infrastructure with integration tests
6. **CI/CD**: GitHub Actions workflow
7. **Examples**: Sample Terraform files for testing

Total: 21 tasks, approximately 21 commits
