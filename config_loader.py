"""Configuration loader for Terraform Diagram Generator."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigLoader:
    """Loads configuration from YAML files with fallback to defaults."""

    def __init__(
        self,
        aggregation_rules_path: Optional[Path] = None,
        logical_connections_path: Optional[Path] = None
    ):
        self._config_dir = Path(__file__).parent / "config"
        self._aggregation_rules_path = aggregation_rules_path or self._config_dir / "aggregation_rules.yaml"
        self._logical_connections_path = logical_connections_path or self._config_dir / "logical_connections.yaml"

        self._aggregation_rules: Optional[Dict[str, Any]] = None
        self._logical_connections: Optional[List[Dict[str, Any]]] = None

    def get_aggregation_rules(self) -> Dict[str, Any]:
        """Load and return aggregation rules."""
        if self._aggregation_rules is None:
            self._aggregation_rules = self._load_yaml(self._aggregation_rules_path)
        return self._aggregation_rules

    def get_logical_connections(self) -> List[Dict[str, Any]]:
        """Load and return logical connections."""
        if self._logical_connections is None:
            data = self._load_yaml(self._logical_connections_path)
            self._logical_connections = data.get("connections", [])
        return self._logical_connections

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file and return parsed content."""
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_flat_aggregation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Return aggregation rules flattened to service_name -> config mapping."""
        rules = self.get_aggregation_rules()
        flat = {}
        for category, services in rules.items():
            for service_name, config in services.items():
                flat[service_name] = {
                    "category": category,
                    **config
                }
        return flat
