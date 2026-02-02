"""Tests for VPC Structure data models and VPCStructureBuilder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from terraformgraph.parser import TerraformResource


class TestSubnetDataclass:
    """Tests for Subnet dataclass."""

    def test_subnet_creation_with_required_fields(self):
        """Test creating Subnet with required fields."""
        from terraformgraph.aggregator import Subnet

        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )

        assert subnet.resource_id == "aws_subnet.public_a"
        assert subnet.name == "public-a"
        assert subnet.subnet_type == "public"
        assert subnet.availability_zone == "us-east-1a"
        assert subnet.cidr_block is None

    def test_subnet_creation_with_cidr_block(self):
        """Test creating Subnet with optional cidr_block."""
        from terraformgraph.aggregator import Subnet

        subnet = Subnet(
            resource_id="aws_subnet.private_a",
            name="private-a",
            subnet_type="private",
            availability_zone="us-east-1a",
            cidr_block="10.0.1.0/24",
        )

        assert subnet.cidr_block == "10.0.1.0/24"


class TestAvailabilityZoneDataclass:
    """Tests for AvailabilityZone dataclass."""

    def test_availability_zone_creation(self):
        """Test creating AvailabilityZone with required fields."""
        from terraformgraph.aggregator import AvailabilityZone, Subnet

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

        assert az.name == "us-east-1a"
        assert az.short_name == "1a"
        assert len(az.subnets) == 1
        assert az.subnets[0].name == "public-a"

    def test_availability_zone_empty_subnets(self):
        """Test creating AvailabilityZone with empty subnets list."""
        from terraformgraph.aggregator import AvailabilityZone

        az = AvailabilityZone(
            name="us-east-1b",
            short_name="1b",
            subnets=[],
        )

        assert az.subnets == []


class TestVPCEndpointDataclass:
    """Tests for VPCEndpoint dataclass."""

    def test_vpc_endpoint_creation(self):
        """Test creating VPCEndpoint with required fields."""
        from terraformgraph.aggregator import VPCEndpoint

        endpoint = VPCEndpoint(
            resource_id="aws_vpc_endpoint.s3",
            name="s3-endpoint",
            endpoint_type="gateway",
            service="s3",
        )

        assert endpoint.resource_id == "aws_vpc_endpoint.s3"
        assert endpoint.name == "s3-endpoint"
        assert endpoint.endpoint_type == "gateway"
        assert endpoint.service == "s3"


class TestVPCStructureDataclass:
    """Tests for VPCStructure dataclass."""

    def test_vpc_structure_creation(self):
        """Test creating VPCStructure with required fields."""
        from terraformgraph.aggregator import (
            AvailabilityZone,
            Subnet,
            VPCEndpoint,
            VPCStructure,
        )

        subnet = Subnet(
            resource_id="aws_subnet.public_a",
            name="public-a",
            subnet_type="public",
            availability_zone="us-east-1a",
        )
        az = AvailabilityZone(name="us-east-1a", short_name="1a", subnets=[subnet])
        endpoint = VPCEndpoint(
            resource_id="aws_vpc_endpoint.s3",
            name="s3-endpoint",
            endpoint_type="gateway",
            service="s3",
        )

        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[az],
            endpoints=[endpoint],
        )

        assert vpc.vpc_id == "aws_vpc.main"
        assert vpc.name == "main-vpc"
        assert len(vpc.availability_zones) == 1
        assert len(vpc.endpoints) == 1

    def test_vpc_structure_empty_lists(self):
        """Test creating VPCStructure with empty lists."""
        from terraformgraph.aggregator import VPCStructure

        vpc = VPCStructure(
            vpc_id="aws_vpc.empty",
            name="empty-vpc",
            availability_zones=[],
            endpoints=[],
        )

        assert vpc.availability_zones == []
        assert vpc.endpoints == []


class TestVPCStructureBuilderAZDetection:
    """Tests for VPCStructureBuilder AZ detection logic."""

    def test_detect_az_from_availability_zone_attribute(self):
        """Test detecting AZ from availability_zone attribute."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public_a",
            module_path="",
            attributes={"availability_zone": "us-east-1a"},
            source_file="main.tf",
        )

        az = builder._detect_availability_zone(resource)
        assert az == "us-east-1a"

    def test_detect_az_from_name_suffix_a(self):
        """Test detecting AZ from name ending with -a."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public_a",
            module_path="",
            attributes={"name": "prod-public-a"},
            source_file="main.tf",
        )

        az = builder._detect_availability_zone(resource)
        assert az is not None
        assert az.endswith("a")

    def test_detect_az_from_name_suffix_1a(self):
        """Test detecting AZ from name ending with -1a."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public_1a",
            module_path="",
            attributes={"name": "prod-public-1a"},
            source_file="main.tf",
        )

        az = builder._detect_availability_zone(resource)
        assert az is not None
        assert "1a" in az or az.endswith("a")

    def test_detect_az_from_name_suffix_az1(self):
        """Test detecting AZ from name containing -az1."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public_az1",
            module_path="",
            attributes={"name": "prod-public-az1"},
            source_file="main.tf",
        )

        az = builder._detect_availability_zone(resource)
        assert az is not None

    def test_detect_az_returns_none_for_unknown(self):
        """Test that unknown AZ patterns return None."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public",
            module_path="",
            attributes={"name": "prod-public"},
            source_file="main.tf",
        )

        az = builder._detect_availability_zone(resource)
        assert az is None


