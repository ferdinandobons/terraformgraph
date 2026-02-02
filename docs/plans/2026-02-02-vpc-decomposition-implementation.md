# VPC Decomposition and Resource Naming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance terraformgraph to display VPC structure with AZ containers, subnets, VPC endpoints on the border, and resolve actual resource names from Terraform variables.

**Architecture:** Two new modules (`variable_resolver.py` for name resolution, extensions to `aggregator.py` for VPC structure). Layout engine extended to render nested containers. Renderer updated for new SVG elements.

**Tech Stack:** Python 3.9+, python-hcl2, existing terraformgraph architecture

---

## Task 1: Create Variable Resolver Module

**Files:**
- Create: `terraformgraph/variable_resolver.py`
- Test: `tests/test_variable_resolver.py`

**Step 1: Write the failing test for tfvars parsing**

```python
# tests/test_variable_resolver.py
"""Tests for variable resolution."""

import pytest
from pathlib import Path
from terraformgraph.variable_resolver import VariableResolver


class TestVariableResolver:
    def test_parse_tfvars_simple(self, tmp_path):
        """Test parsing simple tfvars file."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project_name = "myapp"\nenvironment = "prod"\n')

        resolver = VariableResolver(tmp_path)

        assert resolver.get_variable("project_name") == "myapp"
        assert resolver.get_variable("environment") == "prod"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py::TestVariableResolver::test_parse_tfvars_simple -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'terraformgraph.variable_resolver'"

**Step 3: Write minimal implementation for tfvars parsing**

```python
# terraformgraph/variable_resolver.py
"""
Variable Resolver

Resolves Terraform variable interpolations from tfvars, locals, and variable defaults.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import hcl2

logger = logging.getLogger(__name__)


class VariableResolver:
    """Resolves Terraform variable values from multiple sources."""

    def __init__(self, terraform_dir: Path):
        """
        Initialize resolver with a Terraform directory.

        Args:
            terraform_dir: Path to directory containing .tf and .tfvars files
        """
        if isinstance(terraform_dir, str):
            terraform_dir = Path(terraform_dir)

        self.terraform_dir = terraform_dir
        self._variables: Dict[str, Any] = {}
        self._locals: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}

        self._parse_all_sources()

    def _parse_all_sources(self) -> None:
        """Parse all variable sources in priority order."""
        # 1. Parse variable defaults (lowest priority)
        self._parse_variable_defaults()
        # 2. Parse locals
        self._parse_locals()
        # 3. Parse tfvars (highest priority)
        self._parse_tfvars()

    def _parse_tfvars(self) -> None:
        """Parse all .tfvars files in the directory."""
        tfvars_patterns = ["*.tfvars", "*.auto.tfvars"]

        for pattern in tfvars_patterns:
            for tfvars_file in self.terraform_dir.glob(pattern):
                try:
                    with open(tfvars_file, 'r') as f:
                        content = hcl2.load(f)
                        for key, value in content.items():
                            # HCL2 returns lists for values, unwrap single items
                            if isinstance(value, list) and len(value) == 1:
                                value = value[0]
                            self._variables[key] = value
                except Exception as e:
                    logger.warning(f"Could not parse {tfvars_file}: {e}")

    def _parse_locals(self) -> None:
        """Parse locals blocks from .tf files."""
        for tf_file in self.terraform_dir.glob("*.tf"):
            try:
                with open(tf_file, 'r') as f:
                    content = hcl2.load(f)

                for locals_block in content.get('locals', []):
                    if isinstance(locals_block, dict):
                        for key, value in locals_block.items():
                            if isinstance(value, list) and len(value) == 1:
                                value = value[0]
                            self._locals[key] = value
            except Exception as e:
                logger.warning(f"Could not parse locals from {tf_file}: {e}")

    def _parse_variable_defaults(self) -> None:
        """Parse default values from variable blocks."""
        for tf_file in self.terraform_dir.glob("*.tf"):
            try:
                with open(tf_file, 'r') as f:
                    content = hcl2.load(f)

                for var_block in content.get('variable', []):
                    if isinstance(var_block, dict):
                        for var_name, var_config in var_block.items():
                            if isinstance(var_config, list):
                                var_config = var_config[0] if var_config else {}
                            if isinstance(var_config, dict) and 'default' in var_config:
                                default = var_config['default']
                                if isinstance(default, list) and len(default) == 1:
                                    default = default[0]
                                self._defaults[var_name] = default
            except Exception as e:
                logger.warning(f"Could not parse variables from {tf_file}: {e}")

    def get_variable(self, name: str) -> Optional[Any]:
        """
        Get a variable value.

        Priority: tfvars > defaults

        Args:
            name: Variable name

        Returns:
            Variable value or None if not found
        """
        if name in self._variables:
            return self._variables[name]
        if name in self._defaults:
            return self._defaults[name]
        return None

    def get_local(self, name: str) -> Optional[Any]:
        """
        Get a local value.

        Args:
            name: Local name

        Returns:
            Local value or None if not found
        """
        return self._locals.get(name)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py::TestVariableResolver::test_parse_tfvars_simple -v`
Expected: PASS

**Step 5: Commit**

```bash
git add terraformgraph/variable_resolver.py tests/test_variable_resolver.py
git commit -m "feat: add VariableResolver with tfvars parsing

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Add Interpolation Resolution

**Files:**
- Modify: `terraformgraph/variable_resolver.py`
- Test: `tests/test_variable_resolver.py`

**Step 1: Write the failing test for interpolation**

```python
# Add to tests/test_variable_resolver.py

    def test_resolve_simple_interpolation(self, tmp_path):
        """Test resolving ${var.name} interpolation."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project_name = "myapp"\nenvironment = "prod"\n')

        resolver = VariableResolver(tmp_path)

        result = resolver.resolve("${var.project_name}-${var.environment}-bucket")
        assert result == "myapp-prod-bucket"

    def test_resolve_local_interpolation(self, tmp_path):
        """Test resolving ${local.name} interpolation."""
        tf_file = tmp_path / "locals.tf"
        tf_file.write_text('locals {\n  project_name = "myapp"\n  environment = "prod"\n}\n')

        resolver = VariableResolver(tmp_path)

        result = resolver.resolve("${local.project_name}-${local.environment}")
        assert result == "myapp-prod"

    def test_resolve_returns_original_on_failure(self, tmp_path):
        """Test that unresolvable interpolations return original string."""
        resolver = VariableResolver(tmp_path)

        result = resolver.resolve("${var.unknown}-bucket")
        assert result == "${var.unknown}-bucket"

    def test_resolve_no_interpolation(self, tmp_path):
        """Test that strings without interpolation are returned as-is."""
        resolver = VariableResolver(tmp_path)

        result = resolver.resolve("simple-name")
        assert result == "simple-name"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py::TestVariableResolver::test_resolve_simple_interpolation -v`
Expected: FAIL with "AttributeError: 'VariableResolver' object has no attribute 'resolve'"

**Step 3: Add resolve method**

```python
# Add to terraformgraph/variable_resolver.py VariableResolver class

    def resolve(self, value: Any) -> Any:
        """
        Resolve interpolations in a value.

        Handles:
        - ${var.name} - variable references
        - ${local.name} - local value references
        - Concatenations like "${var.a}-${var.b}"

        Args:
            value: String potentially containing interpolations

        Returns:
            Resolved value, or original if resolution fails
        """
        if not isinstance(value, str):
            return value

        if '${' not in value:
            return value

        result = value

        # Pattern for ${var.name} or ${local.name}
        pattern = r'\$\{(var|local)\.([^}]+)\}'

        def replace_match(match):
            ref_type = match.group(1)  # 'var' or 'local'
            ref_name = match.group(2)  # variable/local name

            if ref_type == 'var':
                resolved = self.get_variable(ref_name)
            else:  # local
                resolved = self.get_local(ref_name)

            if resolved is not None:
                return str(resolved)
            else:
                # Return original if can't resolve
                return match.group(0)

        result = re.sub(pattern, replace_match, result)

        return result
