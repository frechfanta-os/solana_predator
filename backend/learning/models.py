"""Models for SOLANA PREDATOR measurable learning and outcome evaluation."""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class DatasetSplitType(str, Enum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class DecisionOutcome(BaseModel):
    """Evaluated empirical outcome of a historical strategic decision."""
    outcome_id: str
    consensus_id: str
    token_mint: str
    evaluated_at: float
    horizon_sec: int
    entry_price_usd: float
    target_price_usd: Optional[float] = None
    invalidation_price_usd: Optional[float] = None
    peak_price_usd: float
    trough_price_usd: float
    final_price_usd: float
    is_correct: bool
    is_false_positive: bool
    is_true_negative: bool
    simulated_net_return_pct: float
    max_drawdown_pct: float
    price_forecast_error_abs: float
    strategy_version: str = "v1.2.0-consensus"
    split_type: DatasetSplitType = DatasetSplitType.TEST
    liquidity_usd: Optional[float] = None
    token_age_hours: Optional[float] = None


class LearningMetrics(BaseModel):
    """Comprehensive performance metrics evaluated across decisions and partitions."""
    total_decisions_evaluated: int = 0
    correct_decisions_rate: float = 0.0
    false_positive_rate: float = 0.0
    simulated_net_return_pct: float = 0.0
    max_simulated_drawdown_pct: float = 0.0
    mean_absolute_error_price: float = 0.0
    
    # Granular Segmentations
    results_by_agent: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    results_by_strategy: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    results_by_liquidity_tier: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    results_by_token_age: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    results_by_horizon: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class StrategyBenchmark(BaseModel):
    """Versioned benchmark comparison against baseline."""
    version: str
    created_at: float
    description: str
    is_active: bool = False
    sample_size: int = 0
    accuracy_rate: float = 0.0
    false_positive_rate: float = 0.0
    simulated_net_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    benchmark_comparison: Dict[str, Any] = Field(default_factory=dict)
