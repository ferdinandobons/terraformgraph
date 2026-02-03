"""Tests for terraform_tools module."""

import json
from pathlib import Path
from unittest.mock import patch

from terraformgraph.terraform_tools import (
    TerraformStateResource,
    TerraformToolsRunner,
    parse_state_json,
)


class TestTerraformStateResource:
    """Tests for TerraformStateResource dataclass."""

    def test_base_address_without_index(self):
        """Test base_address for resource without index."""
        resource = TerraformStateResource(
            address="aws_subnet.public",
            resource_type="aws_subnet",
            name="public",
            index=None,
            values={},
        )
        assert resource.base_address == "aws_subnet.public"

    def test_base_address_with_index(self):
        """Test base_address strips index."""
        resource = TerraformStateResource(
            address="aws_subnet.public[0]",
            resource_type="aws_subnet",
            name="public",
            index=0,
            values={},
        )
        assert resource.base_address == "aws_subnet.public"

    def test_base_address_with_string_index(self):
        """Test base_address strips string index (for_each)."""
        resource = TerraformStateResource(
            address='aws_subnet.public["us-east-1a"]',
            resource_type="aws_subnet",
            name="public",
            index="us-east-1a",
            values={},
        )
        assert resource.base_address == "aws_subnet.public"

    def test_full_id_without_module(self):
        """Test full_id without module path."""
        resource = TerraformStateResource(
            address="aws_vpc.main",
            resource_type="aws_vpc",
            name="main",
            index=None,
            values={},
        )
        assert resource.full_id == "aws_vpc.main"

    def test_full_id_with_module(self):
        """Test full_id with module path."""
        resource = TerraformStateResource(
            address="module.network.aws_vpc.main",
            resource_type="aws_vpc",
            name="main",
            index=None,
            values={},
            module_path="module.network",
        )
        assert resource.full_id == "module.network.aws_vpc.main"


class TestTerraformToolsRunner:
    """Tests for TerraformToolsRunner class."""

    def test_check_terraform_available_found(self):
        """Test terraform is found in PATH."""
        with patch("shutil.which", return_value="/usr/bin/terraform"):
            runner = TerraformToolsRunner(Path("/tmp"))
            assert runner.check_terraform_available() is True

    def test_check_terraform_available_not_found(self):
        """Test terraform is not found in PATH."""
        with patch("shutil.which", return_value=None):
            runner = TerraformToolsRunner(Path("/tmp"))
            assert runner.check_terraform_available() is False

    def test_check_initialized_true(self, tmp_path):
        """Test terraform is initialized."""
        terraform_dir = tmp_path / ".terraform"
        terraform_dir.mkdir()
        runner = TerraformToolsRunner(tmp_path)
        assert runner.check_initialized() is True

    def test_check_initialized_false(self, tmp_path):
        """Test terraform is not initialized."""
        runner = TerraformToolsRunner(tmp_path)
        assert runner.check_initialized() is False


class TestParseStateJson:
    """Tests for parse_state_json function."""

    def test_parse_empty_json(self):
        """Test parsing empty JSON."""
        result = parse_state_json({})
        assert result.resources == []

    def test_parse_non_dict_input(self):
        """Test parsing non-dict input returns empty result."""
        result = parse_state_json([])
        assert result.resources == []

        result = parse_state_json("string")
        assert result.resources == []

        result = parse_state_json(None)
        assert result.resources == []

    def test_parse_show_json_format(self):
        """Test parsing terraform show -json format."""
        json_data = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_vpc.main",
                            "type": "aws_vpc",
                            "name": "main",
                            "values": {"cidr_block": "10.0.0.0/16"},
                        }
                    ]
                }
            }
        }
        result = parse_state_json(json_data)
        assert len(result.resources) == 1
        assert result.resources[0].resource_type == "aws_vpc"
        assert result.resources[0].name == "main"

    def test_parse_plan_json_format(self):
        """Test parsing terraform plan -json format."""
        json_data = {
            "planned_values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_s3_bucket.test",
                            "type": "aws_s3_bucket",
                            "name": "test",
                            "values": {"bucket": "my-bucket"},
                        }
                    ]
                }
            }
        }
        result = parse_state_json(json_data)
        assert len(result.resources) == 1
        assert result.resources[0].resource_type == "aws_s3_bucket"

    def test_parse_with_child_modules(self):
        """Test parsing JSON with child modules."""
        json_data = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_vpc.main",
                            "type": "aws_vpc",
                            "name": "main",
                            "values": {},
                        }
                    ],
                    "child_modules": [
                        {
                            "address": "module.network",
                            "resources": [
                                {
                                    "address": "module.network.aws_subnet.public",
                                    "type": "aws_subnet",
                                    "name": "public",
                                    "values": {},
                                }
                            ],
                        }
                    ],
                }
            }
        }
        result = parse_state_json(json_data)
        assert len(result.resources) == 2

    def test_parse_resource_with_index(self):
        """Test parsing resource with count index."""
        json_data = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_subnet.public[0]",
                            "type": "aws_subnet",
                            "name": "public",
                            "index": 0,
                            "values": {},
                        },
                        {
                            "address": "aws_subnet.public[1]",
                            "type": "aws_subnet",
                            "name": "public",
                            "index": 1,
                            "values": {},
                        },
                    ]
                }
            }
        }
        result = parse_state_json(json_data)
        assert len(result.resources) == 2
        assert result.resources[0].index == 0
        assert result.resources[1].index == 1

    def test_parse_resource_with_string_index(self):
        """Test parsing resource with for_each string index."""
        json_data = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": 'aws_subnet.public["us-east-1a"]',
                            "type": "aws_subnet",
                            "name": "public",
                            "index": "us-east-1a",
                            "values": {},
                        },
                    ]
                }
            }
        }
        result = parse_state_json(json_data)
        assert len(result.resources) == 1
        assert result.resources[0].index == "us-east-1a"

    def test_parse_resource_with_invalid_values(self):
        """Test parsing resource with non-dict values."""
        json_data = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_vpc.main",
                            "type": "aws_vpc",
                            "name": "main",
                            "values": "not a dict",
                        }
                    ]
                }
            }
        }
        result = parse_state_json(json_data)
        assert len(result.resources) == 1
        assert result.resources[0].values == {}


class TestTerraformToolsRunnerIntegration:
    """Integration tests for TerraformToolsRunner with file I/O."""

    def test_run_show_json_from_file(self, tmp_path):
        """Test loading state from a JSON file."""
        state_data = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "aws_vpc.main",
                            "type": "aws_vpc",
                            "name": "main",
                            "values": {"cidr_block": "10.0.0.0/16"},
                        }
                    ]
                }
            }
        }
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(state_data))

        runner = TerraformToolsRunner(tmp_path)
        result = runner.run_show_json(state_file=state_file)

        assert result is not None
        assert len(result.resources) == 1
        assert result.resources[0].name == "main"

    def test_run_show_json_file_not_found(self, tmp_path):
        """Test handling of missing state file."""
        runner = TerraformToolsRunner(tmp_path)
        result = runner.run_show_json(state_file=tmp_path / "nonexistent.json")
        assert result is None

    def test_run_show_json_invalid_json(self, tmp_path):
        """Test handling of invalid JSON file."""
        state_file = tmp_path / "invalid.json"
        state_file.write_text("not valid json {")

        runner = TerraformToolsRunner(tmp_path)
        result = runner.run_show_json(state_file=state_file)
        assert result is None
