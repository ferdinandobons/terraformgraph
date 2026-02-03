"""
SVG/HTML Renderer

Generates interactive HTML diagrams with:
- Drag-and-drop for repositioning services
- Connections that follow moved elements
- Export to PNG/JPG
"""

import html
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .aggregator import AggregatedResult, LogicalConnection, LogicalService, ResourceAggregator
from .icons import IconMapper
from .layout import LayoutConfig, Position, ServiceGroup

if TYPE_CHECKING:
    from .aggregator import Subnet, VPCEndpoint, VPCStructure


class SVGRenderer:
    """Renders infrastructure diagrams as SVG."""

    def __init__(self, icon_mapper: IconMapper, config: Optional[LayoutConfig] = None):
        self.icon_mapper = icon_mapper
        self.config = config or LayoutConfig()

    def render_svg(
        self,
        services: List[LogicalService],
        positions: Dict[str, Position],
        connections: List[LogicalConnection],
        groups: List[ServiceGroup],
        vpc_structure: Optional["VPCStructure"] = None,
        actual_height: Optional[int] = None,
    ) -> str:
        """Generate SVG content for the diagram."""
        svg_parts = []

        # Use actual height if provided (from layout engine), otherwise use config
        canvas_height = actual_height if actual_height else self.config.canvas_height

        # SVG header with responsive viewBox
        # width="100%" allows SVG to scale to container, preserveAspectRatio maintains proportions
        svg_parts.append(
            f"""<svg id="diagram-svg" xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            viewBox="0 0 {self.config.canvas_width} {canvas_height}"
            width="100%" preserveAspectRatio="xMidYMin meet"
            style="max-width: {self.config.canvas_width}px;">"""
        )

        # Defs for arrows and filters
        svg_parts.append(self._render_defs())

        # Background
        svg_parts.append("""<rect width="100%" height="100%" fill="#f8f9fa"/>""")

        # Render groups (AWS Cloud, VPC, AZ)
        for group in groups:
            svg_parts.append(self._render_group(group))

        # Build mapping from AWS subnet IDs to resource IDs for state-based lookups
        aws_id_to_resource_id: Dict[str, str] = {}
        if vpc_structure:
            for az in vpc_structure.availability_zones:
                for subnet in az.subnets:
                    if subnet.aws_id:
                        aws_id_to_resource_id[subnet.aws_id] = subnet.resource_id

        # Render subnets layer (below connections)
        if vpc_structure:
            svg_parts.append('<g id="subnets-layer">')
            for az in vpc_structure.availability_zones:
                for subnet in az.subnets:
                    if subnet.resource_id in positions:
                        svg_parts.append(
                            self._render_subnet(
                                subnet.resource_id, positions[subnet.resource_id], subnet
                            )
                        )
            svg_parts.append("</g>")

        # Build service_type_map for connection rendering
        service_type_map: Dict[str, str] = {}
        for service in services:
            service_type_map[service.id] = service.service_type

        # Connections container - render individual connections
        svg_parts.append('<g id="connections-layer">')
        for connection in connections:
            source_pos = positions.get(connection.source_id)
            target_pos = positions.get(connection.target_id)
            if source_pos and target_pos:
                svg_parts.append(
                    self._render_connection(
                        source_pos, target_pos, connection, service_type_map
                    )
                )
        svg_parts.append("</g>")

        # Render VPC endpoints layer
        if vpc_structure:
            svg_parts.append('<g id="endpoints-layer">')
            for endpoint in vpc_structure.endpoints:
                if endpoint.resource_id in positions:
                    svg_parts.append(
                        self._render_vpc_endpoint(
                            endpoint.resource_id, positions[endpoint.resource_id], endpoint
                        )
                    )
            svg_parts.append("</g>")

        # Services layer
        svg_parts.append('<g id="services-layer">')
        for service in services:
            if service.id in positions:
                svg_parts.append(
                    self._render_service(
                        service,
                        positions[service.id],
                        aws_id_to_resource_id,
                        positions,
                        vpc_structure,
                    )
                )
        svg_parts.append("</g>")

        svg_parts.append("</svg>")

        return "\n".join(svg_parts)

    def _render_defs(self) -> str:
        """Render SVG definitions (markers, filters)."""
        return """
        <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7"
                refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#999"/>
            </marker>
            <marker id="arrowhead-data" markerWidth="10" markerHeight="7"
                refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#3B48CC"/>
            </marker>
            <marker id="arrowhead-trigger" markerWidth="10" markerHeight="7"
                refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#E7157B"/>
            </marker>
            <marker id="arrowhead-network" markerWidth="10" markerHeight="7"
                refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#0d7c3f"/>
            </marker>
            <marker id="arrowhead-security" markerWidth="10" markerHeight="7"
                refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#d97706"/>
            </marker>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.15"/>
            </filter>
        </defs>
        """

    def _render_group(self, group: ServiceGroup) -> str:
        """Render a group container (AWS Cloud, VPC, AZ)."""
        if not group.position:
            return ""

        pos = group.position

        # Handle AZ groups with special rendering
        if group.group_type == "az":
            return self._render_az(group)

        colors = {
            "aws_cloud": ("#232f3e", "#ffffff", "#232f3e"),
            "vpc": ("#8c4fff", "#faf8ff", "#8c4fff"),
        }

        border_color, bg_color, text_color = colors.get(group.group_type, ("#666", "#fff", "#666"))

        return f"""
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
        """

    def _render_az(self, group: ServiceGroup) -> str:
        """Render an Availability Zone container with dashed border."""
        if not group.position:
            return ""

        pos = group.position
        border_color = "#ff9900"  # AWS orange for AZ
        bg_color = "#fff8f0"  # Light orange background
        text_color = "#ff9900"

        return f"""
        <g class="group group-az" data-group-type="az">
            <rect class="az-bg" x="{pos.x}" y="{pos.y}" width="{pos.width}" height="{pos.height}"
                fill="{bg_color}" stroke="{border_color}" stroke-width="1.5"
                stroke-dasharray="5,3" rx="8" ry="8"/>
            <text x="{pos.x + 10}" y="{pos.y + 18}"
                font-family="Arial, sans-serif" font-size="12" font-weight="bold"
                fill="{text_color}">{html.escape(group.name)}</text>
        </g>
        """

    def _render_subnet(self, subnet_id: str, pos: Position, subnet_info: "Subnet") -> str:
        """Render a colored subnet box.

        Colors:
        - public: green
        - private: blue
        - database: yellow/gold
        - unknown: gray
        """
        colors = {
            "public": ("#22a06b", "#e3fcef"),  # Green
            "private": ("#0052cc", "#deebff"),  # Blue
            "database": ("#ff991f", "#fffae6"),  # Yellow/Gold
            "unknown": ("#6b778c", "#f4f5f7"),  # Gray
        }

        border_color, bg_color = colors.get(subnet_info.subnet_type, colors["unknown"])

        rt_label = ""
        if subnet_info.route_table_name:
            rt_label = f"""
            <text x="{pos.x + pos.width - 8}" y="{pos.y + pos.height/2 + 16}"
                font-family="Arial, sans-serif" font-size="9" fill="#999"
                text-anchor="end" opacity="0.6">
                RT: {html.escape(subnet_info.route_table_name)}
            </text>"""

        return f"""
        <g class="subnet subnet-{subnet_info.subnet_type}" data-subnet-id="{html.escape(subnet_id)}"
            data-min-x="{pos.x}" data-min-y="{pos.y}"
            data-max-x="{pos.x + pos.width}" data-max-y="{pos.y + pos.height}">
            <rect x="{pos.x}" y="{pos.y}" width="{pos.width}" height="{pos.height}"
                fill="{bg_color}" stroke="{border_color}" stroke-width="1.5" rx="4" ry="4"/>
            <text x="{pos.x + 8}" y="{pos.y + pos.height/2 + 4}"
                font-family="Arial, sans-serif" font-size="11" fill="{border_color}">
                {html.escape(subnet_info.name)}
            </text>
            <text x="{pos.x + pos.width - 8}" y="{pos.y + pos.height/2 + 4}"
                font-family="Arial, sans-serif" font-size="10" fill="{border_color}"
                text-anchor="end" opacity="0.7">
                {html.escape(subnet_info.cidr_block) if subnet_info.cidr_block else subnet_info.subnet_type}
            </text>{rt_label}
        </g>
        """

    def _render_vpc_endpoint(
        self, endpoint_id: str, pos: Position, endpoint_info: "VPCEndpoint"
    ) -> str:
        """Render a VPC endpoint with AWS icon and service name.

        Colors:
        - gateway: green (S3, DynamoDB)
        - interface: blue (ECR, CloudWatch, SSM, etc.)
        """
        # Colors by type
        colors = {
            "gateway": ("#22a06b", "#e3fcef"),  # Green
            "interface": ("#0052cc", "#deebff"),  # Blue
        }
        border_color, bg_color = colors.get(endpoint_info.endpoint_type, colors["interface"])

        # Extract clean service name
        service_name = endpoint_info.service
        if "." in service_name:
            service_name = service_name.split(".")[0]
        service_display = service_name.upper()

        # Type label
        type_label = "Gateway" if endpoint_info.endpoint_type == "gateway" else "Interface"

        # Box dimensions
        box_width = pos.width
        box_height = pos.height

        # Center positions
        cx = pos.x + box_width / 2

        # Try to get official AWS VPC Endpoints icon
        icon_svg = self.icon_mapper.get_icon_svg("aws_vpc_endpoint", 48)
        icon_content = None

        # Check if we got a real icon (not the fallback with "RES" text)
        if icon_svg and "Endpoints" in icon_svg:
            icon_content = self._extract_svg_content(icon_svg)

        if icon_content:
            # Use official AWS icon
            icon_size = 32
            return f"""
            <g class="vpc-endpoint endpoint-{endpoint_info.endpoint_type}" data-endpoint-id="{html.escape(endpoint_id)}">
                <rect x="{pos.x}" y="{pos.y}" width="{box_width}" height="{box_height}"
                    fill="white" stroke="#e0e0e0" stroke-width="1" rx="6" ry="6"
                    filter="url(#shadow)"/>
                <svg x="{cx - icon_size/2}" y="{pos.y + 6}" width="{icon_size}" height="{icon_size}" viewBox="0 0 48 48">
                    {icon_content}
                </svg>
                <text x="{cx}" y="{pos.y + 48}"
                    font-family="Arial, sans-serif" font-size="10" fill="#333"
                    text-anchor="middle" font-weight="bold">
                    {html.escape(service_display)}
                </text>
                <text x="{cx}" y="{pos.y + 60}"
                    font-family="Arial, sans-serif" font-size="8" fill="#666"
                    text-anchor="middle">
                    {type_label}
                </text>
                <title>{html.escape(endpoint_info.name)} ({endpoint_info.endpoint_type} endpoint for {service_name})</title>
            </g>
            """
        else:
            # Fallback: colored box with service name
            return f"""
            <g class="vpc-endpoint endpoint-{endpoint_info.endpoint_type}" data-endpoint-id="{html.escape(endpoint_id)}">
                <rect x="{pos.x}" y="{pos.y}" width="{box_width}" height="{box_height}"
                    fill="{bg_color}" stroke="{border_color}" stroke-width="1.5" rx="6" ry="6"
                    filter="url(#shadow)"/>
                <text x="{cx}" y="{pos.y + box_height/2 - 6}"
                    font-family="Arial, sans-serif" font-size="11" fill="{border_color}"
                    text-anchor="middle" font-weight="bold">
                    {html.escape(service_display)}
                </text>
                <text x="{cx}" y="{pos.y + box_height/2 + 8}"
                    font-family="Arial, sans-serif" font-size="9" fill="{border_color}"
                    text-anchor="middle" opacity="0.7">
                    {type_label}
                </text>
                <title>{html.escape(endpoint_info.name)} ({endpoint_info.endpoint_type} endpoint for {service_name})</title>
            </g>
            """

    def _render_service(
        self,
        service: LogicalService,
        pos: Position,
        aws_id_to_resource_id: Optional[Dict[str, str]] = None,
        all_positions: Optional[Dict[str, Position]] = None,
        vpc_structure: Optional["VPCStructure"] = None,
    ) -> str:
        """Render a draggable logical service with its icon."""
        icon_svg = self.icon_mapper.get_icon_svg(service.icon_resource_type, 48)
        color = self.icon_mapper.get_category_color(service.icon_resource_type)

        # Count badge
        count_badge = ""
        if service.count > 1:
            count_badge = f"""
            <circle class="count-badge" cx="{pos.width - 8}" cy="8" r="12"
                fill="{color}" stroke="white" stroke-width="2"/>
            <text class="count-text" x="{pos.width - 8}" y="12"
                font-family="Arial, sans-serif" font-size="11" fill="white"
                text-anchor="middle" font-weight="bold">{service.count}</text>
            """

        resource_count = len(service.resources)
        tooltip = f"{service.name} ({resource_count} resources)"

        # Determine if this is a VPC service
        is_vpc_service = "true" if service.is_vpc_resource else "false"

        # Determine subnet constraint directly from service.subnet_ids
        # This ensures the drag constraint matches the service's actual subnet assignment
        subnet_attr = ""
        if service.subnet_ids and vpc_structure and all_positions:
            # Map from AWS IDs to resource IDs for state-based lookups
            for subnet_id in service.subnet_ids:
                resolved_id = subnet_id
                # Handle _state_subnet: prefixed IDs (from Terraform state)
                if subnet_id.startswith("_state_subnet:") and aws_id_to_resource_id:
                    aws_id = subnet_id[len("_state_subnet:") :]
                    resolved_id = aws_id_to_resource_id.get(aws_id)

                # Find the subnet that contains this service's position
                if resolved_id and resolved_id in all_positions:
                    subnet_pos = all_positions[resolved_id]
                    # Check if service position is inside this subnet
                    if (
                        subnet_pos.x <= pos.x <= subnet_pos.x + subnet_pos.width
                        and subnet_pos.y <= pos.y <= subnet_pos.y + subnet_pos.height
                    ):
                        subnet_attr = f'data-subnet-id="{html.escape(resolved_id)}"'
                        break

        if icon_svg:
            icon_content = self._extract_svg_content(icon_svg)
            icon_viewbox = self._extract_svg_viewbox(icon_svg)

            svg = f"""
            <g class="service draggable" data-service-id="{html.escape(service.id)}"
               data-service-type="{html.escape(service.service_type)}"
               data-tooltip="{html.escape(tooltip)}" data-is-vpc="{is_vpc_service}" {subnet_attr}
               transform="translate({pos.x}, {pos.y})" style="cursor: grab;">
                <rect class="service-bg" x="-8" y="-8"
                    width="{pos.width + 16}" height="{pos.height + 36}"
                    fill="white" stroke="#e0e0e0" stroke-width="1" rx="8" ry="8"
                    filter="url(#shadow)"/>
                <svg class="service-icon" width="{pos.width}" height="{pos.height}" viewBox="{icon_viewbox}">
                    {icon_content}
                </svg>
                <text class="service-label" x="{pos.width/2}" y="{pos.height + 16}"
                    font-family="Arial, sans-serif" font-size="12" fill="#333"
                    text-anchor="middle" font-weight="500">
                    {html.escape(service.name)}
                </text>
                {count_badge}
            </g>
            """
        else:
            svg = f"""
            <g class="service draggable" data-service-id="{html.escape(service.id)}"
               data-service-type="{html.escape(service.service_type)}"
               data-tooltip="{html.escape(tooltip)}" data-is-vpc="{is_vpc_service}" {subnet_attr}
               transform="translate({pos.x}, {pos.y})" style="cursor: grab;">
                <rect class="service-bg" x="-8" y="-8"
                    width="{pos.width + 16}" height="{pos.height + 36}"
                    fill="white" stroke="#e0e0e0" stroke-width="1" rx="8" ry="8"
                    filter="url(#shadow)"/>
                <rect x="0" y="0" width="{pos.width}" height="{pos.height}"
                    fill="{color}" rx="8" ry="8"/>
                <text x="{pos.width/2}" y="{pos.height/2 + 5}"
                    font-family="Arial, sans-serif" font-size="11" fill="white"
                    text-anchor="middle">{html.escape(service.service_type[:8])}</text>
                <text class="service-label" x="{pos.width/2}" y="{pos.height + 16}"
                    font-family="Arial, sans-serif" font-size="12" fill="#333"
                    text-anchor="middle" font-weight="500">
                    {html.escape(service.name)}
                </text>
                {count_badge}
            </g>
            """

        return svg

    def _extract_svg_content(self, svg_string: str) -> str:
        """Extract the inner content of an SVG, removing outer tags."""
        svg_string = re.sub(r"<\?xml[^?]*\?>\s*", "", svg_string)
        match = re.search(r"<svg[^>]*>(.*)</svg>", svg_string, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def _extract_svg_viewbox(self, svg_string: str) -> str:
        """Extract the viewBox attribute from an SVG string."""
        match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_string)
        if match:
            return match.group(1)
        # Default to 64 64 for Architecture icons
        return "0 0 64 64"

    def _render_connection(
        self,
        source_pos: Position,
        target_pos: Position,
        connection: LogicalConnection,
        service_type_map: Optional[Dict[str, str]] = None,
    ) -> str:
        """Render a connection line between services."""
        styles = {
            "data_flow": ("#3B48CC", "", "url(#arrowhead-data)"),
            "trigger": ("#E7157B", "", "url(#arrowhead-trigger)"),
            "encrypt": ("#6c757d", "4,4", "url(#arrowhead)"),
            "network_flow": ("#0d7c3f", "", "url(#arrowhead-network)"),
            "security_rule": ("#d97706", "2,4", "url(#arrowhead-security)"),
            "default": ("#999999", "", "url(#arrowhead)"),
        }

        stroke_color, stroke_dash, marker = styles.get(
            connection.connection_type, styles["default"]
        )
        dash_attr = f'stroke-dasharray="{stroke_dash}"' if stroke_dash else ""

        # Calculate initial path
        half_size = self.config.icon_size / 2
        sx = source_pos.x + half_size
        sy = source_pos.y + half_size
        tx = target_pos.x + half_size
        ty = target_pos.y + half_size

        # Adjust to connect from edges
        if abs(ty - sy) > abs(tx - sx):
            # Mostly vertical
            if ty > sy:
                sy = source_pos.y + self.config.icon_size + 8
                ty = target_pos.y - 8
            else:
                sy = source_pos.y - 8
                ty = target_pos.y + self.config.icon_size + 8
        else:
            # Mostly horizontal
            if tx > sx:
                sx = source_pos.x + self.config.icon_size + 8
                tx = target_pos.x - 8
            else:
                sx = source_pos.x - 8
                tx = target_pos.x + self.config.icon_size + 8

        # Simple quadratic curve path (better for export)
        mid_x = (sx + tx) / 2
        mid_y = (sy + ty) / 2
        path = f"M {sx} {sy} Q {mid_x} {sy}, {mid_x} {mid_y} T {tx} {ty}"

        label = connection.label or ""
        source_type = ""
        target_type = ""
        if service_type_map:
            source_type = service_type_map.get(connection.source_id, "")
            target_type = service_type_map.get(connection.target_id, "")
        return f"""
        <g class="connection" data-source="{html.escape(connection.source_id)}"
           data-target="{html.escape(connection.target_id)}"
           data-source-type="{html.escape(source_type)}"
           data-target-type="{html.escape(target_type)}"
           data-conn-type="{connection.connection_type}"
           data-label="{html.escape(label)}">
            <path class="connection-hitarea" d="{path}" fill="none" stroke="transparent" stroke-width="15"/>
            <path class="connection-path" d="{path}" fill="none" stroke="{stroke_color}"
                stroke-width="1.5" {dash_attr} marker-end="{marker}" opacity="0.7"/>
        </g>
        """


