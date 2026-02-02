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
from typing import TYPE_CHECKING, Dict, List, Optional

from .aggregator import AggregatedResult, LogicalConnection, LogicalService
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
        actual_height: Optional[int] = None
    ) -> str:
        """Generate SVG content for the diagram."""
        svg_parts = []

        # Use actual height if provided (from layout engine), otherwise use config
        canvas_height = actual_height if actual_height else self.config.canvas_height

        # SVG header with responsive viewBox
        # width="100%" allows SVG to scale to container, preserveAspectRatio maintains proportions
        svg_parts.append(f'''<svg id="diagram-svg" xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            viewBox="0 0 {self.config.canvas_width} {canvas_height}"
            width="100%" height="auto" preserveAspectRatio="xMidYMin meet"
            style="max-width: {self.config.canvas_width}px; min-height: {canvas_height}px;">''')

        # Defs for arrows and filters
        svg_parts.append(self._render_defs())

        # Background
        svg_parts.append('''<rect width="100%" height="100%" fill="#f8f9fa"/>''')

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
                        svg_parts.append(self._render_subnet(
                            subnet.resource_id,
                            positions[subnet.resource_id],
                            subnet
                        ))
            svg_parts.append('</g>')

        # Connections container (will be updated dynamically)
        svg_parts.append('<g id="connections-layer">')
        for conn in connections:
            if conn.source_id in positions and conn.target_id in positions:
                svg_parts.append(self._render_connection(
                    positions[conn.source_id],
                    positions[conn.target_id],
                    conn
                ))
        svg_parts.append('</g>')

        # Render VPC endpoints layer
        if vpc_structure:
            svg_parts.append('<g id="endpoints-layer">')
            for endpoint in vpc_structure.endpoints:
                if endpoint.resource_id in positions:
                    svg_parts.append(self._render_vpc_endpoint(
                        endpoint.resource_id,
                        positions[endpoint.resource_id],
                        endpoint
                    ))
            svg_parts.append('</g>')

        # Services layer
        svg_parts.append('<g id="services-layer">')
        for service in services:
            if service.id in positions:
                svg_parts.append(self._render_service(
                    service, positions[service.id], aws_id_to_resource_id,
                    positions, vpc_structure
                ))
        svg_parts.append('</g>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _render_defs(self) -> str:
        """Render SVG definitions (markers, filters)."""
        return '''
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
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.15"/>
            </filter>
        </defs>
        '''

    def _render_group(self, group: ServiceGroup) -> str:
        """Render a group container (AWS Cloud, VPC, AZ)."""
        if not group.position:
            return ''

        pos = group.position

        # Handle AZ groups with special rendering
        if group.group_type == 'az':
            return self._render_az(group)

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

    def _render_az(self, group: ServiceGroup) -> str:
        """Render an Availability Zone container with dashed border."""
        if not group.position:
            return ''

        pos = group.position
        border_color = '#ff9900'  # AWS orange for AZ
        bg_color = '#fff8f0'  # Light orange background
        text_color = '#ff9900'

        return f'''
        <g class="group group-az" data-group-type="az">
            <rect class="az-bg" x="{pos.x}" y="{pos.y}" width="{pos.width}" height="{pos.height}"
                fill="{bg_color}" stroke="{border_color}" stroke-width="1.5"
                stroke-dasharray="5,3" rx="8" ry="8"/>
            <text x="{pos.x + 10}" y="{pos.y + 18}"
                font-family="Arial, sans-serif" font-size="12" font-weight="bold"
                fill="{text_color}">{html.escape(group.name)}</text>
        </g>
        '''

    def _render_subnet(
        self,
        subnet_id: str,
        pos: Position,
        subnet_info: "Subnet"
    ) -> str:
        """Render a colored subnet box.

        Colors:
        - public: green
        - private: blue
        - database: yellow/gold
        - unknown: gray
        """
        colors = {
            'public': ('#22a06b', '#e3fcef'),  # Green
            'private': ('#0052cc', '#deebff'),  # Blue
            'database': ('#ff991f', '#fffae6'),  # Yellow/Gold
            'unknown': ('#6b778c', '#f4f5f7'),  # Gray
        }

        border_color, bg_color = colors.get(subnet_info.subnet_type, colors['unknown'])

        return f'''
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
                {subnet_info.subnet_type}
            </text>
        </g>
        '''

    def _render_vpc_endpoint(
        self,
        endpoint_id: str,
        pos: Position,
        endpoint_info: "VPCEndpoint"
    ) -> str:
        """Render a VPC endpoint with AWS icon and service name.

        Colors:
        - gateway: green (S3, DynamoDB)
        - interface: blue (ECR, CloudWatch, SSM, etc.)
        """
        # Colors by type
        colors = {
            'gateway': ('#22a06b', '#e3fcef'),   # Green
            'interface': ('#0052cc', '#deebff'),  # Blue
        }
        border_color, bg_color = colors.get(endpoint_info.endpoint_type, colors['interface'])

        # Extract clean service name
        service_name = endpoint_info.service
        if '.' in service_name:
            service_name = service_name.split('.')[0]
        service_display = service_name.upper()

        # Type label
        type_label = "Gateway" if endpoint_info.endpoint_type == "gateway" else "Interface"

        # Box dimensions
        box_width = pos.width
        box_height = pos.height

        # Center positions
        cx = pos.x + box_width / 2

        # Try to get official AWS VPC Endpoints icon
        icon_svg = self.icon_mapper.get_icon_svg('aws_vpc_endpoint', 48)
        icon_content = None

        # Check if we got a real icon (not the fallback with "RES" text)
        if icon_svg and 'Endpoints' in icon_svg:
            icon_content = self._extract_svg_content(icon_svg)

        if icon_content:
            # Use official AWS icon
            icon_size = 32
            return f'''
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
            '''
        else:
            # Fallback: colored box with service name
            return f'''
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
            '''

    def _render_service(
        self,
        service: LogicalService,
        pos: Position,
        aws_id_to_resource_id: Optional[Dict[str, str]] = None,
        all_positions: Optional[Dict[str, Position]] = None,
        vpc_structure: Optional["VPCStructure"] = None
    ) -> str:
        """Render a draggable logical service with its icon."""
        icon_svg = self.icon_mapper.get_icon_svg(service.icon_resource_type, 48)
        color = self.icon_mapper.get_category_color(service.icon_resource_type)

        # Count badge
        count_badge = ''
        if service.count > 1:
            count_badge = f'''
            <circle class="count-badge" cx="{pos.width - 8}" cy="8" r="12"
                fill="{color}" stroke="white" stroke-width="2"/>
            <text class="count-text" x="{pos.width - 8}" y="12"
                font-family="Arial, sans-serif" font-size="11" fill="white"
                text-anchor="middle" font-weight="bold">{service.count}</text>
            '''

        resource_count = len(service.resources)
        tooltip = f"{service.name} ({resource_count} resources)"

        # Determine if this is a VPC service
        is_vpc_service = 'true' if service.is_vpc_resource else 'false'

        # For non-VPC services with multiple resources, add expandable attributes
        expand_attrs = ''
        if not service.is_vpc_resource and service.count > 1:
            resources_data = json.dumps([{
                'name': r.attributes.get('name', r.resource_name),
                'type': r.resource_type,
                'id': r.full_id
            } for r in service.resources])
            # Use single quotes for JSON to avoid conflict with HTML double quotes
            expand_attrs = f"data-expandable='true' data-resources='{html.escape(resources_data)}'"

        # Determine subnet constraint directly from service.subnet_ids
        # This ensures the drag constraint matches the service's actual subnet assignment
        subnet_attr = ''
        if service.subnet_ids and vpc_structure and all_positions:
            # Map from AWS IDs to resource IDs for state-based lookups
            for subnet_id in service.subnet_ids:
                resolved_id = subnet_id
                # Handle _state_subnet: prefixed IDs (from Terraform state)
                if subnet_id.startswith("_state_subnet:"):
                    aws_id = subnet_id[len("_state_subnet:"):]
                    resolved_id = aws_id_to_resource_id.get(aws_id)

                # Find the subnet that contains this service's position
                if resolved_id and resolved_id in all_positions:
                    subnet_pos = all_positions[resolved_id]
                    # Check if service position is inside this subnet
                    if (subnet_pos.x <= pos.x <= subnet_pos.x + subnet_pos.width and
                        subnet_pos.y <= pos.y <= subnet_pos.y + subnet_pos.height):
                        subnet_attr = f'data-subnet-id="{html.escape(resolved_id)}"'
                        break

        if icon_svg:
            icon_content = self._extract_svg_content(icon_svg)
            icon_viewbox = self._extract_svg_viewbox(icon_svg)

            svg = f'''
            <g class="service draggable" data-service-id="{html.escape(service.id)}"
               data-tooltip="{html.escape(tooltip)}" data-is-vpc="{is_vpc_service}" {subnet_attr}
               {expand_attrs}
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
            '''
        else:
            svg = f'''
            <g class="service draggable" data-service-id="{html.escape(service.id)}"
               data-tooltip="{html.escape(tooltip)}" data-is-vpc="{is_vpc_service}" {subnet_attr}
               {expand_attrs}
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
            '''

        return svg

    def _extract_svg_content(self, svg_string: str) -> str:
        """Extract the inner content of an SVG, removing outer tags."""
        svg_string = re.sub(r'<\?xml[^?]*\?>\s*', '', svg_string)
        match = re.search(r'<svg[^>]*>(.*)</svg>', svg_string, re.DOTALL)
        if match:
            return match.group(1)
        return ''

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
        connection: LogicalConnection
    ) -> str:
        """Render a connection line between services."""
        styles = {
            'data_flow': ('#3B48CC', '', 'url(#arrowhead-data)'),
            'trigger': ('#E7157B', '', 'url(#arrowhead-trigger)'),
            'encrypt': ('#6c757d', '4,4', 'url(#arrowhead)'),
            'default': ('#999999', '', 'url(#arrowhead)'),
        }

        stroke_color, stroke_dash, marker = styles.get(connection.connection_type, styles['default'])
        dash_attr = f'stroke-dasharray="{stroke_dash}"' if stroke_dash else ''

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

        label = connection.label or ''
        return f'''
        <g class="connection" data-source="{html.escape(connection.source_id)}"
           data-target="{html.escape(connection.target_id)}"
           data-conn-type="{connection.connection_type}"
           data-label="{html.escape(label)}">
            <path class="connection-hitarea" d="{path}" fill="none" stroke="transparent" stroke-width="15"/>
            <path class="connection-path" d="{path}" fill="none" stroke="{stroke_color}"
                stroke-width="1.5" {dash_attr} marker-end="{marker}" opacity="0.7"/>
        </g>
        '''


