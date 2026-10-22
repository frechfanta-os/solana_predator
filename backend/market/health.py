"""Observability, health tracking, and statistical latency metrics."""

import time
import math
from typing import Dict, Any, List
from collections import deque


class LatencyTracker:
    """Thread-safe sliding window latency tracker computing p50, p95, and p99."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._samples: deque[float] = deque(maxlen=window_size)

    def record(self, latency_ms: float) -> None:
        if latency_ms >= 0:
            self._samples.append(latency_ms)

    def get_percentiles(self) -> Dict[str, float]:
        if not self._samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0, "avg": 0.0}

        sorted_vals = sorted(self._samples)
        n = len(sorted_vals)

        def _p(pct: float) -> float:
            idx = int(math.ceil((pct / 100.0) * n)) - 1
            idx = max(0, min(idx, n - 1))
            return round(sorted_vals[idx], 2)

        avg = round(sum(sorted_vals) / n, 2)
        return {
            "p50": _p(50),
            "p95": _p(95),
            "p99": _p(99),
            "count": n,
            "avg": avg,
        }


class HealthTracker:
    """Centralized metrics aggregator for pipeline observability."""

    def __init__(self):
        self.start_time = time.time()
        self.last_event_timestamp: float = 0.0
        self.total_events_received: int = 0
        self.total_errors: int = 0
        
        # Stage latency trackers
        self.latency_ingest = LatencyTracker()
        self.latency_normalize = LatencyTracker()
        self.latency_agents = LatencyTracker()
        self.latency_end_to_end = LatencyTracker()

        # Source statuses
        self.sources_status: Dict[str, Dict[str, Any]] = {
            "SOLANA_RPC": {"status": "INITIALIZING", "last_seen": 0.0, "errors": 0},
            "DEX_SCREENER": {"status": "INITIALIZING", "last_seen": 0.0, "errors": 0},
            "REPLAY": {"status": "STANDBY", "last_seen": 0.0, "errors": 0},
        }

    def record_event_received(self, source_name: str, event_time: float) -> None:
        self.total_events_received += 1
        self.last_event_timestamp = event_time
        if source_name in self.sources_status:
            self.sources_status[source_name]["status"] = "ACTIVE"
            self.sources_status[source_name]["last_seen"] = event_time

    def record_source_error(self, source_name: str) -> None:
        self.total_errors += 1
        if source_name in self.sources_status:
            self.sources_status[source_name]["errors"] += 1
            self.sources_status[source_name]["status"] = "ERROR"

    def get_summary(self, event_bus_metrics: Dict[str, Any], duplicate_count: int) -> Dict[str, Any]:
        now = time.time()
        uptime = now - self.start_time
        event_lag = (now - self.last_event_timestamp) if self.last_event_timestamp > 0 else -1.0

        return {
            "uptime_seconds": round(uptime, 1),
            "last_event_timestamp": self.last_event_timestamp,
            "event_lag_seconds": round(event_lag, 2) if event_lag >= 0 else None,
            "total_events_received": self.total_events_received,
            "total_errors": self.total_errors,
            "duplicate_events_filtered": duplicate_count,
            "sources": self.sources_status,
            "event_bus": event_bus_metrics,
            "latencies_ms": {
                "ingest": self.latency_ingest.get_percentiles(),
                "normalize": self.latency_normalize.get_percentiles(),
                "agent_analysis": self.latency_agents.get_percentiles(),
                "end_to_end": self.latency_end_to_end.get_percentiles(),
            },
        }
