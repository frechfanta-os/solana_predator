"""Tests for event normalization, deduplication, and quality assessment."""

import time
import pytest
from backend.market.normalizer import EventNormalizer, EventDeduplicator
from backend.models import MarketSource, EventQuality


def test_deduplicator_lru_and_ttl():
    dedup = EventDeduplicator(maxsize=3, ttl_seconds=1.0)
    
    assert dedup.is_duplicate("sig1") is False
    assert dedup.is_duplicate("sig1") is True  # Duplicate
    assert dedup.duplicate_count == 1

    assert dedup.is_duplicate("sig2") is False
    assert dedup.is_duplicate("sig3") is False
    # Now size is 3. Adding sig4 should evict sig1 (oldest)
    assert dedup.is_duplicate("sig4") is False
    
    # Wait for TTL expiration
    time.sleep(1.05)
    assert dedup.is_duplicate("sig4") is False  # Expired, treated as new


def test_normalize_dex_screener_valid(normalizer):
    pair_data = {
        "chainId": "solana",
        "pairAddress": "PairAddress1111111111111111111111111111111111",
        "baseToken": {
            "address": "TokenMint1111111111111111111111111111111111",
            "name": "Predator",
            "symbol": "PRED",
        },
        "priceUsd": "0.00045",
        "liquidity": {"usd": 50000.0},
        "volume": {"h24": 120000.0},
        "pairCreatedAt": (time.time() - 3600) * 1000,
    }

    event = normalizer.normalize_dex_screener_pair(pair_data)
    assert event is not None
    assert event.source == MarketSource.DEX_SCREENER
    assert event.token_mint == "TokenMint1111111111111111111111111111111111"
    assert event.price_usd == 0.00045
    assert event.liquidity_usd == 50000.0
    assert event.volume_24h_usd == 120000.0
    assert event.quality == EventQuality.ACCEPTABLE

    # Immediate second call with identical content should return None (deduplicated)
    dup_event = normalizer.normalize_dex_screener_pair(pair_data)
    assert dup_event is None


def test_normalize_never_fabricates_missing_data(normalizer):
    pair_data = {
        "chainId": "solana",
        "pairAddress": "PairAddress2222222222222222222222222222222222",
        "baseToken": {
            "address": "TokenMint2222222222222222222222222222222222",
        },
        # No price or liquidity provided
    }

    event = normalizer.normalize_dex_screener_pair(pair_data)
    assert event is not None
    assert event.price_usd is None  # Never fabricated!
    assert event.liquidity_usd is None  # Never fabricated!
    assert event.quality == EventQuality.DEGRADED
    assert event.confidence_score <= 0.50
