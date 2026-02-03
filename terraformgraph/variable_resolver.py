"""
Variable Resolver Module

Parses and resolves Terraform variables, locals, and interpolations.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

import hcl2
from lark.exceptions import UnexpectedInput, UnexpectedToken

logger = logging.getLogger(__name__)


class VariableResolver:
    """Resolves Terraform variables and locals from tfvars and .tf files."""

    def __init__(self, directory: Union[str, Path]):
        """Initialize the resolver by parsing files in the given directory.

        Args:
            directory: Path to directory containing Terraform files
        """
        self.directory = Path(directory)
        self._variables: Dict[str, Any] = {}
        self._locals: Dict[str, Any] = {}

        # Parse files in order of precedence
        self._parse_variable_defaults()
        self._parse_tfvars()
        self._parse_locals()

    def _parse_tfvars(self) -> None:
        """Parse .tfvars and .auto.tfvars files for variable values.

        Files are parsed in alphabetical order, with later files overriding earlier ones.
        terraform.tfvars is parsed last to give it highest precedence.
        """
        tfvars_files = []

        # Collect .auto.tfvars files
        tfvars_files.extend(sorted(self.directory.glob("*.auto.tfvars")))

        # Add terraform.tfvars last (highest precedence)
        terraform_tfvars = self.directory / "terraform.tfvars"
        if terraform_tfvars.exists():
            tfvars_files.append(terraform_tfvars)

        for tfvars_file in tfvars_files:
            try:
                with open(tfvars_file, "r", encoding="utf-8") as f:
                    content = hcl2.load(f)
                    for key, value in content.items():
                        self._variables[key] = value
            except OSError as e:
                logger.warning("Could not read tfvars file %s: %s", tfvars_file, e)
            except (UnexpectedInput, UnexpectedToken) as e:
                logger.warning("Could not parse tfvars file %s: %s", tfvars_file, e)

    def _parse_locals(self) -> None:
        """Parse locals blocks from all .tf files."""
        for tf_file in self.directory.glob("*.tf"):
            try:
                with open(tf_file, "r", encoding="utf-8") as f:
                    content = hcl2.load(f)

                for locals_block in content.get("locals", []):
                    if isinstance(locals_block, dict):
                        for key, value in locals_block.items():
                            self._locals[key] = value
            except OSError as e:
                logger.warning("Could not read file %s: %s", tf_file, e)
            except (UnexpectedInput, UnexpectedToken) as e:
                logger.warning("Could not parse locals from %s: %s", tf_file, e)

    def _parse_variable_defaults(self) -> None:
        """Parse variable blocks for default values from all .tf files."""
        for tf_file in self.directory.glob("*.tf"):
            try:
                with open(tf_file, "r", encoding="utf-8") as f:
                    content = hcl2.load(f)

                for variable_block in content.get("variable", []):
                    if isinstance(variable_block, dict):
                        for var_name, var_config in variable_block.items():
                            if isinstance(var_config, dict):
                                default = var_config.get("default")
                                if default is not None:
                                    self._variables[var_name] = default
                            elif isinstance(var_config, list) and var_config:
                                # HCL2 sometimes returns list of configs
                                config = var_config[0]
                                if isinstance(config, dict):
                                    default = config.get("default")
                                    if default is not None:
                                        self._variables[var_name] = default
            except OSError as e:
                logger.warning("Could not read file %s: %s", tf_file, e)
            except (UnexpectedInput, UnexpectedToken) as e:
                logger.warning("Could not parse variables from %s: %s", tf_file, e)

    def get_variable(self, name: str) -> Optional[Any]:
        """Get a variable value by name.

        Args:
            name: The variable name (without 'var.' prefix)

        Returns:
            The variable value, or None if not found
        """
        return self._variables.get(name)

    def get_local(self, name: str) -> Optional[Any]:
        """Get a local value by name.

        Args:
            name: The local name (without 'local.' prefix)

        Returns:
            The local value, or None if not found
        """
        return self._locals.get(name)

    def resolve(self, value: Any) -> Any:
        """Resolve interpolations in a value.

        Handles ${var.name} and ${local.name} interpolations.

        Args:
            value: The value to resolve (string or other type)

        Returns:
            The resolved value with interpolations replaced,
            or the original value if no interpolations or resolution failed
        """
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        # Pattern to match ${var.name} or ${local.name}
        pattern = r"\$\{(var|local)\.(\w+)\}"

        def replace_interpolation(match: re.Match) -> str:
            ref_type = match.group(1)
            ref_name = match.group(2)

            if ref_type == "var":
                resolved = self.get_variable(ref_name)
            else:  # local
                resolved = self.get_local(ref_name)

            if resolved is not None:
                return str(resolved)
            else:
                # Keep original if not resolvable
                return match.group(0)

        return re.sub(pattern, replace_interpolation, value)

    @staticmethod
    def truncate_name(name: str, max_length: int = 25) -> str:
        """Truncate a name to a maximum length with ellipsis.

        Args:
            name: The name to truncate
            max_length: Maximum length (default 25)

        Returns:
            The truncated name with '...' suffix if it exceeds max_length
        """
        if len(name) <= max_length:
            return name

        # Leave room for '...' suffix
        return name[: max_length - 3] + "..."
