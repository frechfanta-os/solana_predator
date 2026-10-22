"""Deterministic Replay provider for offline verification and backtesting."""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    EventQuality,
)
from backend.market.event_bus import EventBus

logger = logging.getLogger("predator.market.replay")


class DeterministicReplayProvider:
    """Feeds pre-configured or recorded market events deterministically into the EventBus."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._is_running = False
        self._replayed_count = 0

    def generate_synthetic_dataset(self) -> List[NormalizedMarketEvent]:
        """Generate a realistic sequence of Solana meme/defi token events for testing."""
        now = time.time()
        base_mint = "PredatorMemeTokenMint1111111111111111111111111"
        pair_address = "PairAddressPredatorRaydiumPool1111111111111111"

        events = [
            # 1. New Token Discovery Event
            NormalizedMarketEvent(
                source=MarketSource.REPLAY,
                event_id="replay_event_001_discovery",
                token_mint=base_mint,
                pair_address=pair_address,
                slot=320000001,
                source_timestamp=now - 120.0,
                local_receive_timestamp=now - 119.5,
                processing_timestamp=now - 119.0,
                freshness_seconds=0.5,
                price_usd=0.000012,
                volume_24h_usd=2500.0,
                liquidity_usd=15000.0,
                signature="5xSigReplayDiscovery1111111111111111111111111111111111111111111111111111111111111111",
                raw_payload_hash="hash_001",
                quality=EventQuality.EXCELLENT,
                confidence_score=0.98,
                metadata={
                    "name": "Predator AI",
                    "symbol": "PRED",
                    "decimals": 9,
                    "dex_id": "raydium",
                    "pool_created_at": now - 120.0,
                },
            ),
            # 2. Whale Buy Event (Early accumulation)
            NormalizedMarketEvent(
                source=MarketSource.REPLAY,
                event_id="replay_event_002_whale_buy",
                token_mint=base_mint,
                pair_address=pair_address,
                slot=320000050,
                source_timestamp=now - 90.0,
                local_receive_timestamp=now - 89.8,
                processing_timestamp=now - 89.5,
                freshness_seconds=0.3,
                price_usd=0.000018,
                volume_24h_usd=8500.0,
                liquidity_usd=22000.0,
                signature="5xSigReplayWhaleBuy2222222222222222222222222222222222222222222222222222222222222222",
                raw_payload_hash="hash_002",
                quality=EventQuality.EXCELLENT,
                confidence_score=0.99,
                metadata={
                    "whale_wallet": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
                    "swap_type": "BUY",
                    "amount_tokens": 150000000.0,
                    "amount_usd": 2700.0,
                },
            ),
            # 3. Momentum Expansion Event
            NormalizedMarketEvent(
                source=MarketSource.REPLAY,
                event_id="replay_event_003_momentum",
                token_mint=base_mint,
                pair_address=pair_address,
                slot=320000100,
                source_timestamp=now - 50.0,
                local_receive_timestamp=now - 49.8,
                processing_timestamp=now - 49.6,
                freshness_seconds=0.2,
                price_usd=0.000028,
                volume_24h_usd=32000.0,
                liquidity_usd=45000.0,
                signature="5xSigReplayMomentum3333333333333333333333333333333333333333333333333333333333333333",
                raw_payload_hash="hash_003",
                quality=EventQuality.EXCELLENT,
                confidence_score=0.99,
                metadata={
                    "txns_5m": {"buys": 45, "sells": 10},
                },
            ),
            # 4. Whale Sell / Exit Signal Event
            NormalizedMarketEvent(
                source=MarketSource.REPLAY,
                event_id="replay_event_004_whale_dump",
                token_mint=base_mint,
                pair_address=pair_address,
                slot=320000200,
                source_timestamp=now - 10.0,
                local_receive_timestamp=now - 9.8,
                processing_timestamp=now - 9.5,
                freshness_seconds=0.3,
                price_usd=0.000022,
                volume_24h_usd=65000.0,
                liquidity_usd=28000.0,  # Dropping liquidity
                signature="5xSigReplayWhaleSell4444444444444444444444444444444444444444444444444444444444444444",
                raw_payload_hash="hash_004",
                quality=EventQuality.EXCELLENT,
                confidence_score=0.95,
                metadata={
                    "whale_wallet": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
                    "swap_type": "SELL",
                    "amount_tokens": 150000000.0,
                    "amount_usd": 3300.0,
                },
            ),
        ]
        return events

    async def run_replay(self, events: Optional[List[NormalizedMarketEvent]] = None, delay_seconds: float = 0.05) -> int:
        """Run through the event list and publish to EventBus."""
        dataset = events or self.generate_synthetic_dataset()
        self._is_running = True
        self._replayed_count = 0

        for event in dataset:
            if not self._is_running:
                break
            await self.event_bus.publish(event)
            self._replayed_count += 1
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

        self._is_running = False
        return self._replayed_count

    def stop(self) -> None:
        self._is_running = False