class TestVPCStructureBuilderSubnetTypeDetection:
    """Tests for VPCStructureBuilder subnet type detection."""

    def test_detect_public_subnet_from_name(self):
        """Test detecting public subnet type from name."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public_a",
            module_path="",
            attributes={"name": "prod-public-a"},
            source_file="main.tf",
        )

        subnet_type = builder._detect_subnet_type(resource)
        assert subnet_type == "public"

    def test_detect_private_subnet_from_name(self):
        """Test detecting private subnet type from name."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="private_a",
            module_path="",
            attributes={"name": "prod-private-a"},
            source_file="main.tf",
        )

        subnet_type = builder._detect_subnet_type(resource)
        assert subnet_type == "private"

    def test_detect_database_subnet_from_name(self):
        """Test detecting database subnet type from name."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="database_a",
            module_path="",
            attributes={"name": "prod-database-a"},
            source_file="main.tf",
        )

        subnet_type = builder._detect_subnet_type(resource)
        assert subnet_type == "database"

    def test_detect_db_subnet_from_name(self):
        """Test detecting database subnet type from 'db' in name."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="db_a",
            module_path="",
            attributes={"name": "prod-db-a"},
            source_file="main.tf",
        )

        subnet_type = builder._detect_subnet_type(resource)
        assert subnet_type == "database"

    def test_detect_subnet_type_from_tags(self):
        """Test detecting subnet type from tags."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="subnet_a",
            module_path="",
            attributes={
                "name": "prod-subnet-a",
                "tags": {"Type": "public"},
            },
            source_file="main.tf",
        )

        subnet_type = builder._detect_subnet_type(resource)
        assert subnet_type == "public"

    def test_detect_unknown_subnet_type(self):
        """Test that unknown subnet types default to 'unknown'."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="subnet_a",
            module_path="",
            attributes={"name": "prod-something-a"},
            source_file="main.tf",
        )

        subnet_type = builder._detect_subnet_type(resource)
        assert subnet_type == "unknown"


