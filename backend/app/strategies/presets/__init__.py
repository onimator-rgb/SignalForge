"""Strategy preset generators."""

from .btd import generate_btd_rules
from .dca_bot import generate_dca_rules
from .grid import generate_grid_rules

__all__ = ["generate_btd_rules", "generate_dca_rules", "generate_grid_rules"]
