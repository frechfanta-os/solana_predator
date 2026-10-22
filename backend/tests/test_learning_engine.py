"""
Technical validation tests for Measurable Learning Engine (Step 3 & Step 7.2).
Tests temporal split isolation, outcome evaluation, error metrics, and strategy optimization.
"""
import pytest
import time
from backend.learning.models import (
    DecisionOutcome,
    LearningMetrics,
    StrategyBenchmark,
    DatasetSplitType,
)
from backend.learning.temporal_split import assign_temporal_splits
from backend.learning.evaluator import DecisionOutcomeEvaluator
from backend.learning.optimizer import StrategyOptimizer
from backend.models import AgentDecision


def generate_dummy_decision_dicts(count=30, base_time=1700000000.0):
    decisions = []
    for i in range(count):
        t = base_time + (i * 3600.0)  # 1 hour intervals
        action = AgentDecision.BUY_CANDIDATE.value if i % 2 == 0 else AgentDecision.PASS.value
        dec = {
            "consensus_id": f"cons_test_{i:03d}",
            "token_mint": f"Mint{i:02d}1111111111111111111111111111111111",
            "decision_timestamp": t,
            "final_decision": action,
            "confidence_score": 0.85 if action == AgentDecision.BUY_CANDIDATE.value else 0.40,
            "confidence_method": "MULTI_AGENT_WEIGHTED_HARMONIC",
            "invalidation_conditions": ["Price drop > 5%"],
            "identified_risks": ["Market volatility"],
            "strategy_version": "v1.1.0-consensus",
            "expected_outcome": "CAPITAL_APPRECIATION",
            "evaluation_horizon_sec": 3600,
            "entry_price_usd": 10.0,
            "target_price_usd": 11.0,
            "invalidation_price_usd": 9.5,
            "details": {"liquidity_usd": 50000.0},
        }
        decisions.append(dec)
    return decisions


def test_strict_temporal_split_zero_lookahead():
    decisions = generate_dummy_decision_dicts(count=30)
    partitioned = assign_temporal_splits(decisions, train_ratio=0.6, val_ratio=0.2)

    train = [d for d, split in partitioned if split == DatasetSplitType.TRAIN]
    val = [d for d, split in partitioned if split == DatasetSplitType.VALIDATION]
    test = [d for d, split in partitioned if split == DatasetSplitType.TEST]

    assert len(train) == 18
    assert len(val) == 6
    assert len(test) == 6

    # Verify strict temporal monotonicity
    train_max_t = max(d["decision_timestamp"] for d in train)
    val_min_t = min(d["decision_timestamp"] for d in val)
    val_max_t = max(d["decision_timestamp"] for d in val)
    test_min_t = min(d["decision_timestamp"] for d in test)

    assert train_max_t < val_min_t, "Temporal leak: train timestamp overlaps with validation"
    assert val_max_t < test_min_t, "Temporal leak: validation timestamp overlaps with test"

    # Verify no duplicate consensus_id across splits
    all_ids = [d["consensus_id"] for d in train] + [d["consensus_id"] for d in val] + [d["consensus_id"] for d in test]
    assert len(all_ids) == len(set(all_ids))


def test_decision_outcome_evaluation_correct_buy(repo):
    evaluator = DecisionOutcomeEvaluator(repository=repo)
    decision = {
        "consensus_id": "cons_eval_01",
        "token_mint": "MintEval01111111111111111111111111111111111",
        "decision_timestamp": 1000.0,
        "final_decision": AgentDecision.BUY_CANDIDATE.value,
        "entry_price_usd": 10.0,
        "target_price_usd": 11.0,
        "invalidation_price_usd": 9.5,
        "evaluation_horizon_sec": 900,
        "strategy_version": "v1.1.0-consensus",
        "details": {"liquidity_usd": 50000.0},
    }

    # Scenario: Price rallies to 11.5 without dipping below invalidation -> Correct BUY
    price_series = [
        {"timestamp": 1050.0, "price_usd": 10.2},
        {"timestamp": 1100.0, "price_usd": 11.5},
        {"timestamp": 1200.0, "price_usd": 11.2},
    ]

    outcome = evaluator.evaluate_single_decision(decision, price_series, split_type=DatasetSplitType.TEST)
    assert outcome is not None
    assert outcome.is_correct is True
    assert outcome.is_false_positive is False
    assert outcome.peak_price_usd == 11.5
    assert outcome.simulated_net_return_pct > 0.0


def test_decision_outcome_evaluation_false_positive(repo):
    evaluator = DecisionOutcomeEvaluator(repository=repo)
    decision = {
        "consensus_id": "cons_eval_02",
        "token_mint": "MintEval02111111111111111111111111111111111",
        "decision_timestamp": 1000.0,
        "final_decision": AgentDecision.BUY_CANDIDATE.value,
        "entry_price_usd": 10.0,
        "target_price_usd": 11.0,
        "invalidation_price_usd": 9.5,
        "evaluation_horizon_sec": 900,
        "strategy_version": "v1.1.0-consensus",
        "details": {"liquidity_usd": 50000.0},
    }

    # Scenario: Price crashes to 9.0 -> False Positive
    price_series = [
        {"timestamp": 1050.0, "price_usd": 9.8},
        {"timestamp": 1100.0, "price_usd": 9.0},
    ]

    outcome = evaluator.evaluate_single_decision(decision, price_series, split_type=DatasetSplitType.TEST)
    assert outcome is not None
    assert outcome.is_correct is False
    assert outcome.is_false_positive is True
    assert outcome.trough_price_usd == 9.0
    assert outcome.max_drawdown_pct == 10.0


