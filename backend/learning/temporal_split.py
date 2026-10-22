"""Temporal time-series dataset partitioner strictly preventing lookahead bias."""

from typing import List, Dict, Any, Tuple
from backend.learning.models import DatasetSplitType


def assign_temporal_splits(
    records: List[Dict[str, Any]],
    timestamp_key: str = "decision_timestamp",
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> List[Tuple[Dict[str, Any], DatasetSplitType]]:
    """Sort records strictly by timestamp and partition chronologically without lookahead bias."""
    if not records:
        return []

    # Strict ascending chronological ordering
    sorted_records = sorted(records, key=lambda x: x.get(timestamp_key, 0.0))
    n = len(sorted_records)

    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    partitioned: List[Tuple[Dict[str, Any], DatasetSplitType]] = []
    for idx, rec in enumerate(sorted_records):
        if idx < train_end:
            split = DatasetSplitType.TRAIN
        elif idx < val_end:
            split = DatasetSplitType.VALIDATION
        else:
            split = DatasetSplitType.TEST
        partitioned.append((rec, split))

    return partitioned
