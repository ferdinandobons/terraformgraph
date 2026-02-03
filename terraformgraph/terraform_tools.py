"""
Terraform CLI Tools Integration

Provides functionality to run terraform commands and parse their output
to enhance the visualization with accurate state information.
"""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TerraformStateResource:
    """A resource from terraform state/plan JSON output."""

    address: str  # e.g., "aws_subnet.public[0]" or "aws_subnet.public[\"key\"]"
    resource_type: str
    name: str
    index: Optional[Any]  # Can be int (count) or str (for_each)
    values: Dict[str, Any]
    module_path: str = ""

    @property
    def base_address(self) -> str:
        """Address without index, e.g., 'aws_subnet.public' from 'aws_subnet.public[0]' or 'aws_subnet.public[\"key\"]'."""
        # Remove numeric index [0] or string index ["key"]
        address = re.sub(r"\[\d+\]$", "", self.address)
        address = re.sub(r'\["[^"]+"\]$', "", address)
        return address

    @property
    def full_id(self) -> str:
        """Full ID matching parser's format."""
        if self.module_path:
            return f"{self.module_path}.{self.resource_type}.{self.name}"
        return f"{self.resource_type}.{self.name}"


@dataclass
class TerraformStateResult:
    """Result from parsing terraform show/plan JSON output."""

    resources: List[TerraformStateResource] = field(default_factory=list)


class TerraformToolsRunner:
    """Executes terraform commands and parses their output."""

    TIMEOUT_SHOW = 120  # seconds

    def __init__(self, terraform_dir: Path, terraform_bin: str = "terraform"):
        self.terraform_dir = Path(terraform_dir)
        self.terraform_bin = terraform_bin

    def check_terraform_available(self) -> bool:
        """Check if terraform CLI is available in PATH."""
        return shutil.which(self.terraform_bin) is not None

    def check_initialized(self) -> bool:
        """Check if terraform init has been run in the directory."""
        terraform_dir = self.terraform_dir / ".terraform"
        return terraform_dir.exists() and terraform_dir.is_dir()

    def run_show_json(self, state_file: Optional[Path] = None) -> Optional[TerraformStateResult]:
        """Run terraform show -json and parse the state output.

        If state_file is provided, reads from that file directly.
        Otherwise, tries to read from local JSON files (plan.json, state.json, terraform.tfstate.json),
        then falls back to running terraform show -json.

        Args:
            state_file: Optional path to a specific JSON state/plan file.

        Returns:
            TerraformStateResult with resources, or None if failed.
        """
        # If a specific state file is provided, use it directly
        if state_file is not None:
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                    result = parse_state_json(json_data)
                    if result and result.resources:
                        logger.info(
                            "Loaded state from %s: %d resources", state_file, len(result.resources)
                        )
                        return result
                    else:
                        logger.warning("No resources found in %s", state_file)
                        return None
                except OSError as e:
                    logger.warning("Could not read %s: %s", state_file, e)
                    return None
                except json.JSONDecodeError as e:
                    logger.warning("Could not parse JSON in %s: %s", state_file, e)
                    return None
            else:
                logger.warning("State file not found: %s", state_file)
                return None

        # Try to read from local JSON files in terraform dir
        json_files = [
            self.terraform_dir / "plan.json",
            self.terraform_dir / "state.json",
            self.terraform_dir / "terraform.tfstate.json",
        ]

        for json_file in json_files:
            if json_file.exists():
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        json_data = json.load(f)

                    result = parse_state_json(json_data)
                    if result and result.resources:
                        logger.info(
                            "Loaded state from %s: %d resources",
                            json_file.name,
                            len(result.resources),
                        )
                        return result
                except OSError as e:
                    logger.debug("Could not read %s: %s", json_file.name, e)
                except json.JSONDecodeError as e:
                    logger.debug("Could not parse JSON in %s: %s", json_file.name, e)

        # Fall back to running terraform show -json
        if not self.check_terraform_available():
            logger.warning("Terraform CLI not found in PATH")
            return None

        if not self.check_initialized():
            logger.warning(
                "Terraform not initialized in %s. Run 'terraform init' first.", self.terraform_dir
            )
            return None

        try:
            result = subprocess.run(
                [self.terraform_bin, "show", "-json"],
                cwd=self.terraform_dir,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_SHOW,
            )

            if result.returncode != 0:
                logger.warning("terraform show -json failed: %s", result.stderr)
                return None

            if not result.stdout.strip():
                logger.info("No terraform state found")
                return None

            try:
                json_data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse terraform show output: %s", e)
                return None

            return parse_state_json(json_data)

        except subprocess.TimeoutExpired:
            logger.warning("terraform show timed out after %ds", self.TIMEOUT_SHOW)
            return None
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("Error running terraform show: %s", e)
            return None


