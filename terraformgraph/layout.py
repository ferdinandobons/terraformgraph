"""
Layout Engine

Computes positions for logical services in the diagram.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from .aggregator import AggregatedResult, LogicalConnection, LogicalService

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
    """Configuration for layout engine.

    Supports responsive sizing based on content. Base values are scaled
    according to the number of services and VPC complexity.
    """
    # Base dimensions (will be scaled)
    canvas_width: int = 1400
    canvas_height: int = 900
    padding: int = 30
    icon_size: int = 64
    icon_spacing: int = 40
    group_padding: int = 25
    label_height: int = 24
    row_spacing: int = 100
    column_spacing: int = 130

    # Responsive scaling factors
    min_scale: float = 0.6
    max_scale: float = 1.5

    def scaled(self, scale: float) -> "LayoutConfig":
        """Create a new config with scaled dimensions."""
        clamped_scale = max(self.min_scale, min(self.max_scale, scale))
        return LayoutConfig(
            canvas_width=int(self.canvas_width * clamped_scale),
            canvas_height=int(self.canvas_height * clamped_scale),
            padding=int(self.padding * clamped_scale),
            icon_size=int(self.icon_size * clamped_scale),
            icon_spacing=int(self.icon_spacing * clamped_scale),
            group_padding=int(self.group_padding * clamped_scale),
            label_height=int(self.label_height * clamped_scale),
            row_spacing=int(self.row_spacing * clamped_scale),
            column_spacing=int(self.column_spacing * clamped_scale),
            min_scale=self.min_scale,
            max_scale=self.max_scale,
        )


class LayoutEngine:
    """Computes positions for diagram elements."""

    def __init__(self, config: Optional[LayoutConfig] = None):
        self.base_config = config or LayoutConfig()
        self.config = self.base_config

    def _compute_responsive_scale(self, aggregated: AggregatedResult) -> float:
        """Compute scale factor based on content complexity.

        Factors considered:
        - Number of services
        - Number of AZs
        - Number of subnets per AZ
        - Number of VPC endpoints
        """
        num_services = len(aggregated.services)

        # Count VPC complexity
        num_azs = 0
        max_subnets_per_az = 0
        num_endpoints = 0

        if aggregated.vpc_structure:
            num_azs = len(aggregated.vpc_structure.availability_zones)
            for az in aggregated.vpc_structure.availability_zones:
                max_subnets_per_az = max(max_subnets_per_az, len(az.subnets))
            num_endpoints = len(aggregated.vpc_structure.endpoints) if aggregated.vpc_structure.endpoints else 0

        # Base scale on service count (optimal for 8-12 services)
        service_scale = 1.0
        if num_services <= 4:
            service_scale = 0.8
        elif num_services <= 8:
            service_scale = 0.9
        elif num_services <= 15:
            service_scale = 1.0
        elif num_services <= 25:
            service_scale = 1.2
        else:
            service_scale = 1.4

        # Adjust for VPC complexity
        vpc_scale = 1.0
        if num_azs >= 3:
            vpc_scale *= 1.1
        if max_subnets_per_az >= 4:
            vpc_scale *= 1.15
        if num_endpoints >= 4:
            vpc_scale *= 1.05

        return service_scale * vpc_scale

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

        Dimensions are computed responsively based on content.
        """
        # Compute responsive scale and apply to config
        scale = self._compute_responsive_scale(aggregated)
        self.config = self.base_config.scaled(scale)

        positions: Dict[str, Position] = {}
        groups: List[ServiceGroup] = []

        # Compute required height based on content (will adjust AWS Cloud later)
        estimated_height = self._estimate_required_height(aggregated)
        actual_canvas_height = max(self.config.canvas_height, estimated_height)

        # Create AWS Cloud container (height will be finalized after layout)
        aws_cloud = ServiceGroup(
            group_type='aws_cloud',
            name='AWS Cloud',
            position=Position(
                x=self.config.padding,
                y=self.config.padding,
                width=self.config.canvas_width - 2 * self.config.padding,
                height=actual_canvas_height - 2 * self.config.padding
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
            elif st in ('alb', 'ecs', 'ec2', 'security_groups', 'security', 'vpc', 'internet_gateway', 'nat_gateway'):
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

        # Track VPC bottom for non-VPC services layout
        vpc_bottom_y = y_offset

        # Row 2: VPC box with internal services (only if VPC resources exist)
        # Filter out 'vpc' itself from vpc_services for positioning
        vpc_internal = [s for s in vpc_services if s.service_type != 'vpc']

        # Only create VPC box if there are VPC services OR vpc_structure exists
        has_vpc_content = len(vpc_internal) > 0 or aggregated.vpc_structure is not None

        if has_vpc_content:
            vpc_x = self.config.padding + 50
            vpc_width = self.config.canvas_width - 2 * (self.config.padding + 50)

            # Separate services: those with subnet_ids go inside subnets, others in top row
            services_with_subnets = [s for s in vpc_internal if s.subnet_ids]
            services_without_subnets = [s for s in vpc_internal if not s.subnet_ids]

            # Use dynamic VPC height if vpc_structure exists
            if aggregated.vpc_structure:
                vpc_height = self._compute_vpc_height(
                    aggregated.vpc_structure,
                    has_vpc_services=len(services_without_subnets) > 0,
                    has_services_in_subnets=len(services_with_subnets) > 0,
                    services_with_subnets=services_with_subnets,
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
            vpc_bottom_y = y_offset

        # Non-VPC services: use connection-based organic layout
        non_vpc_services = data_services + messaging_services + security_services + other_services

        if non_vpc_services:
            y_offset = self._layout_by_connections(
                services=non_vpc_services,
                connections=aggregated.connections,
                start_x=self.config.padding + 50,
                start_y=vpc_bottom_y,
                available_width=self.config.canvas_width - 2 * (self.config.padding + 50),
                positions=positions
            )

        return positions, groups

    def _build_connection_graph(
        self,
        services: List[LogicalService],
        connections: List[LogicalConnection]
    ) -> Dict[str, Set[str]]:
        """Build adjacency list of connected service types.

        Returns a bidirectional graph where each service_type maps to
        the set of service_types it's connected to.
        """
        # Get service types present
        present_types = {s.service_type for s in services}

        # Build adjacency list (bidirectional)
        graph: Dict[str, Set[str]] = {t: set() for t in present_types}

        for conn in connections:
            src, tgt = conn.source_id, conn.target_id
            # Extract service_type from id (e.g., "lambda.Api Handler" -> "lambda")
            src_type = src.split('.')[0] if '.' in src else src
            tgt_type = tgt.split('.')[0] if '.' in tgt else tgt

            if src_type in present_types and tgt_type in present_types:
                graph[src_type].add(tgt_type)
                graph[tgt_type].add(src_type)

        return graph

    def _layout_by_connections(
        self,
        services: List[LogicalService],
        connections: List[LogicalConnection],
        start_x: float,
        start_y: float,
        available_width: float,
        positions: Dict[str, Position]
    ) -> float:
        """Position services based on their connections (organic layout).

        Services with connections are placed adjacent to each other.
        Returns the Y position after all services are placed.
        """
        if not services:
            return start_y

        # Build connection graph
        graph = self._build_connection_graph(services, connections)

        # Group services by type
        by_type: Dict[str, List[LogicalService]] = {}
        for s in services:
            by_type.setdefault(s.service_type, []).append(s)

        # Sort types by number of connections (most connected first)
        sorted_types = sorted(
            by_type.keys(),
            key=lambda t: len(graph.get(t, set())),
            reverse=True
        )

        # Calculate grid dimensions
        service_width = self.config.icon_size + 50  # icon + padding
        service_height = self.config.icon_size + 50  # icon + label + padding
        cols = max(1, int(available_width / service_width))

        # Track placed service types and their grid positions
        placed_positions: Dict[str, Tuple[int, int]] = {}  # type -> (row, col)
        grid: Dict[Tuple[int, int], str] = {}  # (row, col) -> service_type

        current_row = 0
        current_col = 0

        for service_type in sorted_types:
            type_services = by_type[service_type]

            # Find best position based on connections
            connected_types = graph.get(service_type, set())
            best_col = current_col
            best_row = current_row

            # If connected to already-placed types, try to position nearby
            for ct in connected_types:
                if ct in placed_positions:
                    ct_row, ct_col = placed_positions[ct]
                    # Try adjacent positions (right, below, left)
                    candidates = [
                        (ct_row, ct_col + 1),
                        (ct_row + 1, ct_col),
                        (ct_row, ct_col - 1),
                        (ct_row + 1, ct_col + 1),
                    ]
                    for r, c in candidates:
                        if c >= 0 and c < cols and (r, c) not in grid:
                            best_row, best_col = r, c
                            break
                    break

            # Ensure we don't go out of bounds
            if best_col >= cols:
                best_col = 0
                best_row = current_row + 1

            # Position all services of this type (they share the same grid cell conceptually)
            for i, service in enumerate(type_services):
                # Calculate actual position
                col = best_col + i
                row = best_row
                if col >= cols:
                    col = col % cols
                    row += (best_col + i) // cols

                x = start_x + col * service_width
                y = start_y + row * service_height

                positions[service.id] = Position(
                    x=x,
                    y=y,
                    width=self.config.icon_size,
                    height=self.config.icon_size
                )

                grid[(row, col)] = service_type
                current_row = max(current_row, row)

            # Track where this type was placed (first position)
            placed_positions[service_type] = (best_row, best_col)

            # Update current position for next unconnected type
            if best_col + len(type_services) >= cols:
                current_row = best_row + 1
                current_col = 0
            else:
                current_col = best_col + len(type_services)

        # Return the Y position after all services
        return start_y + (current_row + 1) * service_height + 20

    def _estimate_required_height(self, aggregated: AggregatedResult) -> int:
        """Estimate the required canvas height based on content.

        Calculates height needed for:
        - Edge services row
        - VPC box (with AZs and subnets)
        - Data services row
        - Messaging services row
        - Security/other services row
        """
        height = self.config.padding + 40  # Initial offset

        # Categorize services to count rows
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
            elif st in ('alb', 'ecs', 'ec2', 'security_groups', 'security', 'vpc', 'internet_gateway', 'nat_gateway'):
                vpc_services.append(service)
            elif st in ('s3', 'dynamodb', 'mongodb'):
                data_services.append(service)
            elif st in ('sqs', 'sns', 'eventbridge'):
                messaging_services.append(service)
            elif st in ('kms', 'secrets', 'secrets_manager', 'iam'):
                security_services.append(service)
            else:
                other_services.append(service)

        # Row 1: Edge services
        if edge_services:
            height += self.config.row_spacing + 20

        # Row 2: VPC box
        vpc_internal = [s for s in vpc_services if s.service_type != 'vpc']
        has_vpc_content = len(vpc_internal) > 0 or aggregated.vpc_structure is not None

        if has_vpc_content:
            services_with_subnets = [s for s in vpc_internal if s.subnet_ids]
            services_without_subnets = [s for s in vpc_internal if not s.subnet_ids]

            if aggregated.vpc_structure:
                vpc_height = self._compute_vpc_height(
                    aggregated.vpc_structure,
                    has_vpc_services=len(services_without_subnets) > 0,
                    has_services_in_subnets=len(services_with_subnets) > 0,
                    services_with_subnets=services_with_subnets,
                )
            else:
                vpc_height = 180

            height += vpc_height + 40

        # Non-VPC services: estimate based on grid layout
        non_vpc_services = data_services + messaging_services + security_services + other_services
        if non_vpc_services:
            service_width = self.config.icon_size + 50
            service_height = self.config.icon_size + 50
            available_width = self.config.canvas_width - 2 * (self.config.padding + 50)
            cols = max(1, int(available_width / service_width))
            rows = (len(non_vpc_services) + cols - 1) // cols
            height += rows * service_height + 40

        # Bottom padding
        height += self.config.padding + 40

        return int(height)

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
        services_with_subnets: Optional[List[LogicalService]] = None,
    ) -> int:
        """Compute VPC box height based on subnet count, services, and endpoints.

        Args:
            vpc_structure: VPCStructure with availability zones, subnets, and endpoints
            has_vpc_services: Whether there are VPC services to display in top row
            has_services_in_subnets: Whether there are services positioned inside subnets
            services_with_subnets: List of services that go inside subnets (for precise calculation)

        Returns:
            Height in pixels for the VPC box
        """
        if not vpc_structure or not vpc_structure.availability_zones:
            return 180  # Default height

        # Constants - MUST use scaled values to match compute_layout()
        subnet_padding = 10  # Padding between subnets
        az_header_height = 30  # Height for AZ header
        # VPC header uses: group_padding + 30 (see compute_layout line 239)
        vpc_header_height = self.config.group_padding + 30
        base_padding = 40  # Bottom padding
        # Services row uses: icon_size + 50 (see compute_layout line 254)
        services_row_height = (self.config.icon_size + 50) if has_vpc_services else 0
        empty_subnet_height = 60
        # Service subnet height uses: icon_size + 56 (see _layout_subnets line 585)
        service_subnet_height = self.config.icon_size + 56

        # Calculate height needed for subnets in each AZ
        # Find which subnets will have services
        subnets_with_services: set = set()
        if services_with_subnets:
            for service in services_with_subnets:
                for subnet_id in service.subnet_ids:
                    # Normalize subnet ID
                    if subnet_id.startswith("_state_subnet:"):
                        # Will be resolved later, assume it matches a subnet
                        subnets_with_services.add(subnet_id)
                    else:
                        subnets_with_services.add(subnet_id)

        # Calculate max height needed across all AZs
        max_az_content_height = 0
        for az in vpc_structure.availability_zones:
            az_content_height = 0
            for subnet in az.subnets:
                # Check if this subnet will have services
                has_services = subnet.resource_id in subnets_with_services
                # Also check by AWS ID
                if subnet.aws_id:
                    if f"_state_subnet:{subnet.aws_id}" in subnets_with_services:
                        has_services = True

                subnet_h = service_subnet_height if has_services else empty_subnet_height
                az_content_height += subnet_h + subnet_padding

            max_az_content_height = max(max_az_content_height, az_content_height)

        # Total height for subnets
        height_for_subnets = (
            vpc_header_height +
            services_row_height +
            az_header_height +
            max_az_content_height +
            base_padding
        )

        # Height based on endpoints (if present)
        num_endpoints = len(vpc_structure.endpoints) if vpc_structure.endpoints else 0
        endpoint_spacing = 72  # Match the actual spacing used in _layout_vpc_structure
        height_for_endpoints = (
            vpc_header_height +
            services_row_height +
            (num_endpoints * endpoint_spacing) +
            base_padding + 20
        ) if num_endpoints > 0 else 0

        return max(200, height_for_subnets, height_for_endpoints)

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

        # Build global mapping from AWS subnet IDs to resource IDs
        # This is needed because ALBs can reference subnets from multiple AZs
        aws_id_to_resource_id: Dict[str, str] = {}
        for az in vpc_structure.availability_zones:
            for subnet in az.subnets:
                if subnet.aws_id:
                    aws_id_to_resource_id[subnet.aws_id] = subnet.resource_id

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
            self._layout_subnets(az, az_pos, positions, services_with_subnets, aws_id_to_resource_id)

            az_x += az_width + az_padding

        # Layout VPC endpoints INSIDE the VPC (right column, within border)
        if vpc_structure.endpoints:
            # Position endpoints inside the VPC border, in the reserved space
            endpoint_box_width = 80
            endpoint_box_height = 65
            endpoint_x = vpc_pos.x + vpc_pos.width - endpoint_width + 3  # Inside the reserved space
            endpoint_y = az_y + 5  # Start at same level as AZs
            endpoint_spacing = 72  # Spacing between endpoints

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
        aws_id_to_resource_id: Optional[Dict[str, str]] = None,
    ) -> None:
        """Layout subnets inside an availability zone.

        Args:
            az: AvailabilityZone containing subnets
            az_pos: Position of the AZ container
            positions: Dict to add subnet positions to
            services_with_subnets: Services that should be placed inside their subnets
            aws_id_to_resource_id: Mapping from AWS subnet IDs to resource IDs
        """
        if not az.subnets:
            return

        subnet_padding = 10
        # Base subnet height: 60px for empty subnets (enough for label and visibility)
        # Must match _compute_vpc_height for consistency
        subnet_height = 60
        subnet_width = az_pos.width - (2 * subnet_padding)

        subnet_y = az_pos.y + 30  # Below AZ header

        # Use provided mapping or empty dict
        if aws_id_to_resource_id is None:
            aws_id_to_resource_id = {}

        # Build mapping: subnet_resource_id -> list of services
        services_by_subnet: Dict[str, List[LogicalService]] = {}
        if services_with_subnets:
            for service in services_with_subnets:
                for subnet_id in service.subnet_ids:
                    # Handle _state_subnet: prefixed IDs (from Terraform state)
                    if subnet_id.startswith("_state_subnet:"):
                        aws_id = subnet_id[len("_state_subnet:"):]
                        # Map AWS ID to resource ID if we have it
                        if aws_id in aws_id_to_resource_id:
                            resource_id = aws_id_to_resource_id[aws_id]
                            services_by_subnet.setdefault(resource_id, []).append(service)
                    else:
                        # Direct resource ID reference (e.g., aws_subnet.public)
                        services_by_subnet.setdefault(subnet_id, []).append(service)

        for subnet in az.subnets:
            # Check if any services belong to this subnet
            subnet_services = services_by_subnet.get(subnet.resource_id, [])

            # Increase subnet height if it contains services
            # Service box needs: icon (64px) + label padding below (36px) + top padding (8px) + margins
            # Total service box height: 64 + 44 = 108px, add margin = 120px
            actual_subnet_height = subnet_height
            if subnet_services:
                actual_subnet_height = max(subnet_height, self.config.icon_size + 56)  # 64 + 56 = 120

            positions[subnet.resource_id] = Position(
                x=az_pos.x + subnet_padding,
                y=subnet_y,
                width=subnet_width,
                height=actual_subnet_height
            )

            # Position services inside this subnet
            if subnet_services:
                service_x = az_pos.x + subnet_padding + 15  # 15px left margin inside subnet
                # Center service vertically, accounting for the -8px top padding from renderer
                # Service icon is at y, but box extends 8px above, so offset by 8
                service_y = subnet_y + 8 + (actual_subnet_height - (self.config.icon_size + 44)) / 2

                for service in subnet_services:
                    # Only position if not already positioned (avoid duplicates)
                    if service.id not in positions:
                        positions[service.id] = Position(
                            x=service_x,
                            y=service_y,
                            width=self.config.icon_size,
                            height=self.config.icon_size
                        )
                        # Space between services: icon width + box padding (16px) + gap (10px)
                        service_x += self.config.icon_size + 26

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
