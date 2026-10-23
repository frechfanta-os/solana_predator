"""Composite Market Data Provider with automatic failover and data quality tracking."""

import time
import logging
from typing import Optional, Dict, Any, List
from backend.market.base import BaseMarketDataProvider
from backend.market.dex_screener_provider import DexScreenerProvider
from backend.market.solana_rpc_provider import SolanaRpcProvider
from backend.market.gmgn_provider import GmgnMarketProvider
from backend.market.mobula_provider import MobulaMarketProvider
from backend.models.events import NormalizedMarketEvent, MarketSource, EventQuality
from backend.config import settings

logger = logging.getLogger("predator.market.composite")


class CompositeMarketDataProvider(BaseMarketDataProvider):
    """Orchestrates market data providers with automatic, seamless fallback.
    
    Priority Hierarchy:
    1. GMGN (Optional rich on-chain analytics, used if configured and available)
    2. Mobula (Optional multi-chain intelligence & distribution stats, used if configured and available)
    3. DEX Screener (Always-available primary pricing and pool liquidity source)
    4. Solana RPC (Always-available on-chain slot, blockhash, and signatures truth)
    
    INVARIANTS:
    - Never fabricates or interpolates missing prices, volumes, or liquidity.
    - Explicitly tags observation state: GENUINELY_OBSERVED, STALE, or MISSING.
    - If GMGN or Mobula is absent/restricted (e.g. Free plan 403), the pipeline operates without interruption.
    """

    def __init__(
        self,
        dex_screener: Optional[DexScreenerProvider] = None,
        solana_rpc: Optional[SolanaRpcProvider] = None,
        gmgn: Optional[GmgnMarketProvider] = None,
        mobula: Optional[MobulaMarketProvider] = None,
    ):
        self.dex_screener = dex_screener or DexScreenerProvider()
        self.solana_rpc = solana_rpc or SolanaRpcProvider()
        self.gmgn = gmgn or GmgnMarketProvider()
        self.mobula = mobula or MobulaMarketProvider()
        self._providers: List[BaseMarketDataProvider] = [
            self.gmgn,
            self.mobula,
            self.dex_screener,
            self.solana_rpc,
        ]

    @property
    def name(self) -> str:
        return "composite_market_data"

    @property
    def source(self) -> MarketSource:
        # Reflects active primary source
        if self.gmgn.is_available:
            return MarketSource.GMGN
        if self.mobula.is_available:
            return MarketSource.MOBULA
        return MarketSource.DEX_SCREENER

    @property
    def is_configured(self) -> bool:
        # Configured if at least one provider is configured
        return any(p.is_configured for p in self._providers)

    @property
    def is_available(self) -> bool:
        # Available if at least one provider is operational
        return any(p.is_available for p in self._providers)

    async def get_token_market_data(self, token_mint: str) -> Optional[NormalizedMarketEvent]:
        """Fetch market data with automatic prioritized fallback and explicit provenance."""
        now = time.time()
        fallback_trail: List[str] = []

        # 1. Try GMGN if configured and operational
        if self.gmgn.is_configured and self.gmgn.is_available:
            try:
                event = await self.gmgn.get_token_market_data(token_mint)
                if event and (event.price_usd is not None or event.liquidity_usd is not None):
                    event.metadata["fallback_path"] = ["gmgn"]
                    event.metadata["provider_resolved"] = self.gmgn.name
                    return event
                fallback_trail.append("gmgn_no_market_data")
            except Exception as e:
                fallback_trail.append(f"gmgn_error_{type(e).__name__}")
                logger.warning("GMGN provider lookup failed (%s). Falling back.", e)
        else:
            fallback_trail.append("gmgn_unconfigured_or_unavailable")

        # 2. Try Mobula if configured and operational
        if self.mobula.is_configured and self.mobula.is_available:
            try:
                event = await self.mobula.get_token_market_data(token_mint)
                if event and (event.price_usd is not None or event.liquidity_usd is not None):
                    event.metadata["fallback_path"] = fallback_trail + ["mobula"]
                    event.metadata["provider_resolved"] = self.mobula.name
                    return event
                fallback_trail.append("mobula_no_market_data")
            except Exception as e:
                fallback_trail.append(f"mobula_error_{type(e).__name__}")
                logger.warning("Mobula provider lookup failed (%s). Falling back.", e)
        else:
            fallback_trail.append("mobula_unconfigured_or_unavailable")

        # 3. Fallback to DEX Screener (Standard primary source for price/liquidity)
        if self.dex_screener.is_available:
            try:
                event = await self.dex_screener.get_token_market_data(token_mint)
                if event and (event.price_usd is not None or event.liquidity_usd is not None):
                    event.metadata["fallback_path"] = fallback_trail + ["dex_screener"]
                    event.metadata["provider_resolved"] = self.dex_screener.name
                    return event
                if event:
                    fallback_trail.append("dex_screener_partial")
                else:
                    fallback_trail.append("dex_screener_unlisted")
            except Exception as e:
                fallback_trail.append(f"dex_screener_error_{type(e).__name__}")
                logger.warning("DEX Screener lookup failed (%s). Falling back to Solana RPC.", e)
        else:
            fallback_trail.append("dex_screener_unavailable")

        # 4. Fallback to Solana RPC (On-chain truth for slot/signatures without faking prices)
        if self.solana_rpc.is_available:
            try:
                event = await self.solana_rpc.get_token_market_data(token_mint)
                if event:
                    event.metadata["fallback_path"] = fallback_trail + ["solana_rpc"]
                    event.metadata["provider_resolved"] = self.solana_rpc.name
                    return event
            except Exception as e:
                logger.error("All market data providers failed for token %s: %s", token_mint, e)

        return None

    async def get_token_pairs(self, token_addresses: List[str]) -> List[NormalizedMarketEvent]:
        """Batch query multiple tokens with prioritized fallback."""
        if self.gmgn.is_configured and self.gmgn.is_available:
            try:
                events = await self.gmgn.get_token_pairs(token_addresses)
                if events:
                    return events
            except Exception:
                pass

        if self.mobula.is_configured and self.mobula.is_available:
            try:
                events = await self.mobula.get_token_pairs(token_addresses)
                if events:
                    return events
            except Exception:
                pass

        # Fallback to DEX Screener batching
        if self.dex_screener.is_available:
            return await self.dex_screener.get_token_pairs(token_addresses)

        # Fallback to Solana RPC
        return await self.solana_rpc.get_token_pairs(token_addresses)

    async def check_health(self) -> Dict[str, Any]:
        """Aggregate health metrics of all underlying market data providers."""
        gmgn_health = await self.gmgn.check_health()
        mobula_health = await self.mobula.check_health()
        dex_health = await self.dex_screener.check_health()
        rpc_health = await self.solana_rpc.check_health()

        active_primary = "dex_screener"
        if self.gmgn.is_available:
            active_primary = "gmgn"
        elif self.mobula.is_available:
            active_primary = "mobula"

        return {
            "name": self.name,
            "status": "OPERATIONAL" if self.is_available else "DEGRADED",
            "active_primary_provider": active_primary,
            "providers": {
                "gmgn": gmgn_health,
                "mobula": mobula_health,
                "dex_screener": dex_health,
                "solana_rpc": rpc_health,
            },
            "timestamp": time.time(),
        }

    async def close(self) -> None:
        for p in self._providers:
            await p.close()
