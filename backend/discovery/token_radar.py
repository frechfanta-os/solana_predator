"""Token Discovery Radar maintaining explicit state transitions and timestamps."""

import time
import logging
from typing import Dict, Optional, List
from backend.models import (
    TokenLifecycleState,
    TokenMetadata,
    NormalizedMarketEvent,
)
from backend.database.repository import Repository

logger = logging.getLogger("predator.discovery.token_radar")


class TokenRadar:
    """Manages token discovery and enforces strict lifecycle state transitions."""

    def __init__(self, repository: Repository):
        self.repository = repository
        self._tokens: Dict[str, TokenMetadata] = {}
        self._states: Dict[str, TokenLifecycleState] = {}

    async def process_event(self, event: NormalizedMarketEvent) -> TokenLifecycleState:
        """Process incoming market event to discover or transition token state."""
        mint = event.token_mint
        now = time.time()

        if mint not in self._tokens:
            # First observation of this token
            pool_created_ts = None
            if event.metadata and "pool_created_at" in event.metadata:
                pool_created_ts = float(event.metadata["pool_created_at"])

            token = TokenMetadata(
                mint=mint,
                name=event.metadata.get("name") if event.metadata else None,
                symbol=event.metadata.get("symbol") if event.metadata else None,
                decimals=event.metadata.get("decimals", 9) if event.metadata else 9,
                first_observed_timestamp=now,
                pool_created_timestamp=pool_created_ts,
                pair_address=event.pair_address,
                dex_id=event.metadata.get("dex_id") if event.metadata else None,
                initial_liquidity_usd=event.liquidity_usd,
            )
            self._tokens[mint] = token
            self._states[mint] = TokenLifecycleState.DISCOVERED
            
            await self.repository.upsert_token(token, initial_state=TokenLifecycleState.DISCOVERED.value)
            await self.repository.update_token_lifecycle(
                mint,
                TokenLifecycleState.DISCOVERED.value,
                f"Discovered via {event.source.value} at slot {event.slot or 'N/A'}",
            )
            logger.info("Token discovered: %s (%s)", mint, token.symbol or "unknown")
            return TokenLifecycleState.DISCOVERED

        # Existing token evaluation
        current_state = self._states.get(mint, TokenLifecycleState.DISCOVERED)

        if current_state == TokenLifecycleState.DISCOVERED:
            # Transition to OBSERVED once we have at least one verified price/liquidity observation
            if event.price_usd is not None and event.liquidity_usd is not None:
                new_state = TokenLifecycleState.OBSERVED
                reason = f"Verified price ${event.price_usd:.6f} and liquidity ${event.liquidity_usd:,.2f}"
                self._states[mint] = new_state
                await self.repository.update_token_lifecycle(mint, new_state.value, reason)
                return new_state

        return current_state

    async def advance_lifecycle(self, mint: str, to_state: TokenLifecycleState, reason: str) -> None:
        """Explicit lifecycle transition (e.g. from multi-agent consensus)."""
        if to_state not in (TokenLifecycleState.ANALYZED, TokenLifecycleState.REJECTED, TokenLifecycleState.PAPER_CANDIDATE):
            raise ValueError(f"Invalid target state: {to_state}")
        self._states[mint] = to_state
        await self.repository.update_token_lifecycle(mint, to_state.value, reason)
        logger.info("Token %s transitioned to %s: %s", mint, to_state.value, reason)

    def get_state(self, mint: str) -> Optional[TokenLifecycleState]:
        return self._states.get(mint)
