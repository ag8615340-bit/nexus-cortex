"""
ram_optimizer.py
Hardware-aware sub-agent capacity planner.
Scales the number of concurrent sub-agent coroutines based on
simulated RAM allocation to control API request parallelism.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from strict_prompts import MAIN_AGENT_TYPES, SUB_AGENT_COUNT_PER_MAIN

logger = logging.getLogger(__name__)

VALID_RAM_VALUES = {4, 8, 16}


@dataclass
class RAMProfile:
    """Describes the resource budget for a given RAM configuration."""
    total_gb: int
    used_gb: float
    available_gb: float
    usage_pct: float
    max_concurrent_sub_agents: int
    sub_agents_per_main_agent: int
    recommendation: str
    active_indices: Dict[str, List[int]] = field(default_factory=dict)


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _normalize_ram_gb(simulated_ram_gb: int) -> int:
    """Clamp input RAM value to the nearest valid tier (4, 8, 16)."""
    if simulated_ram_gb not in VALID_RAM_VALUES:
        logger.warning(
            "Non-standard RAM value %sGB provided — clamping to nearest valid tier.",
            simulated_ram_gb,
        )
    if simulated_ram_gb <= 4:
        return 4
    elif simulated_ram_gb <= 8:
        return 8
    else:
        return 16


def _build_active_indices(sub_agents_per_main: int) -> Dict[str, List[int]]:
    """
    Dynamically build active sub-agent index map from strict_prompts constants.
    Stays in sync automatically if agent definitions change.
    """
    return {
        agent: list(range(sub_agents_per_main))
        for agent in MAIN_AGENT_TYPES
    }


# ──────────────────────────────────────────────
# Active sub-agent index map per RAM tier
# Generated from strict_prompts — no manual sync needed
# ──────────────────────────────────────────────
ACTIVE_SUB_AGENT_INDICES: Dict[int, Dict[str, List[int]]] = {
    4:  _build_active_indices(1),
    8:  _build_active_indices(SUB_AGENT_COUNT_PER_MAIN),
    16: _build_active_indices(SUB_AGENT_COUNT_PER_MAIN),
}

# ──────────────────────────────────────────────
# RAM usage model constants
# ──────────────────────────────────────────────
_BASE_OS_OVERHEAD_GB = 2.0       # Simulated OS baseline usage
_MEMORY_PER_SUB_AGENT_GB = 0.5  # Simulated per-sub-agent cost
_MAIN_AGENT_COUNT = len(MAIN_AGENT_TYPES)


def get_active_sub_agent_count(simulated_ram_gb: int) -> RAMProfile:
    """
    Given a simulated RAM allocation in GB (4, 8, or 16),
    return a RAMProfile describing the resource budget and
    the number of sub-agents that should be active per main agent.

    Controls API request parallelism — higher RAM tiers allow
    more concurrent sub-agent coroutines per main agent.

    Parameters
    ----------
    simulated_ram_gb : int
        Must be 4, 8, or 16. Other values will be clamped to the nearest.

    Returns
    -------
    RAMProfile
        A dataclass with budget details and sub-agent capacity.
    """
    gb = _normalize_ram_gb(simulated_ram_gb)

    if gb == 4:
        per_agent = 1
        max_concurrent = per_agent * _MAIN_AGENT_COUNT
        recommendation = (
            "LIMITED: Running at 4GB — only 1 sub-agent per main agent active. "
            "Upgrade to 8GB+ for full agent orchestration."
        )
    elif gb == 8:
        per_agent = SUB_AGENT_COUNT_PER_MAIN
        max_concurrent = per_agent * _MAIN_AGENT_COUNT
        recommendation = (
            "MODERATE: Running at 8GB — all 4 sub-agents per main agent active. "
            "All agents can run, but monitor CPU usage."
        )
    else:  # 16
        per_agent = SUB_AGENT_COUNT_PER_MAIN
        max_concurrent = per_agent * _MAIN_AGENT_COUNT
        recommendation = (
            "OPTIMAL: Running at 16GB — all 4 sub-agents per main agent active. "
            "Full matrix capacity available."
        )

    # Calculate usage based on active sub-agents
    total_active = per_agent * _MAIN_AGENT_COUNT
    used_gb = round(_BASE_OS_OVERHEAD_GB + (total_active * _MEMORY_PER_SUB_AGENT_GB), 1)
    available_gb = round(max(float(gb) - used_gb, 0.0), 1)
    usage_pct = round((used_gb / gb) * 100, 1)

    return RAMProfile(
        total_gb=gb,
        used_gb=used_gb,
        available_gb=available_gb,
        usage_pct=usage_pct,
        max_concurrent_sub_agents=max_concurrent,
        sub_agents_per_main_agent=per_agent,
        recommendation=recommendation,
        active_indices=ACTIVE_SUB_AGENT_INDICES[gb],
    )


def get_active_indices_for_ram(
    simulated_ram_gb: int,
) -> Dict[str, List[int]]:
    """
    Get the list of active sub-agent indices for each main agent
    given the current RAM configuration.

    Returns a dict like:
        {
            "market_strategist": [0, 1, 2, 3],
            "financial_analyst": [0, 1, 2, 3],
            "operations_optimizer": [0, 1, 2, 3],
        }
    """
    gb = _normalize_ram_gb(simulated_ram_gb)
    return ACTIVE_SUB_AGENT_INDICES[gb]