def parse_state_json(json_data: Any) -> TerraformStateResult:
    """Parse terraform show -json or terraform plan -json output.

    Supports multiple JSON structures:

    1. terraform show -json (state):
        {
            "values": {
                "root_module": {
                    "resources": [...],
                    "child_modules": [...]
                }
            }
        }

    2. terraform plan -json:
        {
            "planned_values": {
                "root_module": {
                    "resources": [...],
                    "child_modules": [...]
                }
            },
            "prior_state": {
                "values": {
                    "root_module": {...}
                }
            }
        }

    Args:
        json_data: Parsed JSON from terraform show/plan -json

    Returns:
        TerraformStateResult with parsed resources (empty if input is invalid)
    """
    result = TerraformStateResult()

    # Validate input type
    if not isinstance(json_data, dict):
        logger.warning("parse_state_json received non-dict input: %s", type(json_data).__name__)
        return result

    # Try different JSON structures in order of preference
    root_module = None

    # 1. Try "values" (terraform show -json format)
    values = json_data.get("values")
    if values:
        root_module = values.get("root_module")
        if root_module:
            logger.debug("Using 'values.root_module' structure (terraform show format)")

    # 2. Try "planned_values" (terraform plan -json format)
    if not root_module:
        planned_values = json_data.get("planned_values")
        if planned_values:
            root_module = planned_values.get("root_module")
            if root_module:
                logger.debug("Using 'planned_values.root_module' structure (terraform plan format)")

    # 3. Try "prior_state.values" (terraform plan -json format, existing state)
    if not root_module:
        prior_state = json_data.get("prior_state")
        if prior_state:
            prior_values = prior_state.get("values")
            if prior_values:
                root_module = prior_values.get("root_module")
                if root_module:
                    logger.debug("Using 'prior_state.values.root_module' structure")

    if not root_module:
        logger.debug("No root_module found in terraform JSON")
        return result

    # Parse root module resources
    _parse_module_resources(root_module, result, module_path="")

    # Parse child modules recursively
    for child_module in root_module.get("child_modules", []):
        _parse_child_module(child_module, result)

    logger.debug("Parsed terraform state: %d resources", len(result.resources))

    return result


def _parse_module_resources(
    module_data: dict, result: TerraformStateResult, module_path: str
) -> None:
    """Parse resources from a module in state JSON."""
    for res in module_data.get("resources", []):
        address = res.get("address", "")
        resource_type = res.get("type", "")
        name = res.get("name", "")
        index = res.get("index")  # Can be int (count) or str (for_each)
        values = res.get("values", {})

        # Ensure values is a dict
        if not isinstance(values, dict):
            values = {}

        if resource_type and name:
            state_resource = TerraformStateResource(
                address=address,
                resource_type=resource_type,
                name=name,
                index=index,  # Keep original type (int or str)
                values=values,
                module_path=module_path,
            )
            result.resources.append(state_resource)


def _parse_child_module(module_data: dict, result: TerraformStateResult) -> None:
    """Recursively parse a child module from state JSON."""
    address = module_data.get("address", "")

    # Extract module path from address (e.g., "module.vpc" -> "vpc")
    module_path = ""
    if address.startswith("module."):
        # Handle nested modules: "module.vpc.module.subnets" -> "vpc.subnets"
        parts = address.split(".")
        module_parts = []
        for i, part in enumerate(parts):
            if part != "module" and (i == 0 or parts[i - 1] == "module"):
                module_parts.append(part)
        module_path = ".".join(module_parts)

    _parse_module_resources(module_data, result, module_path)

    # Recurse into nested child modules
    for child in module_data.get("child_modules", []):
        _parse_child_module(child, result)


def map_state_to_resource_id(state_address: str) -> str:
    """Convert terraform state address to parser resource full_id format.

    Examples:
        "aws_vpc.main" -> "aws_vpc.main"
        "aws_subnet.public[0]" -> "aws_subnet.public"
        "module.vpc.aws_subnet.public[0]" -> "vpc.aws_subnet.public"

    Args:
        state_address: Resource address from terraform state

    Returns:
        Resource ID matching parser's full_id format
    """
    # Remove index brackets
    address = re.sub(r"\[\d+\]", "", state_address)
    address = re.sub(r'\["[^"]+"\]', "", address)

    # Handle module prefix
    if address.startswith("module."):
        parts = address.split(".")
        # module.vpc.aws_subnet.public -> vpc.aws_subnet.public
        module_parts = []
        resource_parts = []

        i = 0
        while i < len(parts):
            if parts[i] == "module" and i + 1 < len(parts):
                module_parts.append(parts[i + 1])
                i += 2
            else:
                resource_parts = parts[i:]
                break

        if module_parts and resource_parts:
            module_path = ".".join(module_parts)
            resource_part = ".".join(resource_parts)
            return f"{module_path}.{resource_part}"

    return address
