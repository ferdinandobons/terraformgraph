"""
Layout Engine

Computes positions for logical services in the diagram.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .aggregator import AggregatedResult, LogicalService

if TYPE_CHECKING:
    from .aggregator import AvailabilityZone, VPCStructure


@dataclass
class Position:
    """Position and size of an element."""
    x: float
    y: float
    width: float
    height: float


@dataclass
class ServiceGroup:
    """A visual group of services."""
    group_type: str  # 'aws_cloud', 'vpc', 'global'
    name: str
    services: List[LogicalService] = field(default_factory=list)
    position: Optional[Position] = None


@dataclass
class LayoutConfig:
    """Configuration for layout engine."""
    canvas_width: int = 1400
    canvas_height: int = 900
    padding: int = 30
    icon_size: int = 64
    icon_spacing: int = 40
    group_padding: int = 25
    label_height: int = 24
    row_spacing: int = 100
    column_spacing: int = 130


class LayoutEngine:
    """Computes positions for diagram elements."""

    def __init__(self, config: Optional[LayoutConfig] = None):
        self.config = config or LayoutConfig()

    def compute_layout(
        self,
        aggregated: AggregatedResult
    ) -> Tuple[Dict[str, Position], List[ServiceGroup]]:
        """
        Compute positions for all logical services.

        Layout structure:
        - Top row: Internet-facing services (CloudFront, WAF, Route53, ACM)
        - Middle: VPC box with ALB, ECS, EC2
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
        edge_services = []  # CloudFront, WAF, Route53, ACM, Cognito
        vpc_services = []   # ALB, ECS, EC2, Security
        data_services = []  # S3, DynamoDB, MongoDB
        messaging_services = []  # SQS, SNS, EventBridge
        security_services = []  # KMS, Secrets, IAM
        other_services = []  # CloudWatch, Bedrock, ECR, etc.

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

        # Row 2: VPC box with internal services
        vpc_x = self.config.padding + 50
        vpc_width = self.config.canvas_width - 2 * (self.config.padding + 50)

        # Filter out 'vpc' itself from vpc_services for positioning
        vpc_internal = [s for s in vpc_services if s.service_type != 'vpc']

        # Separate services: those with subnet_ids go inside subnets, others in top row
        services_with_subnets = [s for s in vpc_internal if s.subnet_ids]
        services_without_subnets = [s for s in vpc_internal if not s.subnet_ids]

        # Use dynamic VPC height if vpc_structure exists
        if aggregated.vpc_structure:
            vpc_height = self._compute_vpc_height(
                aggregated.vpc_structure,
                has_vpc_services=len(services_without_subnets) > 0,
                has_services_in_subnets=len(services_with_subnets) > 0,
            )
        else:
            vpc_height = 180

        vpc_pos = Position(x=vpc_x, y=y_offset, width=vpc_width, height=vpc_height)
        vpc_group = ServiceGroup(
            group_type='vpc',
            name='VPC',
            services=vpc_internal,
            position=vpc_pos
        )
        groups.append(vpc_group)

        # Position services WITHOUT subnet_ids at the TOP, above AZs
        services_row_y = y_offset + self.config.group_padding + 30
        if services_without_subnets:
            x = self._center_row_start(len(services_without_subnets), vpc_x + self.config.group_padding,
                                        vpc_x + vpc_width - self.config.group_padding)
            for service in services_without_subnets:
                positions[service.id] = Position(
                    x=x, y=services_row_y,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )
                x += self.config.column_spacing

        # Layout VPC structure (AZs and endpoints) BELOW services
        if aggregated.vpc_structure:
            # AZs start below the services row
            az_start_y = services_row_y + self.config.icon_size + 50 if services_without_subnets else services_row_y
            self._layout_vpc_structure(
                aggregated.vpc_structure,
                vpc_pos,
                positions,
                groups,
                az_start_y=az_start_y,
                services_with_subnets=services_with_subnets,
            )

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

    def _center_row_start(
        self,
        num_items: int,
        min_x: Optional[float] = None,
        max_x: Optional[float] = None
    ) -> float:
        """Calculate starting X position to center items in a row."""
        if min_x is None:
            min_x = self.config.padding
        if max_x is None:
            max_x = self.config.canvas_width - self.config.padding

        available_width = max_x - min_x
        total_items_width = num_items * self.config.icon_size + (num_items - 1) * self.config.icon_spacing
        return min_x + (available_width - total_items_width) / 2

    def _compute_vpc_height(
        self,
        vpc_structure: "VPCStructure",
        has_vpc_services: bool = True,
        has_services_in_subnets: bool = False,
    ) -> int:
        """Compute VPC box height based on subnet count, services, and endpoints.

        Args:
            vpc_structure: VPCStructure with availability zones, subnets, and endpoints
            has_vpc_services: Whether there are VPC services to display in top row
            has_services_in_subnets: Whether there are services positioned inside subnets

        Returns:
            Height in pixels for the VPC box
        """
        if not vpc_structure or not vpc_structure.availability_zones:
            return 180  # Default height

        # Find max subnets in any AZ
        max_subnets = 0
        for az in vpc_structure.availability_zones:
            max_subnets = max(max_subnets, len(az.subnets))

        # Calculate height: base height + per-subnet height
        # Increase subnet height if services are inside
        subnet_height = 85 if has_services_in_subnets else 50
        az_header_height = 30  # Height for AZ header
        vpc_header_height = 40  # Height for VPC header
        base_padding = 40  # Top and bottom padding
        services_row_height = 100 if has_vpc_services else 0  # Height for services row

        # Height based on subnets
        height_for_subnets = (
            vpc_header_height +
            services_row_height +
            az_header_height +
            (max_subnets * subnet_height) +
            base_padding
        )

        # Height based on endpoints (if present)
        num_endpoints = len(vpc_structure.endpoints) if vpc_structure.endpoints else 0
        endpoint_spacing = 55
        height_for_endpoints = (
            vpc_header_height +
            services_row_height +
            (num_endpoints * endpoint_spacing) +
            base_padding
        ) if num_endpoints > 0 else 0

        return max(180, height_for_subnets, height_for_endpoints)

    def _layout_vpc_structure(
        self,
        vpc_structure: "VPCStructure",
        vpc_pos: Position,
        positions: Dict[str, Position],
        groups: List[ServiceGroup],
        az_start_y: Optional[float] = None,
        services_with_subnets: Optional[List[LogicalService]] = None,
    ) -> None:
        """Layout availability zones and endpoints within VPC.

        Args:
            vpc_structure: VPCStructure with AZs and endpoints
            vpc_pos: Position of the VPC container
            positions: Dict to add subnet positions to
            groups: List to add AZ groups to
            az_start_y: Optional Y position where AZs should start (below services)
            services_with_subnets: Services that should be placed inside their subnets
        """
        if not vpc_structure:
            return

        num_azs = len(vpc_structure.availability_zones)
        if num_azs == 0:
            return

        # Calculate AZ dimensions
        az_padding = 15
        endpoint_width = 90  # Space reserved for endpoints on right
        available_width = vpc_pos.width - (2 * az_padding) - endpoint_width
        az_width = (available_width - (num_azs - 1) * az_padding) / num_azs

        # Layout each AZ
        az_y = az_start_y if az_start_y is not None else vpc_pos.y + 40
        az_height = (vpc_pos.y + vpc_pos.height - 20) - az_y  # Extend to bottom of VPC
        az_x = vpc_pos.x + az_padding

        for az in vpc_structure.availability_zones:
            az_pos = Position(
                x=az_x,
                y=az_y,
                width=az_width,
                height=az_height
            )

            # Create AZ group
            az_group = ServiceGroup(
                group_type='az',
                name=f"AZ {az.short_name}",
                position=az_pos
            )
            groups.append(az_group)

            # Layout subnets inside this AZ
            self._layout_subnets(az, az_pos, positions, services_with_subnets)

            az_x += az_width + az_padding

        # Layout VPC endpoints INSIDE the VPC (right column, within border)
        if vpc_structure.endpoints:
            # Position endpoints inside the VPC border, in the reserved space
            endpoint_box_width = 75
            endpoint_box_height = 45
            endpoint_x = vpc_pos.x + vpc_pos.width - endpoint_width + 5  # Inside the reserved space
            endpoint_y = az_y + 5  # Start at same level as AZs
            endpoint_spacing = 55  # Spacing between endpoints

            for endpoint in vpc_structure.endpoints:
                positions[endpoint.resource_id] = Position(
                    x=endpoint_x,
                    y=endpoint_y,
                    width=endpoint_box_width,
                    height=endpoint_box_height
                )
                endpoint_y += endpoint_spacing

    def _layout_subnets(
        self,
        az: "AvailabilityZone",
        az_pos: Position,
        positions: Dict[str, Position],
        services_with_subnets: Optional[List[LogicalService]] = None,
    ) -> None:
        """Layout subnets inside an availability zone.

        Args:
            az: AvailabilityZone containing subnets
            az_pos: Position of the AZ container
            positions: Dict to add subnet positions to
            services_with_subnets: Services that should be placed inside their subnets
        """
        if not az.subnets:
            return

        subnet_padding = 10
        subnet_height = 40
        subnet_width = az_pos.width - (2 * subnet_padding)

        subnet_y = az_pos.y + 30  # Below AZ header

        # Build mapping: subnet_resource_id -> list of services
        services_by_subnet: Dict[str, List[LogicalService]] = {}
        if services_with_subnets:
            for service in services_with_subnets:
                for subnet_id in service.subnet_ids:
                    services_by_subnet.setdefault(subnet_id, []).append(service)

        for subnet in az.subnets:
            # Check if any services belong to this subnet
            subnet_services = services_by_subnet.get(subnet.resource_id, [])

            # Increase subnet height if it contains services
            actual_subnet_height = subnet_height
            if subnet_services:
                actual_subnet_height = max(subnet_height, self.config.icon_size + 20)

            positions[subnet.resource_id] = Position(
                x=az_pos.x + subnet_padding,
                y=subnet_y,
                width=subnet_width,
                height=actual_subnet_height
            )

            # Position services inside this subnet
            if subnet_services:
                service_x = az_pos.x + subnet_padding + 10
                service_y = subnet_y + (actual_subnet_height - self.config.icon_size) / 2

                for service in subnet_services:
                    # Only position if not already positioned (avoid duplicates)
                    if service.id not in positions:
                        positions[service.id] = Position(
                            x=service_x,
                            y=service_y,
                            width=self.config.icon_size,
                            height=self.config.icon_size
                        )
                        service_x += self.config.icon_size + 20

            subnet_y += actual_subnet_height + subnet_padding

    def compute_connection_path(
        self,
        source_pos: Position,
        target_pos: Position,
        connection_type: str = 'default'
    ) -> str:
        """Compute SVG path for a connection between two services."""
        # Calculate center points
        sx = source_pos.x + source_pos.width / 2
        sy = source_pos.y + source_pos.height / 2
        tx = target_pos.x + target_pos.width / 2
        ty = target_pos.y + target_pos.height / 2

        # Use straight lines with slight curves for cleaner look
        if abs(ty - sy) > abs(tx - sx):
            # Mostly vertical - connect top/bottom
            if ty > sy:
                sy = source_pos.y + source_pos.height
                ty = target_pos.y
            else:
                sy = source_pos.y
                ty = target_pos.y + target_pos.height
        else:
            # Mostly horizontal - connect left/right
            if tx > sx:
                sx = source_pos.x + source_pos.width
                tx = target_pos.x
            else:
                sx = source_pos.x
                tx = target_pos.x + target_pos.width

        # Simple curved path
        mid_x = (sx + tx) / 2
        mid_y = (sy + ty) / 2

        return f"M {sx} {sy} Q {mid_x} {sy}, {mid_x} {mid_y} Q {mid_x} {ty}, {tx} {ty}"