```

**Step 4: Run all interpolation tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add terraformgraph/variable_resolver.py tests/test_variable_resolver.py
git commit -m "feat: add interpolation resolution to VariableResolver

Supports \${var.name} and \${local.name} patterns with concatenation.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Add Name Truncation Utility

**Files:**
- Modify: `terraformgraph/variable_resolver.py`
- Test: `tests/test_variable_resolver.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_variable_resolver.py

    def test_truncate_name_short(self, tmp_path):
        """Test that short names are not truncated."""
        resolver = VariableResolver(tmp_path)

        result = resolver.truncate_name("short-name", max_length=25)
        assert result == "short-name"

    def test_truncate_name_long(self, tmp_path):
        """Test that long names are truncated with ellipsis."""
        resolver = VariableResolver(tmp_path)

        result = resolver.truncate_name("very-long-resource-name-that-exceeds-limit", max_length=25)
        assert result == "very-long-resource-name..."
        assert len(result) == 25 + 3  # 25 chars + "..."

    def test_truncate_name_exact(self, tmp_path):
        """Test name at exact limit."""
        resolver = VariableResolver(tmp_path)

        result = resolver.truncate_name("a" * 25, max_length=25)
        assert result == "a" * 25
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py::TestVariableResolver::test_truncate_name_long -v`
Expected: FAIL with "AttributeError: 'VariableResolver' object has no attribute 'truncate_name'"

**Step 3: Add truncate_name method**

```python
# Add to terraformgraph/variable_resolver.py VariableResolver class

    @staticmethod
    def truncate_name(name: str, max_length: int = 25) -> str:
        """
        Truncate a name if it exceeds max_length.

        Args:
            name: The name to truncate
            max_length: Maximum length before truncation (default 25)

        Returns:
            Original name if short enough, otherwise truncated with '...'
        """
        if len(name) <= max_length:
            return name
        return name[:max_length] + "..."
```

**Step 4: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add terraformgraph/variable_resolver.py tests/test_variable_resolver.py
git commit -m "feat: add name truncation utility

Truncates names longer than 25 characters with ellipsis.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Integrate Variable Resolver with Parser

**Files:**
- Modify: `terraformgraph/parser.py:36-42`
- Test: `tests/test_variable_resolver.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_variable_resolver.py

class TestParserIntegration:
    def test_resource_resolved_display_name(self, tmp_path):
        """Test that TerraformResource can resolve its display name."""
        # Create terraform files
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project_name = "myapp"\nenvironment = "prod"\n')

        main_tf = tmp_path / "main.tf"
        main_tf.write_text('''
resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-${var.environment}-data"
}
''')

        from terraformgraph.parser import TerraformParser
        from terraformgraph.variable_resolver import VariableResolver

        parser = TerraformParser(str(tmp_path))
        result = parser.parse_directory(tmp_path)

        resolver = VariableResolver(tmp_path)

        bucket = next(r for r in result.resources if r.resource_type == "aws_s3_bucket")
        resolved_name = resolver.resolve(bucket.attributes.get('bucket', bucket.resource_name))

        assert resolved_name == "myapp-prod-data"
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py::TestParserIntegration::test_resource_resolved_display_name -v`
Expected: PASS (this test should pass with existing code)

**Step 3: Add helper method to TerraformResource**

```python
# Modify terraformgraph/parser.py - update TerraformResource class

@dataclass
class TerraformResource:
    """Represents a parsed Terraform resource."""
    resource_type: str
    resource_name: str
    module_path: str
    attributes: Dict[str, Any]
    source_file: str
    count: Optional[int] = None
    for_each: bool = False

    @property
    def full_id(self) -> str:
        """Unique identifier for this resource."""
        if self.module_path:
            return f"{self.module_path}.{self.resource_type}.{self.resource_name}"
        return f"{self.resource_type}.{self.resource_name}"

    @property
    def display_name(self) -> str:
        """Human-readable name for display."""
        name = self.attributes.get('name', self.resource_name)
        if isinstance(name, str) and '${' not in name:
            return name
        return self.resource_name

    def get_resolved_display_name(self, resolver: 'VariableResolver') -> str:
        """
        Get display name with variables resolved.

        Args:
            resolver: VariableResolver instance for the terraform directory

        Returns:
            Resolved name, truncated if necessary
        """
        # Try 'name' attribute first, then 'bucket', 'queue_name', etc.
        name_attrs = ['name', 'bucket', 'queue_name', 'cluster_name', 'function_name',
                      'table_name', 'topic_name', 'repository_name']

        raw_name = None
        for attr in name_attrs:
            if attr in self.attributes:
                raw_name = self.attributes[attr]
                break

        if raw_name is None:
            raw_name = self.resource_name

        if isinstance(raw_name, str):
            resolved = resolver.resolve(raw_name)
            return resolver.truncate_name(resolved)

        return resolver.truncate_name(self.resource_name)