class TestVPCStructureBuilderEndpointDetection:
    """Tests for VPCStructureBuilder endpoint detection."""

    def test_detect_gateway_endpoint_type(self):
        """Test detecting gateway endpoint type."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="s3",
            module_path="",
            attributes={"vpc_endpoint_type": "Gateway"},
            source_file="main.tf",
        )

        endpoint_type = builder._detect_endpoint_type(resource)
        assert endpoint_type == "gateway"

    def test_detect_interface_endpoint_type(self):
        """Test detecting interface endpoint type."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="ecr_api",
            module_path="",
            attributes={"vpc_endpoint_type": "Interface"},
            source_file="main.tf",
        )

        endpoint_type = builder._detect_endpoint_type(resource)
        assert endpoint_type == "interface"

    def test_detect_endpoint_type_default(self):
        """Test default endpoint type is interface when not specified."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="ecr_api",
            module_path="",
            attributes={},
            source_file="main.tf",
        )

        endpoint_type = builder._detect_endpoint_type(resource)
        assert endpoint_type == "interface"

    def test_detect_endpoint_service_s3(self):
        """Test detecting S3 service from endpoint."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="s3",
            module_path="",
            attributes={"service_name": "com.amazonaws.us-east-1.s3"},
            source_file="main.tf",
        )

        service = builder._detect_endpoint_service(resource)
        assert service == "s3"

    def test_detect_endpoint_service_dynamodb(self):
        """Test detecting DynamoDB service from endpoint."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="dynamodb",
            module_path="",
            attributes={"service_name": "com.amazonaws.us-east-1.dynamodb"},
            source_file="main.tf",
        )

        service = builder._detect_endpoint_service(resource)
        assert service == "dynamodb"

    def test_detect_endpoint_service_ecr_api(self):
        """Test detecting ECR API service from endpoint."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="ecr_api",
            module_path="",
            attributes={"service_name": "com.amazonaws.us-east-1.ecr.api"},
            source_file="main.tf",
        )

        service = builder._detect_endpoint_service(resource)
        assert service == "ecr.api"

    def test_detect_endpoint_service_unknown(self):
        """Test detecting unknown service from endpoint."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resource = TerraformResource(
            resource_type="aws_vpc_endpoint",
            resource_name="unknown",
            module_path="",
            attributes={},
            source_file="main.tf",
        )

        service = builder._detect_endpoint_service(resource)
        assert service == "unknown"


class TestVPCStructureBuilderBuild:
    """Tests for VPCStructureBuilder.build() method."""

    def test_build_empty_resources(self):
        """Test building VPC structure from empty resources list."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        result = builder.build([])

        assert result is None

    def test_build_no_vpc(self):
        """Test building VPC structure when no VPC resource exists."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resources = [
            TerraformResource(
                resource_type="aws_s3_bucket",
                resource_name="main",
                module_path="",
                attributes={},
                source_file="main.tf",
            )
        ]

        result = builder.build(resources)
        assert result is None

    def test_build_vpc_with_subnets(self):
        """Test building VPC structure with subnets."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resources = [
            TerraformResource(
                resource_type="aws_vpc",
                resource_name="main",
                module_path="",
                attributes={"name": "main-vpc"},
                source_file="main.tf",
            ),
            TerraformResource(
                resource_type="aws_subnet",
                resource_name="public_a",
                module_path="",
                attributes={
                    "name": "public-a",
                    "availability_zone": "us-east-1a",
                    "cidr_block": "10.0.1.0/24",
                },
                source_file="main.tf",
            ),
            TerraformResource(
                resource_type="aws_subnet",
                resource_name="public_b",
                module_path="",
                attributes={
                    "name": "public-b",
                    "availability_zone": "us-east-1b",
                    "cidr_block": "10.0.2.0/24",
                },
                source_file="main.tf",
            ),
        ]

        result = builder.build(resources)

        assert result is not None
        assert result.vpc_id == "aws_vpc.main"
        assert len(result.availability_zones) == 2

        az_names = [az.name for az in result.availability_zones]
        assert "us-east-1a" in az_names
        assert "us-east-1b" in az_names

    def test_build_vpc_with_endpoints(self):
        """Test building VPC structure with endpoints."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resources = [
            TerraformResource(
                resource_type="aws_vpc",
                resource_name="main",
                module_path="",
                attributes={"name": "main-vpc"},
                source_file="main.tf",
            ),
            TerraformResource(
                resource_type="aws_vpc_endpoint",
                resource_name="s3",
                module_path="",
                attributes={
                    "service_name": "com.amazonaws.us-east-1.s3",
                    "vpc_endpoint_type": "Gateway",
                },
                source_file="main.tf",
            ),
        ]

        result = builder.build(resources)

        assert result is not None
        assert len(result.endpoints) == 1
        assert result.endpoints[0].service == "s3"
        assert result.endpoints[0].endpoint_type == "gateway"

    def test_build_vpc_multiple_subnets_same_az(self):
        """Test building VPC with multiple subnets in same AZ."""
        from terraformgraph.aggregator import VPCStructureBuilder

        builder = VPCStructureBuilder()
        resources = [
            TerraformResource(
                resource_type="aws_vpc",
                resource_name="main",
                module_path="",
                attributes={"name": "main-vpc"},
                source_file="main.tf",
            ),
            TerraformResource(
                resource_type="aws_subnet",
                resource_name="public_a",
                module_path="",
                attributes={
                    "name": "public-a",
                    "availability_zone": "us-east-1a",
                },
                source_file="main.tf",
            ),
            TerraformResource(
                resource_type="aws_subnet",
                resource_name="private_a",
                module_path="",
                attributes={
                    "name": "private-a",
                    "availability_zone": "us-east-1a",
                },
                source_file="main.tf",
            ),
        ]

        result = builder.build(resources)

        assert result is not None
        assert len(result.availability_zones) == 1
        az = result.availability_zones[0]
        assert len(az.subnets) == 2

    def test_build_with_resolver(self, tmp_path):
        """Test building VPC structure with variable resolver."""
        from terraformgraph.aggregator import VPCStructureBuilder
        from terraformgraph.variable_resolver import VariableResolver

        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('vpc_name = "resolved-vpc"\n')
        resolver = VariableResolver(tmp_path)

        builder = VPCStructureBuilder()
        resources = [
            TerraformResource(
                resource_type="aws_vpc",
                resource_name="main",
                module_path="",
                attributes={"name": "${var.vpc_name}"},
                source_file="main.tf",
            ),
        ]

        result = builder.build(resources, resolver=resolver)

        assert result is not None
        assert result.name == "resolved-vpc"


class TestAggregatedResultVPCStructure:
    """Tests for AggregatedResult with vpc_structure field."""

    def test_aggregated_result_has_vpc_structure_field(self):
        """Test that AggregatedResult has vpc_structure field."""
        from terraformgraph.aggregator import AggregatedResult

        result = AggregatedResult()
        assert hasattr(result, "vpc_structure")
        assert result.vpc_structure is None

    def test_aggregated_result_with_vpc_structure(self):
        """Test creating AggregatedResult with VPCStructure."""
        from terraformgraph.aggregator import AggregatedResult, VPCStructure

        vpc = VPCStructure(
            vpc_id="aws_vpc.main",
            name="main-vpc",
            availability_zones=[],
            endpoints=[],
        )

        result = AggregatedResult(vpc_structure=vpc)
        assert result.vpc_structure is not None
        assert result.vpc_structure.name == "main-vpc"


class TestResourceAggregatorWithTerraformDir:
    """Tests for ResourceAggregator.aggregate() with terraform_dir parameter."""

    def test_aggregate_without_terraform_dir(self):
        """Test that aggregate works without terraform_dir."""
        from terraformgraph.aggregator import ResourceAggregator
        from terraformgraph.parser import ParseResult, TerraformResource

        aggregator = ResourceAggregator()
        parse_result = ParseResult(
            resources=[
                TerraformResource(
                    resource_type="aws_vpc",
                    resource_name="main",
                    module_path="",
                    attributes={"name": "main-vpc"},
                    source_file="main.tf",
                ),
            ]
        )

        result = aggregator.aggregate(parse_result)

        # Should work without vpc_structure when no terraform_dir
        assert result is not None

    def test_aggregate_with_terraform_dir(self, tmp_path):
        """Test that aggregate builds VPC structure when terraform_dir provided."""
        from terraformgraph.aggregator import ResourceAggregator
        from terraformgraph.parser import ParseResult, TerraformResource

        # Create a simple tfvars file
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('vpc_name = "resolved-vpc"\n')

        aggregator = ResourceAggregator()
        parse_result = ParseResult(
            resources=[
                TerraformResource(
                    resource_type="aws_vpc",
                    resource_name="main",
                    module_path="",
                    attributes={"name": "${var.vpc_name}"},
                    source_file="main.tf",
                ),
                TerraformResource(
                    resource_type="aws_subnet",
                    resource_name="public_a",
                    module_path="",
                    attributes={
                        "name": "public-a",
                        "availability_zone": "us-east-1a",
                    },
                    source_file="main.tf",
                ),
            ]
        )

        result = aggregator.aggregate(parse_result, terraform_dir=tmp_path)

        assert result.vpc_structure is not None
        assert result.vpc_structure.name == "resolved-vpc"
        assert len(result.vpc_structure.availability_zones) == 1


class TestVPCStructureBuilderPatterns:
    """Tests for VPCStructureBuilder pattern constants."""

    def test_az_patterns_exist(self):
        """Test that AZ_PATTERNS constant exists."""
        from terraformgraph.aggregator import VPCStructureBuilder

        assert hasattr(VPCStructureBuilder, "AZ_PATTERNS")
        assert isinstance(VPCStructureBuilder.AZ_PATTERNS, list)
        assert len(VPCStructureBuilder.AZ_PATTERNS) > 0

    def test_subnet_type_patterns_exist(self):
        """Test that SUBNET_TYPE_PATTERNS constant exists."""
        from terraformgraph.aggregator import VPCStructureBuilder

        assert hasattr(VPCStructureBuilder, "SUBNET_TYPE_PATTERNS")
        assert isinstance(VPCStructureBuilder.SUBNET_TYPE_PATTERNS, dict)
        assert "public" in VPCStructureBuilder.SUBNET_TYPE_PATTERNS
        assert "private" in VPCStructureBuilder.SUBNET_TYPE_PATTERNS
        assert "database" in VPCStructureBuilder.SUBNET_TYPE_PATTERNS