class HTMLRenderer:
    """Wraps SVG in interactive HTML with drag-and-drop and export."""

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Infrastructure Diagram</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #2d2d2d;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1500px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 20px 25px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            color: #232f3e;
        }}
        .header .subtitle {{
            margin: 4px 0 0 0;
            font-size: 14px;
            color: #666;
        }}
        .header-right {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        .stats {{
            display: flex;
            gap: 30px;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
            color: #8c4fff;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .export-buttons {{
            display: flex;
            gap: 10px;
        }}
        .export-btn {{
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .export-btn-primary {{
            background: #8c4fff;
            color: white;
        }}
        .export-btn-primary:hover {{
            background: #7a3de8;
        }}
        .export-btn-secondary {{
            background: #e9ecef;
            color: #333;
        }}
        .export-btn-secondary:hover {{
            background: #dee2e6;
        }}
        .diagram-container {{
            background: #f8f9fa;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
        }}
        .toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .toolbar-info {{
            font-size: 13px;
            color: #666;
        }}
        .toolbar-actions {{
            display: flex;
            gap: 10px;
        }}
        .toolbar-btn {{
            padding: 6px 12px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .toolbar-btn:hover {{
            background: #f0f0f0;
            border-color: #ccc;
        }}
        .diagram-wrapper {{
            padding: 10px;
            overflow: visible;
        }}
        .diagram-wrapper svg {{
            display: block;
            margin: 0 auto;
            width: 100%;
            height: auto;
            max-height: none;
        }}
        @media (max-width: 1200px) {{
            .header {{
                flex-direction: column;
                gap: 15px;
            }}
            .header-right {{
                flex-direction: column;
                width: 100%;
            }}
            .stats {{
                justify-content: center;
            }}
            .export-buttons {{
                justify-content: center;
            }}
        }}
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            .header h1 {{
                font-size: 18px;
            }}
            .stats {{
                gap: 15px;
            }}
            .stat-value {{
                font-size: 20px;
            }}
            .legend-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .service.dragging {{
            opacity: 0.8;
            cursor: grabbing !important;
        }}
        .service:hover .service-bg {{
            stroke: #8c4fff;
            stroke-width: 2;
        }}
        /* Highlighting states */
        .service.highlighted .service-bg {{
            stroke: #8c4fff;
            stroke-width: 3;
            filter: url(#shadow) drop-shadow(0 0 8px rgba(140, 79, 255, 0.5));
        }}
        .service.dimmed {{
            opacity: 0.3;
        }}
        .connection.highlighted .connection-path {{
            stroke-width: 3 !important;
            opacity: 1 !important;
        }}
        .connection.dimmed {{
            opacity: 0.1 !important;
        }}
        .connection {{
            cursor: pointer;
        }}
        .connection:hover .connection-path {{
            stroke-width: 3;
            opacity: 1;
        }}
        .connection-hitarea {{
            stroke: transparent;
            stroke-width: 15;
            fill: none;
            cursor: pointer;
        }}
        /* Spoke connection styles */
        .spoke-connection {{
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .spoke-connection:hover .spoke-path {{
            stroke-width: 4 !important;
            opacity: 1 !important;
        }}
        .spoke-connection.highlighted .spoke-path {{
            stroke-width: 4 !important;
            opacity: 1 !important;
        }}
        .spoke-connection.dimmed {{
            opacity: 0.15 !important;
        }}
        .spoke-hitarea {{
            stroke: transparent;
            stroke-width: 20;
            fill: none;
            cursor: pointer;
        }}
        /* Spoke rays - subtle lines from edge point to service icons */
        .spoke-ray {{
            stroke: #bbb;
            stroke-width: 1;
            opacity: 0.3;
            transition: opacity 0.2s, stroke 0.2s;
        }}
        .spoke-rays.highlighted .spoke-ray {{
            opacity: 0.6;
            stroke: #888;
        }}
        .spoke-ray.highlighted {{
            opacity: 0.8 !important;
            stroke: #666 !important;
            stroke-width: 1.5 !important;
        }}
        .spoke-ray.dimmed {{
            opacity: 0.1 !important;
        }}
        .legend {{
            margin-top: 20px;
            padding: 20px 25px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .legend h3 {{
            margin: 0 0 15px 0;
            font-size: 16px;
            color: #232f3e;
        }}
        .legend-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .legend-section h4 {{
            margin: 0 0 10px 0;
            font-size: 13px;
            color: #666;
            text-transform: uppercase;
        }}
        .legend-items {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
        }}
        .legend-line {{
            width: 36px;
            height: 14px;
            flex-shrink: 0;
        }}
        .legend-line svg {{
            display: block;
        }}
        .legend-box {{
            width: 24px;
            height: 16px;
            border-radius: 3px;
            border: 1.5px solid;
        }}
        .legend-circle {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
        }}
        .tooltip {{
            position: fixed;
            padding: 10px 14px;
            background: #232f3e;
            color: white;
            border-radius: 6px;
            font-size: 13px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .export-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 2000;
            justify-content: center;
            align-items: center;
        }}
        .export-modal.active {{
            display: flex;
        }}
        .export-modal-content {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            max-width: 400px;
        }}
        .export-modal h3 {{
            margin: 0 0 20px 0;
        }}
        .export-preview {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .export-modal-actions {{
            display: flex;
            gap: 10px;
            justify-content: center;
        }}
        .highlight-info {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 20px;
            background: #232f3e;
            color: white;
            border-radius: 10px;
            font-size: 14px;
            line-height: 1.6;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 1000;
            display: none;
            max-width: 280px;
        }}
        .highlight-info strong {{
            color: #8c4fff;
        }}
        .highlight-info small {{
            color: #999;
            display: block;
            margin-top: 8px;
            font-size: 11px;
        }}
        /* ============ AGGREGATION UI ============ */
        .aggregation-panel {{
            margin-top: 15px;
            padding: 15px 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .aggregation-panel-label {{
            font-size: 13px;
            font-weight: 600;
            color: #232f3e;
            margin-right: 5px;
        }}
        .aggregation-chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            user-select: none;
            border: 2px solid;
        }}
        .aggregation-chip.active {{
            color: white;
        }}
        .aggregation-chip.inactive {{
            background: transparent;
        }}
        .aggregation-chip:hover {{
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .aggregation-chip .chip-check {{
            font-size: 11px;
        }}
        /* Aggregate node styles */
        .aggregate-node .service-bg {{
            stroke-dasharray: 6,3 !important;
            stroke-width: 2 !important;
        }}
        .aggregate-node {{
            cursor: pointer;
        }}
        .aggregate-badge {{
            pointer-events: none;
        }}
        /* Aggregate connection styles */
        .aggregate-connection .connection-path {{
            opacity: 0.6;
        }}
        .aggregate-connection .multiplicity-label {{
            font-family: Arial, sans-serif;
            font-size: 10px;
            font-weight: bold;
            fill: #666;
        }}
        /* Popover styles */
        .aggregate-popover {{
            position: fixed;
            background: white;
            border-radius: 10px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            z-index: 1500;
            max-height: 300px;
            overflow-y: auto;
            min-width: 220px;
            padding: 8px 0;
        }}
        .aggregate-popover-header {{
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
            color: #666;
            border-bottom: 1px solid #eee;
            text-transform: uppercase;
        }}
        .aggregate-popover-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 13px;
            color: #333;
            transition: background 0.15s;
        }}
        .aggregate-popover-item:hover {{
            background: #f5f5f5;
        }}
        .aggregate-popover-item.selected {{
            background: #ede7f6;
            color: #6200ea;
            font-weight: 500;
        }}
        .aggregate-popover-item svg {{
            width: 24px;
            height: 24px;
            flex-shrink: 0;
        }}
        /* Transition animations for aggregation */
        .service.agg-hidden {{
            display: none !important;
        }}
        .connection.agg-hidden {{
            display: none !important;
        }}
        .connection.conn-type-hidden {{
            display: none !important;
        }}
        /* ============ CONNECTION TYPE FILTER UI ============ */
        .conn-filter-panel {{
            margin-top: 15px;
            padding: 15px 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .conn-filter-panel-label {{
            font-size: 13px;
            font-weight: 600;
            color: #232f3e;
            margin-right: 5px;
        }}
        .conn-filter-chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            user-select: none;
            border: 2px solid;
        }}
        .conn-filter-chip.active {{
            color: white;
        }}
        .conn-filter-chip.inactive {{
            background: transparent;
        }}
        .conn-filter-chip:hover {{
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .conn-filter-chip .chip-check {{
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>AWS Infrastructure Diagram</h1>
                <p class="subtitle">Environment: {environment} | Drag icons to reposition</p>
            </div>
            <div class="header-right">
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{service_count}</div>
                        <div class="stat-label">Services</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{resource_count}</div>
                        <div class="stat-label">Resources</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{connection_count}</div>
                        <div class="stat-label">Connections</div>
                    </div>
                </div>
                <div class="export-buttons">
                    <button class="export-btn export-btn-secondary" onclick="exportAs('png')">Export PNG</button>
                    <button class="export-btn export-btn-primary" onclick="exportAs('jpg')">Export JPG</button>
                </div>
            </div>
        </div>
        <div class="diagram-container">
            <div class="toolbar">
                <div class="toolbar-info">Click and drag services to reposition. Connections update automatically.</div>
                <div class="toolbar-actions">
                    <button class="toolbar-btn" onclick="resetPositions()">Reset Layout</button>
                    <button class="toolbar-btn" onclick="savePositions()">Save Layout</button>
                    <button class="toolbar-btn" onclick="loadPositions()">Load Layout</button>
                </div>
            </div>
            <div class="diagram-wrapper" id="diagram-wrapper">
                {svg_content}
            </div>
        </div>
        <div class="aggregation-panel" id="aggregation-panel" style="display:none;">
            <span class="aggregation-panel-label">Aggregation:</span>
            <div id="aggregation-chips" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
        </div>
        <div class="conn-filter-panel" id="conn-filter-panel">
            <span class="conn-filter-panel-label">Connections:</span>
            <div id="conn-filter-chips" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
        </div>
        <div class="legend">
            <h3>Legend</h3>
            <div class="legend-grid">
                <div class="legend-section">
                    <h4>Connection Types</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <div class="legend-line"><svg width="36" height="14" xmlns="http://www.w3.org/2000/svg"><defs><marker id="lm-data" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#3B48CC"/></marker></defs><line x1="0" y1="7" x2="28" y2="7" stroke="#3B48CC" stroke-width="2" marker-end="url(#lm-data)"/></svg></div>
                            <span>Data Flow</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line"><svg width="36" height="14" xmlns="http://www.w3.org/2000/svg"><defs><marker id="lm-trigger" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#E7157B"/></marker></defs><line x1="0" y1="7" x2="28" y2="7" stroke="#E7157B" stroke-width="2" marker-end="url(#lm-trigger)"/></svg></div>
                            <span>Event Trigger</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line"><svg width="36" height="14" xmlns="http://www.w3.org/2000/svg"><defs><marker id="lm-encrypt" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#6c757d"/></marker></defs><line x1="0" y1="7" x2="28" y2="7" stroke="#6c757d" stroke-width="2" stroke-dasharray="4,3" marker-end="url(#lm-encrypt)"/></svg></div>
                            <span>Encryption</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line"><svg width="36" height="14" xmlns="http://www.w3.org/2000/svg"><defs><marker id="lm-ref" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#999"/></marker></defs><line x1="0" y1="7" x2="28" y2="7" stroke="#999" stroke-width="2" marker-end="url(#lm-ref)"/></svg></div>
                            <span>Reference</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line"><svg width="36" height="14" xmlns="http://www.w3.org/2000/svg"><defs><marker id="lm-network" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#0d7c3f"/></marker></defs><line x1="0" y1="7" x2="28" y2="7" stroke="#0d7c3f" stroke-width="2" marker-end="url(#lm-network)"/></svg></div>
                            <span>Network Flow</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-line"><svg width="36" height="14" xmlns="http://www.w3.org/2000/svg"><defs><marker id="lm-security" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#d97706"/></marker></defs><line x1="0" y1="7" x2="28" y2="7" stroke="#d97706" stroke-width="2" stroke-dasharray="2,4" marker-end="url(#lm-security)"/></svg></div>
                            <span>Security Rule</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4>Subnet Types</h4>
                    <div class="legend-items">
                        <div class="legend-item">
                            <div class="legend-box" style="background: #e3fcef; border-color: #22a06b;"></div>
                            <span>Public Subnet</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-box" style="background: #deebff; border-color: #0052cc;"></div>
                            <span>Private Subnet</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-box" style="background: #fffae6; border-color: #ff991f;"></div>
                            <span>Database Subnet</span>
                        </div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4>VPC Endpoints</h4>
                    <div class="legend-items">
                        <div class="legend-item"><span><strong>Gateway</strong> &mdash; S3, DynamoDB</span></div>
                        <div class="legend-item"><span><strong>Interface</strong> &mdash; ECR, Logs, etc.</span></div>
                    </div>
                </div>
                <div class="legend-section">
                    <h4>Interactions</h4>
                    <div class="legend-items">
                        <div class="legend-item">Click service to highlight connections</div>
                        <div class="legend-item">Click connection to highlight endpoints</div>
                        <div class="legend-item">Drag icons to reposition</div>
                        <div class="legend-item">Toggle connection types and aggregation</div>
                        <div class="legend-item">Save/Load to persist layout</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="tooltip" id="tooltip"></div>
    <div class="highlight-info" id="highlight-info"></div>
    <div class="export-modal" id="export-modal">
        <div class="export-modal-content">
            <h3>Export Diagram</h3>
            <canvas id="export-canvas" style="display:none;"></canvas>
            <img id="export-preview" class="export-preview" alt="Preview"/>
            <div class="export-modal-actions">
                <button class="export-btn export-btn-secondary" onclick="closeExportModal()">Cancel</button>
                <a id="export-download" class="export-btn export-btn-primary" download="diagram.png">Download</a>
            </div>
        </div>
    </div>

    <script>
        // Aggregation configuration (injected by Python)
        const AGGREGATION_CONFIG = {aggregation_config_json};
    </script>
    <script>
        // Service positions storage
        const servicePositions = {{}};
        const iconSize = {icon_size};
        let originalPositions = {{}};

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            initDragAndDrop();
            initTooltips();
            initHighlighting();
            updateAllConnections();
            saveOriginalPositions();
            initAggregation();
            initConnectionTypeFilter();
        }});

        function saveOriginalPositions() {{
            document.querySelectorAll('.service').forEach(el => {{
                const id = el.dataset.serviceId;
                const transform = el.getAttribute('transform');
                const match = transform.match(/translate\\(([^,]+),\\s*([^)]+)\\)/);
                if (match) {{
                    originalPositions[id] = {{ x: parseFloat(match[1]), y: parseFloat(match[2]) }};
                    servicePositions[id] = {{ ...originalPositions[id] }};
                }}
            }});
        }}

        function initDragAndDrop() {{
            const svg = document.getElementById('diagram-svg');
            let dragging = null;
            let offset = {{ x: 0, y: 0 }};

            // Use event delegation on SVG for mousedown to handle dynamically created nodes
            svg.addEventListener('mousedown', (e) => {{
                const target = e.target.closest('.service.draggable');
                if (target) startDrag(e, target);
            }});
            svg.addEventListener('mousemove', drag);
            svg.addEventListener('mouseup', endDrag);
            svg.addEventListener('mouseleave', endDrag);

            function startDrag(e, targetEl) {{
                e.preventDefault();

                // Guard against null CTM (can happen during rendering)
                const ctm = svg.getScreenCTM();
                if (!ctm) return;

                dragging = targetEl;
                dragging.classList.add('dragging');
                dragging.style.cursor = 'grabbing';

                const pt = svg.createSVGPoint();
                pt.x = e.clientX;
                pt.y = e.clientY;
                const svgP = pt.matrixTransform(ctm.inverse());

                // Validate coordinates to prevent NaN issues
                if (isNaN(svgP.x) || isNaN(svgP.y)) {{
                    dragging.classList.remove('dragging');
                    dragging.style.cursor = 'grab';
                    dragging = null;
                    return;
                }}

                const id = dragging.dataset.serviceId;
                const pos = servicePositions[id] || {{ x: 0, y: 0 }};
                offset.x = svgP.x - pos.x;
                offset.y = svgP.y - pos.y;

                // Hide tooltip while dragging
                document.getElementById('tooltip').style.display = 'none';
            }}

            function drag(e) {{
                if (!dragging) return;

                // Guard against null CTM
                const ctm = svg.getScreenCTM();
                if (!ctm) return;

                const pt = svg.createSVGPoint();
                pt.x = e.clientX;
                pt.y = e.clientY;
                const svgP = pt.matrixTransform(ctm.inverse());

                // Validate coordinates to prevent NaN issues
                if (isNaN(svgP.x) || isNaN(svgP.y)) return;

                let newX = svgP.x - offset.x;
                let newY = svgP.y - offset.y;

                // Check if service belongs to a specific subnet
                const subnetId = dragging.dataset.subnetId;
                if (subnetId) {{
                    // Constrain to subnet bounds
                    const subnetGroup = document.querySelector(`.subnet[data-subnet-id="${{subnetId}}"]`);
                    if (subnetGroup) {{
                        const padding = 10;
                        const minX = parseFloat(subnetGroup.dataset.minX) + padding;
                        const minY = parseFloat(subnetGroup.dataset.minY) + padding;
                        const maxX = parseFloat(subnetGroup.dataset.maxX) - iconSize - padding;
                        const maxY = parseFloat(subnetGroup.dataset.maxY) - iconSize - padding;

                        newX = Math.max(minX, Math.min(maxX, newX));
                        newY = Math.max(minY, Math.min(maxY, newY));
                    }}
                }} else if (dragging.dataset.isVpc === 'true') {{
                    // Constrain to VPC bounds
                    const vpcGroup = document.querySelector('.group-vpc .group-bg');
                    if (vpcGroup) {{
                        const minX = parseFloat(vpcGroup.dataset.minX) + 20;
                        const minY = parseFloat(vpcGroup.dataset.minY) + 40;
                        const maxX = parseFloat(vpcGroup.dataset.maxX) - iconSize - 20;
                        const maxY = parseFloat(vpcGroup.dataset.maxY) - iconSize - 40;

                        newX = Math.max(minX, Math.min(maxX, newX));
                        newY = Math.max(minY, Math.min(maxY, newY));

                        // VPC services without subnet assignment cannot enter subnet areas
                        if (!dragging.dataset.subnetId) {{
                            document.querySelectorAll('.subnet').forEach(sub => {{
                                const sMinX = parseFloat(sub.dataset.minX);
                                const sMinY = parseFloat(sub.dataset.minY);
                                const sMaxX = parseFloat(sub.dataset.maxX);
                                const sMaxY = parseFloat(sub.dataset.maxY);
                                const nodeR = newX + iconSize;
                                const nodeB = newY + iconSize;
                                if (nodeR > sMinX && newX < sMaxX && nodeB > sMinY && newY < sMaxY) {{
                                    const dL = Math.abs(nodeR - sMinX);
                                    const dR = Math.abs(newX - sMaxX);
                                    const dT = Math.abs(nodeB - sMinY);
                                    const dB = Math.abs(newY - sMaxY);
                                    const m = Math.min(dL, dR, dT, dB);
                                    if (m === dT) newY = sMinY - iconSize;
                                    else if (m === dB) newY = sMaxY;
                                    else if (m === dL) newX = sMinX - iconSize;
                                    else newX = sMaxX;
                                }}
                            }});
                        }}
                    }}
                }} else {{
                    // AWS Cloud bounds - expandable downward
                    const cloudGroup = document.querySelector('.group-aws_cloud .group-bg');
                    if (cloudGroup) {{
                        const minX = parseFloat(cloudGroup.dataset.minX) + 20;
                        const minY = parseFloat(cloudGroup.dataset.minY) + 40;
                        const maxX = parseFloat(cloudGroup.dataset.maxX) - iconSize - 20;
                        const currentMaxY = parseFloat(cloudGroup.dataset.maxY);

                        // Constrain X and minY, but allow expansion downward
                        newX = Math.max(minX, Math.min(maxX, newX));
                        newY = Math.max(minY, newY);

                        // Prevent global services from entering the VPC area
                        const vpcBg = document.querySelector('.group-vpc .group-bg');
                        if (vpcBg) {{
                            const vpcMinX = parseFloat(vpcBg.dataset.minX);
                            const vpcMinY = parseFloat(vpcBg.dataset.minY);
                            const vpcMaxX = parseFloat(vpcBg.dataset.maxX);
                            const vpcMaxY = parseFloat(vpcBg.dataset.maxY);
                            const nodeRight = newX + iconSize;
                            const nodeBottom = newY + iconSize;

                            // Check if node overlaps VPC box
                            if (nodeRight > vpcMinX && newX < vpcMaxX &&
                                nodeBottom > vpcMinY && newY < vpcMaxY) {{
                                // Push to nearest edge outside VPC
                                const distLeft = Math.abs(nodeRight - vpcMinX);
                                const distRight = Math.abs(newX - vpcMaxX);
                                const distTop = Math.abs(nodeBottom - vpcMinY);
                                const distBottom = Math.abs(newY - vpcMaxY);
                                const minDist = Math.min(distLeft, distRight, distTop, distBottom);

                                if (minDist === distTop) newY = vpcMinY - iconSize;
                                else if (minDist === distBottom) newY = vpcMaxY;
                                else if (minDist === distLeft) newX = vpcMinX - iconSize;
                                else newX = vpcMaxX;
                            }}
                        }}

                        // Expand AWS Cloud box and canvas if dragging below current bounds
                        const requiredBottom = newY + iconSize + 40;
                        if (requiredBottom > currentMaxY) {{
                            expandCanvas(requiredBottom);
                        }}
                    }}
                }}

                const id = dragging.dataset.serviceId;
                servicePositions[id] = {{ x: newX, y: newY }};

                dragging.setAttribute('transform', `translate(${{newX}}, ${{newY}})`);
                updateConnectionsFor(id);
            }}

            function endDrag() {{
                if (dragging) {{
                    dragging.classList.remove('dragging');
                    dragging.style.cursor = 'grab';
                    dragging = null;
                }}
            }}
        }}

        function expandCanvas(newBottom) {{
            const svg = document.getElementById('diagram-svg');
            const cloudGroup = document.querySelector('.group-aws_cloud .group-bg');

            if (!cloudGroup || !svg) return;

            // Get current viewBox
            const viewBox = svg.getAttribute('viewBox').split(' ').map(Number);
            const currentHeight = viewBox[3];

            // Small margin below content (matching layout.py)
            const bottomMargin = 20;
            const padding = {icon_size} > 64 ? 45 : 30;  // Approximate padding based on scale
            const newHeight = Math.max(currentHeight, newBottom + bottomMargin);

            // Only expand if needed
            if (newHeight <= currentHeight) return;

            // Update SVG viewBox - this automatically resizes the container
            svg.setAttribute('viewBox', `${{viewBox[0]}} ${{viewBox[1]}} ${{viewBox[2]}} ${{newHeight}}`);

            // Expand AWS Cloud box to fill the entire canvas (minus margin)
            const minY = parseFloat(cloudGroup.dataset.minY);
            const newMaxY = newHeight - bottomMargin;

            cloudGroup.dataset.maxY = newMaxY;

            // Update the AWS Cloud rect to fill the space
            const awsRect = document.querySelector('.group-aws_cloud rect');
            if (awsRect) {{
                awsRect.setAttribute('height', newMaxY - minY);
            }}
        }}

        var _baseUpdateConnectionsFor = function(serviceId) {{
            document.querySelectorAll('.connection').forEach(conn => {{
                if (conn.dataset.source === serviceId || conn.dataset.target === serviceId) {{
                    updateConnection(conn);
                }}
            }});
        }};
        var updateConnectionsFor = _baseUpdateConnectionsFor;

        function updateAllConnections() {{
            document.querySelectorAll('.connection').forEach(updateConnection);
        }}

        function updateConnection(connEl) {{
            const sourceId = connEl.dataset.source;
            const targetId = connEl.dataset.target;

            const sourcePos = servicePositions[sourceId];
            const targetPos = servicePositions[targetId];

            if (!sourcePos || !targetPos) return;

            // Calculate center points
            const halfSize = iconSize / 2;
            let sx = sourcePos.x + halfSize;
            let sy = sourcePos.y + halfSize;
            let tx = targetPos.x + halfSize;
            let ty = targetPos.y + halfSize;

            // Adjust to connect from edges
            if (Math.abs(ty - sy) > Math.abs(tx - sx)) {{
                // Mostly vertical
                if (ty > sy) {{
                    sy = sourcePos.y + iconSize + 8;
                    ty = targetPos.y - 8;
                }} else {{
                    sy = sourcePos.y - 8;
                    ty = targetPos.y + iconSize + 8;
                }}
            }} else {{
                // Mostly horizontal
                if (tx > sx) {{
                    sx = sourcePos.x + iconSize + 8;
                    tx = targetPos.x - 8;
                }} else {{
                    sx = sourcePos.x - 8;
                    tx = targetPos.x + iconSize + 8;
                }}
            }}

            // Quadratic curve path (matches server-side rendering)
            const midX = (sx + tx) / 2;
            const midY = (sy + ty) / 2;
            const path = `M ${{sx}} ${{sy}} Q ${{midX}} ${{sy}}, ${{midX}} ${{midY}} T ${{tx}} ${{ty}}`;

            const pathEl = connEl.querySelector('.connection-path');
            const hitareaEl = connEl.querySelector('.connection-hitarea');
            if (pathEl) {{
                pathEl.setAttribute('d', path);
            }}
            if (hitareaEl) {{
                hitareaEl.setAttribute('d', path);
            }}

            // Update multiplicity label position if present
            const multLabel = connEl.querySelector('.multiplicity-label');
            if (multLabel) {{
                const labelMidX = (sourcePos.x + targetPos.x) / 2 + halfSize;
                const labelMidY = (sourcePos.y + targetPos.y) / 2 + halfSize;
                multLabel.setAttribute('x', `${{labelMidX + 8}}`);
                multLabel.setAttribute('y', `${{labelMidY - 5}}`);
            }}
        }}

        // ============ HIGHLIGHTING SYSTEM ============
        let currentHighlight = null;

        function initHighlighting() {{
            const svg = document.getElementById('diagram-svg');

            // Use event delegation on SVG for dynamic element support
            svg.addEventListener('click', (e) => {{
                // Check if clicked on a service
                const serviceEl = e.target.closest('.service');
                if (serviceEl) {{
                    if (serviceEl.classList.contains('dragging')) return;
                    // Don't interfere with aggregate node popover (handled separately)
                    if (serviceEl.classList.contains('aggregate-node')) return;
                    e.stopPropagation();

                    const serviceId = serviceEl.dataset.serviceId;
                    if (currentHighlight === serviceId) {{
                        clearHighlights();
                    }} else {{
                        highlightService(serviceId);
                    }}
                    return;
                }}

                // Check if clicked on a connection
                const connEl = e.target.closest('.connection');
                if (connEl) {{
                    e.stopPropagation();
                    const sourceId = connEl.dataset.source;
                    const targetId = connEl.dataset.target;
                    const connKey = `conn:${{sourceId}}->${{targetId}}`;
                    if (currentHighlight === connKey) {{
                        clearHighlights();
                    }} else {{
                        highlightConnection(connEl, sourceId, targetId);
                    }}
                    return;
                }}

                // Clicked on background
                if (e.target.tagName === 'svg' || e.target.classList.contains('group-bg')) {{
                    clearHighlights();
                }}
            }});
        }}

        function highlightService(serviceId) {{
            clearHighlights();
            currentHighlight = serviceId;

            // Find all connections involving this service
            const connectedServiceIds = new Set([serviceId]);
            const connectedConnections = [];

            document.querySelectorAll('.connection:not(.conn-type-hidden)').forEach(conn => {{
                const srcId = conn.dataset.source;
                const tgtId = conn.dataset.target;

                if (srcId === serviceId || tgtId === serviceId) {{
                    connectedServiceIds.add(srcId);
                    connectedServiceIds.add(tgtId);
                    connectedConnections.push(conn);
                }}
            }});

            // Dim all services and connections
            document.querySelectorAll('.service').forEach(el => {{
                el.classList.add('dimmed');
            }});
            document.querySelectorAll('.connection').forEach(el => {{
                el.classList.add('dimmed');
            }});

            // Highlight connected services
            document.querySelectorAll('.service').forEach(el => {{
                const elId = el.dataset.serviceId;
                if (connectedServiceIds.has(elId)) {{
                    el.classList.remove('dimmed');
                    el.classList.add('highlighted');
                }}
            }});

            // Highlight connections
            connectedConnections.forEach(conn => {{
                conn.classList.remove('dimmed');
                conn.classList.add('highlighted');
            }});

            // Show info tooltip
            showHighlightInfo(serviceId, connectedServiceIds.size - 1, connectedConnections.length);
        }}

        function highlightConnection(connEl, sourceId, targetId) {{
            clearHighlights();
            currentHighlight = `conn:${{sourceId}}->${{targetId}}`;

            // Dim all
            document.querySelectorAll('.service').forEach(el => {{
                el.classList.add('dimmed');
            }});
            document.querySelectorAll('.connection').forEach(el => {{
                el.classList.add('dimmed');
            }});

            // Highlight the connection
            connEl.classList.remove('dimmed');
            connEl.classList.add('highlighted');

            // Highlight source and target services
            const sourceEl = document.querySelector(`[data-service-id="${{sourceId}}"]`);
            const targetEl = document.querySelector(`[data-service-id="${{targetId}}"]`);

            if (sourceEl) {{
                sourceEl.classList.remove('dimmed');
                sourceEl.classList.add('highlighted');
            }}
            if (targetEl) {{
                targetEl.classList.remove('dimmed');
                targetEl.classList.add('highlighted');
            }}

            // Show connection info
            const label = connEl.dataset.label || connEl.dataset.connType;
            const sourceName = sourceEl ? sourceEl.dataset.tooltip.split(' (')[0] : sourceId;
            const targetName = targetEl ? targetEl.dataset.tooltip.split(' (')[0] : targetId;
            showConnectionInfo(sourceName, targetName, label);
        }}

        function clearHighlights() {{
            currentHighlight = null;

            document.querySelectorAll('.service').forEach(el => {{
                el.classList.remove('dimmed', 'highlighted');
            }});
            document.querySelectorAll('.connection').forEach(el => {{
                el.classList.remove('dimmed', 'highlighted');
            }});

            hideHighlightInfo();
        }}

        function showHighlightInfo(serviceId, connectedCount, connectionCount) {{
            const el = document.querySelector(`[data-service-id="${{serviceId}}"]`);
            const name = el ? el.dataset.tooltip.split(' (')[0] : serviceId;

            const infoEl = document.getElementById('highlight-info');
            infoEl.innerHTML = `
                <strong>${{name}}</strong><br>
                Connected to ${{connectedCount}} service${{connectedCount !== 1 ? 's' : ''}}<br>
                ${{connectionCount}} connection${{connectionCount !== 1 ? 's' : ''}}
                <br><small>Click elsewhere to clear</small>
            `;
            infoEl.style.display = 'block';
        }}

        function showConnectionInfo(sourceName, targetName, label) {{
            const infoEl = document.getElementById('highlight-info');
            infoEl.innerHTML = `
                <strong>${{sourceName}}</strong><br>
                ↓ ${{label}}<br>
                <strong>${{targetName}}</strong>
                <br><small>Click elsewhere to clear</small>
            `;
            infoEl.style.display = 'block';
        }}

        function hideHighlightInfo() {{
            document.getElementById('highlight-info').style.display = 'none';
        }}

        function initTooltips() {{
            const tooltip = document.getElementById('tooltip');
            const svg = document.getElementById('diagram-svg');
            let tooltipTarget = null;

            // Use event delegation on SVG for tooltip support on dynamic elements
            svg.addEventListener('mouseover', (e) => {{
                const service = e.target.closest('.service');
                if (service && service !== tooltipTarget) {{
                    tooltipTarget = service;
                    if (service.classList.contains('dragging')) return;
                    const data = service.dataset.tooltip;
                    if (data) {{
                        tooltip.textContent = data;
                        tooltip.style.display = 'block';
                    }}
                }}
            }});
            svg.addEventListener('mousemove', (e) => {{
                if (tooltipTarget && !tooltipTarget.classList.contains('dragging')) {{
                    tooltip.style.left = e.clientX + 15 + 'px';
                    tooltip.style.top = e.clientY + 15 + 'px';
                }}
            }});
            svg.addEventListener('mouseout', (e) => {{
                const service = e.target.closest('.service');
                if (service && service === tooltipTarget) {{
                    // Check if we're leaving to a child element (not really leaving)
                    const related = e.relatedTarget;
                    if (related && service.contains(related)) return;
                    tooltipTarget = null;
                    tooltip.style.display = 'none';
                }}
            }});
        }}

        var resetPositions = function() {{
            Object.keys(originalPositions).forEach(id => {{
                servicePositions[id] = {{ ...originalPositions[id] }};
                const el = document.querySelector(`[data-service-id="${{id}}"]`);
                if (el) {{
                    el.setAttribute('transform', `translate(${{originalPositions[id].x}}, ${{originalPositions[id].y}})`);
                }}
            }});
            updateAllConnections();
        }};

        var savePositions = function() {{
            const data = JSON.stringify(servicePositions);
            localStorage.setItem('diagramPositions', data);
            alert('Layout saved to browser storage!');
        }};

        var loadPositions = function() {{
            const data = localStorage.getItem('diagramPositions');
            if (!data) {{
                alert('No saved layout found.');
                return;
            }}

            const saved = JSON.parse(data);
            Object.keys(saved).forEach(id => {{
                if (servicePositions[id]) {{
                    servicePositions[id] = saved[id];
                    const el = document.querySelector(`[data-service-id="${{id}}"]`);
                    if (el) {{
                        el.setAttribute('transform', `translate(${{saved[id].x}}, ${{saved[id].y}})`);
                    }}
                }}
            }});
            updateAllConnections();
            alert('Layout loaded!');
        }};

        function exportAs(format) {{
            const svg = document.getElementById('diagram-svg');
            const canvas = document.getElementById('export-canvas');
            const ctx = canvas.getContext('2d');

            const vbW = svg.viewBox.baseVal.width;
            const vbH = svg.viewBox.baseVal.height;
            const scale = 2; // Higher resolution
            canvas.width = vbW * scale;
            canvas.height = vbH * scale;

            // Clone SVG so we can modify attributes for standalone rendering
            const svgClone = svg.cloneNode(true);
            // Set explicit pixel dimensions (width="100%" won't resolve in a blob image)
            svgClone.setAttribute('width', vbW);
            svgClone.setAttribute('height', vbH);
            svgClone.removeAttribute('style');

            // Embed essential CSS inside the SVG for standalone rendering
            const styleEl = document.createElementNS('http://www.w3.org/2000/svg', 'style');
            styleEl.textContent = `
                .agg-hidden {{ display: none !important; }}
                .conn-type-hidden {{ display: none !important; }}
            `;
            svgClone.insertBefore(styleEl, svgClone.firstChild);

            // Serialize and encode as data URI (avoids canvas taint from blob URLs)
            const svgData = new XMLSerializer().serializeToString(svgClone);
            const svgBase64 = btoa(unescape(encodeURIComponent(svgData)));
            const dataUri = 'data:image/svg+xml;base64,' + svgBase64;

            const img = new Image();
            img.onload = () => {{
                ctx.fillStyle = 'white';
                ctx.fillRect(0, 0, canvas.width, canvas.height);

                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                try {{
                    const mimeType = format === 'jpg' ? 'image/jpeg' : 'image/png';
                    const quality = format === 'jpg' ? 0.95 : undefined;
                    const dataUrl = canvas.toDataURL(mimeType, quality);

                    const preview = document.getElementById('export-preview');
                    const download = document.getElementById('export-download');

                    preview.src = dataUrl;
                    download.href = dataUrl;
                    download.download = `aws-diagram.${{format}}`;

                    document.getElementById('export-modal').classList.add('active');
                }} catch (err) {{
                    alert('Export failed: ' + err.message);
                }}
            }};
            img.onerror = () => {{
                alert('Failed to render SVG for export.');
            }};
            img.src = dataUri;
        }}

        function closeExportModal() {{
            document.getElementById('export-modal').classList.remove('active');
        }}

        // Close modal on background click
        document.getElementById('export-modal').addEventListener('click', (e) => {{
            if (e.target.id === 'export-modal') {{
                closeExportModal();
            }}
        }});

        // ============ AGGREGATION SYSTEM ============
        const aggregationState = {{}};       // {{ serviceType: bool }} true=aggregated
        const originalConnections = [];      // snapshot of all original connections
        const aggregateNodes = {{}};          // {{ serviceType: SVGGElement }}
        const aggregateConnections = {{}};    // {{ serviceType: [SVGGElement...] }}
        let activePopover = null;
        let selectedPopoverResource = null;

        // Connection type filter state: {{ connType: bool }} true=visible
        const CONNECTION_TYPES = [
            {{ id: 'data_flow', label: 'Data Flow', color: '#3B48CC' }},
            {{ id: 'trigger', label: 'Event Trigger', color: '#E7157B' }},
            {{ id: 'encrypt', label: 'Encryption', color: '#6c757d' }},
            {{ id: 'network_flow', label: 'Network Flow', color: '#0d7c3f' }},
            {{ id: 'security_rule', label: 'Security Rule', color: '#d97706' }},
            {{ id: 'default', label: 'Reference', color: '#999999' }}
        ];
        const connTypeFilterState = {{}};

        function initAggregation() {{
            if (!AGGREGATION_CONFIG || !AGGREGATION_CONFIG.groups) return;

            // Check if any group qualifies for aggregation
            const qualifyingGroups = Object.entries(AGGREGATION_CONFIG.groups)
                .filter(([_, g]) => g.count >= AGGREGATION_CONFIG.threshold);
            if (qualifyingGroups.length === 0) return;

            // Snapshot all original connections from DOM
            snapshotConnections();

            // Load saved state from localStorage or use defaults
            const savedState = localStorage.getItem('diagramAggregationState');
            let loaded = null;
            if (savedState) {{
                try {{ loaded = JSON.parse(savedState); }} catch(e) {{}}
            }}

            for (const [stype, group] of Object.entries(AGGREGATION_CONFIG.groups)) {{
                if (group.count >= AGGREGATION_CONFIG.threshold) {{
                    aggregationState[stype] = loaded ? !!loaded[stype] : group.defaultAggregated;
                }}
            }}

            // Render chip panel
            renderChipPanel();

            // Apply initial aggregation (skip per-group connection recalc)
            for (const [stype, isAgg] of Object.entries(aggregationState)) {{
                if (isAgg) {{
                    aggregateGroup(stype, true);
                }}
            }}

            // Recalculate all connections once, considering all aggregated groups
            recalculateAllAggregateConnections();
        }}

        function snapshotConnections() {{
            originalConnections.length = 0;
            document.querySelectorAll('.connection').forEach(conn => {{
                originalConnections.push({{
                    element: conn,
                    sourceId: conn.dataset.source,
                    targetId: conn.dataset.target,
                    sourceType: conn.dataset.sourceType || '',
                    targetType: conn.dataset.targetType || '',
                    label: conn.dataset.label || '',
                    connType: conn.dataset.connType || 'default',
                }});
            }});
        }}

        function getServiceNodesForType(serviceType) {{
            return Array.from(document.querySelectorAll(`.service[data-service-type="${{serviceType}}"]`))
                .filter(el => !el.classList.contains('aggregate-node'));
        }}

        function computeCentroid(serviceType) {{
            const group = AGGREGATION_CONFIG.groups[serviceType];
            if (!group) return {{ x: 0, y: 0 }};
            let sumX = 0, sumY = 0, count = 0;
            for (const sid of group.serviceIds) {{
                const pos = servicePositions[sid];
                if (pos) {{
                    sumX += pos.x;
                    sumY += pos.y;
                    count++;
                }}
            }}
            if (count === 0) return {{ x: 100, y: 100 }};
            return {{ x: sumX / count, y: sumY / count }};
        }}

        function aggregateGroup(serviceType, skipConnectionRecalc) {{
            const group = AGGREGATION_CONFIG.groups[serviceType];
            if (!group) return;

            // Hide individual nodes
            for (const sid of group.serviceIds) {{
                const el = document.querySelector(`[data-service-id="${{sid}}"]`);
                if (el) el.classList.add('agg-hidden');
            }}

            // Calculate centroid
            const centroid = computeCentroid(serviceType);

            // Create aggregate node in SVG
            const svg = document.getElementById('diagram-svg');
            const servicesLayer = document.getElementById('services-layer');

            const aggG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            aggG.classList.add('service', 'draggable', 'aggregate-node');
            aggG.dataset.serviceId = `__agg_${{serviceType}}`;
            aggG.dataset.serviceType = serviceType;
            aggG.dataset.tooltip = `${{group.label}} (${{group.count}} resources - click to inspect)`;
            // Inherit VPC status from the first service in the group
            const firstNode = document.querySelector(`[data-service-id="${{group.serviceIds[0]}}"]`);
            aggG.dataset.isVpc = (firstNode && firstNode.dataset.isVpc === 'true') ? 'true' : 'false';
            aggG.setAttribute('transform', `translate(${{centroid.x}}, ${{centroid.y}})`);
            aggG.style.cursor = 'pointer';

            // Background rect (dashed border)
            const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            bgRect.classList.add('service-bg');
            bgRect.setAttribute('x', '-8');
            bgRect.setAttribute('y', '-8');
            bgRect.setAttribute('width', `${{iconSize + 16}}`);
            bgRect.setAttribute('height', `${{iconSize + 36}}`);
            bgRect.setAttribute('fill', 'white');
            bgRect.setAttribute('stroke', group.color || '#999');
            bgRect.setAttribute('stroke-width', '2');
            bgRect.setAttribute('stroke-dasharray', '6,3');
            bgRect.setAttribute('rx', '8');
            bgRect.setAttribute('ry', '8');
            bgRect.setAttribute('filter', 'url(#shadow)');
            aggG.appendChild(bgRect);

            // Icon
            if (group.iconHtml) {{
                const foreignObj = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
                foreignObj.setAttribute('x', '0');
                foreignObj.setAttribute('y', '0');
                foreignObj.setAttribute('width', `${{iconSize}}`);
                foreignObj.setAttribute('height', `${{iconSize}}`);
                const div = document.createElement('div');
                div.innerHTML = group.iconHtml;
                div.style.width = `${{iconSize}}px`;
                div.style.height = `${{iconSize}}px`;
                const innerSvg = div.querySelector('svg');
                if (innerSvg) {{
                    innerSvg.setAttribute('width', `${{iconSize}}`);
                    innerSvg.setAttribute('height', `${{iconSize}}`);
                }}
                foreignObj.appendChild(div);
                aggG.appendChild(foreignObj);
            }}

            // Label
            const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            label.classList.add('service-label');
            label.setAttribute('x', `${{iconSize / 2}}`);
            label.setAttribute('y', `${{iconSize + 16}}`);
            label.setAttribute('font-family', 'Arial, sans-serif');
            label.setAttribute('font-size', '12');
            label.setAttribute('fill', '#333');
            label.setAttribute('text-anchor', 'middle');
            label.setAttribute('font-weight', '500');
            label.textContent = `${{group.label}} (${{group.count}})`;
            aggG.appendChild(label);

            // Count badge
            const badgeCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            badgeCircle.classList.add('aggregate-badge');
            badgeCircle.setAttribute('cx', `${{iconSize + 8 - 8}}`);
            badgeCircle.setAttribute('cy', '8');
            badgeCircle.setAttribute('r', '12');
            badgeCircle.setAttribute('fill', group.color || '#ff9900');
            badgeCircle.setAttribute('stroke', 'white');
            badgeCircle.setAttribute('stroke-width', '2');
            aggG.appendChild(badgeCircle);

            const badgeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            badgeText.classList.add('aggregate-badge');
            badgeText.setAttribute('x', `${{iconSize + 8 - 8}}`);
            badgeText.setAttribute('y', '12');
            badgeText.setAttribute('font-family', 'Arial, sans-serif');
            badgeText.setAttribute('font-size', '11');
            badgeText.setAttribute('fill', 'white');
            badgeText.setAttribute('text-anchor', 'middle');
            badgeText.setAttribute('font-weight', 'bold');
            badgeText.textContent = group.count;
            aggG.appendChild(badgeText);

            servicesLayer.appendChild(aggG);
            aggregateNodes[serviceType] = aggG;

            // Register position
            servicePositions[`__agg_${{serviceType}}`] = {{ x: centroid.x, y: centroid.y }};

            // Setup drag for aggregate node
            aggG.addEventListener('mousedown', (e) => {{
                // Drag is handled by the existing drag system since we add .draggable class
                // But we also need click for popover — distinguish via a moved flag
            }});

            // Setup click for popover (using mouseup without movement)
            let aggDragStartPos = null;
            aggG.addEventListener('mousedown', (e) => {{
                aggDragStartPos = {{ x: e.clientX, y: e.clientY }};
            }});
            aggG.addEventListener('mouseup', (e) => {{
                if (aggDragStartPos) {{
                    const dx = Math.abs(e.clientX - aggDragStartPos.x);
                    const dy = Math.abs(e.clientY - aggDragStartPos.y);
                    if (dx < 5 && dy < 5) {{
                        // This was a click, not a drag — show popover
                        // Do NOT stopPropagation: SVG mouseup must fire to clear drag state
                        showAggregatePopover(serviceType, e.clientX, e.clientY);
                    }}
                }}
                aggDragStartPos = null;
            }});

            // Re-route all connections (considers all aggregated groups)
            if (!skipConnectionRecalc) {{
                recalculateAllAggregateConnections();
            }}
        }}

        function deaggregateGroup(serviceType) {{
            const group = AGGREGATION_CONFIG.groups[serviceType];
            if (!group) return;

            // Close popover if open for this group
            if (activePopover) {{
                closeAggregatePopover();
            }}

            // Show individual nodes
            for (const sid of group.serviceIds) {{
                const el = document.querySelector(`[data-service-id="${{sid}}"]`);
                if (el) el.classList.remove('agg-hidden');
            }}

            // Remove aggregate node
            if (aggregateNodes[serviceType]) {{
                aggregateNodes[serviceType].remove();
                delete aggregateNodes[serviceType];
                delete servicePositions[`__agg_${{serviceType}}`];
            }}

            // Recalculate all connections (considers remaining aggregated groups)
            recalculateAllAggregateConnections();
        }}

        // ============ CONNECTION RE-ROUTING ============
        // Single function that recalculates ALL aggregate connections
        // considering ALL currently aggregated groups at once.
        // This avoids cross-group issues where group A's aggregate connections
        // point to individual nodes of group B that are now hidden.
        function recalculateAllAggregateConnections() {{
            // 1. Remove ALL existing aggregate connections
            for (const [stype, conns] of Object.entries(aggregateConnections)) {{
                conns.forEach(c => c.remove());
            }}
            for (const k of Object.keys(aggregateConnections)) delete aggregateConnections[k];

            // 2. Reset hidden state on ALL original connections
            for (const conn of originalConnections) {{
                conn.element.classList.remove('agg-hidden');
            }}

            // 3. Build a map: serviceId -> aggregated group type (or null)
            const idToAggGroup = {{}};
            for (const [stype, isAgg] of Object.entries(aggregationState)) {{
                if (!isAgg) continue;
                const group = AGGREGATION_CONFIG.groups[stype];
                if (!group) continue;
                for (const sid of group.serviceIds) {{
                    idToAggGroup[sid] = stype;
                }}
            }}

            // 4. Process each original connection: hide and build merged map
            // Key for merged map: "resolvedSource|resolvedTarget|connType"
            // where resolvedSource/Target is either the original ID or __agg_<type>
            const mergedMap = {{}};

            for (const conn of originalConnections) {{
                const srcGroup = idToAggGroup[conn.sourceId] || null;
                const tgtGroup = idToAggGroup[conn.targetId] || null;

                if (!srcGroup && !tgtGroup) {{
                    // Neither endpoint is aggregated: leave visible
                    continue;
                }}

                // At least one endpoint is aggregated: hide original
                conn.element.classList.add('agg-hidden');

                if (srcGroup && tgtGroup && srcGroup === tgtGroup) {{
                    // Both in same group: hide entirely, no aggregate connection
                    continue;
                }}

                // Resolve endpoints: use aggregate node ID if in an aggregated group
                const resolvedSource = srcGroup ? `__agg_${{srcGroup}}` : conn.sourceId;
                const resolvedTarget = tgtGroup ? `__agg_${{tgtGroup}}` : conn.targetId;

                const key = `${{resolvedSource}}|${{resolvedTarget}}|${{conn.connType}}`;
                if (!mergedMap[key]) {{
                    mergedMap[key] = {{
                        sourceId: resolvedSource,
                        targetId: resolvedTarget,
                        connType: conn.connType,
                        label: conn.label,
                        count: 0,
                    }};
                }}
                mergedMap[key].count++;
            }}

            // 5. Create aggregate connections from merged map
            const connLayer = document.getElementById('connections-layer');
            const styles = {{
                'data_flow': {{ color: '#3B48CC', dash: '', marker: 'url(#arrowhead-data)' }},
                'trigger': {{ color: '#E7157B', dash: '', marker: 'url(#arrowhead-trigger)' }},
                'encrypt': {{ color: '#6c757d', dash: '4,4', marker: 'url(#arrowhead)' }},
                'network_flow': {{ color: '#0d7c3f', dash: '', marker: 'url(#arrowhead-network)' }},
                'security_rule': {{ color: '#d97706', dash: '2,4', marker: 'url(#arrowhead-security)' }},
                'default': {{ color: '#999999', dash: '', marker: 'url(#arrowhead)' }},
            }};

            // Group aggregate connections by which agg group they belong to (for tracking)
            const newAggConns = {{}};

            for (const [key, info] of Object.entries(mergedMap)) {{
                const style = styles[info.connType] || styles['default'];

                const sourcePos = servicePositions[info.sourceId];
                const targetPos = servicePositions[info.targetId];
                if (!sourcePos || !targetPos) continue;

                const pathD = calcConnectionPath(sourcePos, targetPos);
                const strokeWidth = info.count > 4 ? 3.5 : info.count > 2 ? 2.5 : 1.5;

                const connG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                connG.classList.add('connection', 'aggregate-connection');
                connG.dataset.source = info.sourceId;
                connG.dataset.target = info.targetId;
                connG.dataset.sourceType = getServiceTypeById(info.sourceId) || '';
                connG.dataset.targetType = getServiceTypeById(info.targetId) || '';
                connG.dataset.connType = info.connType;
                connG.dataset.label = info.label;
                connG.dataset.multiplicity = info.count;

                const hitarea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                hitarea.classList.add('connection-hitarea');
                hitarea.setAttribute('d', pathD);
                hitarea.setAttribute('fill', 'none');
                hitarea.setAttribute('stroke', 'transparent');
                hitarea.setAttribute('stroke-width', '15');
                connG.appendChild(hitarea);

                const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                pathEl.classList.add('connection-path');
                pathEl.setAttribute('d', pathD);
                pathEl.setAttribute('fill', 'none');
                pathEl.setAttribute('stroke', style.color);
                pathEl.setAttribute('stroke-width', `${{strokeWidth}}`);
                if (style.dash) pathEl.setAttribute('stroke-dasharray', style.dash);
                pathEl.setAttribute('marker-end', style.marker);
                pathEl.setAttribute('opacity', '0.7');
                connG.appendChild(pathEl);

                if (info.count > 1) {{
                    const midX = (sourcePos.x + targetPos.x) / 2 + iconSize / 2;
                    const midY = (sourcePos.y + targetPos.y) / 2 + iconSize / 2;
                    const multLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    multLabel.classList.add('multiplicity-label');
                    multLabel.setAttribute('x', `${{midX + 8}}`);
                    multLabel.setAttribute('y', `${{midY - 5}}`);
                    multLabel.setAttribute('font-family', 'Arial, sans-serif');
                    multLabel.setAttribute('font-size', '10');
                    multLabel.setAttribute('font-weight', 'bold');
                    multLabel.setAttribute('fill', style.color);
                    multLabel.textContent = `x${{info.count}}`;
                    connG.appendChild(multLabel);
                }}

                connLayer.appendChild(connG);

                // Track by involved agg groups for cleanup
                const involvedGroups = new Set();
                if (info.sourceId.startsWith('__agg_')) involvedGroups.add(info.sourceId.replace('__agg_', ''));
                if (info.targetId.startsWith('__agg_')) involvedGroups.add(info.targetId.replace('__agg_', ''));
                for (const g of involvedGroups) {{
                    if (!newAggConns[g]) newAggConns[g] = [];
                    newAggConns[g].push(connG);
                }}
            }}

            // Update the global tracking object
            for (const [g, conns] of Object.entries(newAggConns)) {{
                aggregateConnections[g] = conns;
            }}

            // Re-apply connection type filter to new aggregate connections
            applyConnTypeFilter();
        }}

        function calcConnectionPath(sourcePos, targetPos) {{
            const halfSize = iconSize / 2;
            let sx = sourcePos.x + halfSize;
            let sy = sourcePos.y + halfSize;
            let tx = targetPos.x + halfSize;
            let ty = targetPos.y + halfSize;

            if (Math.abs(ty - sy) > Math.abs(tx - sx)) {{
                if (ty > sy) {{
                    sy = sourcePos.y + iconSize + 8;
                    ty = targetPos.y - 8;
                }} else {{
                    sy = sourcePos.y - 8;
                    ty = targetPos.y + iconSize + 8;
                }}
            }} else {{
                if (tx > sx) {{
                    sx = sourcePos.x + iconSize + 8;
                    tx = targetPos.x - 8;
                }} else {{
                    sx = sourcePos.x - 8;
                    tx = targetPos.x + iconSize + 8;
                }}
            }}

            const midX = (sx + tx) / 2;
            const midY = (sy + ty) / 2;
            return `M ${{sx}} ${{sy}} Q ${{midX}} ${{sy}}, ${{midX}} ${{midY}} T ${{tx}} ${{ty}}`;
        }}

        function getServiceTypeById(serviceId) {{
            const el = document.querySelector(`[data-service-id="${{serviceId}}"]`);
            return el ? (el.dataset.serviceType || '') : '';
        }}

        // ============ CHIP PANEL ============
        function renderChipPanel() {{
            const panel = document.getElementById('aggregation-panel');
            const chipsContainer = document.getElementById('aggregation-chips');
            if (!panel || !chipsContainer) return;

            // Get qualifying groups sorted by count desc
            const groups = Object.entries(AGGREGATION_CONFIG.groups)
                .filter(([_, g]) => g.count >= AGGREGATION_CONFIG.threshold)
                .sort((a, b) => b[1].count - a[1].count);

            if (groups.length === 0) return;

            panel.style.display = 'flex';
            chipsContainer.innerHTML = '';

            for (const [stype, group] of groups) {{
                const chip = document.createElement('div');
                chip.classList.add('aggregation-chip');
                chip.dataset.serviceType = stype;
                const isActive = !!aggregationState[stype];
                chip.classList.add(isActive ? 'active' : 'inactive');
                const color = group.color || '#666';
                chip.style.borderColor = color;
                chip.style.backgroundColor = isActive ? color : 'transparent';
                chip.style.color = isActive ? 'white' : color;

                chip.innerHTML = `<span class="chip-check">${{isActive ? '&#10003;' : ''}}</span>${{group.label}} (${{group.count}})`;

                chip.addEventListener('click', () => toggleAggregation(stype));
                chipsContainer.appendChild(chip);
            }}
        }}

        function toggleAggregation(serviceType) {{
            const wasAggregated = aggregationState[serviceType];
            aggregationState[serviceType] = !wasAggregated;

            if (aggregationState[serviceType]) {{
                aggregateGroup(serviceType);
            }} else {{
                deaggregateGroup(serviceType);
            }}

            // Update chip visual
            renderChipPanel();

            // Save state
            localStorage.setItem('diagramAggregationState', JSON.stringify(aggregationState));
        }}

        // ============ CONNECTION TYPE FILTER ============
        function initConnectionTypeFilter() {{
            // Load saved state or default all visible
            const saved = localStorage.getItem('diagramConnTypeFilter');
            let loaded = null;
            if (saved) {{
                try {{ loaded = JSON.parse(saved); }} catch(e) {{}}
            }}
            for (const ct of CONNECTION_TYPES) {{
                connTypeFilterState[ct.id] = loaded ? (loaded[ct.id] !== false) : true;
            }}
            renderConnFilterPanel();
            applyConnTypeFilter();
        }}

        function renderConnFilterPanel() {{
            const container = document.getElementById('conn-filter-chips');
            if (!container) return;
            container.innerHTML = '';

            for (const ct of CONNECTION_TYPES) {{
                const chip = document.createElement('div');
                chip.classList.add('conn-filter-chip');
                const isActive = connTypeFilterState[ct.id] !== false;
                chip.classList.add(isActive ? 'active' : 'inactive');
                chip.style.borderColor = ct.color;
                chip.style.backgroundColor = isActive ? ct.color : 'transparent';
                chip.style.color = isActive ? 'white' : ct.color;
                chip.innerHTML = `<span class="chip-check">${{isActive ? '&#10003;' : ''}}</span>${{ct.label}}`;
                chip.addEventListener('click', () => toggleConnTypeFilter(ct.id));
                container.appendChild(chip);
            }}
        }}

        function toggleConnTypeFilter(connType) {{
            connTypeFilterState[connType] = connTypeFilterState[connType] === false;
            applyConnTypeFilter();
            renderConnFilterPanel();
            localStorage.setItem('diagramConnTypeFilter', JSON.stringify(connTypeFilterState));
        }}

        function applyConnTypeFilter() {{
            // Apply to original connections
            document.querySelectorAll('.connection').forEach(conn => {{
                const ct = conn.dataset.connType || 'default';
                if (connTypeFilterState[ct] === false) {{
                    conn.classList.add('conn-type-hidden');
                }} else {{
                    conn.classList.remove('conn-type-hidden');
                }}
            }});
            // Apply to aggregate connections
            for (const conns of Object.values(aggregateConnections)) {{
                conns.forEach(conn => {{
                    const ct = conn.dataset.connType || 'default';
                    if (connTypeFilterState[ct] === false) {{
                        conn.classList.add('conn-type-hidden');
                    }} else {{
                        conn.classList.remove('conn-type-hidden');
                    }}
                }});
            }}
        }}

        // ============ POPOVER ============
        function showAggregatePopover(serviceType, clientX, clientY) {{
            closeAggregatePopover();
            clearHighlights();

            const group = AGGREGATION_CONFIG.groups[serviceType];
            if (!group) return;

            const popover = document.createElement('div');
            popover.classList.add('aggregate-popover');
            popover.id = 'aggregate-popover';

            const header = document.createElement('div');
            header.classList.add('aggregate-popover-header');
            header.textContent = `${{group.label}} (${{group.count}})`;
            popover.appendChild(header);

            group.serviceIds.forEach((sid, idx) => {{
                const item = document.createElement('div');
                item.classList.add('aggregate-popover-item');
                item.dataset.resourceId = sid;

                const iconDiv = document.createElement('div');
                iconDiv.innerHTML = group.iconHtml || '';
                const innerSvg = iconDiv.querySelector('svg');
                if (innerSvg) {{
                    innerSvg.setAttribute('width', '24');
                    innerSvg.setAttribute('height', '24');
                }}
                item.appendChild(innerSvg || iconDiv);

                const nameSpan = document.createElement('span');
                nameSpan.textContent = group.serviceNames[idx] || sid;
                item.appendChild(nameSpan);

                item.addEventListener('click', (e) => {{
                    e.stopPropagation();
                    selectResourceInPopover(sid, serviceType, item);
                }});

                popover.appendChild(item);
            }});

            // Position popover near click
            popover.style.left = `${{clientX + 10}}px`;
            popover.style.top = `${{clientY + 10}}px`;

            document.body.appendChild(popover);
            activePopover = popover;

            // Adjust if off-screen
            const rect = popover.getBoundingClientRect();
            if (rect.right > window.innerWidth) {{
                popover.style.left = `${{clientX - rect.width - 10}}px`;
            }}
            if (rect.bottom > window.innerHeight) {{
                popover.style.top = `${{clientY - rect.height - 10}}px`;
            }}

            // Close on click outside (delayed to avoid immediate close)
            setTimeout(() => {{
                document.addEventListener('click', closePopoverOnOutsideClick);
            }}, 10);
        }}

        function closePopoverOnOutsideClick(e) {{
            if (activePopover && !activePopover.contains(e.target)) {{
                closeAggregatePopover();
            }}
        }}

        function closeAggregatePopover() {{
            if (activePopover) {{
                activePopover.remove();
                activePopover = null;
                selectedPopoverResource = null;
                document.removeEventListener('click', closePopoverOnOutsideClick);

                // Restore aggregate connections opacity
                document.querySelectorAll('.aggregate-connection').forEach(c => {{
                    c.style.opacity = '';
                }});
                // Remove any temporary highlight connections
                document.querySelectorAll('.popover-highlight-conn').forEach(c => c.remove());
            }}
        }}

        function selectResourceInPopover(resourceId, serviceType, itemEl) {{
            const group = AGGREGATION_CONFIG.groups[serviceType];
            if (!group) return;
            const groupIds = new Set(group.serviceIds);

            // Toggle selection
            if (selectedPopoverResource === resourceId) {{
                // Deselect
                selectedPopoverResource = null;
                itemEl.classList.remove('selected');
                // Restore ALL aggregate connections
                for (const conns of Object.values(aggregateConnections)) {{
                    conns.forEach(c => c.style.opacity = '');
                }}
                document.querySelectorAll('.popover-highlight-conn').forEach(c => c.remove());
                return;
            }}

            // Clear previous selection
            if (activePopover) {{
                activePopover.querySelectorAll('.aggregate-popover-item').forEach(i => i.classList.remove('selected'));
            }}
            selectedPopoverResource = resourceId;
            itemEl.classList.add('selected');

            // Dim ALL aggregate connections (not just this group's)
            for (const conns of Object.values(aggregateConnections)) {{
                conns.forEach(c => c.style.opacity = '0.15');
            }}

            // Remove previous highlight connections
            document.querySelectorAll('.popover-highlight-conn').forEach(c => c.remove());

            // Find original connections for this specific resource and draw them from aggregate node
            const aggNodeId = `__agg_${{serviceType}}`;
            const aggPos = servicePositions[aggNodeId];
            if (!aggPos) return;

            const connLayer = document.getElementById('connections-layer');
            const styles = {{
                'data_flow': {{ color: '#3B48CC', dash: '', marker: 'url(#arrowhead-data)' }},
                'trigger': {{ color: '#E7157B', dash: '', marker: 'url(#arrowhead-trigger)' }},
                'encrypt': {{ color: '#6c757d', dash: '4,4', marker: 'url(#arrowhead)' }},
                'network_flow': {{ color: '#0d7c3f', dash: '', marker: 'url(#arrowhead-network)' }},
                'security_rule': {{ color: '#d97706', dash: '2,4', marker: 'url(#arrowhead-security)' }},
                'default': {{ color: '#999999', dash: '', marker: 'url(#arrowhead)' }},
            }};

            // Build map of which IDs are in aggregated groups (for resolving targets)
            const idToAggGroup = {{}};
            for (const [stype, isAgg] of Object.entries(aggregationState)) {{
                if (!isAgg || stype === serviceType) continue;
                const g = AGGREGATION_CONFIG.groups[stype];
                if (!g) continue;
                for (const sid of g.serviceIds) {{
                    idToAggGroup[sid] = stype;
                }}
            }}

            // Collect and deduplicate highlight connections
            const hlMerged = {{}};
            for (const conn of originalConnections) {{
                let externalId = null;
                let direction = null;

                if (conn.sourceId === resourceId && !groupIds.has(conn.targetId)) {{
                    externalId = conn.targetId;
                    direction = 'out';
                }} else if (conn.targetId === resourceId && !groupIds.has(conn.sourceId)) {{
                    externalId = conn.sourceId;
                    direction = 'in';
                }}

                if (!externalId) continue;

                // Resolve external ID to aggregate node if the target is in another aggregated group
                const resolvedId = idToAggGroup[externalId] ? `__agg_${{idToAggGroup[externalId]}}` : externalId;
                const hlSource = direction === 'out' ? aggNodeId : resolvedId;
                const hlTarget = direction === 'out' ? resolvedId : aggNodeId;
                const key = `${{hlSource}}|${{hlTarget}}|${{conn.connType || 'default'}}`;

                if (!hlMerged[key]) {{
                    hlMerged[key] = {{ source: hlSource, target: hlTarget, connType: conn.connType || 'default', count: 0 }};
                }}
                hlMerged[key].count++;
            }}

            // Draw deduplicated highlight connections
            for (const [key, info] of Object.entries(hlMerged)) {{
                const sourcePos = servicePositions[info.source];
                const targetPos = servicePositions[info.target];
                if (!sourcePos || !targetPos) continue;

                const pathD = calcConnectionPath(sourcePos, targetPos);
                const style = styles[info.connType] || styles['default'];
                const strokeWidth = info.count > 4 ? 3.5 : info.count > 2 ? 2.5 : 2;

                const connG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                connG.classList.add('connection', 'popover-highlight-conn');
                connG.dataset.connType = info.connType;
                if (connTypeFilterState[info.connType] === false) {{
                    connG.classList.add('conn-type-hidden');
                }}
                connG.dataset.source = info.source;
                connG.dataset.target = info.target;

                const hitarea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                hitarea.classList.add('connection-hitarea');
                hitarea.setAttribute('d', pathD);
                hitarea.setAttribute('fill', 'none');
                hitarea.setAttribute('stroke', 'transparent');
                hitarea.setAttribute('stroke-width', '15');
                connG.appendChild(hitarea);

                const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                pathEl.classList.add('connection-path');
                pathEl.setAttribute('d', pathD);
                pathEl.setAttribute('fill', 'none');
                pathEl.setAttribute('stroke', style.color);
                pathEl.setAttribute('stroke-width', `${{strokeWidth}}`);
                if (style.dash) pathEl.setAttribute('stroke-dasharray', style.dash);
                pathEl.setAttribute('marker-end', style.marker);
                pathEl.setAttribute('opacity', '1');
                connG.appendChild(pathEl);

                if (info.count > 1) {{
                    const midX = (sourcePos.x + targetPos.x) / 2 + iconSize / 2;
                    const midY = (sourcePos.y + targetPos.y) / 2 + iconSize / 2;
                    const multLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    multLabel.classList.add('multiplicity-label');
                    multLabel.setAttribute('x', `${{midX + 8}}`);
                    multLabel.setAttribute('y', `${{midY - 5}}`);
                    multLabel.setAttribute('font-family', 'Arial, sans-serif');
                    multLabel.setAttribute('font-size', '10');
                    multLabel.setAttribute('font-weight', 'bold');
                    multLabel.setAttribute('fill', style.color);
                    multLabel.textContent = `x${{info.count}}`;
                    connG.appendChild(multLabel);
                }}

                connLayer.appendChild(connG);
            }}
        }}

        // ============ AGGREGATION-AWARE DRAG ============
        // Override updateConnectionsFor to also handle aggregate connections
        updateConnectionsFor = function(serviceId) {{
            // Update original connections
            _baseUpdateConnectionsFor(serviceId);

            // Update aggregate connections involving this serviceId
            document.querySelectorAll(`.aggregate-connection[data-source="${{serviceId}}"], .aggregate-connection[data-target="${{serviceId}}"]`).forEach(conn => {{
                updateConnection(conn);
            }});

            // Also update popover highlight connections
            document.querySelectorAll(`.popover-highlight-conn`).forEach(conn => {{
                const sId = conn.dataset.source;
                const tId = conn.dataset.target;
                if (sId === serviceId || tId === serviceId) {{
                    const sPos = servicePositions[sId];
                    const tPos = servicePositions[tId];
                    if (sPos && tPos) {{
                        const pathD = calcConnectionPath(sPos, tPos);
                        const pathEl = conn.querySelector('.connection-path');
                        const hitEl = conn.querySelector('.connection-hitarea');
                        if (pathEl) pathEl.setAttribute('d', pathD);
                        if (hitEl) hitEl.setAttribute('d', pathD);
                        // Update multiplicity label position
                        const multLabel = conn.querySelector('.multiplicity-label');
                        if (multLabel) {{
                            const midX = (sPos.x + tPos.x) / 2 + iconSize / 2;
                            const midY = (sPos.y + tPos.y) / 2 + iconSize / 2;
                            multLabel.setAttribute('x', `${{midX + 8}}`);
                            multLabel.setAttribute('y', `${{midY - 5}}`);
                        }}
                    }}
                }}
            }});
        }};

        // ============ PERSISTENCE INTEGRATION ============
        // Override save/load/reset to include aggregation state

        savePositions = function() {{
            // Save positions (including aggregate node positions)
            const data = JSON.stringify(servicePositions);
            localStorage.setItem('diagramPositions', data);
            // Save aggregation state
            localStorage.setItem('diagramAggregationState', JSON.stringify(aggregationState));
            // Save connection type filter state
            localStorage.setItem('diagramConnTypeFilter', JSON.stringify(connTypeFilterState));
            alert('Layout and aggregation state saved!');
        }};

        loadPositions = function() {{
            const data = localStorage.getItem('diagramPositions');
            if (!data) {{
                alert('No saved layout found.');
                return;
            }}

            const saved = JSON.parse(data);
            Object.keys(saved).forEach(id => {{
                if (servicePositions[id] !== undefined) {{
                    servicePositions[id] = saved[id];
                    const el = document.querySelector(`[data-service-id="${{id}}"]`);
                    if (el) {{
                        el.setAttribute('transform', `translate(${{saved[id].x}}, ${{saved[id].y}})`);
                    }}
                }}
            }});

            // Load aggregation state
            const aggData = localStorage.getItem('diagramAggregationState');
            if (aggData) {{
                try {{
                    const savedAgg = JSON.parse(aggData);
                    for (const [stype, isAgg] of Object.entries(savedAgg)) {{
                        if (aggregationState[stype] !== undefined && aggregationState[stype] !== isAgg) {{
                            toggleAggregation(stype);
                        }}
                    }}
                }} catch(e) {{}}
            }}

            // Load connection type filter state
            const ctData = localStorage.getItem('diagramConnTypeFilter');
            if (ctData) {{
                try {{
                    const savedCt = JSON.parse(ctData);
                    for (const ct of CONNECTION_TYPES) {{
                        if (savedCt[ct.id] !== undefined) {{
                            connTypeFilterState[ct.id] = savedCt[ct.id];
                        }}
                    }}
                    renderConnFilterPanel();
                    applyConnTypeFilter();
                }} catch(e) {{}}
            }}

            updateAllConnections();
            alert('Layout loaded!');
        }};

        resetPositions = function() {{
            // Reset individual node positions
            Object.keys(originalPositions).forEach(id => {{
                servicePositions[id] = {{ ...originalPositions[id] }};
                const el = document.querySelector(`[data-service-id="${{id}}"]`);
                if (el) {{
                    el.setAttribute('transform', `translate(${{originalPositions[id].x}}, ${{originalPositions[id].y}})`);
                }}
            }});

            // Reset aggregation to defaults
            for (const [stype, group] of Object.entries(AGGREGATION_CONFIG.groups)) {{
                if (group.count >= AGGREGATION_CONFIG.threshold) {{
                    const shouldAgg = group.defaultAggregated;
                    if (aggregationState[stype] !== shouldAgg) {{
                        aggregationState[stype] = shouldAgg;
                        if (shouldAgg) {{
                            aggregateGroup(stype);
                        }} else {{
                            deaggregateGroup(stype);
                        }}
                    }} else if (shouldAgg && aggregateNodes[stype]) {{
                        // Recalculate centroid with reset positions
                        const centroid = computeCentroid(stype);
                        servicePositions[`__agg_${{stype}}`] = centroid;
                        aggregateNodes[stype].setAttribute('transform', `translate(${{centroid.x}}, ${{centroid.y}})`);
                    }}
                }}
            }}

            renderChipPanel();
            updateAllConnections();
            // Also update aggregate connections
            for (const [stype, conns] of Object.entries(aggregateConnections)) {{
                conns.forEach(c => updateConnection(c));
            }}

            localStorage.removeItem('diagramAggregationState');

            // Reset connection type filter to all visible
            for (const ct of CONNECTION_TYPES) {{
                connTypeFilterState[ct.id] = true;
            }}
            renderConnFilterPanel();
            applyConnTypeFilter();
            localStorage.removeItem('diagramConnTypeFilter');
        }};
    </script>
</body>
</html>"""

    def __init__(self, svg_renderer: SVGRenderer):
        self.svg_renderer = svg_renderer

    def render_html(
        self,
        aggregated: AggregatedResult,
        positions: Dict[str, Position],
        groups: List[ServiceGroup],
        environment: str = "dev",
        actual_height: Optional[int] = None,
    ) -> str:
        """Generate complete HTML page with interactive diagram."""
        svg_content = self.svg_renderer.render_svg(
            aggregated.services,
            positions,
            aggregated.connections,
            groups,
            vpc_structure=aggregated.vpc_structure,
            actual_height=actual_height,
        )

        total_resources = sum(len(s.resources) for s in aggregated.services)

        # Build aggregation config for client-side JS
        agg_metadata = ResourceAggregator.get_aggregation_metadata(aggregated)
        # Add icon SVG HTML for each service type so JS can render aggregate nodes
        agg_config: Dict[str, Any] = {"threshold": 3, "groups": {}}
        for stype, info in agg_metadata.items():
            icon_svg = self.svg_renderer.icon_mapper.get_icon_svg(
                info["icon_resource_type"], 48
            )
            icon_html = ""
            if icon_svg:
                icon_content = self.svg_renderer._extract_svg_content(icon_svg)
                icon_viewbox = self.svg_renderer._extract_svg_viewbox(icon_svg)
                if icon_content:
                    icon_html = (
                        f'<svg width="48" height="48" viewBox="{icon_viewbox}">'
                        f"{icon_content}</svg>"
                    )
            color = self.svg_renderer.icon_mapper.get_category_color(
                info["icon_resource_type"]
            )
            agg_config["groups"][stype] = {
                "count": info["count"],
                "label": info["label"],
                "defaultAggregated": info["defaultAggregated"],
                "iconHtml": icon_html,
                "color": color,
                "serviceIds": info["service_ids"],
                "serviceNames": info["service_names"],
            }

        html_content = self.HTML_TEMPLATE.format(
            svg_content=svg_content,
            service_count=len(aggregated.services),
            resource_count=total_resources,
            connection_count=len(aggregated.connections),
            environment=environment,
            icon_size=self.svg_renderer.config.icon_size,
            aggregation_config_json=json.dumps(agg_config),
        )

        return html_content
