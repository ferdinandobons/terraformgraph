"""Tests for parser module."""

from pathlib import Path

import pytest

from terraformgraph.parser import (
    ParseResult,
    TerraformParser,
    TerraformResource,
)


class TestTerraformResource:
    """Tests for TerraformResource dataclass."""

    def test_full_id_simple(self):
        """Test full_id for simple resource."""
        resource = TerraformResource(
            resource_type="aws_vpc",
            resource_name="main",
            module_path="",
            attributes={"cidr_block": "10.0.0.0/16"},
            source_file="main.tf",
        )
        assert resource.full_id == "aws_vpc.main"

    def test_full_id_with_module(self):
        """Test full_id with module path."""
        resource = TerraformResource(
            resource_type="aws_subnet",
            resource_name="public",
            module_path="module.network",
            attributes={},
            source_file="main.tf",
        )
        assert resource.full_id == "module.network.aws_subnet.public"

    def test_display_name_from_attributes(self):
        """Test display_name uses name attribute."""
        resource = TerraformResource(
            resource_type="aws_s3_bucket",
            resource_name="logs",
            module_path="",
            attributes={"name": "my-logs-bucket"},
            source_file="main.tf",
        )
        assert resource.display_name == "my-logs-bucket"

    def test_display_name_fallback(self):
        """Test display_name falls back to resource_name."""
        resource = TerraformResource(
            resource_type="aws_vpc",
            resource_name="main",
            module_path="",
            attributes={},
            source_file="main.tf",
        )
        assert resource.display_name == "main"


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_default_values(self):
        """Test default empty collections."""
        result = ParseResult()
        assert result.resources == []
        assert result.relationships == []
        assert result.modules == []


class TestTerraformParser:
    """Tests for TerraformParser class."""

    def test_parse_empty_directory(self, tmp_path):
        """Test parsing directory with no .tf files."""
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)
        assert result.resources == []

    def test_parse_simple_resource(self, tmp_path):
        """Test parsing a simple resource definition."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "main-vpc"
  }
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 1
        resource = result.resources[0]
        assert resource.resource_type == "aws_vpc"
        assert resource.resource_name == "main"
        assert resource.attributes.get("cidr_block") == "10.0.0.0/16"

    def test_parse_multiple_resources(self, tmp_path):
        """Test parsing multiple resources."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}

resource "aws_subnet" "private" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.2.0/24"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 3
        types = {r.resource_type for r in result.resources}
        assert "aws_vpc" in types
        assert "aws_subnet" in types

    def test_parse_resource_with_count(self, tmp_path):
        """Test parsing resource with count meta-argument."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
resource "aws_subnet" "private" {
  count      = 3
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.${count.index}.0/24"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 1
        resource = result.resources[0]
        assert resource.count == 3

    def test_parse_resource_with_for_each(self, tmp_path):
        """Test parsing resource with for_each meta-argument."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
resource "aws_s3_bucket" "buckets" {
  for_each = toset(["logs", "data", "backup"])
  bucket   = "my-${each.value}-bucket"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 1
        resource = result.resources[0]
        assert resource.for_each is True

    def test_parse_multiple_files(self, tmp_path):
        """Test parsing multiple .tf files in directory."""
        vpc_file = tmp_path / "vpc.tf"
        vpc_file.write_text(
            """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
"""
        )
        ec2_file = tmp_path / "ec2.tf"
        ec2_file.write_text(
            """
resource "aws_instance" "web" {
  ami           = "ami-12345"
  instance_type = "t2.micro"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 2
        types = {r.resource_type for r in result.resources}
        assert "aws_vpc" in types
        assert "aws_instance" in types

    def test_parse_invalid_hcl(self, tmp_path):
        """Test graceful handling of invalid HCL."""
        tf_file = tmp_path / "invalid.tf"
        tf_file.write_text(
            """
resource "aws_vpc" "main" {
  this is not valid HCL
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        # Should not raise, just log warning and continue
        result = parser.parse_directory(tmp_path)
        assert result.resources == []

    def test_parse_data_source(self, tmp_path):
        """Test that data sources are not parsed as resources."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t2.micro"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        # Only the resource should be parsed, not the data source
        assert len(result.resources) == 1
        assert result.resources[0].resource_type == "aws_instance"

    def test_parse_module_reference(self, tmp_path):
        """Test parsing module blocks."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
module "vpc" {
  source = "./modules/vpc"

  cidr_block = "10.0.0.0/16"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.modules) == 1
        assert result.modules[0].name == "vpc"
        assert result.modules[0].source == "./modules/vpc"

    def test_parse_nonexistent_directory(self, tmp_path):
        """Test error handling for nonexistent directory."""
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        with pytest.raises(ValueError, match="does not exist"):
            parser.parse_directory(Path("/nonexistent/path"))

    def test_parse_locals_block(self, tmp_path):
        """Test that locals blocks don't cause errors."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
locals {
  common_tags = {
    Environment = "production"
  }
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags       = local.common_tags
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 1
        assert result.resources[0].resource_type == "aws_vpc"

    def test_parse_variable_block(self, tmp_path):
        """Test that variable blocks don't cause errors."""
        variables_file = tmp_path / "variables.tf"
        variables_file.write_text(
            """
variable "environment" {
  type        = string
  default     = "production"
  description = "Environment name"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}
"""
        )
        main_file = tmp_path / "main.tf"
        main_file.write_text(
            """
resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 1

    def test_parse_output_block(self, tmp_path):
        """Test that output blocks don't cause errors."""
        tf_file = tmp_path / "outputs.tf"
        tf_file.write_text(
            """
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}
"""
        )
        main_file = tmp_path / "main.tf"
        main_file.write_text(
            """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 1


class TestTerraformParserRelationships:
    """Tests for relationship extraction in TerraformParser."""

    def test_extract_vpc_reference(self, tmp_path):
        """Test extracting VPC reference from subnet."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        # Check that relationships were extracted
        assert len(result.resources) == 2

        # Find the subnet resource
        subnet = next(r for r in result.resources if r.resource_type == "aws_subnet")
        assert "vpc_id" in subnet.attributes

    def test_extract_security_group_reference(self, tmp_path):
        """Test extracting security group reference."""
        tf_file = tmp_path / "main.tf"
        tf_file.write_text(
            """
resource "aws_security_group" "web" {
  name = "web-sg"
}

resource "aws_instance" "web" {
  ami                    = "ami-12345"
  instance_type          = "t2.micro"
  vpc_security_group_ids = [aws_security_group.web.id]
}
"""
        )
        parser = TerraformParser(infrastructure_path=str(tmp_path))
        result = parser.parse_directory(tmp_path)

        assert len(result.resources) == 2
