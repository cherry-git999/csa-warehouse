"""
Pipeline Registry module.

Manages pipeline configurations decentralized into domain-specific modules.
Exposes a single authoritative mutable dictionary instance that is shared with
PIPELINE_CONFIG in pipeline_mapping.py to guarantee strict backward compatibility,
zero divergence, and seamless unittest.mock.patch.dict support.
"""

from typing import Dict, Any, Optional

from app.pipelines.configs.nf_coordinator import (
    PIPELINE_ID as PID_NF,
    CONFIG as CFG_NF,
)
from app.pipelines.configs.territory_transactions import (
    PIPELINE_ID as PID_TERRITORY,
    CONFIG as CFG_TERRITORY,
)
from app.pipelines.configs.farmer_income_visits import (
    PIPELINE_ID as PID_FARMER,
    CONFIG as CFG_FARMER,
)
from app.pipelines.configs.stock_movement import (
    PIPELINE_ID as PID_STOCK_MOV,
    CONFIG as CFG_STOCK_MOV,
)
from app.pipelines.configs.stock_inventory import (
    PIPELINE_ID as PID_STOCK_INV,
    CONFIG as CFG_STOCK_INV,
)
from app.pipelines.configs.revenue_analysis import (
    PIPELINE_ID as PID_REV,
    CONFIG as CFG_REV,
)
from app.pipelines.configs.generic import GENERIC_CONFIGS


class PipelineRegistry:
    """
    Central registry aggregating decentralized pipeline configurations.
    Maintains a single authoritative dictionary instance to prevent divergence.
    """

    def __init__(self):
        self._shared_dict: Dict[str, Dict[str, Any]] = {}
        self._load_all_pipeline_configs()

    def _load_all_pipeline_configs(self) -> None:
        """Register all modular dashboard and generic pipeline configurations."""
        # 1. Dashboard Pipelines
        self._shared_dict[PID_NF] = dict(CFG_NF)
        self._shared_dict[PID_TERRITORY] = dict(CFG_TERRITORY)
        self._shared_dict[PID_FARMER] = dict(CFG_FARMER)
        self._shared_dict[PID_STOCK_MOV] = dict(CFG_STOCK_MOV)
        self._shared_dict[PID_STOCK_INV] = dict(CFG_STOCK_INV)
        self._shared_dict[PID_REV] = dict(CFG_REV)

        # 2. Generic Baseline Pipelines
        for pid, cfg in GENERIC_CONFIGS.items():
            self._shared_dict[pid] = dict(cfg)

    @property
    def configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Return the single live authoritative dictionary.
        This instance is exposed as PIPELINE_CONFIG in pipeline_mapping.py.
        """
        return self._shared_dict

    def get(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific pipeline ID."""
        return self._shared_dict.get(pipeline_id)

    def register(self, pipeline_id: str, config: Dict[str, Any]) -> None:
        """Register or update a pipeline configuration."""
        self._shared_dict[pipeline_id] = config

    def unregister(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Unregister a pipeline configuration."""
        return self._shared_dict.pop(pipeline_id, None)


# Singleton instance
_GLOBAL_REGISTRY: Optional[PipelineRegistry] = None


def get_pipeline_registry() -> PipelineRegistry:
    """Get the singleton PipelineRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = PipelineRegistry()
    return _GLOBAL_REGISTRY
