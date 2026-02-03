#!/usr/bin/env python3
"""
terraformgraph - Terraform Diagram Generator

Generates AWS infrastructure diagrams from Terraform code using official AWS icons.
Creates high-level architectural diagrams with logical service groupings.

PREREQUISITES:
    Before using terraformgraph, run these commands in your Terraform directory:

    cd ./infrastructure
    terraform init
    terraform apply   # or terraform plan for undeployed infrastructure

Usage:
    # Generate diagram (auto-generates state JSON if needed)
    terraformgraph -t ./infrastructure

    # With pre-generated state file
    terraformgraph -t ./infrastructure --state-file state.json

    # With specific environment subdirectory
    terraformgraph -t ./infrastructure -e prod

    # With custom output path
    terraformgraph -t ./infrastructure -o my-diagram.html
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .aggregator import ResourceAggregator
from .icons import IconMapper
from .layout import LayoutConfig, LayoutEngine
from .parser import TerraformParser
from .renderer import HTMLRenderer, SVGRenderer
from .terraform_tools import TerraformToolsRunner

# File name for auto-generated state cache
STATE_CACHE_FILE = ".terraformgraph-state.json"


def _generate_state_json(terraform_dir: Path, verbose: bool = False) -> Path:
    """Generate state JSON from terraform show -json.

    Args:
        terraform_dir: Path to terraform directory
        verbose: Print progress messages

    Returns:
        Path to the generated JSON file

    Raises:
        RuntimeError: If terraform is not available or not initialized
    """
    runner = TerraformToolsRunner(terraform_dir)

    if not runner.check_terraform_available():
        raise RuntimeError(
            "Terraform CLI not found in PATH.\n"
            "Please install Terraform: https://developer.hashicorp.com/terraform/install"
        )

    if not runner.check_initialized():
        raise RuntimeError(
            f"Terraform not initialized in {terraform_dir}.\n"
            f"Please run: cd {terraform_dir} && terraform init"
        )

    if verbose:
        print("Generating state JSON from terraform show -json...")

    try:
        result = subprocess.run(
            ["terraform", "show", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(f"terraform show -json failed: {result.stderr}")

        if not result.stdout.strip():
            raise RuntimeError(
                "No terraform state found.\n"
                f"Please run: cd {terraform_dir} && terraform apply (or terraform plan)"
            )

        # Validate JSON
        try:
            json_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from terraform show: {e}")

        # Save to cache file
        cache_file = terraform_dir / STATE_CACHE_FILE
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)

        if verbose:
            print(f"State cached to {cache_file}")

        return cache_file

    except subprocess.TimeoutExpired:
        raise RuntimeError("terraform show -json timed out after 120 seconds")
    except OSError as e:
        raise RuntimeError(f"Error running terraform: {e}")


def _get_state_file(
    terraform_dir: Path, state_file_arg: Optional[str], verbose: bool = False
) -> Path:
    """Determine which state file to use.

    Priority:
    1. User-specified --state-file argument
    2. Existing .terraformgraph-state.json cache
    3. Existing plan.json or state.json in terraform dir
    4. Auto-generate from terraform show -json

    Args:
        terraform_dir: Path to terraform directory
        state_file_arg: User-provided state file path (or None)
        verbose: Print progress messages

    Returns:
        Path to the state file to use

    Raises:
        RuntimeError: If state cannot be obtained
    """
    # 1. User-specified file
    if state_file_arg:
        state_path = Path(state_file_arg)
        if not state_path.exists():
            raise RuntimeError(f"State file not found: {state_path}")
        if verbose:
            print(f"Using specified state file: {state_path}")
        return state_path

    # 2. Check for cached state file
    cache_file = terraform_dir / STATE_CACHE_FILE
    if cache_file.exists():
        if verbose:
            print(f"Using cached state: {cache_file}")
        return cache_file

    # 3. Check for existing JSON files in terraform dir
    for filename in ["plan.json", "state.json", "terraform.tfstate.json"]:
        json_file = terraform_dir / filename
        if json_file.exists():
            if verbose:
                print(f"Using existing state file: {json_file}")
            return json_file

    # 4. Auto-generate from terraform
    return _generate_state_json(terraform_dir, verbose)


def main():
    parser = argparse.ArgumentParser(
        description="Generate AWS infrastructure diagrams from Terraform code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prerequisites:
    Before running terraformgraph, ensure your Terraform is initialized:

    cd ./infrastructure
    terraform init
    terraform apply   # or terraform plan

Examples:
    # Generate diagram (auto-generates state if needed)
    terraformgraph -t ./infrastructure

    # With pre-generated state file
    terraform show -json > state.json
    terraformgraph -t ./infrastructure --state-file state.json

    # With specific environment subdirectory
    terraformgraph -t ./infrastructure -e prod

    # With custom icons path
    terraformgraph -t ./infrastructure -i /path/to/aws-icons
        """,
    )

    parser.add_argument(
        "-t", "--terraform", required=True, help="Path to the Terraform infrastructure directory"
    )

    parser.add_argument(
        "-e",
        "--environment",
        help="Environment name (dev, staging, prod). If not provided, parses the terraform directory directly.",
        default=None,
    )

    parser.add_argument(
        "-i",
        "--icons",
        help="Path to AWS icons directory (auto-discovers in ./aws-official-icons, ~/aws-official-icons, ~/.terraformgraph/icons)",
        default=None,
    )

    parser.add_argument(
        "-o",
        "--output",
        default="terraformgraph.html",
        help="Output file path (HTML). Default: terraformgraph.html",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    parser.add_argument(
        "--state-file",
        "-s",
        metavar="FILE",
        help="Path to terraform state JSON file (from 'terraform show -json'). If not provided, auto-generates from terraform CLI.",
    )

    parser.add_argument(
        "--refresh-state",
        action="store_true",
        help="Force regeneration of state JSON even if cached file exists.",
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
        print(
            f"Warning: Icons path not found: {icons_path}. Using fallback colors.", file=sys.stderr
        )
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
            available = [
                d.name
                for d in terraform_path.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            print(f"Available environments: {available}", file=sys.stderr)
            sys.exit(1)
    else:
        # Direct mode: terraform_path is the folder to parse
        parse_path = terraform_path
        title = terraform_path.name

    try:
        # Delete cached state if --refresh-state is specified
        if args.refresh_state:
            cache_file = parse_path / STATE_CACHE_FILE
            if cache_file.exists():
                cache_file.unlink()
                if args.verbose:
                    print(f"Removed cached state: {cache_file}")

        # Get state file (auto-generates if needed)
        state_file = _get_state_file(parse_path, args.state_file, args.verbose)

        # Parse Terraform files
        if args.verbose:
            print(f"Parsing Terraform files from {parse_path}...")

        tf_parser = TerraformParser(
            str(terraform_path),
            use_terraform_state=True,
            state_file=str(state_file),
        )

        if args.environment:
            parse_result = tf_parser.parse_environment(args.environment)
        else:
            parse_result = tf_parser.parse_directory(parse_path)

        if args.verbose:
            print(f"Found {len(parse_result.resources)} raw resources")
            print(f"Found {len(parse_result.modules)} module calls")
            if tf_parser.get_state_result():
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
                print(
                    f"  - {service.name}: {len(service.resources)} resources (count: {service.count})"
                )
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
        positions, groups, actual_height = layout_engine.compute_layout(aggregated)

        # Get the scaled config from the layout engine
        responsive_config = layout_engine.config

        if args.verbose:
            print(f"Positioned {len(positions)} services")
            print(
                f"Canvas: {responsive_config.canvas_width}x{actual_height} (scale: {layout_engine._compute_responsive_scale(aggregated):.2f})"
            )

        # Setup renderers with the responsive config
        icon_mapper = IconMapper(str(icons_path) if icons_path else None)
        svg_renderer = SVGRenderer(icon_mapper, responsive_config)
        html_renderer = HTMLRenderer(svg_renderer)

        # Generate HTML with actual calculated height
        if args.verbose:
            print("Generating HTML output...")

        html_content = html_renderer.render_html(
            aggregated,
            positions,
            groups,
            environment=args.environment or title,
            actual_height=actual_height,
        )

        # Write output
        output_path = Path(args.output)
        output_path.write_text(html_content, encoding="utf-8")

        print(f"Diagram generated: {output_path.absolute()}")
        print("\nSummary:")
        print(f"  Services: {len(aggregated.services)}")
        print(f"  Resources: {sum(len(s.resources) for s in aggregated.services)}")
        print(f"  Connections: {len(aggregated.connections)}")

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
