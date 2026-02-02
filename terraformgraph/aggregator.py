"""
Resource Aggregator

Aggregates low-level Terraform resources into high-level logical services
for cleaner architecture diagrams.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from .config_loader import ConfigLoader
from .parser import ParseResult, TerraformResource

if TYPE_CHECKING:
    from .terraform_tools import TerraformStateResult
    from .variable_resolver import VariableResolver


# VPC Structure Data Models (Task 5)


@dataclass
class Subnet:
    """Represents a subnet within a VPC."""

    resource_id: str
    name: str
    subnet_type: str  # 'public', 'private', 'database', 'unknown'
    availability_zone: str
    cidr_block: Optional[str] = None
    aws_id: Optional[str] = None  # AWS subnet ID (e.g., 'subnet-xxx') from state


@dataclass
class AvailabilityZone:
    """Represents an availability zone containing subnets."""

    name: str
    short_name: str  # e.g., '1a', '1b'
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
    """Represents the complete VPC structure with AZs and endpoints."""

    vpc_id: str
    name: str
    availability_zones: List[AvailabilityZone] = field(default_factory=list)
    endpoints: List[VPCEndpoint] = field(default_factory=list)


@dataclass
class LogicalService:
    """A high-level logical service aggregating multiple resources."""
    service_type: str  # e.g., 'alb', 'ecs', 's3', 'sqs'
    name: str
    icon_resource_type: str  # The Terraform type to use for the icon
    resources: List[TerraformResource] = field(default_factory=list)
    count: int = 1  # How many instances (e.g., 24 SQS queues)
    is_vpc_resource: bool = False
    attributes: Dict[str, str] = field(default_factory=dict)
    subnet_ids: List[str] = field(default_factory=list)  # Subnet resource IDs this service belongs to
    resource_id: Optional[str] = None  # For de-grouped VPC services, uses resource's full_id

    @property
    def id(self) -> str:
        # Use resource_id for de-grouped services (unique per resource)
        if self.resource_id:
            return self.resource_id
        return f"{self.service_type}.{self.name}"


@dataclass
class LogicalConnection:
    """A connection between logical services."""
    source_id: str
    target_id: str
    label: Optional[str] = None
    connection_type: str = 'default'  # 'default', 'data_flow', 'trigger', 'encrypt'


@dataclass
class AggregatedResult:
    """Result of aggregating resources into logical services."""

    services: List[LogicalService] = field(default_factory=list)
    connections: List[LogicalConnection] = field(default_factory=list)
    vpc_services: List[LogicalService] = field(default_factory=list)
    global_services: List[LogicalService] = field(default_factory=list)
    vpc_structure: Optional[VPCStructure] = None


class ResourceAggregator:
    """Aggregates Terraform resources into logical services."""

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        self._config = config_loader or ConfigLoader()
        self._aggregation_rules = self._build_aggregation_rules()
        self._logical_connections = self._config.get_logical_connections()
        self._build_type_to_rule_map()

    def _build_aggregation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Build aggregation rules dict from config."""
        flat_rules = self._config.get_flat_aggregation_rules()
        result = {}
        for service_name, config in flat_rules.items():
            # Map YAML format (primary/secondary/in_vpc) to internal format
            result[service_name] = {
                'primary': config.get("primary", []),
                'aggregate': config.get("secondary", []),  # secondary in YAML -> aggregate internally
                'icon': config.get("primary", [""])[0] if config.get("primary") else "",
                'display_name': service_name.replace("_", " ").title(),
                'is_vpc': config.get("in_vpc", False),
            }
        return result

    def _build_type_to_rule_map(self) -> None:
        """Build a mapping from resource type to aggregation rule."""
        self._type_to_rule: Dict[str, str] = {}
        for rule_name, rule in self._aggregation_rules.items():
            for res_type in rule['primary']:
                self._type_to_rule[res_type] = rule_name
            for res_type in rule['aggregate']:
                self._type_to_rule[res_type] = rule_name

    def _extract_subnet_ids(
        self,
        resources: List[TerraformResource],
        state_result: Optional["TerraformStateResult"] = None,
    ) -> List[str]:
        """Extract unique subnet IDs from a list of resources.

        Checks both HCL attributes and terraform state for subnet information.

        Args:
            resources: List of TerraformResource objects
            state_result: Optional terraform state with resolved values

        Returns:
            List of unique subnet resource IDs (e.g., ['aws_subnet.public', 'aws_subnet.private'])
        """
        subnet_ids: Set[str] = set()

        # Build state index if available
        state_index: Dict[str, Dict[str, Any]] = {}
        if state_result:
            from .terraform_tools import map_state_to_resource_id
            for state_res in state_result.resources:
                resource_id = map_state_to_resource_id(state_res.address)
                state_index[resource_id] = state_res.values

        for resource in resources:
            # Check state values first (more accurate)
            if resource.full_id in state_index:
                state_values = state_index[resource.full_id]
                # Check for subnet_id (single)
                subnet_id = state_values.get("subnet_id")
                if subnet_id and isinstance(subnet_id, str):
                    # State contains actual subnet ID (vpc-xxx), need to map back
                    # For now, store the raw value - we'll match by ID later
                    subnet_ids.add(f"_state_subnet:{subnet_id}")

                # Check for subnet_ids (list)
                subnet_id_list = state_values.get("subnet_ids")
                if subnet_id_list and isinstance(subnet_id_list, list):
                    for sid in subnet_id_list:
                        if isinstance(sid, str):
                            subnet_ids.add(f"_state_subnet:{sid}")

                # Check for subnets (list) - used by ALB/NLB resources
                subnets_list = state_values.get("subnets")
                if subnets_list and isinstance(subnets_list, list):
                    for sid in subnets_list:
                        if isinstance(sid, str):
                            subnet_ids.add(f"_state_subnet:{sid}")

            # Check HCL attributes for references like aws_subnet.public.id
            # Search in common attribute names and nested structures
            import re
            self._extract_subnet_refs_from_attrs(resource.attributes, subnet_ids)

        return list(subnet_ids)

    def _extract_subnet_refs_from_attrs(
        self,
        attrs: Any,
        subnet_ids: Set[str],
        depth: int = 0,
    ) -> None:
        """Recursively extract subnet references from attributes.

        Searches through nested dicts and lists for aws_subnet references.

        Args:
            attrs: Attribute value (dict, list, or string)
            subnet_ids: Set to add found subnet IDs to
            depth: Current recursion depth (max 5 to prevent infinite loops)
        """
        import re

        if depth > 5:
            return

        if isinstance(attrs, dict):
            # Check specific keys that commonly contain subnet info
            for key in ("subnet_id", "subnet_ids", "subnets", "network_configuration"):
                if key in attrs:
                    self._extract_subnet_refs_from_attrs(attrs[key], subnet_ids, depth + 1)
            # Also check all values for nested structures
            for value in attrs.values():
                if isinstance(value, (dict, list)):
                    self._extract_subnet_refs_from_attrs(value, subnet_ids, depth + 1)
        elif isinstance(attrs, list):
            for item in attrs:
                self._extract_subnet_refs_from_attrs(item, subnet_ids, depth + 1)
        elif isinstance(attrs, str):
            # Look for aws_subnet.name references
            for match in re.finditer(r'aws_subnet\.(\w+)', attrs):
                subnet_name = match.group(1)
                subnet_ids.add(f"aws_subnet.{subnet_name}")

    def _get_resource_display_name(
        self,
        resource: TerraformResource,
        resolver: Optional["VariableResolver"] = None,
    ) -> str:
        """Extract display name for a single resource.

        Args:
            resource: TerraformResource to get display name for
            resolver: Optional VariableResolver for resolving interpolations

        Returns:
            Human-readable display name for the resource
        """
        # Try to get name from attributes or use resource_name
        attr_name = resource.attributes.get('name', '')
        fallback_name = resource.resource_name

        display_name = fallback_name

        # If attribute name contains unresolved variables, use resource_name
        if isinstance(attr_name, str) and attr_name:
            # Resolve any variable interpolations
            if resolver:
                resolved_name = resolver.resolve(attr_name)
                # If still contains ${, fall back to resource name
                if '${' not in resolved_name:
                    display_name = resolved_name
            else:
                # If it doesn't contain ${, use attr_name
                if '${' not in attr_name:
                    display_name = attr_name

        # Clean up underscore-based names to be more readable
        display_name = display_name.replace('_', ' ').title()

        # Truncate long names
        if len(display_name) > 20:
            display_name = display_name[:17] + "..."

        return display_name

    def aggregate(
        self,
        parse_result: ParseResult,
        terraform_dir: Optional[Union[str, Path]] = None,
        state_result: Optional["TerraformStateResult"] = None,
    ) -> AggregatedResult:
        """Aggregate parsed resources into logical services.

        Args:
            parse_result: ParseResult containing Terraform resources
            terraform_dir: Optional path to Terraform directory for variable resolution

        Returns:
            AggregatedResult with logical services and optional VPC structure
        """
        result = AggregatedResult()

        # Initialize variable resolver if terraform_dir is provided
        resolver = None
        if terraform_dir is not None:
            from .variable_resolver import VariableResolver
            resolver = VariableResolver(terraform_dir)

        # Group resources by aggregation rule
        rule_resources: Dict[str, List[TerraformResource]] = {}
        unmatched: List[TerraformResource] = []

        for resource in parse_result.resources:
            rule_name = self._type_to_rule.get(resource.resource_type)
            if rule_name:
                rule_resources.setdefault(rule_name, []).append(resource)
            else:
                unmatched.append(resource)

        # Create logical services from grouped resources
        for rule_name, resources in rule_resources.items():
            rule = self._aggregation_rules[rule_name]

            # Count primary resources
            primary_resources = [r for r in resources if r.resource_type in rule['primary']]
            primary_count = len(primary_resources)
            if primary_count == 0:
                continue  # Skip if no primary resources

            # VPC resources: de-group - create one LogicalService per primary resource
            if rule['is_vpc']:
                for resource in primary_resources:
                    # Extract subnet_ids for this specific resource
                    subnet_ids = self._extract_subnet_ids([resource], state_result)

                    # Get display name for this specific resource
                    display_name = self._get_resource_display_name(resource, resolver)

                    service = LogicalService(
                        service_type=rule_name,
                        name=display_name,
                        icon_resource_type=rule['icon'],
                        resources=[resource],  # Single resource
                        count=1,
                        is_vpc_resource=True,
                        subnet_ids=subnet_ids,
                        resource_id=resource.full_id,  # Unique ID for this resource
                    )

                    result.services.append(service)
                    result.vpc_services.append(service)
            else:
                # Non-VPC resources: keep grouped (original behavior)
                display_name = rule['display_name']
                if primary_resources:
                    first_resource = primary_resources[0]
                    # Try to get name from attributes or use resource_name
                    attr_name = first_resource.attributes.get('name', '')
                    fallback_name = first_resource.resource_name

                    # If attribute name contains unresolved variables, use resource_name
                    if isinstance(attr_name, str) and attr_name:
                        # Resolve any variable interpolations
                        if resolver:
                            resolved_name = resolver.resolve(attr_name)
                            # If still contains ${, fall back to resource name
                            if '${' in resolved_name:
                                display_name = fallback_name
                            else:
                                display_name = resolved_name
                        else:
                            # If it contains ${, use resource_name, else use attr_name
                            if '${' in attr_name:
                                display_name = fallback_name
                            else:
                                display_name = attr_name
                    else:
                        display_name = fallback_name

                    # Clean up underscore-based names to be more readable
                    display_name = display_name.replace('_', ' ').title()

                    # Truncate long names
                    if len(display_name) > 20:
                        display_name = display_name[:17] + "..."

                # Extract subnet_ids from all resources (for non-VPC, usually empty)
                subnet_ids = self._extract_subnet_ids(resources, state_result)

                service = LogicalService(
                    service_type=rule_name,
                    name=display_name,
                    icon_resource_type=rule['icon'],
                    resources=resources,
                    count=primary_count,
                    is_vpc_resource=False,
                    subnet_ids=subnet_ids,
                )

                result.services.append(service)
                result.global_services.append(service)

        # Create logical connections based on which services exist
        # Build a mapping from service_type to list of services (supports de-grouped services)
        services_by_type: Dict[str, List[LogicalService]] = {}
        for s in result.services:
            services_by_type.setdefault(s.service_type, []).append(s)

        for conn in self._logical_connections:
            source_type = conn.get("source", "")
            target_type = conn.get("target", "")
            if source_type in services_by_type and target_type in services_by_type:
                source_services = services_by_type[source_type]
                target_services = services_by_type[target_type]
                # Connect each source to each target of matching type
                for source_service in source_services:
                    for target_service in target_services:
                        result.connections.append(LogicalConnection(
                            source_id=source_service.id,
                            target_id=target_service.id,
                            label=conn.get("label", ""),
                            connection_type=conn.get("type", "default"),
                        ))

        # Build VPC structure if resolver is available
        if resolver is not None:
            vpc_builder = VPCStructureBuilder()
            result.vpc_structure = vpc_builder.build(
                parse_result.resources,
                resolver=resolver,
                state_result=state_result,
            )

        return result


