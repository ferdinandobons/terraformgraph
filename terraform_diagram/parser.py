"""
Terraform HCL Parser

Parses Terraform files and extracts AWS resources and their relationships.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
import hcl2
import json


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


@dataclass
class ModuleCall:
    """Represents a module instantiation."""
    name: str
    source: str
    inputs: Dict[str, Any]
    source_file: str


@dataclass
class ResourceRelationship:
    """Represents a connection between resources."""
    source_id: str
    target_id: str
    relationship_type: str
    label: Optional[str] = None


@dataclass
class ParseResult:
    """Result of parsing Terraform files."""
    resources: List[TerraformResource] = field(default_factory=list)
    modules: List[ModuleCall] = field(default_factory=list)
    relationships: List[ResourceRelationship] = field(default_factory=list)


class TerraformParser:
    """Parses Terraform HCL files and extracts resources."""

    REFERENCE_PATTERNS = [
        # module.X.output
        (r'module\.(\w+)\.(\w+)', 'module_ref'),
        # aws_resource.name.attribute
        (r'(aws_\w+)\.(\w+)\.(\w+)', 'resource_ref'),
        # var.X
        (r'var\.(\w+)', 'var_ref'),
        # local.X
        (r'local\.(\w+)', 'local_ref'),
    ]

    RELATIONSHIP_EXTRACTORS = {
        'vpc_id': ('belongs_to_vpc', 'aws_vpc'),
        'subnet_id': ('deployed_in_subnet', 'aws_subnet'),
        'subnet_ids': ('deployed_in_subnets', 'aws_subnet'),
        'security_group_ids': ('uses_security_group', 'aws_security_group'),
        'kms_master_key_id': ('encrypted_by', 'aws_kms_key'),
        'kms_key_id': ('encrypted_by', 'aws_kms_key'),
        'target_group_arn': ('routes_to', 'aws_lb_target_group'),
        'load_balancer_arn': ('attached_to', 'aws_lb'),
        'web_acl_arn': ('protected_by', 'aws_wafv2_web_acl'),
        'waf_acl_arn': ('protected_by', 'aws_wafv2_web_acl'),
        'certificate_arn': ('uses_certificate', 'aws_acm_certificate'),
        'role_arn': ('assumes_role', 'aws_iam_role'),
        'queue_arn': ('sends_to_queue', 'aws_sqs_queue'),
        'topic_arn': ('publishes_to', 'aws_sns_topic'),
        'alarm_topic_arn': ('alerts_to', 'aws_sns_topic'),
    }

    def __init__(self, infrastructure_path: str, icons_path: Optional[str] = None):
        self.infrastructure_path = Path(infrastructure_path)
        self.icons_path = Path(icons_path) if icons_path else None
        self._parsed_modules: Dict[str, ParseResult] = {}

    def parse_environment(self, environment: str) -> ParseResult:
        """Parse all Terraform files for a specific environment."""
        env_path = self.infrastructure_path / environment
        if not env_path.exists():
            raise ValueError(f"Environment path not found: {env_path}")

        return self.parse_directory(env_path)

    def parse_directory(self, directory: Path) -> ParseResult:
        """Parse all Terraform files in a directory (non-environment mode).

        Args:
            directory: Path to directory containing .tf files

        Returns:
            ParseResult with all resources and relationships
        """
        if isinstance(directory, str):
            directory = Path(directory)

        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        result = ParseResult()

        # Parse all .tf files in directory
        tf_files = list(directory.glob("*.tf"))
        if not tf_files:
            print(f"Warning: No .tf files found in {directory}")

        for tf_file in tf_files:
            self._parse_file(tf_file, result, module_path="")

        # Parse referenced modules
        modules_to_parse = list(result.modules)
        for module in modules_to_parse:
            module_result = self._parse_module(module.source, directory, module.name)
            result.resources.extend(module_result.resources)
            result.relationships.extend(module_result.relationships)

        # Extract relationships from all resources
        self._extract_relationships(result)

        return result

    def _parse_file(self, file_path: Path, result: ParseResult, module_path: str) -> None:
        """Parse a single Terraform file."""
        try:
            with open(file_path, 'r') as f:
                content = hcl2.load(f)
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return

        # Extract resources
        for resource_block in content.get('resource', []):
            for resource_type, resources in resource_block.items():
                for resource_name, config in resources.items():
                    # Handle list configs (HCL2 can return lists)
                    if isinstance(config, list):
                        config = config[0] if config else {}

                    resource = TerraformResource(
                        resource_type=resource_type,
                        resource_name=resource_name,
                        module_path=module_path,
                        attributes=config,
                        source_file=str(file_path),
                        count=self._extract_count(config),
                        for_each='for_each' in config
                    )
                    result.resources.append(resource)

        # Extract module calls
        for module_block in content.get('module', []):
            for module_name, config in module_block.items():
                if isinstance(config, list):
                    config = config[0] if config else {}

                source = config.get('source', '')
                module = ModuleCall(
                    name=module_name,
                    source=source,
                    inputs=config,
                    source_file=str(file_path)
                )
                result.modules.append(module)

    def _parse_module(self, source: str, base_path: Path, module_name: str) -> ParseResult:
        """Parse a module from its source path."""
        # Resolve relative path
        if source.startswith('../') or source.startswith('./'):
            module_path = (base_path / source).resolve()
        else:
            module_path = self.infrastructure_path / '.modules' / source

        if not module_path.exists():
            print(f"Warning: Module path not found: {module_path}")
            return ParseResult()

        # Check cache
        cache_key = str(module_path)
        if cache_key in self._parsed_modules:
            # Return a copy with updated module paths
            cached = self._parsed_modules[cache_key]
            result = ParseResult()
            for res in cached.resources:
                new_res = TerraformResource(
                    resource_type=res.resource_type,
                    resource_name=res.resource_name,
                    module_path=module_name,
                    attributes=res.attributes,
                    source_file=res.source_file,
                    count=res.count,
                    for_each=res.for_each
                )
                result.resources.append(new_res)
            return result

        result = ParseResult()
        for tf_file in module_path.glob("*.tf"):
            self._parse_file(tf_file, result, module_path=module_name)

        self._parsed_modules[cache_key] = result
        return result

    def _extract_count(self, config: Dict[str, Any]) -> Optional[int]:
        """Extract count value from resource config."""
        count = config.get('count')
        if count is None:
            return None
        if isinstance(count, int):
            return count
        if isinstance(count, str):
            # Try to parse simple numbers
            try:
                return int(count)
            except ValueError:
                # Complex expression, return -1 to indicate "multiple"
                return -1
        return None

    def _extract_relationships(self, result: ParseResult) -> None:
        """Extract relationships between resources."""
        resource_index = {r.full_id: r for r in result.resources}
        type_index: Dict[str, List[TerraformResource]] = {}
        for r in result.resources:
            type_index.setdefault(r.resource_type, []).append(r)

        for resource in result.resources:
            # Check for DLQ redrive policy
            self._extract_dlq_relationship(resource, result, type_index)

            # Check standard attribute references
            for attr_name, (rel_type, target_type) in self.RELATIONSHIP_EXTRACTORS.items():
                value = resource.attributes.get(attr_name)
                if value:
                    targets = self._find_referenced_resources(value, target_type, type_index)
                    for target in targets:
                        result.relationships.append(ResourceRelationship(
                            source_id=resource.full_id,
                            target_id=target.full_id,
                            relationship_type=rel_type
                        ))

    def _extract_dlq_relationship(
        self,
        resource: TerraformResource,
        result: ParseResult,
        type_index: Dict[str, List[TerraformResource]]
    ) -> None:
        """Extract SQS dead letter queue relationships."""
        if resource.resource_type != 'aws_sqs_queue':
            return

        redrive = resource.attributes.get('redrive_policy')
        if not redrive:
            return

        # Parse redrive policy (could be string or dict)
        if isinstance(redrive, str):
            # Try to find DLQ reference in string
            match = re.search(r'aws_sqs_queue\.(\w+)\.arn', redrive)
            if match:
                dlq_name = match.group(1)
                for queue in type_index.get('aws_sqs_queue', []):
                    if queue.resource_name == dlq_name:
                        result.relationships.append(ResourceRelationship(
                            source_id=resource.full_id,
                            target_id=queue.full_id,
                            relationship_type='redrives_to',
                            label='DLQ'
                        ))
                        break

    def _find_referenced_resources(
        self,
        value: Any,
        target_type: str,
        type_index: Dict[str, List[TerraformResource]]
    ) -> List[TerraformResource]:
        """Find resources referenced in a value."""
        results = []
        value_str = str(value)

        # Look for resource references
        pattern = rf'{target_type}\.(\w+)\.'
        for match in re.finditer(pattern, value_str):
            res_name = match.group(1)
            for res in type_index.get(target_type, []):
                if res.resource_name == res_name:
                    results.append(res)
                    break

        # Look for module references
        module_pattern = r'module\.(\w+)\.(\w+)'
        for match in re.finditer(module_pattern, value_str):
            module_name = match.group(1)
            output_name = match.group(2)
            # Find resources in that module
            for res in type_index.get(target_type, []):
                if res.module_path == module_name:
                    results.append(res)
                    break

        return results


def get_resource_summary(result: ParseResult) -> Dict[str, int]:
    """Get a summary count of resources by type."""
    summary: Dict[str, int] = {}
    for resource in result.resources:
        count = 1
        if resource.count and resource.count > 0:
            count = resource.count
        elif resource.for_each:
            count = 1  # Unknown, but at least 1
        summary[resource.resource_type] = summary.get(resource.resource_type, 0) + count
    return summary
