"""Tests for the bounded asynchronous event bus."""

import asyncio
import pytest
from backend.market.event_bus import EventBus
from backend.models import NormalizedMarketEvent, MarketSource, EventQuality


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus(maxsize=10)
    received = []

    async def _listener(event: NormalizedMarketEvent):
        received.append(event)

    bus.subscribe(_listener)
    await bus.start()

    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="test_ev_1",
        token_mint="Mint1",
        local_receive_timestamp=1000.0,
        processing_timestamp=1000.1,
    )
    await bus.publish(ev)
    await asyncio.sleep(0.05)

    assert len(received) == 1
    assert received[0].event_id == "test_ev_1"
    await bus.stop()


@pytest.mark.asyncio
async def test_event_bus_bounded_overflow_policy():
    bus = EventBus(maxsize=3)
    # Don't start worker loop yet to test queue filling and backpressure dropping
    for i in range(5):
        ev = NormalizedMarketEvent(
            source=MarketSource.SYNTHETIC,
            event_id=f"overflow_ev_{i}",
            token_mint="MintTest",
            local_receive_timestamp=1000.0 + i,
            processing_timestamp=1000.1 + i,
        )
        await bus.publish(ev)

    metrics = bus.get_metrics()
    assert metrics["published_total"] == 5
    assert metrics["dropped_total"] >= 2
    assert metrics["queue_depth"] <= 3
    assert metrics["high_water_mark"] >= 3
