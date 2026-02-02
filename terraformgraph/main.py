#!/usr/bin/env python3
"""
terraformgraph - Terraform Diagram Generator

Generates AWS infrastructure diagrams from Terraform code using official AWS icons.
Creates high-level architectural diagrams with logical service groupings.

Usage:
    # Parse a directory directly (generates diagram.html by default)
    terraformgraph -t ./infrastructure

    # Parse a specific environment subdirectory
    terraformgraph -t ./infrastructure -e dev

    # With custom output path
    terraformgraph -t ./infrastructure -o my-diagram.html

    # With custom icons path
    terraformgraph -t ./infrastructure -i /path/to/icons
"""

import argparse
import sys
from pathlib import Path

from .aggregator import ResourceAggregator
from .icons import IconMapper
from .layout import LayoutConfig, LayoutEngine
from .parser import TerraformParser
from .renderer import HTMLRenderer, SVGRenderer


def main():
    parser = argparse.ArgumentParser(
        description='Generate AWS infrastructure diagrams from Terraform code.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Parse a directory (generates diagram.html by default)
    terraformgraph -t ./infrastructure

    # Parse a specific environment subdirectory
    terraformgraph -t ./infrastructure -e dev

    # With custom output path
    terraformgraph -t ./infrastructure -o my-diagram.html

    # With custom icons path
    terraformgraph -t ./infrastructure -i /path/to/icons
        '''
    )

    parser.add_argument(
        '-t', '--terraform',
        required=True,
        help='Path to the Terraform infrastructure directory'
    )

    parser.add_argument(
        '-e', '--environment',
        help='Environment name (dev, staging, prod). If not provided, parses the terraform directory directly.',
        default=None
    )

    parser.add_argument(
        '-i', '--icons',
        help='Path to AWS icons directory (auto-discovers in ./aws-official-icons, ~/aws-official-icons, ~/.terraformgraph/icons)',
        default=None
    )

    parser.add_argument(
        '-o', '--output',
        default='diagram.html',
        help='Output file path (HTML). Default: diagram.html'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--use-graph',
        action='store_true',
        help='Use terraform graph for dependency information (requires terraform init)'
    )

    parser.add_argument(
        '--use-state', '-s',
        nargs='?',
        const=True,
        default=False,
        metavar='FILE',
        help='Use terraform state for actual resource values. Optionally specify a JSON file path (plan.json, state.json). If no file given, auto-discovers in terraform dir or runs terraform show -json.'
    )

    args = parser.parse_args()

    # Validate paths
    terraform_path = Path(args.terraform)
    if not terraform_path.exists():
        print(f"Error: Terraform path not found: {terraform_path}", file=sys.stderr)
        sys.exit(1)

    # Auto-discover icons path
    icons_path = None
    if args.icons:
        icons_path = Path(args.icons)
    else:
        # Try common locations for AWS icons
        search_paths = [
            Path.cwd() / "aws-official-icons",
            Path.cwd() / "aws-icons",
            Path.cwd() / "AWS_Icons",
            Path(__file__).parent.parent / "aws-official-icons",
            Path.home() / "aws-official-icons",
            Path.home() / ".terraformgraph" / "icons",
        ]
        for search_path in search_paths:
            if search_path.exists() and any(search_path.glob("Architecture-Service-Icons_*")):
                icons_path = search_path
                break

    if icons_path and not icons_path.exists():
        print(f"Warning: Icons path not found: {icons_path}. Using fallback colors.", file=sys.stderr)
        icons_path = None
    elif icons_path and args.verbose:
        print(f"Using icons from: {icons_path}")

    # Determine parsing mode
    if args.environment:
        # Environment mode: terraform_path/environment/
        parse_path = terraform_path / args.environment
        title = f"{args.environment.upper()} Environment"
        if not parse_path.exists():
            print(f"Error: Environment not found: {parse_path}", file=sys.stderr)
            available = [d.name for d in terraform_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
            print(f"Available environments: {available}", file=sys.stderr)
            sys.exit(1)
    else:
        # Direct mode: terraform_path is the folder to parse
        parse_path = terraform_path
        title = terraform_path.name

    try:
        # Parse Terraform files
        if args.verbose:
            print(f"Parsing Terraform files from {parse_path}...")

        # Determine state file path if provided
        state_file = None
        if args.use_state and args.use_state is not True:
            # User provided a specific file path
            state_file = args.use_state

        tf_parser = TerraformParser(
            str(terraform_path),
            str(icons_path) if icons_path else None,
            use_terraform_graph=args.use_graph,
            use_terraform_state=bool(args.use_state),
            state_file=state_file,
        )

        if args.environment:
            parse_result = tf_parser.parse_environment(args.environment)
        else:
            parse_result = tf_parser.parse_directory(parse_path)

        if args.verbose:
            print(f"Found {len(parse_result.resources)} raw resources")
            print(f"Found {len(parse_result.modules)} module calls")
            if args.use_graph and tf_parser.get_graph_result():
                graph = tf_parser.get_graph_result()
                print(f"Enhanced with terraform graph: {len(graph.edges)} edges")
            if args.use_state and tf_parser.get_state_result():
                state = tf_parser.get_state_result()
                print(f"Enhanced with terraform state: {len(state.resources)} resources")

        # Aggregate into logical services
        if args.verbose:
            print("Aggregating into logical services...")

        aggregator = ResourceAggregator()
        aggregated = aggregator.aggregate(
            parse_result,
            terraform_dir=parse_path,
            state_result=tf_parser.get_state_result(),
        )

        if args.verbose:
            print(f"Created {len(aggregated.services)} logical services:")
            for service in aggregated.services:
                print(f"  - {service.name}: {len(service.resources)} resources (count: {service.count})")
            print(f"Created {len(aggregated.connections)} logical connections")
            if aggregated.vpc_structure:
                vpc = aggregated.vpc_structure
                print(f"VPC Structure: {vpc.name}")
                print(f"  - {len(vpc.availability_zones)} Availability Zones")
                for az in vpc.availability_zones:
                    print(f"    - {az.name}: {len(az.subnets)} subnets")
                print(f"  - {len(vpc.endpoints)} VPC Endpoints")

        # Setup layout (config is now responsive and scaled based on content)
        base_config = LayoutConfig()
        layout_engine = LayoutEngine(base_config)
        positions, groups = layout_engine.compute_layout(aggregated)

        # Get the scaled config and calculated height from the layout engine
        responsive_config = layout_engine.config
        actual_height = layout_engine._estimate_required_height(aggregated)

        if args.verbose:
            print(f"Positioned {len(positions)} services")
            print(f"Canvas: {responsive_config.canvas_width}x{actual_height} (scale: {layout_engine._compute_responsive_scale(aggregated):.2f})")

        # Setup renderers with the responsive config
        icon_mapper = IconMapper(str(icons_path) if icons_path else None)
        svg_renderer = SVGRenderer(icon_mapper, responsive_config)
        html_renderer = HTMLRenderer(svg_renderer)

        # Generate HTML with actual calculated height
        if args.verbose:
            print("Generating HTML output...")

        html_content = html_renderer.render_html(
            aggregated, positions, groups,
            environment=args.environment or title,
            actual_height=actual_height
        )

        # Write output
        output_path = Path(args.output)
        output_path.write_text(html_content, encoding='utf-8')

        print(f"Diagram generated: {output_path.absolute()}")
        print("\nSummary:")
        print(f"  Services: {len(aggregated.services)}")
        print(f"  Resources: {sum(len(s.resources) for s in aggregated.services)}")
        print(f"  Connections: {len(aggregated.connections)}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
