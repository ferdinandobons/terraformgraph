"""
Resource Aggregator

Aggregates low-level Terraform resources into high-level logical services
for cleaner architecture diagrams.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config_loader import ConfigLoader
from .parser import ParseResult, TerraformResource


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

    @property
    def id(self) -> str:
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

    def aggregate(self, parse_result: ParseResult) -> AggregatedResult:
        """Aggregate parsed resources into logical services."""
        result = AggregatedResult()

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
            primary_count = sum(1 for r in resources if r.resource_type in rule['primary'])
            if primary_count == 0:
                continue  # Skip if no primary resources

            service = LogicalService(
                service_type=rule_name,
                name=rule['display_name'],
                icon_resource_type=rule['icon'],
                resources=resources,
                count=primary_count,
                is_vpc_resource=rule['is_vpc'],
            )

            result.services.append(service)
            if service.is_vpc_resource:
                result.vpc_services.append(service)
            else:
                result.global_services.append(service)

        # Create logical connections based on which services exist
        existing_services = {s.service_type for s in result.services}
        for conn in self._logical_connections:
            source = conn.get("source", "")
            target = conn.get("target", "")
            if source in existing_services and target in existing_services:
                result.connections.append(LogicalConnection(
                    source_id=f"{source}.{self._aggregation_rules[source]['display_name']}",
                    target_id=f"{target}.{self._aggregation_rules[target]['display_name']}",
                    label=conn.get("label", ""),
                    connection_type=conn.get("type", "default"),
                ))

        return result


def aggregate_resources(parse_result: ParseResult) -> AggregatedResult:
    """Convenience function to aggregate resources."""
    aggregator = ResourceAggregator()
    return aggregator.aggregate(parse_result)
