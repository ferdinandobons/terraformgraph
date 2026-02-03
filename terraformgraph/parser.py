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
from lark.exceptions import UnexpectedInput, UnexpectedToken

if TYPE_CHECKING:
    from terraformgraph.terraform_tools import TerraformStateResult
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
        name = self.attributes.get("name", self.resource_name)
        if isinstance(name, str) and "${" not in name:
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

        name = self.attributes.get("name", self.resource_name)
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

    RELATIONSHIP_EXTRACTORS = {
        "vpc_id": ("belongs_to_vpc", "aws_vpc"),
        "subnet_id": ("deployed_in_subnet", "aws_subnet"),
        "subnet_ids": ("deployed_in_subnets", "aws_subnet"),
        "security_group_ids": ("uses_security_group", "aws_security_group"),
        "vpc_security_group_ids": ("uses_security_group", "aws_security_group"),
        "security_groups": ("uses_security_group", "aws_security_group"),
        "kms_master_key_id": ("encrypted_by", "aws_kms_key"),
        "kms_key_id": ("encrypted_by", "aws_kms_key"),
        "target_group_arn": ("routes_to", "aws_lb_target_group"),
        "load_balancer_arn": ("attached_to", "aws_lb"),
        "web_acl_arn": ("protected_by", "aws_wafv2_web_acl"),
        "waf_acl_arn": ("protected_by", "aws_wafv2_web_acl"),
        "certificate_arn": ("uses_certificate", "aws_acm_certificate"),
        "role_arn": ("assumes_role", "aws_iam_role"),
        "queue_arn": ("sends_to_queue", "aws_sqs_queue"),
        "topic_arn": ("publishes_to", "aws_sns_topic"),
        "alarm_topic_arn": ("alerts_to", "aws_sns_topic"),
    }

    def __init__(
        self,
        infrastructure_path: str,
        use_terraform_state: bool = False,
        state_file: Optional[str] = None,
    ):
        self.infrastructure_path = Path(infrastructure_path)
        self._parsed_modules: Dict[str, ParseResult] = {}
        self.use_terraform_state = use_terraform_state
        self.state_file = Path(state_file) if state_file else None
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

        # Enhance with terraform state if requested
        if self.use_terraform_state:
            self._enhance_with_terraform_state(result, directory)

        return result

    def _enhance_with_terraform_state(self, result: ParseResult, directory: Path) -> None:
        """Enhance parse result with data from terraform state."""
        from terraformgraph.terraform_tools import TerraformToolsRunner

        runner = TerraformToolsRunner(directory)
        state_result = runner.run_show_json(state_file=self.state_file)
        if state_result:
            self._state_result = state_result
            self._enrich_resources_with_state(result, state_result)
            logger.info("Enhanced with terraform state: %d resources", len(state_result.resources))

    def _enrich_resources_with_state(
        self, result: ParseResult, state_result: "TerraformStateResult"
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

    def _parse_file(self, file_path: Path, result: ParseResult, module_path: str) -> None:
        """Parse a single Terraform file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = hcl2.load(f)
        except OSError as e:
            logger.warning("Could not read %s: %s", file_path, e)
            return
        except (UnexpectedInput, UnexpectedToken) as e:
            logger.warning("Could not parse HCL in %s: %s", file_path, e)
            return

        # Extract resources
        for resource_block in content.get("resource", []):
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
                        for_each="for_each" in config,
                    )
                    result.resources.append(resource)

        # Extract module calls
        for module_block in content.get("module", []):
            for module_name, config in module_block.items():
                if isinstance(config, list):
                    config = config[0] if config else {}

                source = config.get("source", "")
                module = ModuleCall(
                    name=module_name, source=source, inputs=config, source_file=str(file_path)
                )
                result.modules.append(module)

    def _parse_module(self, source: str, base_path: Path, module_name: str) -> ParseResult:
        """Parse a module from its source path."""
        # Resolve relative path
        if source.startswith("../") or source.startswith("./"):
            module_path = (base_path / source).resolve()
        else:
            module_path = self.infrastructure_path / ".modules" / source

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
                    for_each=res.for_each,
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
        count = config.get("count")
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
                        result.relationships.append(
                            ResourceRelationship(
                                source_id=resource.full_id,
                                target_id=target.full_id,
                                relationship_type=rel_type,
                            )
                        )

            # Deep scan: find resource references in ALL attributes (catches nested refs
            # like environment.variables that RELATIONSHIP_EXTRACTORS miss)
            self._extract_deep_references(resource, result, type_index)

            # Check for security group cross-references
            self._extract_sg_cross_references(resource, result, type_index)

    # Resource types excluded from deep scan (infrastructure plumbing, not logical connections)
    _DEEP_SCAN_EXCLUDED_TYPES = frozenset({
        "aws_security_group", "aws_iam_role", "aws_iam_policy",
        "aws_subnet", "aws_vpc", "aws_route_table", "aws_route_table_association",
        "aws_eip", "aws_network_interface",
    })

    def _extract_deep_references(
        self,
        resource: TerraformResource,
        result: ParseResult,
        type_index: Dict[str, List[TerraformResource]],
    ) -> None:
        """Scan all attribute values for resource references not caught by RELATIONSHIP_EXTRACTORS."""
        # Build set of already-known targets to avoid duplicates
        known_targets: set = set()
        for rel in result.relationships:
            if rel.source_id == resource.full_id:
                known_targets.add(rel.target_id)

        # Convert entire attributes dict to string and scan for all known resource types
        attrs_str = str(resource.attributes)
        for target_type, resources_of_type in type_index.items():
            if target_type == resource.resource_type:
                continue  # Skip self-type references
            if target_type in self._DEEP_SCAN_EXCLUDED_TYPES:
                continue  # Skip infrastructure plumbing types
            pattern = rf"{re.escape(target_type)}\.(\w+)\."
            for match in re.finditer(pattern, attrs_str):
                res_name = match.group(1)
                for target_res in resources_of_type:
                    if target_res.resource_name == res_name and target_res.full_id not in known_targets:
                        known_targets.add(target_res.full_id)
                        result.relationships.append(
                            ResourceRelationship(
                                source_id=resource.full_id,
                                target_id=target_res.full_id,
                                relationship_type="references",
                            )
                        )
                        break

    def _extract_dlq_relationship(
        self,
        resource: TerraformResource,
        result: ParseResult,
        type_index: Dict[str, List[TerraformResource]],
    ) -> None:
        """Extract SQS dead letter queue relationships."""
        if resource.resource_type != "aws_sqs_queue":
            return

        redrive = resource.attributes.get("redrive_policy")
        if not redrive:
            return

        # Parse redrive policy (could be string or dict)
        if isinstance(redrive, str):
            # Try to find DLQ reference in string
            match = re.search(r"aws_sqs_queue\.(\w+)\.arn", redrive)
            if match:
                dlq_name = match.group(1)
                for queue in type_index.get("aws_sqs_queue", []):
                    if queue.resource_name == dlq_name:
                        result.relationships.append(
                            ResourceRelationship(
                                source_id=resource.full_id,
                                target_id=queue.full_id,
                                relationship_type="redrives_to",
                                label="DLQ",
                            )
                        )
                        break

    def _extract_sg_cross_references(
        self,
        resource: TerraformResource,
        result: ParseResult,
        type_index: Dict[str, List[TerraformResource]],
    ) -> None:
        """Extract security group cross-references from ingress rules.

        Creates sg_allows_from relationships when a security group rule
        references another security group as its source.
        """
        sg_resources = type_index.get("aws_security_group", [])
        if not sg_resources:
            return

        # Case 1: Inline ingress rules in aws_security_group
        if resource.resource_type == "aws_security_group":
            ingress_rules = resource.attributes.get("ingress", [])
            if not isinstance(ingress_rules, list):
                return
            for rule in ingress_rules:
                if not isinstance(rule, dict):
                    continue
                self._process_sg_rule(
                    rule, resource.full_id, result, sg_resources, is_inline=True
                )

        # Case 2: Standalone aws_security_group_rule with type=ingress
        elif resource.resource_type == "aws_security_group_rule":
            if resource.attributes.get("type") != "ingress":
                return
            # The SG this rule belongs to
            sg_id_attr = resource.attributes.get("security_group_id", "")
            target_sg = self._resolve_sg_ref(str(sg_id_attr), sg_resources)
            if not target_sg:
                return
            source_ref = resource.attributes.get("source_security_group_id", "")
            source_sg = self._resolve_sg_ref(str(source_ref), sg_resources)
            if source_sg and source_sg.full_id != target_sg.full_id:
                port_label = self._format_port_label(resource.attributes)
                result.relationships.append(
                    ResourceRelationship(
                        source_id=source_sg.full_id,
                        target_id=target_sg.full_id,
                        relationship_type="sg_allows_from",
                        label=port_label,
                    )
                )

        # Case 3: aws_vpc_security_group_ingress_rule
        elif resource.resource_type == "aws_vpc_security_group_ingress_rule":
            sg_id_attr = resource.attributes.get("security_group_id", "")
            target_sg = self._resolve_sg_ref(str(sg_id_attr), sg_resources)
            if not target_sg:
                return
            source_ref = resource.attributes.get(
                "referenced_security_group_id", ""
            )
            source_sg = self._resolve_sg_ref(str(source_ref), sg_resources)
            if source_sg and source_sg.full_id != target_sg.full_id:
                port_label = self._format_port_label(resource.attributes)
                result.relationships.append(
                    ResourceRelationship(
                        source_id=source_sg.full_id,
                        target_id=target_sg.full_id,
                        relationship_type="sg_allows_from",
                        label=port_label,
                    )
                )

    def _process_sg_rule(
        self,
        rule: dict,
        sg_full_id: str,
        result: ParseResult,
        sg_resources: List[TerraformResource],
        is_inline: bool = True,
    ) -> None:
        """Process a single SG ingress rule for cross-references."""
        # Look for security_groups list (inline rules use this)
        sg_refs = rule.get("security_groups", [])
        if not isinstance(sg_refs, list):
            sg_refs = [sg_refs] if sg_refs else []

        for ref in sg_refs:
            source_sg = self._resolve_sg_ref(str(ref), sg_resources)
            if source_sg and source_sg.full_id != sg_full_id:
                port_label = self._format_port_label(rule)
                result.relationships.append(
                    ResourceRelationship(
                        source_id=source_sg.full_id,
                        target_id=sg_full_id,
                        relationship_type="sg_allows_from",
                        label=port_label,
                    )
                )

    @staticmethod
    def _resolve_sg_ref(
        value: str, sg_resources: List[TerraformResource]
    ) -> Optional[TerraformResource]:
        """Resolve a security group reference to a TerraformResource."""
        if not value:
            return None
        match = re.search(r"aws_security_group\.(\w+)", value)
        if match:
            name = match.group(1)
            for sg in sg_resources:
                if sg.resource_name == name:
                    return sg
        return None

    @staticmethod
    def _format_port_label(attrs: dict) -> str:
        """Format a port label from rule attributes (e.g., 'TCP/80')."""
        from_port = attrs.get("from_port")
        to_port = attrs.get("to_port")
        protocol = attrs.get("protocol", "tcp")

        if from_port is None:
            return ""

        # Coerce ports to int (HCL2 may return strings in some contexts)
        try:
            from_port = int(from_port)
        except (TypeError, ValueError):
            pass
        try:
            to_port = int(to_port)
        except (TypeError, ValueError):
            pass

        if isinstance(protocol, str):
            protocol = protocol.upper()
            if protocol == "-1":
                return "All Traffic"

        if from_port == to_port or to_port is None:
            return f"{protocol}/{from_port}"
        if from_port == 0 and to_port == 65535:
            return f"{protocol}/All"
        return f"{protocol}/{from_port}-{to_port}"

    def _find_referenced_resources(
        self, value: Any, target_type: str, type_index: Dict[str, List[TerraformResource]]
    ) -> List[TerraformResource]:
        """Find resources referenced in a value."""
        results = []
        value_str = str(value)

        # Look for resource references
        pattern = rf"{target_type}\.(\w+)\."
        for match in re.finditer(pattern, value_str):
            res_name = match.group(1)
            for res in type_index.get(target_type, []):
                if res.resource_name == res_name:
                    results.append(res)
                    break

        # Look for module references
        module_pattern = r"module\.(\w+)\.(\w+)"
        for match in re.finditer(module_pattern, value_str):
            module_name = match.group(1)
            # Find resources in that module
            for res in type_index.get(target_type, []):
                if res.module_path == module_name:
                    results.append(res)
                    break

        return results
