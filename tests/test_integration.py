"""Integration tests for the full pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tfgraph.aggregator import ResourceAggregator
from tfgraph.icons import IconMapper
from tfgraph.layout import LayoutEngine
from tfgraph.parser import TerraformParser
from tfgraph.renderer import HTMLRenderer, SVGRenderer


class TestFullPipeline:
    def test_parse_simple_example(self, simple_example):
        """Test parsing the simple example directory."""
        parser = TerraformParser(str(simple_example))
        result = parser.parse_directory(simple_example)

        assert len(result.resources) > 0

        resource_types = {r.resource_type for r in result.resources}
        assert "aws_vpc" in resource_types
        assert "aws_ecs_cluster" in resource_types
        assert "aws_s3_bucket" in resource_types

    def test_aggregation(self, simple_example):
        """Test resource aggregation."""
        parser = TerraformParser(str(simple_example))
        result = parser.parse_directory(simple_example)

        aggregator = ResourceAggregator()
        aggregated = aggregator.aggregate(result)

        assert len(aggregated.services) > 0

        service_types = {s.service_type for s in aggregated.services}
        # Check for expected service types
        assert "ecs" in service_types or "vpc" in service_types

    def test_full_pipeline_produces_html(self, simple_example, tmp_path):
        """Test the full pipeline produces valid HTML."""
        # Parse
        parser = TerraformParser(str(simple_example))
        result = parser.parse_directory(simple_example)

        # Aggregate
        aggregator = ResourceAggregator()
        aggregated = aggregator.aggregate(result)

        # Layout
        layout = LayoutEngine()
        positions, groups = layout.compute_layout(aggregated)

        # Render
        icon_mapper = IconMapper()  # No icons path - uses fallback
        svg_renderer = SVGRenderer(icon_mapper)
        html_renderer = HTMLRenderer(svg_renderer)

        html = html_renderer.render_html(
            aggregated, positions, groups,
            environment="test"
        )

        # Write output
        output_file = tmp_path / "test_diagram.html"
        output_file.write_text(html)

        assert output_file.exists()
        assert "<html" in html.lower()
        assert "<svg" in html.lower() or "svg" in html.lower()
