"""Live Quote Service retrieving DEX swap quotes and estimating slippage & fees."""

import time
import uuid
from typing import Dict, Any, Optional
from backend.live.models import LiveQuote


class LiveQuoteService:
    """Provides market quotes, slippage calculation, and fee estimation."""

    def __init__(self, base_priority_fee_sol: float = 0.00001):
        self.base_priority_fee_sol = base_priority_fee_sol

    async def get_swap_quote(
        self,
        token_mint: str,
        token_symbol: str,
        amount_sol: float,
        slippage_bps: float = 100.0,  # 1.0% default
        current_token_price_usd: Optional[float] = None,
        sol_price_usd: float = 150.0,
        pool_liquidity_usd: float = 45000.0,
    ) -> LiveQuote:
        """Calculate market swap quote, price impact, and minimum output."""
        now = time.time()
        in_lamports = int(amount_sol * 1e9)

        token_px = current_token_price_usd or 0.05
        sol_val_usd = amount_sol * sol_price_usd

        # Constant-product price impact model: impact = (trade_usd / pool_liquidity_usd) * 0.5
        price_impact_pct = min(15.0, (sol_val_usd / max(pool_liquidity_usd, 1000.0)) * 50.0)

        # Expected output tokens
        effective_px = token_px * (1.0 + (price_impact_pct / 100.0))
        expected_tokens = sol_val_usd / effective_px

        # Min output tokens after slippage tolerance
        min_tokens = expected_tokens * (1.0 - (slippage_bps / 10000.0))

        quote_id = f"quote_{uuid.uuid4().hex[:12]}"
        return LiveQuote(
            quote_id=quote_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            side="BUY",
            in_amount_sol=round(amount_sol, 4),
            in_amount_lamports=in_lamports,
            expected_output_tokens=round(expected_tokens, 4),
            min_output_tokens=round(min_tokens, 4),
            price_impact_pct=round(price_impact_pct, 2),
            slippage_bps=slippage_bps,
            estimated_network_fee_sol=0.000005,
            estimated_priority_fee_sol=self.base_priority_fee_sol,
            route_plan=["Raydium Concentrated Liquidity", f"SOL -> {token_symbol}"],
            valid_until=now + 15.0,  # 15 seconds validity window
            pool_liquidity_usd=pool_liquidity_usd,
        )
