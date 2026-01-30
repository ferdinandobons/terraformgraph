"""tfgraph - Create architecture diagrams from Terraform configurations."""

__version__ = "1.0.0"

from .aggregator import ResourceAggregator
from .config_loader import ConfigLoader
from .layout import LayoutEngine
from .parser import TerraformParser
from .renderer import HTMLRenderer, SVGRenderer

__all__ = [
    "__version__",
    "TerraformParser",
    "ResourceAggregator",
    "LayoutEngine",
    "SVGRenderer",
    "HTMLRenderer",
    "ConfigLoader",
]
