"""Tests for the Layout Engine with VPC structure support."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from terraformgraph.aggregator import (
    AggregatedResult,
    AvailabilityZone,
    LogicalService,
    Subnet,
    VPCEndpoint,
    VPCStructure,
)
from terraformgraph.layout import LayoutConfig, LayoutEngine, Position, ServiceGroup


class TestLayoutEngine:
    """Tests for LayoutEngine basic functionality."""

    def test_layout_engine_creation(self):
        """Test creating a LayoutEngine with default config."""
        engine = LayoutEngine()
        assert engine.config is not None
        assert engine.config.canvas_width == 1400
        assert engine.config.canvas_height == 900

    def test_layout_engine_custom_config(self):
        """Test creating a LayoutEngine with custom config."""
        config = LayoutConfig(canvas_width=1600, canvas_height=1000)
        engine = LayoutEngine(config)
        assert engine.config.canvas_width == 1600
        assert engine.config.canvas_height == 1000

    def test_compute_layout_empty_services(self):
        """Test compute_layout with no services."""
        engine = LayoutEngine()
        aggregated = AggregatedResult(services=[], connections=[])

        positions, groups = engine.compute_layout(aggregated)

        assert isinstance(positions, dict)
        assert isinstance(groups, list)
        # Should have at least AWS Cloud and VPC groups
        assert len(groups) >= 2


class TestComputeVPCHeight:
    """Tests for _compute_vpc_height method."""

    def test_vpc_height_with_no_structure(self):
        """Test VPC height returns default when no structure."""
        engine = LayoutEngine()
        height = engine._compute_vpc_height(None)
        assert height == 180

    def test_vpc_height_with_empty_azs(self):
        """Test VPC height with empty availability zones."""
        engine = LayoutEngine()
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[],
            endpoints=[],
        )
        height = engine._compute_vpc_height(vpc)
        assert height == 180

    def test_vpc_height_with_one_subnet(self):
        """Test VPC height with one subnet in one AZ."""
        engine = LayoutEngine()
        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[subnet],
        )
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[],
        )

        height = engine._compute_vpc_height(vpc)
        assert height >= 180  # Should be at least default

    def test_vpc_height_with_multiple_subnets(self):
        """Test VPC height increases with more subnets."""
        engine = LayoutEngine()

        # Create 3 subnets
        subnets = []
        for i, stype in enumerate(["public", "private", "database"]):
            subnets.append(
                Subnet(
                    resource_id=f"aws_subnet.{stype}_a",
                    name=f"{stype}-a",
                    subnet_type=stype,
                    availability_zone="us-east-1a",
                )
            )

        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=subnets,
        )
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[],
        )

        height = engine._compute_vpc_height(vpc)
        # Should be taller with 3 subnets
        assert height > 180


class TestLayoutVPCStructure:
    """Tests for _layout_vpc_structure method."""

    def test_layout_vpc_structure_with_none(self):
        """Test _layout_vpc_structure handles None gracefully."""
        engine = LayoutEngine()
        positions = {}
        groups = []
        vpc_pos = Position(x=100, y=100, width=800, height=300)

        # Should not raise
        engine._layout_vpc_structure(None, vpc_pos, positions, groups)

        assert len(positions) == 0
        assert len(groups) == 0

    def test_layout_vpc_structure_with_empty_azs(self):
        """Test _layout_vpc_structure with no AZs."""
        engine = LayoutEngine()
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[],
            endpoints=[],
        )
        positions = {}
        groups = []
        vpc_pos = Position(x=100, y=100, width=800, height=300)

        engine._layout_vpc_structure(vpc, vpc_pos, positions, groups)

        assert len(positions) == 0
        assert len(groups) == 0

    def test_layout_vpc_structure_creates_az_groups(self):
        """Test that AZ groups are created for each availability zone."""
        engine = LayoutEngine()
        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[subnet],
        )
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[],
        )
        positions = {}
        groups = []
        vpc_pos = Position(x=100, y=100, width=800, height=300)

        engine._layout_vpc_structure(vpc, vpc_pos, positions, groups)

        assert len(groups) == 1
        assert groups[0].group_type == "az"
        assert groups[0].name == "AZ 1a"

    def test_layout_vpc_structure_positions_subnets(self):
        """Test that subnets get positions."""
        engine = LayoutEngine()
        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[subnet],
        )
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[],
        )
        positions = {}
        groups = []
        vpc_pos = Position(x=100, y=100, width=800, height=300)

        engine._layout_vpc_structure(vpc, vpc_pos, positions, groups)

        assert "aws_subnet.public_a" in positions
        pos = positions["aws_subnet.public_a"]
        assert pos.x >= vpc_pos.x
        assert pos.y >= vpc_pos.y

    def test_layout_vpc_structure_positions_endpoints(self):
        """Test that VPC endpoints get positions on the right border."""
        engine = LayoutEngine()
        endpoint = VPCEndpoint(
            resource_id="aws_vpc_endpoint.s3",
            name="s3-endpoint",
            endpoint_type="gateway",
            service="s3",
        )
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[],
        )
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[endpoint],
        )
        positions = {}
        groups = []
        vpc_pos = Position(x=100, y=100, width=800, height=300)

        engine._layout_vpc_structure(vpc, vpc_pos, positions, groups)

        assert "aws_vpc_endpoint.s3" in positions
        pos = positions["aws_vpc_endpoint.s3"]
        # Endpoint should be near right edge
        assert pos.x > vpc_pos.x + vpc_pos.width / 2

    def test_layout_vpc_structure_multiple_azs(self):
        """Test layout with multiple availability zones."""
        engine = LayoutEngine()
        az1 = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[
                Subnet(
                    resource_id="aws_subnet.public_a",
                    name="public-a",
                    subnet_type="public",
                    availability_zone="us-east-1a",
                )
            ],
        )
        az2 = AvailabilityZone(
            name="us-east-1b",
            short_name="1b",
            subnets=[
                Subnet(
                    resource_id="aws_subnet.public_b",
                    name="public-b",
                    subnet_type="public",
                    availability_zone="us-east-1b",
                )
            ],
        )
        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az1, az2],
            endpoints=[],
        )
        positions = {}
        groups = []
        vpc_pos = Position(x=100, y=100, width=800, height=300)

        engine._layout_vpc_structure(vpc, vpc_pos, positions, groups)

        assert len(groups) == 2
        assert groups[0].name == "AZ 1a"
        assert groups[1].name == "AZ 1b"

        # AZ2 should be to the right of AZ1
        assert groups[1].position.x > groups[0].position.x


class TestLayoutSubnets:
    """Tests for _layout_subnets method."""

    def test_layout_subnets_empty(self):
        """Test _layout_subnets with no subnets."""
        engine = LayoutEngine()
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[],
        )
        positions = {}
        az_pos = Position(x=100, y=100, width=200, height=200)

        engine._layout_subnets(az, az_pos, positions)

        assert len(positions) == 0

    def test_layout_subnets_single(self):
        """Test _layout_subnets with one subnet."""
        engine = LayoutEngine()
        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[subnet],
        )
        positions = {}
        az_pos = Position(x=100, y=100, width=200, height=200)

        engine._layout_subnets(az, az_pos, positions)

        assert "aws_subnet.public_a" in positions
        pos = positions["aws_subnet.public_a"]
        assert pos.x >= az_pos.x
        assert pos.y >= az_pos.y
        assert pos.width <= az_pos.width

    def test_layout_subnets_multiple(self):
        """Test _layout_subnets with multiple subnets."""
        engine = LayoutEngine()
        subnets = [
            Subnet(
                resource_id="aws_subnet.public_a",
                name="public-a",
                subnet_type="public",
                availability_zone="us-east-1a",
            ),
            Subnet(
                resource_id="aws_subnet.private_a",
                name="private-a",
                subnet_type="private",
                availability_zone="us-east-1a",
            ),
        ]
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=subnets,
        )
        positions = {}
        az_pos = Position(x=100, y=100, width=200, height=200)

        engine._layout_subnets(az, az_pos, positions)

        assert "aws_subnet.public_a" in positions
        assert "aws_subnet.private_a" in positions

        # Second subnet should be below first
        pos1 = positions["aws_subnet.public_a"]
        pos2 = positions["aws_subnet.private_a"]
        assert pos2.y > pos1.y


class TestComputeLayoutWithVPCStructure:
    """Tests for compute_layout with vpc_structure."""

    def test_compute_layout_with_vpc_structure(self):
        """Test compute_layout includes VPC structure in layout."""
        engine = LayoutEngine()

        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )
        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=[subnet],
        )
        vpc_structure = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[],
        )

        aggregated = AggregatedResult(
            services=[],
            connections=[],
            vpc_structure=vpc_structure,
        )

        positions, groups = engine.compute_layout(aggregated)

        # Should have AWS Cloud, VPC, and AZ groups
        group_types = [g.group_type for g in groups]
        assert "aws_cloud" in group_types
        assert "vpc" in group_types
        assert "az" in group_types

        # Subnet should have position
        assert "aws_subnet.public_a" in positions

    def test_compute_layout_dynamic_vpc_height(self):
        """Test that VPC height adjusts based on subnet count."""
        engine = LayoutEngine()

        # Create 4 subnets
        subnets = []
        for i, stype in enumerate(["public", "private", "database", "extra"]):
            subnets.append(
                Subnet(
                    resource_id=f"aws_subnet.{stype}_a",
                    name=f"{stype}-a",
                    subnet_type=stype if stype != "extra" else "unknown",
                    availability_zone="us-east-1a",
                )
            )

        az = AvailabilityZone(
            name="us-east-1a",
            short_name="1a",
            subnets=subnets,
        )
        vpc_structure = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[],
        )

        aggregated = AggregatedResult(
            services=[],
            connections=[],
            vpc_structure=vpc_structure,
        )

        positions, groups = engine.compute_layout(aggregated)

        # Find VPC group
        vpc_group = next(g for g in groups if g.group_type == "vpc")

        # VPC height should be larger than default
        assert vpc_group.position.height > 180

    def test_compute_layout_without_vpc_structure(self):
        """Test compute_layout works without vpc_structure."""
        engine = LayoutEngine()
        aggregated = AggregatedResult(
            services=[],
            connections=[],
            vpc_structure=None,
        )

        positions, groups = engine.compute_layout(aggregated)

        # Should still work
        assert isinstance(positions, dict)
        assert isinstance(groups, list)

        # VPC group should have default height
        vpc_group = next(g for g in groups if g.group_type == "vpc")
        assert vpc_group.position.height == 180