class HTMLRenderer:
    """Wraps SVG in interactive HTML with drag-and-drop and export."""

    HTML_TEMPLATE = '''<!DOCTYPE html>
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            background: white;
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
            padding: 20px;
            overflow: auto;
        }}
        .diagram-wrapper svg {{
            display: block;
            margin: 0 auto;
            width: 100%;
            height: auto;
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
            width: 30px;
            height: 3px;
            border-radius: 2px;
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
        .expand-popup {{
            position: fixed;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.25);
            padding: 16px;
            z-index: 2000;
            max-width: 320px;
            max-height: 400px;
            overflow-y: auto;
        }}
        .expand-popup-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }}
        .expand-popup-title {{
            margin: 0;
            font-size: 14px;
            font-weight: 600;
            color: #232f3e;
        }}
        .expand-popup-close {{
            cursor: pointer;
            font-size: 20px;
            color: #999;
            line-height: 1;
            padding: 4px;
        }}
        .expand-popup-close:hover {{
            color: #333;
        }}
        .expand-popup-item {{
            padding: 10px 12px;
            border-radius: 6px;
            margin-bottom: 6px;
            background: #f8f9fa;
            transition: background 0.15s;
        }}
        .expand-popup-item:hover {{
            background: #e9ecef;
        }}
        .expand-popup-item:last-child {{
            margin-bottom: 0;
        }}
        .expand-popup-item-name {{
            font-weight: 500;
            font-size: 13px;
            color: #333;
            margin-bottom: 2px;
        }}
        .expand-popup-item-type {{
            font-size: 11px;
            color: #666;
        }}
        .service[data-expandable="true"] {{
            cursor: pointer !important;
        }}
        .service[data-expandable="true"]:hover .service-bg {{
            stroke: #8c4fff;
            stroke-width: 2;
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
                        <div class="legend-item">
                            <div class="legend-circle" style="background: #9c27b0;"></div>
                            <span>Gateway Endpoint</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-circle" style="background: #2196f3;"></div>
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
    </div>
    <div class="tooltip" id="tooltip"></div>
    <div class="highlight-info" id="highlight-info"></div>
    <div class="expand-popup" id="expand-popup" style="display: none;">
        <div class="expand-popup-header">
            <h4 class="expand-popup-title" id="expand-popup-title">Resources</h4>
            <span class="expand-popup-close" onclick="closeExpandPopup()">&times;</span>
        </div>
        <div id="expand-popup-content"></div>
    </div>
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

            document.querySelectorAll('.service.draggable').forEach(el => {{
                el.addEventListener('mousedown', startDrag);
            }});

            svg.addEventListener('mousemove', drag);
            svg.addEventListener('mouseup', endDrag);
            svg.addEventListener('mouseleave', endDrag);

            function startDrag(e) {{
                e.preventDefault();

                // Guard against null CTM (can happen during rendering)
                const ctm = svg.getScreenCTM();
                if (!ctm) return;

                dragging = e.currentTarget;
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
                    }}
                }} else {{
                    // Constrain to AWS Cloud bounds
                    const cloudGroup = document.querySelector('.group-aws_cloud .group-bg');
                    if (cloudGroup) {{
                        const minX = parseFloat(cloudGroup.dataset.minX) + 20;
                        const minY = parseFloat(cloudGroup.dataset.minY) + 40;
                        const maxX = parseFloat(cloudGroup.dataset.maxX) - iconSize - 20;
                        const maxY = parseFloat(cloudGroup.dataset.maxY) - iconSize - 40;

                        newX = Math.max(minX, Math.min(maxX, newX));
                        newY = Math.max(minY, Math.min(maxY, newY));
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

        function updateConnectionsFor(serviceId) {{
            document.querySelectorAll('.connection').forEach(conn => {{
                if (conn.dataset.source === serviceId || conn.dataset.target === serviceId) {{
                    updateConnection(conn);
                }}
            }});
        }}

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
        }}

        // ============ HIGHLIGHTING SYSTEM ============
        let currentHighlight = null;

        function initHighlighting() {{
            // Click on service to highlight connections or expand
            document.querySelectorAll('.service').forEach(el => {{
                el.addEventListener('click', (e) => {{
                    // Don't process if dragging
                    if (el.classList.contains('dragging')) return;
                    e.stopPropagation();

                    // Check if this is an expandable service (non-VPC with multiple resources)
                    if (el.dataset.expandable === 'true') {{
                        showExpandPopup(el, e.clientX, e.clientY);
                        return;
                    }}

                    const serviceId = el.dataset.serviceId;

                    // Toggle highlight
                    if (currentHighlight === serviceId) {{
                        clearHighlights();
                    }} else {{
                        highlightService(serviceId);
                    }}
                }});
            }});

            // Click on connection to highlight
            document.querySelectorAll('.connection').forEach(el => {{
                el.addEventListener('click', (e) => {{
                    e.stopPropagation();

                    const sourceId = el.dataset.source;
                    const targetId = el.dataset.target;
                    const connKey = `conn:${{sourceId}}->${{targetId}}`;

                    // Toggle highlight
                    if (currentHighlight === connKey) {{
                        clearHighlights();
                    }} else {{
                        highlightConnection(el, sourceId, targetId);
                    }}
                }});
            }});

            // Click on background to clear highlights and close popups
            document.getElementById('diagram-svg').addEventListener('click', (e) => {{
                if (e.target.tagName === 'svg' || e.target.classList.contains('group-bg')) {{
                    clearHighlights();
                    closeExpandPopup();
                }}
            }});
        }}

        // ============ EXPAND POPUP SYSTEM ============
        function showExpandPopup(serviceEl, x, y) {{
            const popup = document.getElementById('expand-popup');
            const title = document.getElementById('expand-popup-title');
            const content = document.getElementById('expand-popup-content');

            // Get service name from tooltip
            const serviceName = serviceEl.dataset.tooltip.split(' (')[0];
            title.textContent = serviceName + ' - Resources';

            // Parse resources data
            let resourceCount = 0;
            try {{
                const resources = JSON.parse(serviceEl.dataset.resources);
                resourceCount = resources.length;

                // Build content
                content.innerHTML = resources.map(r => `
                    <div class="expand-popup-item">
                        <div class="expand-popup-item-name">${{r.name}}</div>
                        <div class="expand-popup-item-type">${{r.type}}</div>
                    </div>
                `).join('');
            }} catch (e) {{
                content.innerHTML = '<div class="expand-popup-item">Error loading resources</div>';
                resourceCount = 1;
            }}

            // Position popup (avoid going off screen)
            const popupWidth = 320;
            const popupHeight = Math.min(400, resourceCount * 60 + 60);
            const posX = Math.min(x + 10, window.innerWidth - popupWidth - 20);
            const posY = Math.min(y + 10, window.innerHeight - popupHeight - 20);

            popup.style.left = posX + 'px';
            popup.style.top = posY + 'px';
            popup.style.display = 'block';
        }}

        function closeExpandPopup() {{
            document.getElementById('expand-popup').style.display = 'none';
        }}

        // Close expand popup when clicking outside
        document.addEventListener('click', (e) => {{
            const popup = document.getElementById('expand-popup');
            if (popup.style.display === 'block' && !popup.contains(e.target)) {{
                const clickedService = e.target.closest('.service');
                if (!clickedService || clickedService.dataset.expandable !== 'true') {{
                    closeExpandPopup();
                }}
            }}
        }});

        function highlightService(serviceId) {{
            clearHighlights();
            currentHighlight = serviceId;

            // Find all connected services
            const connectedServices = new Set([serviceId]);
            const connectedConnections = [];

            document.querySelectorAll('.connection').forEach(conn => {{
                const source = conn.dataset.source;
                const target = conn.dataset.target;

                if (source === serviceId || target === serviceId) {{
                    connectedServices.add(source);
                    connectedServices.add(target);
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
            connectedServices.forEach(id => {{
                const el = document.querySelector(`[data-service-id="${{id}}"]`);
                if (el) {{
                    el.classList.remove('dimmed');
                    el.classList.add('highlighted');
                }}
            }});

            // Highlight connected connections
            connectedConnections.forEach(conn => {{
                conn.classList.remove('dimmed');
                conn.classList.add('highlighted');
            }});

            // Show info tooltip
            showHighlightInfo(serviceId, connectedServices.size - 1, connectedConnections.length);
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

            document.querySelectorAll('.service').forEach(el => {{
                el.addEventListener('mouseenter', (e) => {{
                    if (el.classList.contains('dragging')) return;
                    const data = el.dataset.tooltip;
                    if (data) {{
                        tooltip.textContent = data;
                        tooltip.style.display = 'block';
                    }}
                }});
                el.addEventListener('mousemove', (e) => {{
                    if (el.classList.contains('dragging')) return;
                    tooltip.style.left = e.clientX + 15 + 'px';
                    tooltip.style.top = e.clientY + 15 + 'px';
                }});
                el.addEventListener('mouseleave', () => {{
                    tooltip.style.display = 'none';
                }});
            }});
        }}

        function resetPositions() {{
            Object.keys(originalPositions).forEach(id => {{
                servicePositions[id] = {{ ...originalPositions[id] }};
                const el = document.querySelector(`[data-service-id="${{id}}"]`);
                if (el) {{
                    el.setAttribute('transform', `translate(${{originalPositions[id].x}}, ${{originalPositions[id].y}})`);
                }}
            }});
            updateAllConnections();
        }}

        function savePositions() {{
            const data = JSON.stringify(servicePositions);
            localStorage.setItem('diagramPositions', data);
            alert('Layout saved to browser storage!');
        }}

        function loadPositions() {{
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
        }}

        function exportAs(format) {{
            const svg = document.getElementById('diagram-svg');
            const canvas = document.getElementById('export-canvas');
            const ctx = canvas.getContext('2d');

            // Set canvas size
            const svgRect = svg.getBoundingClientRect();
            const scale = 2; // Higher resolution
            canvas.width = svg.viewBox.baseVal.width * scale;
            canvas.height = svg.viewBox.baseVal.height * scale;

            // Create image from SVG
            const svgData = new XMLSerializer().serializeToString(svg);
            const svgBlob = new Blob([svgData], {{ type: 'image/svg+xml;charset=utf-8' }});
            const url = URL.createObjectURL(svgBlob);

            const img = new Image();
            img.onload = () => {{
                // White background for JPG
                if (format === 'jpg') {{
                    ctx.fillStyle = 'white';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                }}

                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(url);

                const mimeType = format === 'jpg' ? 'image/jpeg' : 'image/png';
                const quality = format === 'jpg' ? 0.95 : undefined;
                const dataUrl = canvas.toDataURL(mimeType, quality);

                // Show modal with preview
                const preview = document.getElementById('export-preview');
                const download = document.getElementById('export-download');

                preview.src = dataUrl;
                download.href = dataUrl;
                download.download = `aws-diagram.${{format}}`;

                document.getElementById('export-modal').classList.add('active');
            }};
            img.src = url;
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
    </script>
</body>
</html>'''

    def __init__(self, svg_renderer: SVGRenderer):
        self.svg_renderer = svg_renderer

    def render_html(
        self,
        aggregated: AggregatedResult,
        positions: Dict[str, Position],
        groups: List[ServiceGroup],
        environment: str = 'dev',
        actual_height: Optional[int] = None
    ) -> str:
        """Generate complete HTML page with interactive diagram."""
        svg_content = self.svg_renderer.render_svg(
            aggregated.services,
            positions,
            aggregated.connections,
            groups,
            vpc_structure=aggregated.vpc_structure,
            actual_height=actual_height
        )

        total_resources = sum(len(s.resources) for s in aggregated.services)

        html_content = self.HTML_TEMPLATE.format(
            svg_content=svg_content,
            service_count=len(aggregated.services),
            resource_count=total_resources,
            connection_count=len(aggregated.connections),
            environment=environment,
            icon_size=self.svg_renderer.config.icon_size
        )

        return html_content
