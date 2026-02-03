"""Tests for VariableResolver module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from terraformgraph.variable_resolver import VariableResolver


class TestVariableResolverParsing:
    """Tests for parsing tfvars, locals, and variable defaults."""

    def test_parse_tfvars_simple_string(self, tmp_path):
        """Test parsing simple string variable from tfvars."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project_name = "my-project"\n')

        resolver = VariableResolver(tmp_path)
        assert resolver.get_variable("project_name") == "my-project"

    def test_parse_tfvars_multiple_variables(self, tmp_path):
        """Test parsing multiple variables from tfvars."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text(
            """
project_name = "my-project"
environment = "production"
instance_count = 3
"""
        )

        resolver = VariableResolver(tmp_path)
        assert resolver.get_variable("project_name") == "my-project"
        assert resolver.get_variable("environment") == "production"
        assert resolver.get_variable("instance_count") == 3

    def test_parse_variable_defaults(self, tmp_path):
        """Test parsing variable defaults from variables.tf."""
        variables_tf = tmp_path / "variables.tf"
        variables_tf.write_text(
            """
variable "region" {
  default = "us-east-1"
}

variable "app_name" {
  default = "my-app"
}
"""
        )

        resolver = VariableResolver(tmp_path)
        assert resolver.get_variable("region") == "us-east-1"
        assert resolver.get_variable("app_name") == "my-app"

    def test_tfvars_overrides_variable_defaults(self, tmp_path):
        """Test that tfvars values override variable defaults."""
        variables_tf = tmp_path / "variables.tf"
        variables_tf.write_text(
            """
variable "environment" {
  default = "development"
}
"""
        )
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('environment = "production"\n')

        resolver = VariableResolver(tmp_path)
        assert resolver.get_variable("environment") == "production"

    def test_parse_locals(self, tmp_path):
        """Test parsing locals from .tf files."""
        main_tf = tmp_path / "main.tf"
        main_tf.write_text(
            """
locals {
  service_name = "api-gateway"
  full_name = "prod-api-gateway"
}
"""
        )

        resolver = VariableResolver(tmp_path)
        assert resolver.get_local("service_name") == "api-gateway"
        assert resolver.get_local("full_name") == "prod-api-gateway"

    def test_get_variable_returns_none_for_missing(self, tmp_path):
        """Test that get_variable returns None for missing variables."""
        resolver = VariableResolver(tmp_path)
        assert resolver.get_variable("nonexistent") is None

    def test_get_local_returns_none_for_missing(self, tmp_path):
        """Test that get_local returns None for missing locals."""
        resolver = VariableResolver(tmp_path)
        assert resolver.get_local("nonexistent") is None

    def test_parse_auto_tfvars(self, tmp_path):
        """Test parsing .auto.tfvars files."""
        auto_tfvars = tmp_path / "generated.auto.tfvars"
        auto_tfvars.write_text('auto_var = "auto-value"\n')

        resolver = VariableResolver(tmp_path)
        assert resolver.get_variable("auto_var") == "auto-value"


class TestInterpolationResolution:
    """Tests for resolve() method handling interpolations."""

    def test_resolve_simple_var_interpolation(self, tmp_path):
        """Test resolving ${var.name} interpolation."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project = "myproject"\n')

        resolver = VariableResolver(tmp_path)
        result = resolver.resolve("${var.project}-bucket")
        assert result == "myproject-bucket"

    def test_resolve_simple_local_interpolation(self, tmp_path):
        """Test resolving ${local.name} interpolation."""
        main_tf = tmp_path / "main.tf"
        main_tf.write_text(
            """
locals {
  prefix = "prod"
}
"""
        )

        resolver = VariableResolver(tmp_path)
        result = resolver.resolve("${local.prefix}-service")
        assert result == "prod-service"

    def test_resolve_multiple_interpolations(self, tmp_path):
        """Test resolving multiple interpolations in one string."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text(
            """
env = "prod"
app = "api"
"""
        )

        resolver = VariableResolver(tmp_path)
        result = resolver.resolve("${var.env}-${var.app}-bucket")
        assert result == "prod-api-bucket"

    def test_resolve_mixed_var_and_local(self, tmp_path):
        """Test resolving mixed var and local interpolations."""
        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('env = "prod"\n')
        main_tf = tmp_path / "main.tf"
        main_tf.write_text(
            """