def test_aggregate_metrics_calculation(repo):
    evaluator = DecisionOutcomeEvaluator(repository=repo)
    
    outcomes = [
        DecisionOutcome(
            outcome_id="out_01",
            consensus_id="c1",
            token_mint="m1",
            evaluated_at=time.time(),
            horizon_sec=900,
            entry_price_usd=10.0,
            target_price_usd=11.0,
            invalidation_price_usd=9.5,
            peak_price_usd=11.2,
            trough_price_usd=9.9,
            final_price_usd=11.0,
            is_correct=True,
            is_false_positive=False,
            is_true_negative=False,
            simulated_net_return_pct=9.5,
            max_drawdown_pct=1.0,
            price_forecast_error_abs=0.2,
            strategy_version="v1.1.0",
            split_type=DatasetSplitType.TEST,
            liquidity_usd=50000.0,
        ),
        DecisionOutcome(
            outcome_id="out_02",
            consensus_id="c2",
            token_mint="m2",
            evaluated_at=time.time(),
            horizon_sec=900,
            entry_price_usd=10.0,
            target_price_usd=11.0,
            invalidation_price_usd=9.5,
            peak_price_usd=10.1,
            trough_price_usd=9.0,
            final_price_usd=9.2,
            is_correct=False,
            is_false_positive=True,
            is_true_negative=False,
            simulated_net_return_pct=-8.5,
            max_drawdown_pct=10.0,
            price_forecast_error_abs=0.9,
            strategy_version="v1.1.0",
            split_type=DatasetSplitType.TEST,
            liquidity_usd=15000.0,
        ),
    ]

    metrics: LearningMetrics = evaluator.compute_aggregate_metrics(outcomes)
    assert metrics.total_decisions_evaluated == 2
    assert metrics.correct_decisions_rate == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.mean_absolute_error_price == pytest.approx(0.55, rel=1e-2)
    assert metrics.max_simulated_drawdown_pct == 10.0


@pytest.mark.asyncio
async def test_strategy_optimizer_simulation_no_live_mutation(repo):
    optimizer = StrategyOptimizer(repository=repo)
    
    baseline_outcomes = [
        DecisionOutcome(
            outcome_id="out_sim_01",
            consensus_id="c1",
            token_mint="m1",
            evaluated_at=time.time(),
            horizon_sec=900,
            entry_price_usd=10.0,
            target_price_usd=11.0,
            invalidation_price_usd=9.5,
            peak_price_usd=11.5,
            trough_price_usd=9.8,
            final_price_usd=11.4,
            is_correct=True,
            is_false_positive=False,
            is_true_negative=False,
            simulated_net_return_pct=13.5,
            max_drawdown_pct=2.0,
            price_forecast_error_abs=0.5,
            strategy_version="v1.1.0",
            split_type=DatasetSplitType.VALIDATION,
        ),
        DecisionOutcome(
            outcome_id="out_sim_02",
            consensus_id="c2",
            token_mint="m2",
            evaluated_at=time.time(),
            horizon_sec=900,
            entry_price_usd=10.0,
            target_price_usd=11.0,
            invalidation_price_usd=9.5,
            peak_price_usd=10.1,
            trough_price_usd=9.2,
            final_price_usd=9.3,
            is_correct=False,
            is_false_positive=True,
            is_true_negative=False,
            simulated_net_return_pct=-7.0,
            max_drawdown_pct=8.0,
            price_forecast_error_abs=0.9,
            strategy_version="v1.1.0",
            split_type=DatasetSplitType.VALIDATION,
        ),
    ]

    benchmark = optimizer.simulate_strategy_candidate(
        candidate_version="v2.0.0-candidate-alpha",
        baseline_outcomes=baseline_outcomes,
        min_confidence_filter=0.85,
        target_multiplier=1.20,
        split_to_use=DatasetSplitType.VALIDATION,
    )

    assert isinstance(benchmark, StrategyBenchmark)
    assert benchmark.version == "v2.0.0-candidate-alpha"
    assert benchmark.sample_size == 2
    assert benchmark.is_active is False  # Inactive until validated
    assert benchmark.accuracy_rate == 0.5
    assert benchmark.max_drawdown_pct >= 0.0

    # Persist benchmark and verify retrieval
    await repo.save_strategy_benchmark(benchmark)
    benchmarks = await repo.get_strategy_benchmarks()
    assert len(benchmarks) >= 1
    assert benchmarks[0]["version"] == "v2.0.0-candidate-alpha"