class VPCStructureBuilder:
    """Builds VPC structure from Terraform resources."""

    # Regex patterns for detecting AZ from resource names
    AZ_PATTERNS: List[tuple] = [
        # Pattern: name-a, name-b, name-c (single letter suffix)
        (r"[-_]([a-f])$", lambda m: m.group(1)),
        # Pattern: name-1a, name-1b, name-2a (number + letter suffix)
        (r"[-_](\d[a-f])$", lambda m: m.group(1)),
        # Pattern: name-az1, name-az2, name-az3 (az + number suffix)
        (r"[-_]az(\d)$", lambda m: m.group(1)),
        # Pattern: zone-a, zone-b in the middle of name
        (r"[-_]([a-f])[-_]", lambda m: m.group(1)),
    ]

    # Patterns for detecting subnet type from name/tags
    SUBNET_TYPE_PATTERNS: Dict[str, List[str]] = {
        "public": ["public", "pub", "external", "ext", "dmz", "bastion"],
        "private": ["private", "priv", "internal", "int", "app", "compute", "worker", "backend", "application"],
        "database": ["database", "db", "rds", "data", "storage", "persistence"],
    }

    def __init__(self) -> None:
        """Initialize the VPCStructureBuilder."""
        pass

    def _detect_availability_zone(
        self, resource: TerraformResource, sequential_index: Optional[int] = None
    ) -> Optional[str]:
        """Detect availability zone from resource attributes or name patterns.

        Args:
            resource: TerraformResource to analyze
            sequential_index: Optional index for sequential AZ naming when patterns fail

        Returns:
            Detected AZ name or None if not detectable
        """
        # First check for explicit availability_zone attribute
        az = resource.attributes.get("availability_zone")
        if az and isinstance(az, str):
            # Check if it's an unresolved variable (contains ${)
            if "${" not in az:
                return az
            # Fall through to pattern detection if unresolved

        # Try to detect from resource name
        name = resource.attributes.get("name", resource.resource_name)
        if not isinstance(name, str):
            name = resource.resource_name

        name_lower = name.lower()

        for pattern, extractor in self.AZ_PATTERNS:
            match = re.search(pattern, name_lower)
            if match:
                suffix = extractor(match)
                # Return a placeholder AZ name with the detected suffix
                return f"detected-{suffix}"

        # If we have a sequential index (for count-based resources), use it
        if sequential_index is not None:
            az_letters = "abcdef"
            if sequential_index < len(az_letters):
                return f"detected-{az_letters[sequential_index]}"

        return None

    def _detect_subnet_type(self, resource: TerraformResource) -> str:
        """Detect subnet type from name or tags.

        Args:
            resource: TerraformResource to analyze

        Returns:
            Detected subnet type ('public', 'private', 'database', or 'unknown')
        """
        # Check resource name and name attribute
        names_to_check = [
            resource.resource_name,
            resource.attributes.get("name", ""),
        ]

        # Check tags
        tags = resource.attributes.get("tags", {})
        if isinstance(tags, dict):
            type_tag = tags.get("Type", tags.get("type", ""))
            if type_tag:
                type_tag_lower = type_tag.lower()
                for subnet_type, patterns in self.SUBNET_TYPE_PATTERNS.items():
                    if type_tag_lower in patterns:
                        return subnet_type

        # Check name patterns
        for name in names_to_check:
            if not isinstance(name, str):
                continue
            name_lower = name.lower()
            for subnet_type, patterns in self.SUBNET_TYPE_PATTERNS.items():
                for pattern in patterns:
                    if pattern in name_lower:
                        return subnet_type

        return "unknown"

    def _detect_endpoint_type(self, resource: TerraformResource) -> str:
        """Detect VPC endpoint type (gateway or interface).

        Args:
            resource: TerraformResource to analyze

        Returns:
            Endpoint type ('gateway' or 'interface')
        """
        endpoint_type = resource.attributes.get("vpc_endpoint_type", "")
        if isinstance(endpoint_type, str):
            endpoint_type_lower = endpoint_type.lower()
            if endpoint_type_lower == "gateway":
                return "gateway"
        return "interface"

    def _detect_endpoint_service(self, resource: TerraformResource) -> str:
        """Extract service name from VPC endpoint.

        Args:
            resource: TerraformResource to analyze

        Returns:
            Service name (e.g., 's3', 'dynamodb', 'ecr.api')
        """
        service_name = resource.attributes.get("service_name", "")
        if not isinstance(service_name, str):
            return "unknown"

        # Service name format: com.amazonaws.<region>.<service>
        # Example: com.amazonaws.us-east-1.s3
        # But if region is a variable like ${var.aws_region}, we get:
        # com.amazonaws.${var.aws_region}.s3

        # Strategy: take the last part(s) after the last known prefix
        # Remove any variable interpolation patterns
        clean_name = service_name

        # If there's a variable pattern, extract service from the end
        if "${" in service_name:
            # Find the service after the variable - typically the last segment
            # e.g., "com.amazonaws.${var.aws_region}.s3" -> "s3"
            parts = service_name.split(".")
            # Get parts after any that contain "${"
            service_parts = []
            found_var = False
            for part in parts:
                if "${" in part or "}" in part:
                    found_var = True
                    service_parts = []  # Reset, service comes after
                elif found_var:
                    service_parts.append(part)
            if service_parts:
                return ".".join(service_parts)

        # Standard parsing: com.amazonaws.<region>.<service>
        parts = service_name.split(".")
        if len(parts) >= 4:
            # Join everything after the region (handles services like ecr.api)
            return ".".join(parts[3:])

        return "unknown"

    def _get_az_short_name(self, az_name: str) -> str:
        """Extract short name from AZ name.

        Args:
            az_name: Full AZ name (e.g., 'us-east-1a' or 'detected-1a')

        Returns:
            Short name (e.g., '1a', 'a')
        """
        # Handle detected AZs
        if az_name.startswith("detected-"):
            return az_name.replace("detected-", "")

        # Handle standard AWS AZ names like us-east-1a
        match = re.search(r"(\d[a-z])$", az_name)
        if match:
            return match.group(1)

        # Handle simple suffix like -a, -b
        if len(az_name) >= 1 and az_name[-1].isalpha():
            return az_name[-1]

        return az_name

    def _extract_az_suffix(self, resource_name: str) -> Optional[str]:
        """Extract AZ suffix from subnet resource name.

        This extracts the numeric or letter suffix that indicates which AZ
        a subnet belongs to, enabling realistic grouping where each AZ
        contains all subnet types.

        Args:
            resource_name: The Terraform resource name (e.g., 'public_subnet_1')

        Returns:
            AZ suffix (e.g., '1', 'a', '1a') or None if not detectable

        Examples:
            'public-subnet-1' -> '1'
            'compute-subnet-a' -> 'a'
            'database_subnet_1a' -> '1a'
            'my-private-subnet' -> None
        """
        name_lower = resource_name.lower()

        # Pattern priority: more specific patterns first
        patterns = [
            r"[-_](\d[a-f])$",  # ends with -1a, -1b, _2a
            r"[-_](\d+)$",      # ends with -1, -2, _3
            r"[-_]([a-f])$",    # ends with -a, -b, _c
        ]

        for pattern in patterns:
            match = re.search(pattern, name_lower)
            if match:
                return match.group(1)

        return None

    def build(
        self,
        resources: List[TerraformResource],
        resolver: Optional["VariableResolver"] = None,
        state_result: Optional["TerraformStateResult"] = None,
    ) -> Optional[VPCStructure]:
        """Build VPCStructure from a list of Terraform resources.

        Args:
            resources: List of TerraformResource objects
            resolver: Optional VariableResolver for resolving interpolations
            state_result: Optional TerraformStateResult with actual state values

        Returns:
            VPCStructure or None if no VPC found
        """
        if not resources:
            return None

        # Build state lookup index if state is available
        state_index: Dict[str, Dict[str, Any]] = {}
        if state_result:
            from .terraform_tools import map_state_to_resource_id
            for state_res in state_result.resources:
                resource_id = map_state_to_resource_id(state_res.address)
                state_index[resource_id] = state_res.values

        # Find VPC resource
        vpc_resource = None
        for r in resources:
            if r.resource_type == "aws_vpc":
                vpc_resource = r
                break

        if not vpc_resource:
            return None

        # Get VPC name
        vpc_name = vpc_resource.attributes.get("name", vpc_resource.resource_name)
        if resolver and isinstance(vpc_name, str):
            vpc_name = resolver.resolve(vpc_name)

        # Collect subnets and group by AZ for realistic representation
        # In AWS, each AZ contains all subnet types (public, private, database)
        subnet_resources = [r for r in resources if r.resource_type == "aws_subnet"]

        # First pass: collect all subnets with their AZ info
        all_subnets: List[Tuple[TerraformResource, Subnet, Optional[str]]] = []
        explicit_azs: Set[str] = set()

        for r in subnet_resources:
            # Get subnet name
            subnet_name = r.attributes.get("name", r.resource_name)
            if resolver and isinstance(subnet_name, str):
                subnet_name = resolver.resolve(subnet_name)

            subnet_type = self._detect_subnet_type(r)

            # Try to get explicit AZ - prefer state data if available
            explicit_az = None
            if r.full_id in state_index:
                state_az = state_index[r.full_id].get("availability_zone")
                if state_az and isinstance(state_az, str):
                    explicit_az = state_az

            # Fallback to HCL-based detection
            if not explicit_az:
                explicit_az = self._detect_availability_zone(r)

            # Try to extract suffix from resource name (e.g., "-a", "-1")
            suffix = self._extract_az_suffix(r.resource_name)

            # Determine AZ key for grouping
            if explicit_az and not explicit_az.startswith("detected-"):
                az_key = explicit_az
                explicit_azs.add(explicit_az)
            elif suffix:
                az_key = f"detected-{suffix}"
            else:
                az_key = None  # Will be assigned later

            # Extract AWS subnet ID from state if available
            aws_subnet_id = None
            if r.full_id in state_index:
                aws_subnet_id = state_index[r.full_id].get("id")

            subnet = Subnet(
                resource_id=r.full_id,
                name=subnet_name,
                subnet_type=subnet_type,
                availability_zone=az_key or "unknown",
                cidr_block=r.attributes.get("cidr_block"),
                aws_id=aws_subnet_id,
            )

            all_subnets.append((r, subnet, az_key))

        # Determine the number of AZs
        if explicit_azs:
            # Use explicit AZs as the primary structure
            az_names = sorted(explicit_azs)
        else:
            # Determine count from resource count or number of subnets
            num_azs = 1
            for r, _, _ in all_subnets:
                if r.count and r.count > num_azs:
                    num_azs = r.count

            # If no count, use number of distinct detected AZs or subnet count
            if num_azs == 1:
                detected_azs = set(az_key for _, _, az_key in all_subnets if az_key and az_key.startswith("detected-"))
                if detected_azs:
                    num_azs = len(detected_azs)
                else:
                    # Count subnets by type and use max
                    type_counts: Dict[str, int] = {}
                    for _, subnet, _ in all_subnets:
                        type_counts[subnet.subnet_type] = type_counts.get(subnet.subnet_type, 0) + 1
                    if type_counts:
                        num_azs = max(type_counts.values())

            az_letters = "abcdef"
            az_names = [f"detected-{az_letters[i % len(az_letters)]}" for i in range(num_azs)]

        # Create AZ objects
        az_map: Dict[str, AvailabilityZone] = {}
        availability_zones = []
        for az_name in az_names:
            az = AvailabilityZone(
                name=az_name,
                short_name=self._get_az_short_name(az_name),
                subnets=[],
            )
            az_map[az_name] = az
            availability_zones.append(az)

        # Distribute subnets to AZs
        type_order = {"public": 0, "private": 1, "database": 2, "unknown": 3}
        unassigned: List[Subnet] = []

        for r, subnet, az_key in sorted(all_subnets, key=lambda x: (type_order.get(x[1].subnet_type, 3), x[1].name)):
            if az_key and az_key in az_map:
                az_map[az_key].subnets.append(subnet)
            elif az_key and az_key.startswith("detected-"):
                # Try to match by suffix
                suffix = az_key.replace("detected-", "")
                matched = False
                for az in availability_zones:
                    if az.short_name == suffix or suffix in az.short_name:
                        az.subnets.append(subnet)
                        matched = True
                        break
                if not matched:
                    unassigned.append(subnet)
            else:
                unassigned.append(subnet)

        # Distribute unassigned subnets round-robin by type
        if unassigned and availability_zones:
            # Group unassigned by type
            unassigned_by_type: Dict[str, List[Subnet]] = {}
            for subnet in unassigned:
                unassigned_by_type.setdefault(subnet.subnet_type, []).append(subnet)

            # Distribute each type across AZs
            az_letters = "abcdef"
            for subnet_type in sorted(unassigned_by_type.keys(), key=lambda t: type_order.get(t, 3)):
                for idx, subnet in enumerate(unassigned_by_type[subnet_type]):
                    az_idx = idx % len(availability_zones)
                    # Add AZ indicator to name if distributing multiple of same type
                    if len(unassigned_by_type[subnet_type]) > 1:
                        subnet.name = f"{subnet.name} ({az_letters[az_idx]})"
                    availability_zones[az_idx].subnets.append(subnet)

        # Collect VPC endpoints
        endpoints = []
        for r in resources:
            if r.resource_type != "aws_vpc_endpoint":
                continue

            endpoint_name = r.attributes.get("name", r.resource_name)
            if resolver and isinstance(endpoint_name, str):
                endpoint_name = resolver.resolve(endpoint_name)

            endpoint = VPCEndpoint(
                resource_id=r.full_id,
                name=endpoint_name,
                endpoint_type=self._detect_endpoint_type(r),
                service=self._detect_endpoint_service(r),
            )
            endpoints.append(endpoint)

        return VPCStructure(
            vpc_id=vpc_resource.full_id,
            name=vpc_name,
            availability_zones=availability_zones,
            endpoints=endpoints,
        )


def aggregate_resources(parse_result: ParseResult) -> AggregatedResult:
    """Convenience function to aggregate resources."""
    aggregator = ResourceAggregator()
    return aggregator.aggregate(parse_result)
