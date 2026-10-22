"""Whale Intelligence engine tracking and classifying observable on-chain activity.

SECURITY & INTEGRITY:
- Tracks configurable public addresses only.
- Strict activity classification without speculative identity inference.
- Signature deduplication and correlation detection.
"""

import time
import logging
from typing import Dict, List, Optional, Set, Any
from backend.models import (
    WhaleActivity,
    WhaleActivityType,
    WhaleConvergenceMetrics,
    NormalizedMarketEvent,
)
from backend.database.repository import Repository
from backend.config import settings

logger = logging.getLogger("predator.whale.intelligence")


class WhaleIntelligenceEngine:
    """Classifies whale transactions and computes non-speculative convergence scores."""

    def __init__(self, repository: Repository, tracked_wallets: Optional[List[str]] = None):
        self.repository = repository
        self.tracked_wallets: Set[str] = set(tracked_wallets or settings.TRACKED_WHALE_WALLETS)
        self._processed_signatures: Set[str] = set()
        
        # In-memory history per token: mint -> List[WhaleActivity]
        self._token_activities: Dict[str, List[WhaleActivity]] = {}
        # In-memory wallet sample stats: wallet -> count
        self._wallet_sample_size: Dict[str, int] = {}

    def add_tracked_wallet(self, wallet_address: str) -> None:
        self.tracked_wallets.add(wallet_address)

    def is_wallet_tracked(self, wallet_address: str) -> bool:
        return wallet_address in self.tracked_wallets

    def classify_raw_transaction(
        self,
        signature: str,
        wallet_address: str,
        token_mint: str,
        parsed_tx: Optional[Dict[str, Any]] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
    ) -> WhaleActivity:
        """Deterministically classify on-chain transaction based on instructions or metadata."""
        now = time.time()
        
        # Check if already processed
        if signature in self._processed_signatures:
            pass  # Handled by deduplication check prior

        # Check metadata provided by market replay or RPC log
        meta = event_metadata or {}
        swap_type = meta.get("swap_type")
        amount_tokens = float(meta.get("amount_tokens", 0.0))
        amount_usd = float(meta.get("amount_usd")) if meta.get("amount_usd") is not None else None

        # Check for failed transaction
        tx_err = None
        if parsed_tx:
            meta_tx = parsed_tx.get("meta") or {}
            tx_err = meta_tx.get("err") or parsed_tx.get("err")
        elif meta:
            tx_err = meta.get("err")

        if tx_err is not None:
            self._wallet_sample_size[wallet_address] = self._wallet_sample_size.get(wallet_address, 0) + 1
            return WhaleActivity(
                activity_id=f"whale_{signature[:12]}_{int(now*1000)}",
                signature=signature,
                wallet_address=wallet_address,
                token_mint=token_mint,
                activity_type=WhaleActivityType.FAILED,
                amount_tokens=amount_tokens,
                amount_usd=amount_usd,
                timestamp=now,
                slot=parsed_tx.get("slot") if parsed_tx else None,
                confidence=0.0,
                evidence_details={"err": tx_err, "is_failed": True},
            )

        activity_type = WhaleActivityType.UNKNOWN_AMBIGUOUS
        confidence = 0.50
        evidence: Dict[str, Any] = {"raw_available": bool(parsed_tx), "meta": meta}

        if swap_type == "BUY":
            activity_type = WhaleActivityType.SWAP_INFLOW
            confidence = 0.95
            evidence["swap_direction"] = "BUY"
        elif swap_type == "SELL":
            activity_type = WhaleActivityType.SWAP_OUTFLOW
            confidence = 0.95
            evidence["swap_direction"] = "SELL"
        elif parsed_tx:
            # Inspect parsed Solana instructions if available
            instructions = parsed_tx.get("transaction", {}).get("message", {}).get("instructions", [])
            for ix in instructions:
                prog = ix.get("program") or ix.get("programId")
                parsed = ix.get("parsed")
                if parsed and isinstance(parsed, dict):
                    ix_type = parsed.get("type")
                    if ix_type in ("transfer", "transferChecked"):
                        activity_type = WhaleActivityType.TRANSFER
                        confidence = 0.90
                        info = parsed.get("info", {})
                        amount_tokens = float(info.get("tokenAmount", {}).get("uiAmount", 0.0) or info.get("amount", 0.0))
                        evidence["transfer_info"] = info
                        break
                    elif ix_type in ("mintTo", "burn"):
                        activity_type = WhaleActivityType.DEPOSIT_WITHDRAW
                        confidence = 0.85
                        break

        # Record sample size
        self._wallet_sample_size[wallet_address] = self._wallet_sample_size.get(wallet_address, 0) + 1

        activity = WhaleActivity(
            activity_id=f"whale_{signature[:12]}_{int(now*1000)}",
            signature=signature,
            wallet_address=wallet_address,
            token_mint=token_mint,
            activity_type=activity_type,
            amount_tokens=amount_tokens,
            amount_usd=amount_usd,
            timestamp=now,
            slot=parsed_tx.get("slot") if parsed_tx else None,
            confidence=confidence,
            evidence_details=evidence,
        )
        return activity

    async def record_activity(self, activity: WhaleActivity) -> bool:
        """Deduplicate and persist whale activity."""
        if activity.signature in self._processed_signatures:
            return False

        self._processed_signatures.add(activity.signature)
        if len(self._processed_signatures) > 50000:
            self._processed_signatures.clear()

        if activity.token_mint not in self._token_activities:
            self._token_activities[activity.token_mint] = []
        self._token_activities[activity.token_mint].append(activity)

        return await self.repository.save_whale_activity(activity)

    def calculate_convergence(self, token_mint: str, window_seconds: float = 3600.0) -> WhaleConvergenceMetrics:
        """Calculate whale-convergence indicator from deduplicated activity."""
        now = time.time()
        activities = self._token_activities.get(token_mint, [])
        recent = [a for a in activities if (now - a.timestamp) <= window_seconds]

        if not recent:
            return WhaleConvergenceMetrics(
                token_mint=token_mint,
                unique_whales_active=0,
                net_flow_usd=0.0,
                buy_volume_usd=0.0,
                sell_volume_usd=0.0,
                convergence_score=0.0,
                is_correlated_cluster=False,
                sample_size=0,
                calculated_at=now,
            )

        unique_wallets = {a.wallet_address for a in recent}
        buy_usd = 0.0
        sell_usd = 0.0

        for a in recent:
            if a.activity_type == WhaleActivityType.FAILED:
                continue
            usd = a.amount_usd or 0.0
            if a.activity_type in (WhaleActivityType.SWAP, WhaleActivityType.SWAP_INFLOW, WhaleActivityType.SWAP_OUTFLOW):
                direction = a.evidence_details.get("swap_direction")
                if a.activity_type == WhaleActivityType.SWAP_INFLOW or direction == "BUY":
                    buy_usd += usd
                elif a.activity_type == WhaleActivityType.SWAP_OUTFLOW or direction == "SELL":
                    sell_usd += usd
            elif a.activity_type == WhaleActivityType.TRANSFER:
                # Transfers are strictly NOT counted as buying flow
                pass

        net_flow = buy_usd - sell_usd
        total_volume = buy_usd + sell_usd

        # Score calculation: 
        # Multi-wallet convergence: more independent wallets buying gives higher score
        convergence = 0.0
        if total_volume > 0:
            flow_ratio = max(0.0, net_flow / total_volume)
            wallet_factor = min(1.0, len(unique_wallets) / 3.0)  # 3+ whales maxes wallet factor
            convergence = round(flow_ratio * wallet_factor, 2)

        # Detect potential correlated clusters (e.g. transfers between tracked wallets)
        is_correlated = False
        transfer_count = sum(1 for a in recent if a.activity_type == WhaleActivityType.TRANSFER)
        if transfer_count >= 2 and len(unique_wallets) > 1:
            is_correlated = True

        return WhaleConvergenceMetrics(
            token_mint=token_mint,
            unique_whales_active=len(unique_wallets),
            net_flow_usd=round(net_flow, 2),
            buy_volume_usd=round(buy_usd, 2),
            sell_volume_usd=round(sell_usd, 2),
            convergence_score=convergence,
            is_correlated_cluster=is_correlated,
            sample_size=len(recent),
            calculated_at=now,
        )

    def get_wallet_profitability_rating(self, wallet_address: str, min_sample_size: int = 10) -> Dict[str, Any]:
        """Verify historical wallet data before attributing profitability or intelligence."""
        sample_count = self._wallet_sample_size.get(wallet_address, 0)
        if sample_count < min_sample_size:
            return {
                "wallet_address": wallet_address,
                "sample_size": sample_count,
                "min_sample_size": min_sample_size,
                "is_rated": False,
                "rating": "UNVERIFIED_INSUFFICIENT_DATA",
                "reason": f"Sample size {sample_count} is below required threshold of {min_sample_size} verified historical events.",
            }
        return {
            "wallet_address": wallet_address,
            "sample_size": sample_count,
            "min_sample_size": min_sample_size,
            "is_rated": True,
            "rating": "OBSERVED_SAMPLE_VALID",
            "reason": f"Sample size {sample_count} satisfies empirical significance requirement.",
        }
