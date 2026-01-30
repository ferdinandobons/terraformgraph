"""
SVG/HTML Renderer

Generates interactive HTML diagrams with:
- Drag-and-drop for repositioning services
- Connections that follow moved elements
- Export to PNG/JPG
"""

import html
import re
import json
from pathlib import Path
from typing import Dict, List, Optional

from .aggregator import LogicalService, LogicalConnection, AggregatedResult
from .icons import IconMapper, CATEGORY_COLORS, TERRAFORM_TO_ICON
from .layout import Position, ServiceGroup, LayoutConfig


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
        groups: List[ServiceGroup]
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
        svg_parts.append(f'''<rect width="100%" height="100%" fill="#f8f9fa"/>''')

        # Render groups (AWS Cloud, VPC)
        for group in groups:
            svg_parts.append(self._render_group(group))

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

        # Services layer
        svg_parts.append('<g id="services-layer">')
        for service in services:
            if service.id in positions:
                svg_parts.append(self._render_service(service, positions[service.id]))
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
        """Render a group container (AWS Cloud, VPC)."""
        if not group.position:
            return ''

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

    def _render_service(self, service: LogicalService, pos: Position) -> str:
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

        if icon_svg:
            icon_content = self._extract_svg_content(icon_svg)

            svg = f'''
            <g class="service draggable" data-service-id="{html.escape(service.id)}"
               data-tooltip="{html.escape(tooltip)}" data-is-vpc="{is_vpc_service}"
               transform="translate({pos.x}, {pos.y})" style="cursor: grab;">
                <rect class="service-bg" x="-8" y="-8"
                    width="{pos.width + 16}" height="{pos.height + 36}"
                    fill="white" stroke="#e0e0e0" stroke-width="1" rx="8" ry="8"
                    filter="url(#shadow)"/>
                <svg class="service-icon" width="{pos.width}" height="{pos.height}" viewBox="0 0 64 64">
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
               data-tooltip="{html.escape(tooltip)}" data-is-vpc="{is_vpc_service}"
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
            <path class="connection-hitarea" d="{path}"/>
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
            max-height: 70vh;
        }}
        .diagram-wrapper svg {{
            display: block;
            margin: 0 auto;
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
                dragging = e.currentTarget;
                dragging.classList.add('dragging');
                dragging.style.cursor = 'grabbing';

                const pt = svg.createSVGPoint();
                pt.x = e.clientX;
                pt.y = e.clientY;
                const svgP = pt.matrixTransform(svg.getScreenCTM().inverse());

                const id = dragging.dataset.serviceId;
                const pos = servicePositions[id] || {{ x: 0, y: 0 }};
                offset.x = svgP.x - pos.x;
                offset.y = svgP.y - pos.y;

                // Hide tooltip while dragging
                document.getElementById('tooltip').style.display = 'none';
            }}

            function drag(e) {{
                if (!dragging) return;

                const pt = svg.createSVGPoint();
                pt.x = e.clientX;
                pt.y = e.clientY;
                const svgP = pt.matrixTransform(svg.getScreenCTM().inverse());

                let newX = svgP.x - offset.x;
                let newY = svgP.y - offset.y;

                // Constrain to VPC if it's a VPC service
                if (dragging.dataset.isVpc === 'true') {{
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
            // Click on service to highlight connections
            document.querySelectorAll('.service').forEach(el => {{
                el.addEventListener('click', (e) => {{
                    // Don't highlight if dragging
                    if (el.classList.contains('dragging')) return;
                    e.stopPropagation();

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

            // Click on background to clear highlights
            document.getElementById('diagram-svg').addEventListener('click', (e) => {{
                if (e.target.tagName === 'svg' || e.target.classList.contains('group-bg')) {{
                    clearHighlights();
                }}
            }});
        }}

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
        environment: str = 'dev'
    ) -> str:
        """Generate complete HTML page with interactive diagram."""
        svg_content = self.svg_renderer.render_svg(
            aggregated.services,
            positions,
            aggregated.connections,
            groups
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