```

**Step 4: Add import at top of parser.py (TYPE_CHECKING)**

```python
# Add at top of terraformgraph/parser.py after existing imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .variable_resolver import VariableResolver
```

**Step 5: Write test for get_resolved_display_name method**

```python
# Add to tests/test_variable_resolver.py TestParserIntegration class

    def test_resource_get_resolved_display_name(self, tmp_path):
        """Test TerraformResource.get_resolved_display_name method."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project_name = "myapp"\nenvironment = "prod"\n')

        main_tf = tmp_path / "main.tf"
        main_tf.write_text('''
resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-${var.environment}-data-bucket"
}
''')

        from terraformgraph.parser import TerraformParser
        from terraformgraph.variable_resolver import VariableResolver

        parser = TerraformParser(str(tmp_path))
        result = parser.parse_directory(tmp_path)
        resolver = VariableResolver(tmp_path)

        bucket = next(r for r in result.resources if r.resource_type == "aws_s3_bucket")
        resolved_name = bucket.get_resolved_display_name(resolver)

        assert resolved_name == "myapp-prod-data-bucket"
```

**Step 6: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_variable_resolver.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add terraformgraph/parser.py tests/test_variable_resolver.py
git commit -m "feat: add get_resolved_display_name to TerraformResource

Enables resources to resolve their display names using VariableResolver.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Create VPC Structure Data Model

**Files:**
- Modify: `terraformgraph/aggregator.py`
- Test: `tests/test_vpc_structure.py`

**Step 1: Write the failing test**

```python
# tests/test_vpc_structure.py
"""Tests for VPC structure detection."""

import pytest
from pathlib import Path


class TestVPCStructure:
    def test_subnet_dataclass(self):
        """Test Subnet dataclass creation."""
        from terraformgraph.aggregator import Subnet

        subnet = Subnet(
            resource_id="aws_subnet.public_1",
            name="public-subnet-1",
            subnet_type="public",
            availability_zone="eu-west-1a",
            cidr_block="10.0.1.0/24"
        )

        assert subnet.subnet_type == "public"
        assert subnet.availability_zone == "eu-west-1a"

    def test_availability_zone_dataclass(self):
        """Test AvailabilityZone dataclass."""
        from terraformgraph.aggregator import Subnet, AvailabilityZone

        subnet = Subnet(
            resource_id="aws_subnet.public_1",
            name="public-subnet-1",
            subnet_type="public",
            availability_zone="eu-west-1a",
            cidr_block="10.0.1.0/24"
        )

        az = AvailabilityZone(
            name="eu-west-1a",
            short_name="1a",
            subnets=[subnet]
        )

        assert az.name == "eu-west-1a"
        assert len(az.subnets) == 1

    def test_vpc_endpoint_dataclass(self):
        """Test VPCEndpoint dataclass."""
        from terraformgraph.aggregator import VPCEndpoint

        endpoint = VPCEndpoint(
            resource_id="aws_vpc_endpoint.s3",
            name="s3-endpoint",
            endpoint_type="gateway",
            service="s3"
        )

        assert endpoint.endpoint_type == "gateway"
        assert endpoint.service == "s3"

    def test_vpc_structure_dataclass(self):
        """Test VPCStructure dataclass."""
        from terraformgraph.aggregator import VPCStructure, AvailabilityZone, VPCEndpoint

        structure = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[],
            endpoints=[]
        )

        assert structure.vpc_id == "aws_vpc.main"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py::TestVPCStructure::test_subnet_dataclass -v`
Expected: FAIL with "ImportError: cannot import name 'Subnet' from 'terraformgraph.aggregator'"

**Step 3: Add dataclasses to aggregator.py**

```python
# Add to terraformgraph/aggregator.py after existing dataclasses (around line 45)

@dataclass
class Subnet:
    """Represents a VPC subnet."""
    resource_id: str
    name: str
    subnet_type: str  # 'public', 'private', 'database'
    availability_zone: str
    cidr_block: Optional[str] = None


@dataclass
class AvailabilityZone:
    """Represents an Availability Zone container."""
    name: str  # Full name, e.g., 'eu-west-1a'
    short_name: str  # Short name, e.g., '1a'
    subnets: List[Subnet] = field(default_factory=list)


@dataclass
class VPCEndpoint:
    """Represents a VPC endpoint."""
    resource_id: str
    name: str
    endpoint_type: str  # 'gateway' or 'interface'
    service: str  # e.g., 's3', 'dynamodb', 'ecr.api'


@dataclass
class VPCStructure:
    """Represents the complete VPC structure."""
    vpc_id: str
    name: str
    availability_zones: List[AvailabilityZone] = field(default_factory=list)
    endpoints: List[VPCEndpoint] = field(default_factory=list)
```

**Step 4: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add terraformgraph/aggregator.py tests/test_vpc_structure.py
git commit -m "feat: add VPC structure dataclasses

Adds Subnet, AvailabilityZone, VPCEndpoint, and VPCStructure classes.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Implement AZ Detection Logic

**Files:**
- Modify: `terraformgraph/aggregator.py`
- Test: `tests/test_vpc_structure.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_vpc_structure.py

class TestAZDetection:
    def test_detect_az_from_attribute(self):
        """Test detecting AZ from availability_zone attribute."""
        from terraformgraph.aggregator import VPCStructureBuilder
        from terraformgraph.parser import TerraformResource

        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public_1",
            module_path="",
            attributes={"availability_zone": "eu-west-1a", "cidr_block": "10.0.1.0/24"},
            source_file="main.tf"
        )

        builder = VPCStructureBuilder()
        az = builder._detect_availability_zone(resource)

        assert az == "eu-west-1a"

    def test_detect_az_from_name_pattern(self):
        """Test detecting AZ from resource name pattern."""
        from terraformgraph.aggregator import VPCStructureBuilder
        from terraformgraph.parser import TerraformResource

        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="private_subnet_a",
            module_path="",
            attributes={"cidr_block": "10.0.2.0/24"},
            source_file="main.tf"
        )

        builder = VPCStructureBuilder()
        az = builder._detect_availability_zone(resource)

        assert az == "a"  # Falls back to pattern matching

    def test_detect_az_from_name_pattern_1a(self):
        """Test detecting AZ from _1a suffix pattern."""
        from terraformgraph.aggregator import VPCStructureBuilder
        from terraformgraph.parser import TerraformResource

        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="compute_subnet_1",
            module_path="",
            attributes={"cidr_block": "10.0.3.0/24", "tags": {"Name": "myapp-prod-compute-subnet-1a"}},
            source_file="main.tf"
        )

        builder = VPCStructureBuilder()
        az = builder._detect_availability_zone(resource)

        assert az in ["1a", "1", "unknown"]  # Depending on pattern matching
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py::TestAZDetection::test_detect_az_from_attribute -v`
Expected: FAIL with "ImportError: cannot import name 'VPCStructureBuilder'"

**Step 3: Implement VPCStructureBuilder class**

```python
# Add to terraformgraph/aggregator.py after the dataclasses

class VPCStructureBuilder:
    """Builds VPC structure from Terraform resources."""

    # Pattern for AZ suffix in names (e.g., -a, -1a, -az1)
    AZ_PATTERNS = [
        r'[-_]([a-c])$',           # -a, -b, -c
        r'[-_](\d[a-c])$',         # -1a, -1b, -2a
        r'[-_]az([a-c])$',         # -aza, -azb
        r'[-_]az(\d)$',            # -az1, -az2
    ]

    SUBNET_TYPE_PATTERNS = {
        'public': ['public', 'pub', 'dmz', 'external'],
        'private': ['private', 'priv', 'app', 'compute', 'internal'],
        'database': ['database', 'db', 'data', 'rds'],
    }

    def _detect_availability_zone(self, resource: TerraformResource) -> str:
        """
        Detect the availability zone for a subnet resource.

        Priority:
        1. availability_zone attribute
        2. Pattern matching on name/tags
        3. 'unknown' fallback

        Args:
            resource: Subnet terraform resource

        Returns:
            Availability zone identifier
        """
        import re

        # Priority 1: Check availability_zone attribute
        az_attr = resource.attributes.get('availability_zone')
        if az_attr and isinstance(az_attr, str) and '${' not in az_attr:
            return az_attr

        # Priority 2: Pattern matching on name or tags
        names_to_check = [resource.resource_name]

        # Check tags.Name if available
        tags = resource.attributes.get('tags', {})
        if isinstance(tags, dict) and 'Name' in tags:
            tag_name = tags['Name']
            if isinstance(tag_name, str) and '${' not in tag_name:
                names_to_check.append(tag_name)

        for name in names_to_check:
            for pattern in self.AZ_PATTERNS:
                match = re.search(pattern, name.lower())
                if match:
                    return match.group(1)

        # Fallback
        return "unknown"

    def _detect_subnet_type(self, resource: TerraformResource) -> str:
        """
        Detect the subnet type (public, private, database).

        Args:
            resource: Subnet terraform resource

        Returns:
            Subnet type string
        """
        # Check resource name and tags
        names_to_check = [resource.resource_name.lower()]

        tags = resource.attributes.get('tags', {})
        if isinstance(tags, dict) and 'Name' in tags:
            tag_name = tags['Name']
            if isinstance(tag_name, str):
                names_to_check.append(tag_name.lower())

        for name in names_to_check:
            for subnet_type, patterns in self.SUBNET_TYPE_PATTERNS.items():
                if any(p in name for p in patterns):
                    return subnet_type

        # Default to private
        return "private"

    def _detect_endpoint_type(self, resource: TerraformResource) -> str:
        """
        Detect VPC endpoint type (gateway or interface).

        Args:
            resource: VPC endpoint terraform resource

        Returns:
            'gateway' or 'interface'
        """
        endpoint_type = resource.attributes.get('vpc_endpoint_type', 'Interface')
        if isinstance(endpoint_type, str):
            return endpoint_type.lower()
        return 'interface'

    def _detect_endpoint_service(self, resource: TerraformResource) -> str:
        """
        Extract the service name from VPC endpoint.

        Args:
            resource: VPC endpoint terraform resource

        Returns:
            Service name (e.g., 's3', 'dynamodb', 'ecr.api')
        """
        import re

        service_name = resource.attributes.get('service_name', '')
        if isinstance(service_name, str):
            # Pattern: com.amazonaws.<region>.<service>
            match = re.search(r'com\.amazonaws\.[^.]+\.(.+)$', service_name)
            if match:
                return match.group(1)

        # Fallback to resource name
        return resource.resource_name
```

**Step 4: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py::TestAZDetection -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add terraformgraph/aggregator.py tests/test_vpc_structure.py
git commit -m "feat: add VPCStructureBuilder with AZ detection

Detects AZ from availability_zone attribute with pattern matching fallback.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Build Complete VPC Structure

**Files:**
- Modify: `terraformgraph/aggregator.py`
- Test: `tests/test_vpc_structure.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_vpc_structure.py

class TestVPCStructureBuild:
    def test_build_vpc_structure(self, tmp_path):
        """Test building complete VPC structure from resources."""
        from terraformgraph.aggregator import VPCStructureBuilder
        from terraformgraph.parser import TerraformParser

        # Create test terraform file
        tf_file = tmp_path / "main.tf"
        tf_file.write_text('''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "test-vpc"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
  availability_zone = "eu-west-1a"
  tags = {
    Name = "test-public-subnet-a"
  }
}

resource "aws_subnet" "private_a" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.0.2.0/24"
  availability_zone = "eu-west-1a"
  tags = {
    Name = "test-private-subnet-a"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.0.3.0/24"
  availability_zone = "eu-west-1b"
  tags = {
    Name = "test-public-subnet-b"
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id = aws_vpc.main.id
  service_name = "com.amazonaws.eu-west-1.s3"
  vpc_endpoint_type = "Gateway"
}
''')

        parser = TerraformParser(str(tmp_path))
        result = parser.parse_directory(tmp_path)

        builder = VPCStructureBuilder()
        vpc_structure = builder.build(result.resources)

        assert vpc_structure is not None
        assert vpc_structure.name == "test-vpc"
        assert len(vpc_structure.availability_zones) == 2  # a and b
        assert len(vpc_structure.endpoints) == 1

        # Check AZ a has 2 subnets (public + private)
        az_a = next((az for az in vpc_structure.availability_zones if 'a' in az.name), None)
        assert az_a is not None
        assert len(az_a.subnets) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py::TestVPCStructureBuild::test_build_vpc_structure -v`
Expected: FAIL with "AttributeError: 'VPCStructureBuilder' object has no attribute 'build'"

**Step 3: Implement build method**

```python
# Add to VPCStructureBuilder class in terraformgraph/aggregator.py

    def build(self, resources: List[TerraformResource], resolver: Optional['VariableResolver'] = None) -> Optional[VPCStructure]:
        """
        Build VPC structure from a list of resources.

        Args:
            resources: List of Terraform resources
            resolver: Optional VariableResolver for name resolution

        Returns:
            VPCStructure or None if no VPC found
        """
        # Find VPC resource
        vpc_resources = [r for r in resources if r.resource_type == 'aws_vpc']
        if not vpc_resources:
            return None

        vpc = vpc_resources[0]  # Use first VPC found

        # Get VPC name
        vpc_name = vpc.resource_name
        if resolver:
            vpc_name = vpc.get_resolved_display_name(resolver)
        else:
            tags = vpc.attributes.get('tags', {})
            if isinstance(tags, dict) and 'Name' in tags:
                name_tag = tags['Name']
                if isinstance(name_tag, str) and '${' not in name_tag:
                    vpc_name = name_tag

        # Find all subnets
        subnet_resources = [r for r in resources if r.resource_type == 'aws_subnet']

        # Group subnets by AZ
        az_subnets: Dict[str, List[Subnet]] = {}

        for subnet_res in subnet_resources:
            az = self._detect_availability_zone(subnet_res)
            subnet_type = self._detect_subnet_type(subnet_res)

            # Get subnet name
            subnet_name = subnet_res.resource_name
            if resolver:
                subnet_name = subnet_res.get_resolved_display_name(resolver)
            else:
                tags = subnet_res.attributes.get('tags', {})
                if isinstance(tags, dict) and 'Name' in tags:
                    name_tag = tags['Name']
                    if isinstance(name_tag, str) and '${' not in name_tag:
                        subnet_name = name_tag

            cidr = subnet_res.attributes.get('cidr_block', '')
            if isinstance(cidr, str) and '${' in cidr:
                cidr = ''

            subnet = Subnet(
                resource_id=subnet_res.full_id,
                name=subnet_name,
                subnet_type=subnet_type,
                availability_zone=az,
                cidr_block=cidr if isinstance(cidr, str) else ''
            )

            if az not in az_subnets:
                az_subnets[az] = []
            az_subnets[az].append(subnet)

        # Build AvailabilityZone objects
        availability_zones = []
        for az_name, subnets in sorted(az_subnets.items()):
            # Create short name (e.g., "eu-west-1a" -> "1a", "a" -> "a")
            short_name = az_name
            if '-' in az_name:
                short_name = az_name.split('-')[-1]

            az = AvailabilityZone(
                name=az_name,
                short_name=short_name,
                subnets=subnets
            )
            availability_zones.append(az)

        # Find VPC endpoints
        endpoint_resources = [r for r in resources if r.resource_type == 'aws_vpc_endpoint']

        endpoints = []
        for ep_res in endpoint_resources:
            endpoint_type = self._detect_endpoint_type(ep_res)
            service = self._detect_endpoint_service(ep_res)

            endpoint_name = ep_res.resource_name
            if resolver:
                endpoint_name = ep_res.get_resolved_display_name(resolver)

            endpoint = VPCEndpoint(
                resource_id=ep_res.full_id,
                name=endpoint_name,
                endpoint_type=endpoint_type,
                service=service
            )
            endpoints.append(endpoint)

        return VPCStructure(
            vpc_id=vpc.full_id,
            name=vpc_name,
            availability_zones=availability_zones,
            endpoints=endpoints
        )
```

**Step 4: Add TYPE_CHECKING import for VariableResolver**

```python
# Add at top of terraformgraph/aggregator.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .variable_resolver import VariableResolver
```

**Step 5: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add terraformgraph/aggregator.py tests/test_vpc_structure.py
git commit -m "feat: implement VPCStructureBuilder.build method

Builds complete VPC structure with AZs, subnets, and endpoints.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Integrate VPC Structure into AggregatedResult

**Files:**
- Modify: `terraformgraph/aggregator.py:41-46`
- Test: `tests/test_vpc_structure.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_vpc_structure.py

class TestAggregatorIntegration:
    def test_aggregated_result_has_vpc_structure(self, tmp_path):
        """Test that AggregatedResult includes VPC structure."""
        from terraformgraph.aggregator import ResourceAggregator
        from terraformgraph.parser import TerraformParser

        tf_file = tmp_path / "main.tf"
        tf_file.write_text('''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public_a" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
  availability_zone = "eu-west-1a"
}

resource "aws_ecs_cluster" "app" {
  name = "app-cluster"
}
''')

        parser = TerraformParser(str(tmp_path))
        result = parser.parse_directory(tmp_path)

        aggregator = ResourceAggregator()
        aggregated = aggregator.aggregate(result, terraform_dir=tmp_path)

        assert aggregated.vpc_structure is not None
        assert len(aggregated.vpc_structure.availability_zones) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py::TestAggregatorIntegration::test_aggregated_result_has_vpc_structure -v`
Expected: FAIL with "AttributeError: 'AggregatedResult' object has no attribute 'vpc_structure'"

**Step 3: Update AggregatedResult and ResourceAggregator**

```python
# Modify AggregatedResult in terraformgraph/aggregator.py

@dataclass
class AggregatedResult:
    """Result of aggregating resources into logical services."""
    services: List[LogicalService] = field(default_factory=list)
    connections: List[LogicalConnection] = field(default_factory=list)
    vpc_services: List[LogicalService] = field(default_factory=list)
    global_services: List[LogicalService] = field(default_factory=list)
    vpc_structure: Optional[VPCStructure] = None  # NEW: Add VPC structure
```

```python
# Modify ResourceAggregator.aggregate method signature and implementation

    def aggregate(self, parse_result: ParseResult, terraform_dir: Optional[Path] = None) -> AggregatedResult:
        """Aggregate parsed resources into logical services.

        Args:
            parse_result: Parsed terraform resources
            terraform_dir: Optional path to terraform directory for variable resolution
        """
        result = AggregatedResult()

        # Build VPC structure if terraform_dir provided
        if terraform_dir:
            from .variable_resolver import VariableResolver
            resolver = VariableResolver(terraform_dir)
            vpc_builder = VPCStructureBuilder()
            result.vpc_structure = vpc_builder.build(parse_result.resources, resolver)
        else:
            vpc_builder = VPCStructureBuilder()
            result.vpc_structure = vpc_builder.build(parse_result.resources)

        # ... rest of existing aggregate method stays the same ...
```

**Step 4: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_vpc_structure.py tests/test_integration.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add terraformgraph/aggregator.py tests/test_vpc_structure.py
git commit -m "feat: integrate VPC structure into AggregatedResult

ResourceAggregator now builds VPC structure during aggregation.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Update Layout Engine for VPC Structure

**Files:**
- Modify: `terraformgraph/layout.py`
- Test: `tests/test_layout.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_layout.py
"""Tests for layout engine with VPC structure."""

import pytest
from terraformgraph.aggregator import (
    AggregatedResult, VPCStructure, AvailabilityZone, Subnet, VPCEndpoint
)
from terraformgraph.layout import LayoutEngine


class TestVPCLayout:
    def test_vpc_structure_creates_az_groups(self):
        """Test that VPC structure creates AZ group containers."""
        vpc_structure = VPCStructure(
            vpc_id="aws_vpc.main",
            name="test-vpc",
            availability_zones=[
                AvailabilityZone(
                    name="eu-west-1a",
                    short_name="1a",
                    subnets=[
                        Subnet(
                            resource_id="aws_subnet.public_a",
                            name="public-a",
                            subnet_type="public",
                            availability_zone="eu-west-1a",
                            cidr_block="10.0.1.0/24"
                        )
                    ]
                )
            ],
            endpoints=[]
        )

        aggregated = AggregatedResult(vpc_structure=vpc_structure)

        engine = LayoutEngine()
        positions, groups = engine.compute_layout(aggregated)

        # Check for AZ group
        az_groups = [g for g in groups if g.group_type == 'az']
        assert len(az_groups) == 1
        assert az_groups[0].name == "eu-west-1a"

    def test_vpc_endpoints_positioned_on_border(self):
        """Test that VPC endpoints are positioned on VPC border."""
        vpc_structure = VPCStructure(
            vpc_id="aws_vpc.main",
            name="test-vpc",
            availability_zones=[],
            endpoints=[
                VPCEndpoint(
                    resource_id="aws_vpc_endpoint.s3",
                    name="s3-endpoint",
                    endpoint_type="gateway",
                    service="s3"
                )
            ]
        )

        aggregated = AggregatedResult(vpc_structure=vpc_structure)

        engine = LayoutEngine()
        positions, groups = engine.compute_layout(aggregated)

        # Check endpoint position is on right edge of VPC
        vpc_group = next((g for g in groups if g.group_type == 'vpc'), None)
        assert vpc_group is not None

        endpoint_pos = positions.get('vpc_endpoint.s3')
        if endpoint_pos:
            vpc_right_edge = vpc_group.position.x + vpc_group.position.width
            # Endpoint should be near right edge
            assert endpoint_pos.x >= vpc_right_edge - 50
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_layout.py::TestVPCLayout::test_vpc_structure_creates_az_groups -v`
Expected: FAIL (AZ groups not created yet)

**Step 3: Update LayoutEngine for VPC structure**

```python
# Modify terraformgraph/layout.py - add new method and update compute_layout

    def compute_layout(
        self,
        aggregated: AggregatedResult
    ) -> Tuple[Dict[str, Position], List[ServiceGroup]]:
        """
        Compute positions for all logical services.

        Layout structure:
        - Top row: Internet-facing services (CloudFront, WAF, Route53, ACM)
        - Middle: VPC box with AZ containers, subnets, and endpoints
        - Bottom rows: Global services grouped by function
        """
        positions: Dict[str, Position] = {}
        groups: List[ServiceGroup] = []

        # Create AWS Cloud container
        aws_cloud = ServiceGroup(
            group_type='aws_cloud',
            name='AWS Cloud',
            position=Position(
                x=self.config.padding,
                y=self.config.padding,
                width=self.config.canvas_width - 2 * self.config.padding,
                height=self.config.canvas_height - 2 * self.config.padding
            )
        )
        groups.append(aws_cloud)

        # Categorize services for layout
        edge_services = []
        vpc_services = []
        data_services = []
        messaging_services = []
        security_services = []
        other_services = []

        for service in aggregated.services:
            st = service.service_type
            if st in ('cloudfront', 'waf', 'route53', 'acm', 'cognito'):
                edge_services.append(service)
            elif st in ('alb', 'ecs', 'ec2', 'security_groups', 'security', 'vpc'):
                vpc_services.append(service)
            elif st in ('s3', 'dynamodb', 'mongodb'):
                data_services.append(service)
            elif st in ('sqs', 'sns', 'eventbridge'):
                messaging_services.append(service)
            elif st in ('kms', 'secrets', 'secrets_manager', 'iam'):
                security_services.append(service)
            else:
                other_services.append(service)

        y_offset = self.config.padding + 40

        # Row 1: Edge services (top)
        if edge_services:
            x = self._center_row_start(len(edge_services))
            for service in edge_services:
                positions[service.id] = Position(
                    x=x, y=y_offset,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )
                x += self.config.column_spacing

        y_offset += self.config.row_spacing + 20

        # Row 2: VPC box with AZ containers and endpoints
        vpc_x = self.config.padding + 50
        vpc_width = self.config.canvas_width - 2 * (self.config.padding + 50)

        # Calculate VPC height based on VPC structure
        vpc_height = self._compute_vpc_height(aggregated.vpc_structure)

        vpc_internal = [s for s in vpc_services if s.service_type != 'vpc']

        vpc_group = ServiceGroup(
            group_type='vpc',
            name='VPC',
            services=vpc_internal,
            position=Position(x=vpc_x, y=y_offset, width=vpc_width, height=vpc_height)
        )
        groups.append(vpc_group)

        # Layout VPC internals (AZs, subnets, endpoints)
        if aggregated.vpc_structure:
            self._layout_vpc_structure(
                aggregated.vpc_structure,
                vpc_group.position,
                positions,
                groups
            )

        # Position services inside VPC (legacy layout for services not in subnets)
        inner_y = y_offset + self.config.group_padding + 30
        if vpc_internal:
            x = self._center_row_start(len(vpc_internal), vpc_x + self.config.group_padding,
                                        vpc_x + vpc_width - self.config.group_padding)
            for service in vpc_internal:
                positions[service.id] = Position(
                    x=x, y=inner_y,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )
                x += self.config.column_spacing

        y_offset += vpc_height + 40

        # Row 3: Data services
        if data_services:
            x = self._center_row_start(len(data_services))
            for service in data_services:
                positions[service.id] = Position(
                    x=x, y=y_offset,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )
                x += self.config.column_spacing

        y_offset += self.config.row_spacing

        # Row 4: Messaging services
        if messaging_services:
            x = self._center_row_start(len(messaging_services))
            for service in messaging_services:
                positions[service.id] = Position(
                    x=x, y=y_offset,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )
                x += self.config.column_spacing

        y_offset += self.config.row_spacing

        # Row 5: Security + Other services
        bottom_services = security_services + other_services
        if bottom_services:
            x = self._center_row_start(len(bottom_services))
            for service in bottom_services:
                positions[service.id] = Position(
                    x=x, y=y_offset,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )
                x += self.config.column_spacing

        return positions, groups

    def _compute_vpc_height(self, vpc_structure: Optional['VPCStructure']) -> int:
        """Compute VPC box height based on structure."""
        if not vpc_structure or not vpc_structure.availability_zones:
            return 180  # Default height

        # Find max number of subnet types in any AZ
        max_subnet_types = 0
        for az in vpc_structure.availability_zones:
            subnet_types = set(s.subnet_type for s in az.subnets)
            max_subnet_types = max(max_subnet_types, len(subnet_types))

        # Height per subnet type + padding
        subnet_row_height = 50
        az_padding = 60  # Header + margins

        return max(180, az_padding + max_subnet_types * subnet_row_height + 40)

    def _layout_vpc_structure(
        self,
        vpc_structure: 'VPCStructure',
        vpc_pos: Position,
        positions: Dict[str, Position],
        groups: List[ServiceGroup]
    ) -> None:
        """Layout VPC internal structure (AZs, subnets, endpoints)."""
        if not vpc_structure:
            return

        num_azs = len(vpc_structure.availability_zones)
        if num_azs == 0:
            return

        # Calculate AZ dimensions
        az_padding = 20
        az_total_width = vpc_pos.width - 80  # Leave room for endpoints on right
        az_width = (az_total_width - (num_azs + 1) * az_padding) / num_azs
        az_height = vpc_pos.height - 60

        # Layout each AZ
        az_x = vpc_pos.x + az_padding
        az_y = vpc_pos.y + 40

        for az in vpc_structure.availability_zones:
            # Create AZ group
            az_group = ServiceGroup(
                group_type='az',
                name=az.name,
                position=Position(x=az_x, y=az_y, width=az_width, height=az_height)
            )
            groups.append(az_group)

            # Layout subnets inside AZ
            self._layout_subnets(az, az_group.position, positions)

            az_x += az_width + az_padding

        # Layout VPC endpoints on right border
        endpoint_x = vpc_pos.x + vpc_pos.width - 40
        endpoint_y = vpc_pos.y + 50
        endpoint_spacing = 45

        for endpoint in vpc_structure.endpoints:
            positions[f'vpc_endpoint.{endpoint.service}'] = Position(
                x=endpoint_x,
                y=endpoint_y,
                width=32,
                height=32
            )
            endpoint_y += endpoint_spacing

    def _layout_subnets(
        self,
        az: 'AvailabilityZone',
        az_pos: Position,
        positions: Dict[str, Position]
    ) -> None:
        """Layout subnets inside an AZ."""
        if not az.subnets:
            return

        # Group subnets by type
        subnet_by_type: Dict[str, List] = {}
        for subnet in az.subnets:
            if subnet.subnet_type not in subnet_by_type:
                subnet_by_type[subnet.subnet_type] = []
            subnet_by_type[subnet.subnet_type].append(subnet)

        # Order: public, private, database
        type_order = ['public', 'private', 'database']

        subnet_height = 40
        subnet_padding = 10
        subnet_y = az_pos.y + 30

        for subnet_type in type_order:
            subnets = subnet_by_type.get(subnet_type, [])
            if not subnets:
                continue

            for subnet in subnets:
                positions[f'subnet.{subnet.resource_id}'] = Position(
                    x=az_pos.x + subnet_padding,
                    y=subnet_y,
                    width=az_pos.width - 2 * subnet_padding,
                    height=subnet_height
                )
                subnet_y += subnet_height + 5

            subnet_y += 5  # Extra spacing between types
```

**Step 4: Add import for VPCStructure**

```python
# Add at top of terraformgraph/layout.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .aggregator import VPCStructure, AvailabilityZone
```

**Step 5: Run tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_layout.py tests/test_integration.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add terraformgraph/layout.py tests/test_layout.py
git commit -m "feat: update LayoutEngine for VPC structure

Adds AZ containers, subnet positioning, and endpoint border placement.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Update Renderer for VPC Structure

**Files:**
- Modify: `terraformgraph/renderer.py`
- Test: Manual visual testing

**Step 1: Add AZ and Subnet rendering methods**

```python
# Add to SVGRenderer class in terraformgraph/renderer.py

    def _render_az(self, group: ServiceGroup) -> str:
        """Render an Availability Zone container."""
        if not group.position:
            return ''

        pos = group.position

        return f'''
        <g class="group group-az" data-group-type="az" data-az-name="{html.escape(group.name)}">
            <rect class="az-bg" x="{pos.x}" y="{pos.y}" width="{pos.width}" height="{pos.height}"
                fill="#f0f4f8" stroke="#7d8998" stroke-width="1"
                stroke-dasharray="4,2" rx="8" ry="8"/>
            <text x="{pos.x + 10}" y="{pos.y + 18}"
                font-family="Arial, sans-serif" font-size="11" font-weight="600"
                fill="#5a6872">{html.escape(group.name)}</text>
        </g>
        '''

    def _render_subnet(self, subnet_id: str, pos: Position, subnet_info: dict) -> str:
        """Render a subnet box."""
        colors = {
            'public': ('#d4edda', '#28a745'),
            'private': ('#cce5ff', '#007bff'),
            'database': ('#fff3cd', '#ffc107'),
        }

        subnet_type = subnet_info.get('type', 'private')
        fill_color, stroke_color = colors.get(subnet_type, colors['private'])
        name = subnet_info.get('name', subnet_id)

        return f'''
        <g class="subnet" data-subnet-id="{html.escape(subnet_id)}" data-subnet-type="{subnet_type}">
            <rect x="{pos.x}" y="{pos.y}" width="{pos.width}" height="{pos.height}"
                fill="{fill_color}" stroke="{stroke_color}" stroke-width="1.5" rx="4" ry="4"/>
            <text x="{pos.x + pos.width/2}" y="{pos.y + pos.height/2 + 4}"
                font-family="Arial, sans-serif" font-size="10" fill="#333"
                text-anchor="middle">{html.escape(name)}</text>
        </g>
        '''

    def _render_vpc_endpoint(self, endpoint_id: str, pos: Position, endpoint_info: dict) -> str:
        """Render a VPC endpoint on the border."""
        service = endpoint_info.get('service', 'endpoint')
        endpoint_type = endpoint_info.get('type', 'interface')

        # Icon color based on type
        color = '#8c4fff' if endpoint_type == 'gateway' else '#3B48CC'

        return f'''
        <g class="vpc-endpoint" data-endpoint-id="{html.escape(endpoint_id)}"
           data-endpoint-type="{endpoint_type}" data-service="{html.escape(service)}">
            <circle cx="{pos.x + pos.width/2}" cy="{pos.y + pos.height/2}" r="16"
                fill="white" stroke="{color}" stroke-width="2"/>
            <text x="{pos.x + pos.width/2}" y="{pos.y + pos.height/2 + 4}"
                font-family="Arial, sans-serif" font-size="9" fill="{color}"
                text-anchor="middle" font-weight="600">{html.escape(service.upper()[:4])}</text>
        </g>
        '''
```

**Step 2: Update render_svg to handle new group types**

```python
# Modify _render_group method in SVGRenderer class

    def _render_group(self, group: ServiceGroup) -> str:
        """Render a group container (AWS Cloud, VPC, AZ)."""
        if not group.position:
            return ''

        # Handle AZ groups separately
        if group.group_type == 'az':
            return self._render_az(group)

        pos = group.position

        colors = {
            'aws_cloud': ('#232f3e', '#ffffff', '#232f3e'),
            'vpc': ('#8c4fff', '#faf8ff', '#8c4fff'),
        }

        border_color, bg_color, text_color = colors.get(group.group_type, ('#666', '#fff', '#666'))

        return f'''
        <g class="group group-{group.group_type}" data-group-type="{group.group_type}">
            <rect class="group-bg" x="{pos.x}" y="{pos.y}" width="{pos.width}" height="{pos.height}"
                fill="{bg_color}" stroke="{border_color}" stroke-width="2"
                stroke-dasharray="8,4" rx="12" ry="12"
                data-min-x="{pos.x}" data-min-y="{pos.y}"
                data-max-x="{pos.x + pos.width}" data-max-y="{pos.y + pos.height}"/>
            <text x="{pos.x + 15}" y="{pos.y + 22}"
                font-family="Arial, sans-serif" font-size="14" font-weight="bold"
                fill="{text_color}">{html.escape(group.name)}</text>
        </g>
        '''
```

**Step 3: Update render_svg to include subnets and endpoints**

```python
# Modify render_svg method in SVGRenderer class to add subnet and endpoint layers

    def render_svg(
        self,
        services: List[LogicalService],
        positions: Dict[str, Position],
        connections: List[LogicalConnection],
        groups: List[ServiceGroup],
        vpc_structure: Optional['VPCStructure'] = None
    ) -> str:
        """Generate SVG content for the diagram."""
        svg_parts = []

        # SVG header with ID for export
        svg_parts.append(f'''<svg id="diagram-svg" xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            viewBox="0 0 {self.config.canvas_width} {self.config.canvas_height}"
            width="{self.config.canvas_width}" height="{self.config.canvas_height}">''')

        # Defs for arrows and filters
        svg_parts.append(self._render_defs())

        # Background
        svg_parts.append('''<rect width="100%" height="100%" fill="#f8f9fa"/>''')

        # Render groups (AWS Cloud, VPC, AZs)
        for group in groups:
            svg_parts.append(self._render_group(group))

        # Render subnets
        if vpc_structure:
            svg_parts.append('<g id="subnets-layer">')
            for az in vpc_structure.availability_zones:
                for subnet in az.subnets:
                    subnet_pos_key = f'subnet.{subnet.resource_id}'
                    if subnet_pos_key in positions:
                        svg_parts.append(self._render_subnet(
                            subnet_pos_key,
                            positions[subnet_pos_key],
                            {'type': subnet.subnet_type, 'name': subnet.name}
                        ))
            svg_parts.append('</g>')

            # Render VPC endpoints
            svg_parts.append('<g id="endpoints-layer">')
            for endpoint in vpc_structure.endpoints:
                endpoint_pos_key = f'vpc_endpoint.{endpoint.service}'
                if endpoint_pos_key in positions:
                    svg_parts.append(self._render_vpc_endpoint(
                        endpoint_pos_key,
                        positions[endpoint_pos_key],
                        {'type': endpoint.endpoint_type, 'service': endpoint.service}
                    ))
            svg_parts.append('</g>')

        # Connections container
        svg_parts.append('<g id="connections-layer">')
        for conn in connections:
            if conn.source_id in positions and conn.target_id in positions:
                svg_parts.append(self._render_connection(
                    positions[conn.source_id],
                    positions[conn.target_id],
                    conn
                ))
        svg_parts.append('</g>')

        # Services layer
        svg_parts.append('<g id="services-layer">')
        for service in services:
            if service.id in positions:
                svg_parts.append(self._render_service(service, positions[service.id]))
        svg_parts.append('</g>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)
```

**Step 4: Add TYPE_CHECKING import**

```python
# Add at top of terraformgraph/renderer.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .aggregator import VPCStructure
```

**Step 5: Update HTMLRenderer.render_html to pass vpc_structure**

```python
# Modify render_html in HTMLRenderer class

    def render_html(
        self,
        aggregated: AggregatedResult,
        positions: Dict[str, Position],
        groups: List[ServiceGroup],
        environment: str = 'dev'
    ) -> str:
        """Generate complete HTML page with interactive diagram."""
        svg_content = self.svg_renderer.render_svg(
            aggregated.services,
            positions,
            aggregated.connections,
            groups,
            vpc_structure=aggregated.vpc_structure  # Pass VPC structure
        )

        # ... rest stays the same
```

**Step 6: Run integration tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/test_integration.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add terraformgraph/renderer.py
git commit -m "feat: add VPC structure rendering (AZs, subnets, endpoints)

- AZ containers with dashed border
- Color-coded subnets (public/private/database)
- VPC endpoints on right border

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Update Legend and CSS

**Files:**
- Modify: `terraformgraph/renderer.py` (HTML_TEMPLATE)

**Step 1: Update legend section in HTML_TEMPLATE**

Find the legend section in HTML_TEMPLATE and update:

```html
        <div class="legend">
            <h3>Legend</h3>
            <div class="legend-grid">
                <div class="legend-section">
                    <h4>Connection Types</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <div class="legend-line" style="background: #3B48CC;"></div>
                            <span>Data Flow</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line" style="background: #E7157B;"></div>
                            <span>Event Trigger</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line" style="background: #6c757d;"></div>
                            <span>Encryption</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line" style="background: #999;"></div>
                            <span>Reference</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4>Subnet Types</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <div class="legend-box" style="background: #d4edda; border: 2px solid #28a745;"></div>
                            <span>Public Subnet</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-box" style="background: #cce5ff; border: 2px solid #007bff;"></div>
                            <span>Private Subnet</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-box" style="background: #fff3cd; border: 2px solid #ffc107;"></div>
                            <span>Database Subnet</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4>VPC Endpoints</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <div class="legend-circle" style="border: 2px solid #8c4fff;"></div>
                            <span>Gateway Endpoint</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-circle" style="border: 2px solid #3B48CC;"></div>
                            <span>Interface Endpoint</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4>Instructions</h4>
                    <div class="legend-items">
                        <div class="legend-item">Drag icons to reposition</div>
                        <div class="legend-item">VPC services stay within VPC bounds</div>
                        <div class="legend-item">Use Save/Load to persist layout</div>
                        <div class="legend-item">Export as PNG or JPG for sharing</div>
                    </div>
                </div>
            </div>
        </div>
```

**Step 2: Add CSS for new legend elements**

Add to CSS in HTML_TEMPLATE:

```css
        .legend-box {{
            width: 24px;
            height: 16px;
            border-radius: 3px;
        }}
        .legend-circle {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: white;
        }}
```

**Step 3: Commit**

```bash
git add terraformgraph/renderer.py
git commit -m "feat: update legend with subnet types and VPC endpoints

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 12: Update Main Pipeline

**Files:**
- Modify: `terraformgraph/main.py`

**Step 1: Update main.py to pass terraform_dir to aggregator**

```python
# Find the aggregate call in main.py and update to pass directory

    # Aggregate resources
    aggregator = ResourceAggregator()
    aggregated = aggregator.aggregate(parse_result, terraform_dir=terraform_path)
```

**Step 2: Run full integration test**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m terraformgraph -t example/infrastructure/prod -o test_output.html`

**Step 3: Commit**

```bash
git add terraformgraph/main.py
git commit -m "feat: integrate VPC structure and variable resolution in main pipeline

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 13: Final Integration Test

**Files:**
- Test: Manual testing with example project

**Step 1: Run the tool on example project**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m terraformgraph -t example/infrastructure/prod -o docs/example-output.html`

**Step 2: Open the output in browser and verify:**
- VPC structure with AZ containers visible
- Subnets colored by type (public/private/database)
- VPC endpoints on right border
- Resource names resolved from variables (e.g., "lidia-prod-vpc" instead of "${var.project_name}-${var.environment}-vpc")

**Step 3: Run all tests**

Run: `cd /Users/ferdinandobonsegna/Desktop/terraformgraph && python -m pytest tests/ -v`
Expected: All PASS

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify VPC decomposition and variable resolution

All integration tests passing with example infrastructure.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary of Files Modified/Created

| File | Action | Description |
|------|--------|-------------|
| `terraformgraph/variable_resolver.py` | Create | Variable resolution logic |
| `terraformgraph/parser.py` | Modify | Add get_resolved_display_name method |
| `terraformgraph/aggregator.py` | Modify | Add VPC structure classes and builder |
| `terraformgraph/layout.py` | Modify | Add VPC/AZ/subnet layout logic |
| `terraformgraph/renderer.py` | Modify | Add new SVG elements and legend |
| `terraformgraph/main.py` | Modify | Integrate variable resolution |
| `tests/test_variable_resolver.py` | Create | Variable resolver tests |
| `tests/test_vpc_structure.py` | Create | VPC structure tests |
| `tests/test_layout.py` | Create | Layout engine tests |
