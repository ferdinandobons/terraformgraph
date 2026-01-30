import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from terraform_diagram.config_loader import ConfigLoader


class TestConfigLoader:
    def test_load_default_aggregation_rules(self):
        loader = ConfigLoader()
        rules = loader.get_aggregation_rules()

        assert "compute" in rules
        assert "ecs" in rules["compute"]
        assert "aws_ecs_cluster" in rules["compute"]["ecs"]["primary"]

    def test_load_default_logical_connections(self):
        loader = ConfigLoader()
        connections = loader.get_logical_connections()

        assert len(connections) > 0
        assert any(c["source"] == "cloudfront" and c["target"] == "s3" for c in connections)

    def test_custom_config_path(self, tmp_path):
        custom_config = tmp_path / "custom_rules.yaml"
        custom_config.write_text("""
compute:
  custom_service:
    primary: ["aws_custom_resource"]
    secondary: []
    in_vpc: false
""")
        loader = ConfigLoader(aggregation_rules_path=custom_config)
        rules = loader.get_aggregation_rules()

        assert "compute" in rules
        assert "custom_service" in rules["compute"]