locals {
  region = "us-east-1"
}
"""
        )

        resolver = VariableResolver(tmp_path)
        result = resolver.resolve("${var.env}-${local.region}")
        assert result == "prod-us-east-1"

    def test_resolve_returns_original_if_unresolvable(self, tmp_path):
        """Test that unresolvable interpolations are kept as-is."""
        resolver = VariableResolver(tmp_path)
        result = resolver.resolve("${var.unknown}-suffix")
        assert result == "${var.unknown}-suffix"

    def test_resolve_no_interpolation(self, tmp_path):
        """Test that strings without interpolation are returned unchanged."""
        resolver = VariableResolver(tmp_path)
        result = resolver.resolve("plain-string")
        assert result == "plain-string"

    def test_resolve_none_value(self, tmp_path):
        """Test that None values are handled."""
        resolver = VariableResolver(tmp_path)
        result = resolver.resolve(None)
        assert result is None

    def test_resolve_non_string_value(self, tmp_path):
        """Test that non-string values are returned as-is."""
        resolver = VariableResolver(tmp_path)
        assert resolver.resolve(42) == 42
        assert resolver.resolve(["a", "b"]) == ["a", "b"]


class TestNameTruncation:
    """Tests for truncate_name static method."""

    def test_truncate_short_name(self):
        """Test that short names are not truncated."""
        result = VariableResolver.truncate_name("short", max_length=25)
        assert result == "short"

    def test_truncate_exact_length(self):
        """Test that names at exact max length are not truncated."""
        name = "a" * 25
        result = VariableResolver.truncate_name(name, max_length=25)
        assert result == name

    def test_truncate_long_name(self):
        """Test that long names are truncated with ellipsis."""
        name = "this-is-a-very-long-resource-name-that-exceeds-limit"
        result = VariableResolver.truncate_name(name, max_length=25)
        assert len(result) == 25
        assert result.endswith("...")

    def test_truncate_custom_length(self):
        """Test truncation with custom max_length."""
        name = "medium-length-name"
        result = VariableResolver.truncate_name(name, max_length=10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_truncate_default_length(self):
        """Test that default max_length is 25."""
        name = "a" * 30
        result = VariableResolver.truncate_name(name)
        assert len(result) == 25
        assert result.endswith("...")

    def test_truncate_preserves_meaningful_prefix(self):
        """Test that truncation keeps meaningful prefix."""
        name = "production-api-gateway-service"
        result = VariableResolver.truncate_name(name, max_length=25)
        assert result.startswith("production-api-gateway")


class TestParserIntegration:
    """Tests for TerraformResource.get_resolved_display_name integration."""

    def test_resource_resolved_display_name_with_var(self, tmp_path):
        """Test getting resolved display name with variable interpolation."""
        from terraformgraph.parser import TerraformResource

        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project = "myproject"\n')
        resolver = VariableResolver(tmp_path)

        resource = TerraformResource(
            resource_type="aws_s3_bucket",
            resource_name="main_bucket",
            module_path="",
            attributes={"name": "${var.project}-bucket"},
            source_file="main.tf",
        )

        display_name = resource.get_resolved_display_name(resolver)
        assert display_name == "myproject-bucket"

    def test_resource_resolved_display_name_truncated(self, tmp_path):
        """Test that resolved display names are truncated."""
        from terraformgraph.parser import TerraformResource

        tfvars = tmp_path / "terraform.tfvars"
        tfvars.write_text('project = "very-long-project-name-that-exceeds-limit"\n')
        resolver = VariableResolver(tmp_path)

        resource = TerraformResource(
            resource_type="aws_s3_bucket",
            resource_name="main_bucket",
            module_path="",
            attributes={"name": "${var.project}-bucket"},
            source_file="main.tf",
        )

        display_name = resource.get_resolved_display_name(resolver)
        assert len(display_name) <= 25

    def test_resource_resolved_display_name_without_interpolation(self, tmp_path):
        """Test resolved display name for resource without interpolation."""
        from terraformgraph.parser import TerraformResource

        resolver = VariableResolver(tmp_path)

        resource = TerraformResource(
            resource_type="aws_s3_bucket",
            resource_name="main_bucket",
            module_path="",
            attributes={"name": "static-bucket-name"},
            source_file="main.tf",
        )

        display_name = resource.get_resolved_display_name(resolver)
        assert display_name == "static-bucket-name"

    def test_resource_resolved_display_name_fallback_to_resource_name(self, tmp_path):
        """Test fallback to resource_name when name attribute missing."""
        from terraformgraph.parser import TerraformResource

        resolver = VariableResolver(tmp_path)

        resource = TerraformResource(
            resource_type="aws_s3_bucket",
            resource_name="main_bucket",
            module_path="",
            attributes={},
            source_file="main.tf",
        )

        display_name = resource.get_resolved_display_name(resolver)
        assert display_name == "main_bucket"
