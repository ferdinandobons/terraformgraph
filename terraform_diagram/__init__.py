"""Terraform Diagram Generator - Create architecture diagrams from Terraform."""

__version__ = "1.0.0"

from .parser import TerraformParser
from .aggregator import ResourceAggregator
from .layout import LayoutEngine
from .renderer import SVGRenderer, HTMLRenderer
from .config_loader import ConfigLoader

__all__ = [
    "__version__",
    "TerraformParser",
    "ResourceAggregator",
    "LayoutEngine",
    "SVGRenderer",
    "HTMLRenderer",
    "ConfigLoader",
]
