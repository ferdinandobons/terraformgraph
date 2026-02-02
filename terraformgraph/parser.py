"""
Terraform HCL Parser

Parses Terraform files and extracts AWS resources and their relationships.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hcl2

if TYPE_CHECKING:
    from terraformgraph.terraform_tools import TerraformGraphResult, TerraformStateResult
    from terraformgraph.variable_resolver import VariableResolver

logger = logging.getLogger(__name__)


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

    def get_resolved_display_name(self, resolver: "VariableResolver") -> str:
        """Get display name with interpolations resolved and truncated.

        Args:
            resolver: VariableResolver instance for resolving interpolations

        Returns:
            Resolved and truncated display name
        """
        from terraformgraph.variable_resolver import VariableResolver

        name = self.attributes.get('name', self.resource_name)
        if isinstance(name, str):
            resolved_name = resolver.resolve(name)
            return VariableResolver.truncate_name(resolved_name)
        return VariableResolver.truncate_name(self.resource_name)


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

    def __init__(
        self,
        infrastructure_path: str,
        icons_path: Optional[str] = None,
        use_terraform_graph: bool = False,
        use_terraform_state: bool = False,
        state_file: Optional[str] = None
    ):
        self.infrastructure_path = Path(infrastructure_path)
        self.icons_path = Path(icons_path) if icons_path else None
        self._parsed_modules: Dict[str, ParseResult] = {}
        self.use_terraform_graph = use_terraform_graph
        self.use_terraform_state = use_terraform_state
        self.state_file = Path(state_file) if state_file else None
        self._graph_result: Optional["TerraformGraphResult"] = None
        self._state_result: Optional["TerraformStateResult"] = None

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
            logger.warning("No .tf files found in %s", directory)

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

        # Enhance with terraform tools if requested
        if self.use_terraform_graph or self.use_terraform_state:
            self._enhance_with_terraform_tools(result, directory)

        return result

    def _enhance_with_terraform_tools(self, result: ParseResult, directory: Path) -> None:
        """Enhance parse result with data from terraform CLI tools."""
        from terraformgraph.terraform_tools import TerraformToolsRunner, map_state_to_resource_id

        runner = TerraformToolsRunner(directory)

        if self.use_terraform_graph:
            graph_result = runner.run_graph()
            if graph_result:
                self._graph_result = graph_result
                self._merge_graph_relationships(result, graph_result)
                logger.info(
                    "Enhanced with terraform graph: %d edges",
                    len(graph_result.edges)
                )

        if self.use_terraform_state:
            state_result = runner.run_show_json(state_file=self.state_file)
            if state_result:
                self._state_result = state_result
                self._enrich_resources_with_state(result, state_result)
                logger.info(
                    "Enhanced with terraform state: %d resources",
                    len(state_result.resources)
                )

    def _merge_graph_relationships(
        self,
        result: ParseResult,
        graph_result: "TerraformGraphResult"
    ) -> None:
        """Merge relationships from terraform graph into parse result."""
        from terraformgraph.terraform_tools import map_state_to_resource_id

        # Build index of existing resources by full_id
        resource_index = {r.full_id: r for r in result.resources}

        # Track existing relationships to avoid duplicates
        existing_rels = {
            (r.source_id, r.target_id) for r in result.relationships
        }

        for source, target in graph_result.edges:
            source_id = map_state_to_resource_id(source)
            target_id = map_state_to_resource_id(target)

            # Only add if both resources exist and relationship is new
            if (source_id in resource_index and
                target_id in resource_index and
                (source_id, target_id) not in existing_rels):

                result.relationships.append(ResourceRelationship(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type='depends_on',
                    label=None
                ))
                existing_rels.add((source_id, target_id))

    def _enrich_resources_with_state(
        self,
        result: ParseResult,
        state_result: "TerraformStateResult"
    ) -> None:
        """Enrich parsed resources with actual values from terraform state."""
        from terraformgraph.terraform_tools import map_state_to_resource_id

        # Build index by full_id
        resource_index = {r.full_id: r for r in result.resources}

        for state_res in state_result.resources:
            resource_id = map_state_to_resource_id(state_res.address)

            if resource_id in resource_index:
                resource = resource_index[resource_id]
                # Merge state values into attributes (state values take precedence)
                for key, value in state_res.values.items():
                    if value is not None:
                        resource.attributes[f"_state_{key}"] = value

    def get_state_result(self) -> Optional["TerraformStateResult"]:
        """Get the terraform state result if available."""
        return self._state_result

    def get_graph_result(self) -> Optional["TerraformGraphResult"]:
        """Get the terraform graph result if available."""
        return self._graph_result

    def _parse_file(self, file_path: Path, result: ParseResult, module_path: str) -> None:
        """Parse a single Terraform file."""
        try:
            with open(file_path, 'r') as f:
                content = hcl2.load(f)
        except Exception as e:
            logger.warning("Could not parse %s: %s", file_path, e)
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
            logger.warning("Module path not found: %s", module_path)
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
